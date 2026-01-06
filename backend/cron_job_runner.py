#!/usr/bin/env python3
"""
Standalone cron job runner for social media publishing
Run this with: python cron_job_runner.py
For continuous testing (5 minutes): python cron_job_runner.py --test
"""

import asyncio
import sys
import logging
import time
import argparse

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

async def run_continuous_test(duration_minutes=5):
    """Run the cron job continuously for testing"""
    print(f'Starting continuous test mode for {duration_minutes} minutes')
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    run_count = 0

    while time.time() < end_time:
        run_count += 1
        print(f'\n=== Run #{run_count} at {__import__("datetime").datetime.now()} ===')

        await run_mvp_cron()

        # Wait 30 seconds between runs (adjust as needed for testing)
        remaining_time = end_time - time.time()
        if remaining_time > 30:
            print(f'Waiting 30 seconds before next run... ({remaining_time:.1f} seconds remaining)')
            await asyncio.sleep(30)
        else:
            print(f'Test duration almost complete. Waiting {remaining_time:.1f} seconds...')
            await asyncio.sleep(remaining_time)

    total_runtime = time.time() - start_time
    print(f'\n=== Continuous test completed ===')
    print(f'Total runs: {run_count}')
    print(f'Total runtime: {total_runtime:.1f} seconds ({total_runtime/60:.1f} minutes)')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MVP Cron Job Runner')
    parser.add_argument('--test', '-t', action='store_true',
                       help='Run in continuous test mode for 5 minutes')
    parser.add_argument('--duration', '-d', type=int, default=5,
                       help='Duration in minutes for test mode (default: 5)')

    args = parser.parse_args()

    if args.test:
        print(f"Starting continuous test mode for {args.duration} minutes - {__import__('datetime').datetime.now()}")
        asyncio.run(run_continuous_test(args.duration))
    else:
        print(f"Starting single MVP cron job - {__import__('datetime').datetime.now()}")
        asyncio.run(run_mvp_cron())
