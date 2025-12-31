#!/usr/bin/env python3
"""
Fetch and Store Analytics Snapshots Script

This script fetches platform data and analytics for a given user and stores snapshots.
It uses service role key or anon key to access platform connections and store analytics.

Usage:
    python scripts/fetch_store_analytics.py <user_id> [--platform PLATFORM] [--days DAYS] [--service-key]

Arguments:
    user_id: User ID to fetch analytics for
    --platform: Specific platform (instagram, facebook) or 'all' (default: all)
    --days: Number of days back to fetch (default: 7)
    --service-key: Use service role key instead of anon key (default: False)

Example:
    python scripts/fetch_store_analytics.py 58d91fe2-1401-46fd-b183-a2a118997fc1
    python scripts/fetch_store_analytics.py 58d91fe2-1401-46fd-b183-a2a118997fc1 --platform instagram --days 30
    python scripts/fetch_store_analytics.py 58d91fe2-1401-46fd-b183-a2a118997fc1 --service-key
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required modules
from supabase import create_client, Client
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PlatformConnection:
    """Platform connection data structure."""
    id: str
    user_id: str
    platform: str
    account_id: str
    access_token_encrypted: str
    is_active: bool
    created_at: str


class AnalyticsFetcher:
    """Main class for fetching and storing analytics."""

    def __init__(self, use_service_key: bool = False):
        """Initialize with Supabase connection."""
        self.supabase_url = os.getenv("SUPABASE_URL")
        if not self.supabase_url:
            raise ValueError("SUPABASE_URL environment variable not found")

        # Use service role key if requested, otherwise use anon key
        if use_service_key:
            self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if not self.supabase_key:
                raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable not found")
            logger.info("Using SERVICE ROLE KEY for database access")
        else:
            self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
            if not self.supabase_key:
                raise ValueError("SUPABASE_ANON_KEY environment variable not found")
            logger.info("Using ANON KEY for database access")

        # Initialize Supabase client
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)

        # Get encryption key for token decryption
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        if not self.encryption_key:
            raise ValueError("ENCRYPTION_KEY environment variable not found")

        # Initialize cipher suite
        try:
            self.cipher_suite = Fernet(self.encryption_key.encode())
        except Exception as e:
            raise ValueError(f"Failed to initialize encryption cipher: {e}")

        logger.info("✅ AnalyticsFetcher initialized successfully")

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt access token."""
        if not encrypted_token:
            return ""

        try:
            decrypted = self.cipher_suite.decrypt(encrypted_token.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Token decryption failed: {e}")
            return ""

    def get_user_platform_connections(self, user_id: str, platform: Optional[str] = None) -> List[PlatformConnection]:
        """Get active platform connections for a user."""
        try:
            logger.info(f"🔍 Fetching platform connections for user: {user_id}")

            # Build query
            query = self.supabase.table("platform_connections").select("*").eq(
                "user_id", user_id
            ).eq("is_active", True)

            if platform and platform.lower() != 'all':
                query = query.eq("platform", platform.lower())

            result = query.execute()

            if not result.data:
                logger.info(f"No active connections found for user {user_id}")
                return []

            connections = []
            for conn_data in result.data:
                connection = PlatformConnection(
                    id=conn_data.get("id"),
                    user_id=conn_data.get("user_id"),
                    platform=conn_data.get("platform", "").lower(),
                    account_id=conn_data.get("account_id") or conn_data.get("page_id", ""),
                    access_token_encrypted=conn_data.get("access_token_encrypted") or conn_data.get("access_token", ""),
                    is_active=conn_data.get("is_active", True),
                    created_at=conn_data.get("created_at", "")
                )
                connections.append(connection)

            logger.info(f"✅ Found {len(connections)} active connections: {[c.platform for c in connections]}")
            return connections

        except Exception as e:
            logger.error(f"Failed to fetch platform connections: {e}")
            return []

    def fetch_instagram_analytics(self, connection: PlatformConnection, days_back: int) -> Dict[str, Any]:
        """Fetch Instagram analytics data."""
        try:
            logger.info(f"📸 Fetching Instagram analytics for account: {connection.account_id}")

            # Decrypt access token
            access_token = self.decrypt_token(connection.access_token_encrypted)
            if not access_token:
                return {"error": "Failed to decrypt access token"}

            account_id = connection.account_id
            if not account_id:
                return {"error": "No account ID found"}

            # Get Instagram Business Account ID if needed
            instagram_account_id = account_id
            if str(account_id).isdigit() and len(str(account_id)) <= 15:
                logger.info("🔄 Converting Facebook Page ID to Instagram Business Account ID")
                page_resp = requests.get(
                    f"https://graph.facebook.com/v18.0/{account_id}",
                    params={"access_token": access_token, "fields": "instagram_business_account"},
                    timeout=10
                )

                if page_resp.status_code == 200:
                    page_data = page_resp.json()
                    ig_account = page_data.get("instagram_business_account")
                    if ig_account:
                        instagram_account_id = ig_account.get("id")
                        logger.info(f"✅ Found Instagram Business Account: {instagram_account_id}")
                    else:
                        return {"error": "No Instagram Business account linked to Facebook Page"}
                else:
                    return {"error": f"Failed to get Instagram account: {page_resp.text}"}

            # Define metrics to fetch
            metrics = ["impressions", "reach", "profile_views", "follower_count"]

            # Fetch insights
            insights_url = f"https://graph.facebook.com/v18.0/{instagram_account_id}/insights"
            params = {
                "access_token": access_token,
                "metric": ",".join(metrics),
                "period": "day"
            }

            # Add date range if specified
            if days_back > 1:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days_back)
                params["since"] = int(start_date.timestamp())
                params["until"] = int(end_date.timestamp())

            logger.info(f"🌐 Fetching Instagram insights: {insights_url}")
            import requests
            response = requests.get(insights_url, params=params, timeout=15)

            if response.status_code != 200:
                error_msg = f"Instagram API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {"error": error_msg}

            insights_data = response.json()
            logger.info(f"✅ Fetched Instagram insights with {len(insights_data.get('data', []))} metrics")

            # Transform data for storage
            analytics_data = {}
            for insight in insights_data.get("data", []):
                metric_name = insight.get("name")
                values = insight.get("values", [])
                if values:
                    latest_value = values[-1].get("value", 0)
                    analytics_data[metric_name] = latest_value

            # Fetch follower count separately if not in insights
            if "follower_count" not in analytics_data:
                logger.info("🔄 Fetching follower count separately")
                account_resp = requests.get(
                    f"https://graph.facebook.com/v18.0/{instagram_account_id}",
                    params={"access_token": access_token, "fields": "followers_count"},
                    timeout=10
                )
                if account_resp.status_code == 200:
                    account_data = account_resp.json()
                    followers = account_data.get("followers_count", 0)
                    analytics_data["follower_count"] = followers

            return {
                "success": True,
                "platform": "instagram",
                "account_id": instagram_account_id,
                "data": analytics_data,
                "fetched_at": datetime.now().isoformat(),
                "days_back": days_back
            }

        except Exception as e:
            logger.error(f"Error fetching Instagram analytics: {e}")
            return {"error": str(e)}

    def fetch_instagram_post_analytics(self, connection: PlatformConnection, days_back: int) -> Dict[str, Any]:
        """Fetch Instagram post-level analytics (fallback when account insights fail)."""
        try:
            logger.info(f"[POST-LEVEL] Fetching Instagram post analytics for account: {connection.account_id}")

            # Decrypt access token
            access_token = self.decrypt_token(connection.access_token_encrypted)
            if not access_token:
                return {"error": "Failed to decrypt access token"}

            account_id = connection.account_id
            if not account_id:
                return {"error": "No account ID found"}

            # Get Instagram Business Account ID if needed
            instagram_account_id = account_id
            if str(account_id).isdigit() and len(str(account_id)) <= 15:
                page_resp = requests.get(
                    f"https://graph.facebook.com/v18.0/{account_id}",
                    params={"access_token": access_token, "fields": "instagram_business_account"},
                    timeout=10
                )
                if page_resp.status_code == 200:
                    ig_account = page_resp.json().get("instagram_business_account")
                    if ig_account:
                        instagram_account_id = ig_account.get("id")

            # Fetch recent posts
            posts_url = f"https://graph.facebook.com/v18.0/{instagram_account_id}/media"
            params = {
                "access_token": access_token,
                "fields": "id,like_count,comments_count,timestamp",
                "limit": min(days_back * 2, 20)  # Get more posts for date range
            }

            response = requests.get(posts_url, params=params, timeout=15)
            if response.status_code != 200:
                return {"error": f"Failed to fetch posts: {response.text}"}

            posts_data = response.json()
            posts = posts_data.get("data", [])

            if not posts:
                return {"error": "No posts found for analytics"}

            # Aggregate metrics from posts
            total_likes = 0
            total_comments = 0
            post_count = 0

            for post in posts:
                total_likes += post.get("like_count", 0) or 0
                total_comments += post.get("comments_count", 0) or 0
                post_count += 1

            analytics_data = {
                "likes": total_likes,
                "comments": total_comments,
                "posts_analyzed": post_count
            }

            logger.info(f"[POST-LEVEL] Analyzed {post_count} posts: {total_likes} likes, {total_comments} comments")

            return {
                "success": True,
                "platform": "instagram",
                "account_id": instagram_account_id,
                "data": analytics_data,
                "fetched_at": datetime.now().isoformat(),
                "days_back": days_back,
                "analytics_type": "post_level"
            }

        except Exception as e:
            logger.error(f"Error fetching Instagram post analytics: {e}")
            return {"error": str(e)}

    def fetch_facebook_post_analytics(self, connection: PlatformConnection, days_back: int) -> Dict[str, Any]:
        """Fetch Facebook post-level analytics."""
        try:
            logger.info(f"[POST-LEVEL] Fetching Facebook post analytics for page: {connection.account_id}")

            # Decrypt access token
            access_token = self.decrypt_token(connection.access_token_encrypted)
            if not access_token:
                return {"error": "Failed to decrypt access token"}

            page_id = connection.account_id
            if not page_id:
                return {"error": "No page ID found"}

            # Fetch recent posts
            posts_url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
            params = {
                "access_token": access_token,
                "fields": "id,likes.summary(true),comments.summary(true),shares,message,created_time",
                "limit": min(days_back * 2, 20)  # Get more posts for date range
            }

            response = requests.get(posts_url, params=params, timeout=15)
            if response.status_code != 200:
                return {"error": f"Failed to fetch posts: {response.text}"}

            posts_data = response.json()
            posts = posts_data.get("data", [])

            if not posts:
                return {"error": "No posts found for analytics"}

            # Aggregate metrics from posts
            total_likes = 0
            total_comments = 0
            total_shares = 0
            post_count = 0

            for post in posts:
                likes_data = post.get("likes", {}).get("summary", {}).get("total_count", 0)
                comments_data = post.get("comments", {}).get("summary", {}).get("total_count", 0)
                shares_data = post.get("shares", {}).get("count", 0)

                total_likes += likes_data or 0
                total_comments += comments_data or 0
                total_shares += shares_data or 0
                post_count += 1

            analytics_data = {
                "likes": total_likes,
                "comments": total_comments,
                "shares": total_shares,
                "posts_analyzed": post_count
            }

            logger.info(f"[POST-LEVEL] Analyzed {post_count} posts: {total_likes} likes, {total_comments} comments, {total_shares} shares")

            return {
                "success": True,
                "platform": "facebook",
                "account_id": page_id,
                "data": analytics_data,
                "fetched_at": datetime.now().isoformat(),
                "days_back": days_back,
                "analytics_type": "post_level"
            }

        except Exception as e:
            logger.error(f"Error fetching Facebook post analytics: {e}")
            return {"error": str(e)}

    def fetch_facebook_analytics(self, connection: PlatformConnection, days_back: int) -> Dict[str, Any]:
        """Fetch Facebook analytics data."""
        try:
            logger.info(f"📘 Fetching Facebook analytics for page: {connection.account_id}")

            # Decrypt access token
            access_token = self.decrypt_token(connection.access_token_encrypted)
            if not access_token:
                return {"error": "Failed to decrypt access token"}

            page_id = connection.account_id
            if not page_id:
                return {"error": "No page ID found"}

            # Define metrics to fetch - using basic Facebook Page insights metrics that work in development
            metrics = ["page_fans", "page_views_total"]

            # Fetch insights
            insights_url = f"https://graph.facebook.com/v18.0/{page_id}/insights"
            params = {
                "access_token": access_token,
                "metric": ",".join(metrics),
                "period": "day"
            }

            # Add date range if specified
            if days_back > 1:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days_back)
                params["since"] = int(start_date.timestamp())
                params["until"] = int(end_date.timestamp())

            logger.info(f"🌐 Fetching Facebook insights: {insights_url}")
            import requests
            response = requests.get(insights_url, params=params, timeout=15)

            if response.status_code != 200:
                error_msg = f"Facebook API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {"error": error_msg}

            insights_data = response.json()
            logger.info(f"✅ Fetched Facebook insights with {len(insights_data.get('data', []))} metrics")

            # Transform data for storage
            analytics_data = {}
            for insight in insights_data.get("data", []):
                metric_name = insight.get("name")
                values = insight.get("values", [])
                if values:
                    latest_value = values[-1].get("value", 0)
                    analytics_data[metric_name] = latest_value

            return {
                "success": True,
                "platform": "facebook",
                "account_id": page_id,
                "data": analytics_data,
                "fetched_at": datetime.now().isoformat(),
                "days_back": days_back
            }

        except Exception as e:
            logger.error(f"Error fetching Facebook analytics: {e}")
            return {"error": str(e)}

    def store_analytics_snapshots(self, user_id: str, analytics_result: Dict[str, Any]) -> Dict[str, Any]:
        """Store analytics data as snapshots in the database."""
        try:
            if "error" in analytics_result:
                return {"success": False, "error": analytics_result["error"]}

            platform = analytics_result["platform"]
            analytics_data = analytics_result["data"]
            fetched_at = analytics_result["fetched_at"]

            stored_count = 0
            errors = []

            # Store each metric as a snapshot
            for metric_name, value in analytics_data.items():
                try:
                    # Prepare snapshot data
                    snapshot_data = {
                        "user_id": user_id,
                        "platform": platform,
                        "source": "social_media",
                        "metric": metric_name,
                        "value": float(value) if value is not None else 0.0,
                        "date": datetime.now().date().isoformat(),
                        "post_id": None,  # Account-level metrics
                        "metadata": {
                            "fetched_at": fetched_at,
                            "script_version": "fetch_store_analytics_v1",
                            "days_back": analytics_result.get("days_back", 1)
                        }
                    }

                    # Insert using upsert to handle duplicates
                    result = self.supabase.table("analytics_snapshots").upsert(
                        snapshot_data,
                        on_conflict="user_id,platform,source,metric,date,post_id"
                    ).execute()

                    if result.data:
                        stored_count += 1
                        logger.info(f"✅ Stored {platform}/{metric_name} = {value}")
                    else:
                        errors.append(f"Failed to store {metric_name}")

                except Exception as e:
                    error_msg = f"Error storing {metric_name}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            return {
                "success": stored_count > 0,
                "stored_count": stored_count,
                "total_metrics": len(analytics_data),
                "errors": errors if errors else None
            }

        except Exception as e:
            logger.error(f"Error storing analytics snapshots: {e}")
            return {"success": False, "error": str(e)}

    def fetch_and_store_user_analytics(self, user_id: str, platform: Optional[str] = None, days_back: int = 7) -> Dict[str, Any]:
        """Main method to fetch and store analytics for a user."""
        logger.info("=" * 80)
        logger.info("ANALYTICS FETCH & STORE OPERATION STARTED")
        logger.info("=" * 80)
        logger.info(f"User ID: {user_id}")
        logger.info(f"Platform filter: {platform or 'all'}")
        logger.info(f"Days back: {days_back}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 80)

        start_time = datetime.now()
        stats = {
            "user_id": user_id,
            "connections_found": 0,
            "platforms_processed": 0,
            "successful_platforms": 0,
            "failed_platforms": 0,
            "total_snapshots_stored": 0,
            "platform_results": {},
            "errors": []
        }

        try:
            # Get user platform connections
            connections = self.get_user_platform_connections(user_id, platform)
            stats["connections_found"] = len(connections)

            if not connections:
                stats["errors"].append("No active platform connections found")
                return stats

            # Process each connection
            for connection in connections:
                platform_name = connection.platform
                stats["platforms_processed"] += 1

                logger.info(f"\n🔄 Processing {platform_name}...")
                platform_result = {
                    "platform": platform_name,
                    "account_id": connection.account_id,
                    "success": False,
                    "snapshots_stored": 0,
                    "error": None
                }

                try:
                    # Fetch analytics based on platform
                    if platform_name == "instagram":
                        # Try account-level analytics first, fall back to post-level if it fails
                        analytics_result = self.fetch_instagram_analytics(connection, days_back)
                        if "error" in analytics_result and "permission" in analytics_result["error"].lower():
                            logger.info(f"Account-level analytics failed, trying post-level analytics for {platform_name}")
                            analytics_result = self.fetch_instagram_post_analytics(connection, days_back)
                    elif platform_name == "facebook":
                        # For Facebook, try post-level analytics since insights may not be available
                        analytics_result = self.fetch_facebook_post_analytics(connection, days_back)
                        if "error" in analytics_result:
                            logger.info(f"Post-level analytics failed for {platform_name}, trying page insights")
                            analytics_result = self.fetch_facebook_analytics(connection, days_back)
                    else:
                        analytics_result = {"error": f"Platform '{platform_name}' not supported"}

                    if "error" not in analytics_result:
                        # Store the analytics data
                        storage_result = self.store_analytics_snapshots(user_id, analytics_result)

                        if storage_result["success"]:
                            platform_result["success"] = True
                            platform_result["snapshots_stored"] = storage_result["stored_count"]
                            platform_result["metrics_count"] = analytics_result.get("data", {})
                            stats["successful_platforms"] += 1
                            stats["total_snapshots_stored"] += storage_result["stored_count"]
                            logger.info(f"✅ {platform_name}: Stored {storage_result['stored_count']} snapshots")
                        else:
                            platform_result["error"] = storage_result.get("error", "Storage failed")
                            stats["failed_platforms"] += 1
                    else:
                        platform_result["error"] = analytics_result["error"]
                        stats["failed_platforms"] += 1
                        stats["errors"].append(f"{platform_name}: {analytics_result['error']}")

                except Exception as e:
                    platform_result["error"] = str(e)
                    stats["failed_platforms"] += 1
                    stats["errors"].append(f"{platform_name}: {str(e)}")
                    logger.error(f"❌ {platform_name} failed: {e}")

                stats["platform_results"][platform_name] = platform_result

        except Exception as e:
            stats["errors"].append(f"Critical error: {str(e)}")
            logger.error(f"Critical error in fetch_and_store_user_analytics: {e}")

        # Calculate duration and finalize
        duration = (datetime.now() - start_time).total_seconds()

        logger.info("\n" + "=" * 80)
        logger.info("ANALYTICS FETCH & STORE OPERATION COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Connections found: {stats['connections_found']}")
        logger.info(f"Platforms processed: {stats['platforms_processed']}")
        logger.info(f"Successful platforms: {stats['successful_platforms']}")
        logger.info(f"Failed platforms: {stats['failed_platforms']}")
        logger.info(f"Total snapshots stored: {stats['total_snapshots_stored']}")
        if stats["errors"]:
            logger.warning(f"Errors encountered: {len(stats['errors'])}")
            for error in stats["errors"]:
                logger.warning(f"  - {error}")
        logger.info("=" * 80)

        return stats


def main():
    """Main function to run the analytics fetch and store script."""
    parser = argparse.ArgumentParser(description="Fetch and store analytics snapshots for a user")
    parser.add_argument("user_id", help="User ID to fetch analytics for")
    parser.add_argument("--platform", choices=["instagram", "facebook", "all"],
                       default="all", help="Platform to fetch analytics for (default: all)")
    parser.add_argument("--days", type=int, default=7,
                       help="Number of days back to fetch analytics (default: 7)")
    parser.add_argument("--service-key", action="store_true",
                       help="Use service role key instead of anon key")

    args = parser.parse_args()

    try:
        # Initialize analytics fetcher
        fetcher = AnalyticsFetcher(use_service_key=args.service_key)

        # Convert platform argument
        platform = None if args.platform == "all" else args.platform

        # Fetch and store analytics
        result = fetcher.fetch_and_store_user_analytics(
            user_id=args.user_id,
            platform=platform,
            days_back=args.days
        )

        # Print summary
        print("\n[ANALYTICS] Operation Summary:")
        print(f"User ID: {result['user_id']}")
        print(f"Connections found: {result['connections_found']}")
        print(f"Platforms processed: {result['platforms_processed']}")
        print(f"Successful: {result['successful_platforms']}")
        print(f"Failed: {result['failed_platforms']}")
        print(f"Snapshots stored: {result['total_snapshots_stored']}")

        if result['platform_results']:
            print("\n[RESULTS] Platform Details:")
            for platform_name, platform_data in result['platform_results'].items():
                status = "[SUCCESS]" if platform_data['success'] else "[FAILED]"
                print(f"  {status} {platform_name}: {platform_data['snapshots_stored']} snapshots")
                if platform_data.get('error'):
                    print(f"      Error: {platform_data['error']}")

        # Exit with appropriate code
        if result['failed_platforms'] > 0:
            print(f"\n[WARNING] Completed with {result['failed_platforms']} platform failures")
            sys.exit(1)
        else:
            print("\n[SUCCESS] Operation completed successfully!")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n[CANCELLED] Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Critical error: {e}")
        print(f"\n[ERROR] Critical error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
