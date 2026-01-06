#!/usr/bin/env python3
"""
Timezone-aware cron job scheduler for multi-user content publishing
Handles different user timezones correctly for Render (UTC) deployment
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client
from cryptography.fernet import Fernet
import pytz
from collections import defaultdict

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TimezoneAwareScheduler:
    """Scheduler that handles multiple user timezones correctly - MVP Optimized for 100 Users × 5 Posts"""

    # MVP Requirements: 100 users × 5 posts = 500 posts total
    MVP_MAX_USERS = 100
    MVP_MAX_POSTS_PER_USER = 5
    MVP_TARGET_POSTS = 500  # 100 × 5

    # Platform limits optimized for 500 posts (21 concurrent total)
    PLATFORM_CONCURRENT_LIMITS = {
        'facebook': 8,    # 8 concurrent Facebook posts (most popular)
        'instagram': 5,   # 5 concurrent Instagram posts (image heavy)
        'linkedin': 4,    # 4 concurrent LinkedIn posts (professional)
        'youtube': 4      # 4 concurrent YouTube posts (video content)
    }

    # Post expiration settings - prevent old posts
    MAX_PUBLISH_DELAY_HOURS = 24  # Posts expire after 24 hours

    def __init__(self):
        # Initialize Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

        self.supabase: Client = create_client(supabase_url, supabase_key)

        # Initialize encryption
        encryption_key = os.getenv("ENCRYPTION_KEY")
        self.cipher = None
        if encryption_key:
            try:
                self.cipher = Fernet(encryption_key.encode())
                logger.info("Encryption initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize encryption: {e}")

    def get_user_timezone(self, user_id: str) -> str:
        """Get user's timezone from database, default to UTC if not found"""
        try:
            # Query user profile for timezone
            response = self.supabase.table("profiles").select("timezone").eq("id", user_id).execute()

            if response.data and len(response.data) > 0:
                user_timezone = response.data[0].get("timezone", "UTC")
                return user_timezone if user_timezone else "UTC"
            else:
                return "UTC"
        except Exception as e:
            logger.warning(f"Could not get timezone for user {user_id}: {e}")
            return "UTC"

    def get_current_time_in_user_timezone(self, user_timezone: str) -> datetime:
        """Get current time in user's timezone"""
        try:
            user_tz = pytz.timezone(user_timezone)
            now_utc = datetime.now(pytz.UTC)
            now_user_time = now_utc.astimezone(user_tz)
            return now_user_time
        except Exception as e:
            logger.warning(f"Invalid timezone {user_timezone}, using UTC: {e}")
            return datetime.now(pytz.UTC)

    def convert_user_time_to_utc(self, user_time: datetime, user_timezone: str) -> datetime:
        """Convert user's local time to UTC"""
        try:
            user_tz = pytz.timezone(user_timezone)
            # If user_time is naive, assume it's in user's timezone
            if user_time.tzinfo is None:
                user_time = user_tz.localize(user_time)
            # Convert to UTC
            utc_time = user_time.astimezone(pytz.UTC)
            return utc_time
        except Exception as e:
            logger.warning(f"Error converting time for timezone {user_timezone}: {e}")
            return user_time  # Return as-is if conversion fails

    def validate_mvp_requirements(self, due_posts):
        """Validate batch meets MVP requirements: 100 users × 5 posts max"""
        if not due_posts:
            return True

        # Count posts per user
        user_post_counts = {}
        total_users = 0

        for post in due_posts:
            user_id = post.get('user_id')
            if user_id not in user_post_counts:
                user_post_counts[user_id] = 0
                total_users += 1
            user_post_counts[user_id] += 1

        # Validate MVP limits
        max_posts_per_user = max(user_post_counts.values()) if user_post_counts else 0
        total_posts = len(due_posts)

        # Log MVP metrics
        logger.info(f"🎯 MVP VALIDATION:")
        logger.info(f"  👥 Users: {total_users}/{self.MVP_MAX_USERS}")
        logger.info(f"  📄 Posts: {total_posts}/{self.MVP_TARGET_POSTS}")
        logger.info(f"  📊 Max per user: {max_posts_per_user}/{self.MVP_MAX_POSTS_PER_USER}")

        # Warnings for exceeding MVP limits
        if total_users > self.MVP_MAX_USERS:
            logger.warning(f"⚠️ Exceeds MVP user limit: {total_users}/{self.MVP_MAX_USERS}")

        if max_posts_per_user > self.MVP_MAX_POSTS_PER_USER:
            logger.warning(f"⚠️ Exceeds MVP posts per user: {max_posts_per_user}/{self.MVP_MAX_POSTS_PER_USER}")

        if total_posts > self.MVP_TARGET_POSTS:
            logger.warning(f"⚠️ Exceeds MVP total posts: {total_posts}/{self.MVP_TARGET_POSTS}")

        return True  # Always proceed, just log warnings

    async def find_scheduled_content_timezone_aware(self):
        """Find scheduled content considering user timezones - MVP Optimized"""
        logger.info("🔍 Checking for scheduled content (timezone-aware - MVP Mode)...")

        try:
            # Get all scheduled content
            response = self.supabase.table("created_content").select(
                "id,user_id,platform,channel,title,content,hashtags,images,scheduled_at,status,god_mode_metadata"
            ).eq("status", "scheduled").execute()

            scheduled_posts = response.data
            logger.info(f"Found {len(scheduled_posts)} total scheduled content items")

            # Group by user to handle timezones efficiently
            posts_by_user = {}
            for post in scheduled_posts:
                user_id = post['user_id']
                if user_id not in posts_by_user:
                    posts_by_user[user_id] = []
                posts_by_user[user_id].append(post)

            # Check each user's posts against their local time
            due_posts = []

            for user_id, user_posts in posts_by_user.items():
                # Get user's timezone
                user_timezone = self.get_user_timezone(user_id)
                logger.info(f"User {user_id}: timezone = {user_timezone}")

                # Get current time in user's timezone
                current_user_time = self.get_current_time_in_user_timezone(user_timezone)
                logger.info(f"User {user_id}: current local time = {current_user_time}")

                # Check each post for this user
                for post in user_posts:
                    scheduled_at_utc = post['scheduled_at']

                    if scheduled_at_utc:
                        try:
                            # Parse the UTC timestamp from database
                            if isinstance(scheduled_at_utc, str):
                                # Handle ISO format strings
                                if scheduled_at_utc.endswith('Z'):
                                    scheduled_at_utc = scheduled_at_utc[:-1] + '+00:00'
                                scheduled_utc_dt = datetime.fromisoformat(scheduled_at_utc.replace('Z', '+00:00'))
                            else:
                                scheduled_utc_dt = scheduled_at_utc

                            # Convert to user's timezone for comparison
                            scheduled_user_time = scheduled_utc_dt.astimezone(pytz.timezone(user_timezone))

                            logger.info(f"Post {post['id']}: scheduled UTC = {scheduled_utc_dt}, local = {scheduled_user_time}")

                            # Check if it's due (current time >= scheduled time)
                            if current_user_time >= scheduled_user_time:
                                due_posts.append(post)
                                logger.info(f"✅ Post {post['id']} is DUE for publishing (local time: {scheduled_user_time})")
                            else:
                                logger.info(f"⏰ Post {post['id']} not yet due (scheduled: {scheduled_user_time})")

                        except Exception as e:
                            logger.error(f"Error parsing scheduled time for post {post['id']}: {e}")

            logger.info(f"📋 Found {len(due_posts)} posts due for publishing across all timezones")

            # Validate MVP requirements
            self.validate_mvp_requirements(due_posts)

            # Process due posts with smart batching
            if due_posts:
                await self.publish_due_posts_smart(due_posts)

            return len(due_posts)

        except Exception as e:
            logger.error(f"Error in timezone-aware scheduling: {e}")
            return 0

    async def publish_due_posts_smart(self, due_posts):
        """MAXIMUM SPEED: Publish ALL posts concurrently - MVP Optimized"""
        import time
        start_time = time.time()

        logger.info(f"⚡ MAXIMUM SPEED MODE: Publishing {len(due_posts)} posts (MVP: 100 users × 5 posts)...")

        # First filter out expired posts
        valid_posts = await self.filter_expired_posts(due_posts)

        if len(valid_posts) < len(due_posts):
            expired_count = len(due_posts) - len(valid_posts)
            logger.info(f"⏰ Filtered out {expired_count} expired posts")

        if not valid_posts:
            logger.info("⏰ No valid posts to publish")
            return 0

        # MVP Performance monitoring
        duration = time.time() - start_time
        await self.log_mvp_performance_metrics(0, len(valid_posts), duration)  # Pre-publishing metrics

        # MAXIMUM SPEED: Publish ALL posts concurrently (no limits)
        published_count = await self.publish_maximum_speed(valid_posts)

        # Final MVP metrics
        total_duration = time.time() - start_time
        await self.log_mvp_performance_metrics(published_count, len(valid_posts), total_duration)

        logger.info(f"⚡ MAXIMUM SPEED COMPLETED: {published_count}/{len(valid_posts)} posts published in {total_duration:.1f}s")
        return published_count

    async def log_mvp_performance_metrics(self, published_count, total_posts, duration):
        """Log MVP-specific performance metrics for 100 users × 5 posts"""
        success_rate = (published_count / total_posts * 100) if total_posts > 0 else 0

        logger.info(f"🎯 MVP PERFORMANCE METRICS:")
        logger.info(f"  👥 Target Users: {self.MVP_MAX_USERS}")
        logger.info(f"  📄 Target Posts: {self.MVP_TARGET_POSTS}")
        logger.info(f"  📊 Actual Posts: {total_posts}")
        if published_count > 0:
            logger.info(f"  ⚡ Publishing Time: {duration:.1f} seconds")
            logger.info(f"  ✅ Success Rate: {success_rate:.1f}%")
            logger.info(f"  🎯 Posts/Minute: {(published_count / max(duration, 1) * 60):.1f}")

        # MVP Target validation
        if published_count > 0 and duration > 120:  # 2 minutes
            logger.warning(f"⚠️ Publishing slower than MVP target: {duration:.1f}s > 120s")

        if published_count > 0 and success_rate < 95:
            logger.warning(f"⚠️ Success rate below MVP target: {success_rate:.1f}% < 95%")

        if total_posts > self.MVP_TARGET_POSTS:
            logger.info(f"📈 Exceeding MVP capacity: {total_posts}/{self.MVP_TARGET_POSTS} posts")

        # Success indicators
        if published_count == 0:
            logger.info("📊 MVP metrics logged (pre-publishing)")
        elif duration <= 120 and success_rate >= 95:
            logger.info("🎉 MVP PERFORMANCE TARGETS MET! ✅")
        else:
            logger.info("📊 Performance within acceptable MVP range 📈")

    async def filter_expired_posts(self, posts):
        """Remove posts that are too old to publish (expired after 24 hours)"""
        valid_posts = []
        now_utc = datetime.now(pytz.UTC)

        for post in posts:
            try:
                # Calculate time since post was scheduled
                scheduled_at = post.get('scheduled_at', '')
                if scheduled_at:
                    if isinstance(scheduled_at, str):
                        if scheduled_at.endswith('Z'):
                            scheduled_at = scheduled_at[:-1] + '+00:00'
                        scheduled_utc = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                    else:
                        scheduled_utc = scheduled_at

                    time_diff = now_utc - scheduled_utc
                    hours_diff = time_diff.total_seconds() / 3600

                    if hours_diff > self.MAX_PUBLISH_DELAY_HOURS:
                        # Mark post as expired
                        await self.mark_post_expired(post)
                        logger.warning(f"⏰ Post {post['id']} EXPIRED ({hours_diff:.1f}h old)")
                        continue

                valid_posts.append(post)

            except Exception as e:
                logger.error(f"Error checking expiration for post {post.get('id', 'unknown')}: {e}")
                # If we can't check expiration, include the post
                valid_posts.append(post)

        return valid_posts

    async def mark_post_expired(self, post):
        """Mark a post as expired in the database"""
        try:
            post_id = post['id']
            self.supabase.table("created_content").update({
                "status": "expired",
                "god_mode_metadata": {
                    **(post.get('god_mode_metadata') or {}),
                    "expired_at": datetime.now(pytz.UTC).isoformat(),
                    "expired_reason": f"Publishing window exceeded ({self.MAX_PUBLISH_DELAY_HOURS}h limit)",
                    "scheduled_time": post.get('scheduled_at')
                }
            }).eq("id", post_id).execute()

        except Exception as e:
            logger.error(f"Failed to mark post {post.get('id', 'unknown')} as expired: {e}")

    async def publish_concurrent_by_platform(self, posts):
        """Publish posts concurrently but limited by platform"""
        # Group posts by platform
        platform_groups = defaultdict(list)
        for post in posts:
            platform = post.get('platform', 'unknown')
            platform_groups[platform].append(post)

        # Create concurrent tasks for each platform
        all_tasks = []
        for platform, platform_posts in platform_groups.items():
            max_concurrent = self.PLATFORM_CONCURRENT_LIMITS.get(platform, 2)
            semaphore = asyncio.Semaphore(max_concurrent)

            logger.info(f"📊 Platform {platform}: {len(platform_posts)} posts, max concurrent: {max_concurrent}")

            for post in platform_posts:
                task = self.publish_single_with_semaphore(post, semaphore)
                all_tasks.append(task)

        # Execute all posts concurrently (limited per platform)
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Count successful publications
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful

        if failed > 0:
            logger.warning(f"⚠️ {failed} posts failed during concurrent publishing")

        return successful

    async def publish_maximum_speed(self, posts):
        """MAXIMUM SPEED: Publish ALL posts concurrently (no limits)"""
        logger.info(f"⚡ MAXIMUM SPEED MODE: Publishing {len(posts)} posts concurrently with NO limits")

        # Create ALL tasks simultaneously (no platform limits, no semaphores)
        tasks = []
        for post in posts:
            task = self.publish_single_post_max_speed(post)
            tasks.append(task)

        # Execute ALL posts at the same time
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count results
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful

        logger.info(f"⚡ MAXIMUM SPEED RESULTS: {successful}/{len(posts)} posts published, {failed} failed")

        if failed > 0:
            logger.warning(f"⚠️ {failed} posts failed - possible rate limiting")

        return successful

    async def publish_single_post_max_speed(self, post):
        """Publish single post without any concurrency limits"""
        try:
            from cron_job.content_publisher import ContentPublisherService
            publisher = ContentPublisherService(self.supabase, self.cipher)
            success = await publisher.publish_created_content(post)

            if success:
                # Update status to published
                post_id = post['id']
                self.supabase.table("created_content").update({
                    "status": "published",
                    "god_mode_metadata": {
                        **(post.get('god_mode_metadata') or {}),
                        "published_at": datetime.now(pytz.UTC).isoformat(),
                        "published_by_cron": True,
                        "platform_published": True,
                        "max_speed_mode": True
                    }
                }).eq("id", post_id).execute()
                return True
            else:
                # Mark as failed
                post_id = post['id']
                self.supabase.table("created_content").update({
                    "status": "draft",
                    "god_mode_metadata": {
                        **(post.get('god_mode_metadata') or {}),
                        "publish_error": "Platform publishing failed",
                        "publish_failed_at": datetime.now(pytz.UTC).isoformat(),
                        "max_speed_mode": True
                    }
                }).eq("id", post_id).execute()
                return False

        except Exception as e:
            logger.error(f"❌ Exception in max speed mode for post {post.get('id', 'unknown')}: {e}")
            return False

    async def publish_single_with_semaphore(self, post, semaphore):
        """Publish a single post with concurrency control"""
        async with semaphore:
            try:
                from cron_job.content_publisher import ContentPublisherService
                publisher = ContentPublisherService(self.supabase, self.cipher)
                return await publisher.publish_created_content(post)
            except Exception as e:
                logger.error(f"❌ Exception publishing post {post.get('id', 'unknown')}: {e}")
                return False

    async def publish_due_posts(self, due_posts):
        """Publish posts that are due using actual platform APIs"""
        from content_publisher import ContentPublisherService

        logger.info(f"🚀 Publishing {len(due_posts)} due posts to platforms...")

        # Initialize content publisher service
        publisher_service = ContentPublisherService(self.supabase, self.cipher)

        for post in due_posts:
            try:
                post_id = post['id']
                platform = post['platform']

                logger.info(f"Publishing post {post_id} to {platform} platform")

                # Actually publish to the platform using ContentPublisherService
                success = await publisher_service.publish_created_content(post)

                if success:
                    # Update status to published
                    self.supabase.table("created_content").update({
                        "status": "published",
                        "god_mode_metadata": {
                            **(post.get('god_mode_metadata') or {}),
                            "published_at": datetime.now(pytz.UTC).isoformat(),
                            "published_by_cron": True,
                            "platform_published": True
                        }
                    }).eq("id", post_id).execute()

                    logger.info(f"✅ Successfully published post {post_id} to {platform}")

                else:
                    # Mark as failed if publishing didn't succeed
                    self.supabase.table("created_content").update({
                        "status": "draft",
                        "god_mode_metadata": {
                            **(post.get('god_mode_metadata') or {}),
                            "publish_error": "Platform publishing failed",
                            "publish_failed_at": datetime.now(pytz.UTC).isoformat()
                        }
                    }).eq("id", post_id).execute()

                    logger.error(f"❌ Failed to publish post {post_id} to {platform}")

            except Exception as e:
                logger.error(f"❌ Exception while publishing post {post['id']}: {e}")

                # Mark as failed
                self.supabase.table("created_content").update({
                    "status": "draft",
                    "god_mode_metadata": {
                        **(post.get('god_mode_metadata') or {}),
                        "publish_error": str(e),
                        "publish_failed_at": datetime.now(pytz.UTC).isoformat()
                    }
                }).eq("id", post['id']).execute()

async def run_timezone_aware_cron():
    """Run the timezone-aware cron job"""
    scheduler = TimezoneAwareScheduler()

    print("🕐 Starting timezone-aware cron scheduler...")
    print("This scheduler considers each user's local timezone")
    print("Press Ctrl+C to stop")
    print()

    check_count = 0
    while True:
        try:
            check_count += 1
            current_time = datetime.now(pytz.UTC).strftime("%H:%M:%S UTC")
            print(f'🔍 Check #{check_count} - {current_time} - Checking all timezones...')

            published_count = await scheduler.find_scheduled_content_timezone_aware()

            if published_count > 0:
                print(f'✅ Published {published_count} posts')
            else:
                print('⏰ No posts due at this time')

            print('⏳ Waiting 60 seconds until next check...')
            print('-' * 60)
            await asyncio.sleep(60)  # Wait 60 seconds

        except KeyboardInterrupt:
            print('🛑 Scheduler stopped by user')
            break
        except Exception as e:
            print(f'❌ Error during check: {e}')
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(run_timezone_aware_cron())
