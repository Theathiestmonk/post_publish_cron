"""
ANALYTICS COLLECTION SCHEDULER

Purpose:
--------
Schedules the daily analytics collector to run at 2:00 AM every day.

Implementation Options:
-----------------------
1. APScheduler (Backend) - IMPLEMENTED BELOW
2. Supabase pg_cron (SQL) - See setup.sql for configuration

Why APScheduler:
----------------
- Python-native, integrates seamlessly with FastAPI
- No database extension dependencies
- Easy to monitor and debug
- Can run alongside the main application

Scheduling:
-----------
Cron: 0 2 * * *  (Every day at 2:00 AM)
Timezone: Server timezone (ensure consistent with deployment)

Usage:
------
Import and initialize in main.py:
    from services.scheduler import start_analytics_scheduler
    start_analytics_scheduler()
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz

logger = logging.getLogger("scheduler")

# Global scheduler instance
scheduler = None


def run_analytics_collection_job():
    """
    Job wrapper for the analytics collector.
    
    This wrapper:
    - Logs job execution
    - Catches exceptions to prevent scheduler crash
    - Reports job status
    """
    job_start = datetime.now()
    logger.info("🕐 Starting scheduled analytics collection job")
    
    try:
        # Import here to avoid circular dependencies
        from services.analytics_collector import collect_daily_analytics
        
        # Run the collection
        stats = collect_daily_analytics()
        
        # Log results
        duration = (datetime.now() - job_start).total_seconds()
        logger.info(
            f"✅ Analytics collection completed successfully in {duration:.2f}s. "
            f"Metrics inserted: {stats.get('total_metrics_inserted', 0)}"
        )
        
    except Exception as e:
        logger.error(f"❌ Analytics collection job failed: {e}", exc_info=True)
        # Don't re-raise - we want the scheduler to continue


def start_analytics_scheduler():
    """
    Initialize and start the analytics collection scheduler.
    
    Schedule:
        - Trigger: Daily at 2:00 AM
        - Timezone: UTC (adjust as needed)
        - Misfire grace time: 1 hour (if server was down)
    
    Returns:
        BackgroundScheduler instance
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("Scheduler already running")
        return scheduler
    
    # Create scheduler
    scheduler = BackgroundScheduler(
        timezone=pytz.UTC,  # Use UTC for consistency across deployments
        job_defaults={
            'coalesce': True,  # Combine multiple missed runs into one
            'max_instances': 1,  # Only one collection job at a time
            'misfire_grace_time': 3600  # Allow 1 hour grace for misfires
        }
    )
    
    # Add daily collection job
    scheduler.add_job(
        func=run_analytics_collection_job,
        trigger=CronTrigger(hour=2, minute=0),  # 2:00 AM daily
        id='daily_analytics_collection',
        name='Daily Analytics Collection',
        replace_existing=True
    )
    
    # Start the scheduler
    scheduler.start()
    
    logger.info("✅ Analytics scheduler started - will run daily at 2:00 AM UTC")
    logger.info(f"   Next run: {scheduler.get_jobs()[0].next_run_time if scheduler.get_jobs() else 'N/A'}")
    
    return scheduler


def stop_analytics_scheduler():
    """
    Stop the analytics collection scheduler.
    
    Call this during application shutdown to clean up gracefully.
    """
    global scheduler
    
    if scheduler is not None:
        scheduler.shutdown(wait=True)
        scheduler = None
        logger.info("Analytics scheduler stopped")


def get_scheduler_status():
    """
    Get current scheduler status and job information.
    
    Returns:
        Dict with scheduler status and next run time
    """
    global scheduler
    
    if scheduler is None:
        return {
            "status": "not_running",
            "jobs": []
        }
    
    jobs = scheduler.get_jobs()
    
    return {
        "status": "running",
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            for job in jobs
        ]
    }


# ============================================================================
# MANUAL TRIGGER (for testing/debugging)
# ============================================================================

def trigger_analytics_collection_now():
    """
    Manually trigger analytics collection (for testing/admin purposes).
    
    Returns:
        Result stats from the collection job
    """
    logger.info("🔧 Manually triggering analytics collection")
    
    try:
        from services.analytics_collector import collect_daily_analytics
        stats = collect_daily_analytics()
        return stats
    except Exception as e:
        logger.error(f"Manual trigger failed: {e}", exc_info=True)
        raise
