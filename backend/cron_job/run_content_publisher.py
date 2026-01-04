#!/usr/bin/env python3
"""
Cron job script to publish scheduled content posts
This script can be called directly or via cron to publish scheduled posts from created_content table
"""

import os
import sys
import argparse
import logging
from datetime import datetime
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler.post_publisher import PostPublisher

# Configure logging
log_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'content_publisher.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Run content publisher once"""
    try:
        logger.info("Starting content publisher cron job...")

        # Get Supabase credentials from environment
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not supabase_url or not supabase_key:
            logger.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables required")
            return 1

        # Create publisher instance
        publisher = PostPublisher(supabase_url, supabase_key)

        # Import asyncio to run the async methods
        import asyncio

        # For testing: Get test user ID from environment or use default
        test_user_id = os.getenv("TEST_USER_ID")
        test_user_email = os.getenv("TEST_USER_EMAIL", "services@atsnai.com")

        if test_user_id:
            logger.info(f"TEST MODE: Only processing posts for user ID {test_user_id} ({test_user_email})")

            # Run publishing for both tables but only for test user
            published_created_content = 0
            published_content_posts = 0

            try:
                # Publish from created_content table (filtered by test user)
                published_created_content = asyncio.run(publisher.check_and_publish_created_content_test_user(test_user_id))
                logger.info(f"Published {published_created_content} posts from created_content table for test user")
            except Exception as e:
                logger.error(f"Error publishing from created_content table: {e}")

            try:
                # Publish from content_posts table (filtered by test user)
                published_content_posts = asyncio.run(publisher.check_and_publish_scheduled_posts_test_user(test_user_id))
                logger.info(f"Published {published_content_posts} posts from content_posts table for test user")
            except Exception as e:
                logger.error(f"Error publishing from content_posts table: {e}")
        else:
            # Production mode: process all users (use original methods)
            logger.info("PRODUCTION MODE: Processing posts for all users")

            # Run publishing for both tables
            published_created_content = 0
            published_content_posts = 0

            try:
                # Publish from created_content table
                published_created_content = asyncio.run(publisher.check_and_publish_created_content())
                logger.info(f"Published {published_created_content} posts from created_content table")
            except Exception as e:
                logger.error(f"Error publishing from created_content table: {e}")

            try:
                # Publish from content_posts table (existing logic)
                published_content_posts = asyncio.run(publisher.check_and_publish_scheduled_posts())
                logger.info(f"Published {published_content_posts} posts from content_posts table")
            except Exception as e:
                logger.error(f"Error publishing from content_posts table: {e}")

        total_published = published_created_content + published_content_posts
        logger.info(f"Content publisher completed for test user. Total published: {total_published} posts")
        return 0

    except Exception as e:
        logger.error("Error in content publisher cron job: %s", e, exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
