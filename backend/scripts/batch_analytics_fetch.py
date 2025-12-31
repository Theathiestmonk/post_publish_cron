#!/usr/bin/env python3
"""
Batch Analytics Fetch Script

This script fetches and stores analytics for multiple users with active platform connections.
It processes users in batches and provides detailed reporting.

Usage:
    python scripts/batch_analytics_fetch.py [--max-users N] [--platform PLATFORM] [--days DAYS] [--service-key]

Arguments:
    --max-users: Maximum number of users to process (default: 10)
    --platform: Specific platform to fetch (instagram, facebook) or 'all' (default: all)
    --days: Number of days back to fetch (default: 7)
    --service-key: Use service role key instead of anon key (default: False)

Example:
    python scripts/batch_analytics_fetch.py --max-users 5
    python scripts/batch_analytics_fetch.py --platform instagram --days 30 --service-key
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required modules
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import our analytics fetcher
from fetch_store_analytics import AnalyticsFetcher

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BatchAnalyticsProcessor:
    """Class for processing analytics for multiple users in batch."""

    def __init__(self, use_service_key: bool = False, max_workers: int = 3):
        """Initialize batch processor."""
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

        # Thread pool for parallel processing
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        logger.info(f"✅ BatchAnalyticsProcessor initialized with {max_workers} workers")

    def get_users_with_connections(self, limit: int = 10) -> List[str]:
        """Get users who have active platform connections."""
        try:
            logger.info(f"🔍 Finding users with active platform connections (limit: {limit})")

            # Query for distinct user_ids with active connections
            result = self.supabase.table("platform_connections").select(
                "user_id"
            ).eq("is_active", True).execute()

            if not result.data:
                logger.info("No users with active connections found")
                return []

            # Get unique user IDs
            user_ids = list(set(row["user_id"] for row in result.data))

            # Limit the number of users
            user_ids = user_ids[:limit]

            logger.info(f"✅ Found {len(user_ids)} users with active connections")
            return user_ids

        except Exception as e:
            logger.error(f"Failed to get users with connections: {e}")
            return []

    def process_single_user(self, user_id: str, platform: str = None, days_back: int = 7) -> Dict[str, Any]:
        """Process analytics for a single user."""
        try:
            logger.info(f"🔄 Processing user: {user_id}")

            # Create analytics fetcher for this user
            fetcher = AnalyticsFetcher(use_service_key=True)  # Always use service key for processing

            # Fetch and store analytics
            result = fetcher.fetch_and_store_user_analytics(
                user_id=user_id,
                platform=platform,
                days_back=days_back
            )

            logger.info(f"✅ Completed user {user_id}: {result.get('total_snapshots_stored', 0)} snapshots")

            return {
                "user_id": user_id,
                "success": True,
                "result": result
            }

        except Exception as e:
            logger.error(f"❌ Failed to process user {user_id}: {e}")
            return {
                "user_id": user_id,
                "success": False,
                "error": str(e)
            }

    def process_batch(self, user_ids: List[str], platform: str = None, days_back: int = 7) -> Dict[str, Any]:
        """Process analytics for multiple users in parallel."""
        logger.info("=" * 100)
        logger.info("BATCH ANALYTICS PROCESSING STARTED")
        logger.info("=" * 100)
        logger.info(f"Users to process: {len(user_ids)}")
        logger.info(f"Platform filter: {platform or 'all'}")
        logger.info(f"Days back: {days_back}")
        logger.info(f"Max workers: {self.max_workers}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 100)

        start_time = datetime.now()
        batch_stats = {
            "total_users": len(user_ids),
            "processed_users": 0,
            "successful_users": 0,
            "failed_users": 0,
            "total_snapshots_stored": 0,
            "user_results": {},
            "errors": []
        }

        # Submit all tasks to thread pool
        future_to_user = {}
        for user_id in user_ids:
            future = self.executor.submit(
                self.process_single_user,
                user_id,
                platform,
                days_back
            )
            future_to_user[future] = user_id

        # Process completed tasks
        for future in as_completed(future_to_user):
            user_id = future_to_user[future]
            batch_stats["processed_users"] += 1

            try:
                user_result = future.result()
                batch_stats["user_results"][user_id] = user_result

                if user_result["success"]:
                    batch_stats["successful_users"] += 1
                    batch_stats["total_snapshots_stored"] += user_result["result"].get("total_snapshots_stored", 0)
                    logger.info(f"✅ User {user_id}: {user_result['result'].get('total_snapshots_stored', 0)} snapshots")
                else:
                    batch_stats["failed_users"] += 1
                    batch_stats["errors"].append(f"User {user_id}: {user_result.get('error', 'Unknown error')}")
                    logger.error(f"❌ User {user_id} failed: {user_result.get('error', 'Unknown error')}")

            except Exception as e:
                batch_stats["failed_users"] += 1
                batch_stats["errors"].append(f"User {user_id}: Exception - {str(e)}")
                logger.error(f"❌ Exception processing user {user_id}: {e}")

        # Calculate duration and finalize
        duration = (datetime.now() - start_time).total_seconds()

        logger.info("\n" + "=" * 100)
        logger.info("BATCH ANALYTICS PROCESSING COMPLETED")
        logger.info("=" * 100)
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Total users: {batch_stats['total_users']}")
        logger.info(f"Processed: {batch_stats['processed_users']}")
        logger.info(f"Successful: {batch_stats['successful_users']}")
        logger.info(f"Failed: {batch_stats['failed_users']}")
        logger.info(f"Total snapshots stored: {batch_stats['total_snapshots_stored']}")
        logger.info(f"Average processing time: {duration / max(batch_stats['processed_users'], 1):.2f} seconds per user")

        if batch_stats["errors"]:
            logger.warning(f"Errors encountered: {len(batch_stats['errors'])}")
            for error in batch_stats["errors"][:5]:  # Show first 5 errors
                logger.warning(f"  - {error}")
            if len(batch_stats["errors"]) > 5:
                logger.warning(f"  ... and {len(batch_stats['errors']) - 5} more errors")

        logger.info("=" * 100)

        # Cleanup
        self.executor.shutdown(wait=True)

        return batch_stats


def main():
    """Main function to run batch analytics processing."""
    parser = argparse.ArgumentParser(description="Batch fetch and store analytics for multiple users")
    parser.add_argument("--max-users", type=int, default=10,
                       help="Maximum number of users to process (default: 10)")
    parser.add_argument("--platform", choices=["instagram", "facebook", "all"],
                       default="all", help="Platform to fetch analytics for (default: all)")
    parser.add_argument("--days", type=int, default=7,
                       help="Number of days back to fetch analytics (default: 7)")
    parser.add_argument("--service-key", action="store_true",
                       help="Use service role key instead of anon key")
    parser.add_argument("--workers", type=int, default=3,
                       help="Number of worker threads (default: 3)")

    args = parser.parse_args()

    try:
        # Initialize batch processor
        processor = BatchAnalyticsProcessor(
            use_service_key=args.service_key,
            max_workers=args.workers
        )

        # Get users with connections
        user_ids = processor.get_users_with_connections(limit=args.max_users)

        if not user_ids:
            print("❌ No users with active platform connections found")
            sys.exit(1)

        print(f"📊 Found {len(user_ids)} users to process")
        print(f"Users: {', '.join(user_ids[:5])}{'...' if len(user_ids) > 5 else ''}")

        # Convert platform argument
        platform = None if args.platform == "all" else args.platform

        # Process batch
        batch_result = processor.process_batch(
            user_ids=user_ids,
            platform=platform,
            days_back=args.days
        )

        # Print summary
        print("\n[BATCH] Processing Summary:")
        print(f"Total users: {batch_result['total_users']}")
        print(f"Processed: {batch_result['processed_users']}")
        print(f"Successful: {batch_result['successful_users']}")
        print(f"Failed: {batch_result['failed_users']}")
        print(f"Total snapshots stored: {batch_result['total_snapshots_stored']}")

        if batch_result['successful_users'] > 0:
            avg_snapshots = batch_result['total_snapshots_stored'] / batch_result['successful_users']
            print(f"Average snapshots per user: {avg_snapshots:.1f}")

        # Detailed user results
        if batch_result['user_results']:
            print("\n[USERS] Results Details:")
            successful_users = [
                uid for uid, result in batch_result['user_results'].items()
                if result.get('success')
            ]
            failed_users = [
                uid for uid, result in batch_result['user_results'].items()
                if not result.get('success')
            ]

            if successful_users:
                print(f"[SUCCESS] Users ({len(successful_users)}):")
                for uid in successful_users[:10]:  # Show first 10
                    result = batch_result['user_results'][uid]['result']
                    snapshots = result.get('total_snapshots_stored', 0)
                    print(f"   {uid}: {snapshots} snapshots")

            if failed_users:
                print(f"[FAILED] Users ({len(failed_users)}):")
                for uid in failed_users[:5]:  # Show first 5
                    error = batch_result['user_results'][uid].get('error', 'Unknown error')
                    print(f"   {uid}: {error}")

        # Exit with appropriate code
        if batch_result['failed_users'] > 0:
            print(f"\n⚠️  Batch completed with {batch_result['failed_users']} user failures")
            sys.exit(1)
        else:
            print("\n🎉 Batch processing completed successfully!")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Critical error: {e}")
        print(f"\n❌ Critical error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
