#!/usr/bin/env python3
"""
Standalone cron job runner for social media publishing
Run this with: python cron_job_runner.py
"""

import asyncio
import sys
import logging

# Configure logging for Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def run_mvp_cron():
    """Main cron job function"""
    print('MVP Cron Job Started')
    print('Configuration: 100 users × 5 posts capacity')

    try:
        from cron_job.timezone_scheduler import TimezoneAwareScheduler

        scheduler = TimezoneAwareScheduler()

        # Log MVP configuration
        print(f'MVP Limits - Users: {scheduler.MVP_MAX_USERS}, Posts/User: {scheduler.MVP_MAX_POSTS_PER_USER}')
        print(f'Concurrent Capacity: {sum(scheduler.PLATFORM_CONCURRENT_LIMITS.values())} posts')

        # Run the publishing logic
        published_count = await scheduler.find_scheduled_content_timezone_aware()

        if published_count > 0:
            print(f'SUCCESS: Published {published_count} posts')
        else:
            print('INFO: No posts due at this time')

        print('MVP Cron Job Completed Successfully')

    except Exception as e:
        print(f'ERROR in MVP cron job: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print(f"Starting MVP cron job - {__import__('datetime').datetime.now()}")
    asyncio.run(run_mvp_cron())
