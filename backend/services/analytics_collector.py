"""
DAILY ANALYTICS COLLECTOR SERVICE

Purpose:
--------
This service runs DAILY at 2:00 AM to collect ACCOUNT-LEVEL analytics from all
connected platforms and store them in the analytics_snapshots table.

Architecture:
-------------
- Runs independently of Emily (chatbot) and Orion (analytics engine)
- Emily & Orion remain READ-ONLY consumers of analytics_snapshots
- This service is the SOLE WRITER for daily account-level metrics

Scope:
------
✅ Collects: Daily account-level metrics (impressions, reach, engagement)
✅ Stores: metadata.post_type (post/reel/video/short) IF available from API
❌ NEVER: Collects individual post-level data (that stays live via APIs)
❌ NEVER: Sets post_id (always NULL for account-level)

Scheduling:
-----------
Runs daily at 02:00 AM via:
- Option 1: Supabase pg_cron (preferred)
- Option 2: Backend task scheduler (APScheduler)

Data Flow:
----------
1. Query all users with active platform connections
2. For each user:
   - For each connected platform:
     - Decrypt access token
     - Fetch DAILY account metrics from platform API
     - Normalize data
     - Insert into analytics_snapshots (UPSERT-safe)
3. Handle failures gracefully (per-platform, per-user isolation)
"""

import os
import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
import requests
from supabase import create_client, Client
from cryptography.fernet import Fernet

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("analytics_collector")

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt platform access token using Fernet encryption."""
    if not ENCRYPTION_KEY or not encrypted_token:
        return encrypted_token or ""
    
    try:
        cipher_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
        return cipher_suite.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        logger.error(f"Token decryption failed: {e}")
        return encrypted_token


def get_yesterday_date() -> str:
    """Get yesterday's date in YYYY-MM-DD format (for daily metrics)."""
    yesterday = date.today() - timedelta(days=1)
    return yesterday.isoformat()


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_all_users_with_connections() -> List[Dict[str, Any]]:
    """
    Fetch all users who have active platform connections.
    
    Returns:
        List of user records with their IDs
    """
    try:
        # Get distinct user_ids from platform_connections where status is active
        result = supabase.table("platform_connections").select(
            "user_id"
        ).eq("status", "active").execute()
        
        if not result.data:
            logger.info("No active platform connections found")
            return []
        
        # Get unique user IDs
        user_ids = list(set(row["user_id"] for row in result.data))
        logger.info(f"Found {len(user_ids)} users with active connections")
        
        return [{"user_id": uid} for uid in user_ids]
        
    except Exception as e:
        logger.error(f"Failed to fetch users with connections: {e}", exc_info=True)
        return []


def get_user_platform_connections(user_id: str) -> List[Dict[str, Any]]:
    """
    Get all active platform connections for a specific user.
    
    Args:
        user_id: User ID
    
    Returns:
        List of platform connection records
    """
    try:
        result = supabase.table("platform_connections").select("*").eq(
            "user_id", user_id
        ).eq("status", "active").execute()
        
        return result.data or []
        
    except Exception as e:
        logger.error(f"Failed to fetch connections for user {user_id}: {e}")
        return []


def insert_analytics_snapshot(
    user_id: str,
    platform: str,
    metric: str,
    value: float,
    snapshot_date: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Insert a single analytics snapshot into the database.
    
    CRITICAL: post_id is ALWAYS NULL because this is ACCOUNT-LEVEL data.
    Individual post analytics are fetched LIVE via APIs, never stored here.
    
    Args:
        user_id: User ID
        platform: Platform name (lowercase)
        metric: Metric name (e.g., 'impressions', 'reach')
        value: Metric value
        snapshot_date: Date in YYYY-MM-DD format
        metadata: Optional metadata (e.g., post_type, API info)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Prepare snapshot data
        snapshot = {
            "user_id": user_id,
            "platform": platform.lower(),
            "source": "social_media",  # All platforms in this collector are social
            "metric": metric,
            "value": float(value) if value is not None else 0.0,
            "date": snapshot_date,
            "post_id": None,  # ⚠️ ALWAYS NULL - this is account-level only
            "metadata": metadata or {}
        }
        
        # Use UPSERT to respect unique constraint and avoid duplicates
        # Constraint: (user_id, platform, source, metric, date, post_id)
        result = supabase.table("analytics_snapshots").upsert(
            snapshot,
            on_conflict="user_id,platform,source,metric,date,post_id"
        ).execute()
        
        return bool(result.data)
        
    except Exception as e:
        logger.error(f"Failed to insert snapshot for {platform}/{metric}: {e}")
        return False


# ============================================================================
# PLATFORM-SPECIFIC COLLECTORS
# ============================================================================

def collect_instagram_daily_metrics(connection: Dict[str, Any], snapshot_date: str) -> List[Dict[str, Any]]:
    """
    Collect Instagram Business/Creator account DAILY metrics.
    
    API: GET /{ig-business-id}/insights?metric=...&period=day
    
    Metrics:
    - impressions: Total number of times posts were seen
    - reach: Unique accounts that saw posts
    - profile_views: Profile visits
    
    Note: If API provides media_type context, we store it in metadata.
    
    Args:
        connection: Platform connection record
        snapshot_date: Date to collect metrics for (YYYY-MM-DD)
    
    Returns:
        List of normalized metric dictionaries
    """
    try:
        access_token = decrypt_token(connection.get("access_token", ""))
        account_id = connection.get("account_id") or connection.get("page_id")
        
        if not access_token or not account_id:
            logger.warning(f"Missing credentials for Instagram (user={connection.get('user_id')})")
            return []
        
        # Get Instagram Business Account ID if needed
        instagram_account_id = account_id
        if str(account_id).isdigit() and len(str(account_id)) <= 15:
            logger.info("Fetching Instagram Business account ID from Facebook Page")
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
                else:
                    logger.warning("No Instagram Business account linked")
                    return []
            else:
                logger.error(f"Failed to get Instagram account: {page_resp.text}")
                return []
        
        # Fetch daily insights
        metrics_to_fetch = ["impressions", "reach", "profile_views"]
        
        insights_url = f"https://graph.facebook.com/v18.0/{instagram_account_id}/insights"
        params = {
            "access_token": access_token,
            "metric": ",".join(metrics_to_fetch),
            "period": "day"
        }
        
        response = requests.get(insights_url, params=params, timeout=15)
        
        if response.status_code != 200:
            logger.error(f"Instagram API error: {response.status_code} - {response.text}")
            return []
        
        data = response.json()
        normalized_metrics = []
        
        for insight in data.get("data", []):
            metric_name = insight.get("name")
            values = insight.get("values", [])
            
            # Get the latest daily value
            if values:
                latest_value = values[-1].get("value", 0)
                
                normalized_metrics.append({
                    "metric": metric_name,
                    "value": latest_value,
                    "metadata": {
                        "api": "instagram_graph",
                        "period": "day",
                        "fetched_at": datetime.now().isoformat()
                    }
                })
        
        logger.info(f"✅ Collected {len(normalized_metrics)} Instagram metrics")
        return normalized_metrics
        
    except Exception as e:
        logger.error(f"Instagram collection failed: {e}", exc_info=True)
        return []


def collect_facebook_daily_metrics(connection: Dict[str, Any], snapshot_date: str) -> List[Dict[str, Any]]:
    """
    Collect Facebook Page DAILY metrics.
    
    API: GET /{page-id}/insights?metric=...&period=day
    
    Metrics:
    - page_impressions: Total views of page content
    - page_engaged_users: Unique users who engaged with page
    - page_views: Total page views
    
    Args:
        connection: Platform connection record
        snapshot_date: Date to collect metrics for
    
    Returns:
        List of normalized metric dictionaries
    """
    try:
        access_token = decrypt_token(connection.get("access_token", ""))
        page_id = connection.get("account_id") or connection.get("page_id")
        
        if not access_token or not page_id:
            logger.warning(f"Missing credentials for Facebook (user={connection.get('user_id')})")
            return []
        
        # Fetch daily page insights
        metrics_to_fetch = ["page_impressions", "page_engaged_users", "page_views"]
        
        insights_url = f"https://graph.facebook.com/v18.0/{page_id}/insights"
        params = {
            "access_token": access_token,
            "metric": ",".join(metrics_to_fetch),
            "period": "day"
        }
        
        response = requests.get(insights_url, params=params, timeout=15)
        
        if response.status_code != 200:
            logger.error(f"Facebook API error: {response.status_code} - {response.text}")
            return []
        
        data = response.json()
        normalized_metrics = []
        
        for insight in data.get("data", []):
            metric_name = insight.get("name")
            values = insight.get("values", [])
            
            # Get the latest daily value
            if values:
                latest_value = values[-1].get("value", 0)
                
                normalized_metrics.append({
                    "metric": metric_name,
                    "value": latest_value,
                    "metadata": {
                        "api": "facebook_graph",
                        "period": "day",
                        "fetched_at": datetime.now().isoformat()
                    }
                })
        
        logger.info(f"✅ Collected {len(normalized_metrics)} Facebook metrics")
        return normalized_metrics
        
    except Exception as e:
        logger.error(f"Facebook collection failed: {e}", exc_info=True)
        return []


def collect_youtube_daily_metrics(connection: Dict[str, Any], snapshot_date: str) -> List[Dict[str, Any]]:
    """
    Collect YouTube Channel DAILY metrics.
    
    Note: YouTube Analytics API requires OAuth2 and separate setup.
    This is a placeholder showing the expected structure.
    
    Metrics:
    - views: Daily video views
    - estimatedMinutesWatched: Watch time
    - subscribersGained: New subscribers
    
    Args:
        connection: Platform connection record
        snapshot_date: Date to collect metrics for
    
    Returns:
        List of normalized metric dictionaries
    """
    try:
        # TODO: Implement YouTube Analytics API integration
        # Requires: Google OAuth2, YouTube Data API v3 enabled
        logger.info("YouTube collection not yet implemented")
        return []
        
    except Exception as e:
        logger.error(f"YouTube collection failed: {e}", exc_info=True)
        return []


def collect_platform_metrics(
    platform: str,
    connection: Dict[str, Any],
    snapshot_date: str
) -> List[Dict[str, Any]]:
    """
    Route to platform-specific collector based on platform name.
    
    Args:
        platform: Platform name
        connection: Platform connection record
        snapshot_date: Date to collect metrics for
    
    Returns:
        List of normalized metric dictionaries
    """
    platform_lower = platform.lower()
    
    if platform_lower == "instagram":
        return collect_instagram_daily_metrics(connection, snapshot_date)
    elif platform_lower == "facebook":
        return collect_facebook_daily_metrics(connection, snapshot_date)
    elif platform_lower == "youtube":
        return collect_youtube_daily_metrics(connection, snapshot_date)
    else:
        logger.warning(f"Platform '{platform}' not supported for collection")
        return []


# ============================================================================
# MAIN COLLECTION ORCHESTRATOR
# ============================================================================

def collect_daily_analytics():
    """
    Main orchestrator function - collects daily analytics for ALL users.
    
    This function:
    1. Gets all users with active platform connections
    2. For each user, collects metrics from each connected platform
    3. Inserts metrics into analytics_snapshots table
    4. Handles errors gracefully (per-user, per-platform isolation)
    
    Returns:
        Dict with collection statistics
    """
    logger.info("=" * 80)
    logger.info("DAILY ANALYTICS COLLECTION STARTED")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    snapshot_date = get_yesterday_date()  # Collect yesterday's metrics
    
    stats = {
        "total_users": 0,
        "successful_users": 0,
        "failed_users": 0,
        "total_platforms": 0,
        "successful_platforms": 0,
        "failed_platforms": 0,
        "total_metrics_inserted": 0
    }
    
    # Step 1: Get all users with connections
    users = get_all_users_with_connections()
    stats["total_users"] = len(users)
    
    if not users:
        logger.info("No users to process")
        return stats
    
    # Step 2: Process each user
    for user in users:
        user_id = user["user_id"]
        logger.info(f"\n{'─' * 80}")
        logger.info(f"Processing user: {user_id}")
        logger.info(f"{'─' * 80}")
        
        try:
            # Get user's platform connections
            connections = get_user_platform_connections(user_id)
            
            if not connections:
                logger.info(f"User {user_id} has no active connections")
                continue
            
            user_success = True
            
            # Step 3: Process each platform for this user
            for connection in connections:
                platform = connection.get("platform", "unknown")
                stats["total_platforms"] += 1
                
                logger.info(f"  Collecting {platform} metrics...")
                
                try:
                    # Collect metrics from platform API
                    metrics = collect_platform_metrics(
                        platform=platform,
                        connection=connection,
                        snapshot_date=snapshot_date
                    )
                    
                    if not metrics:
                        logger.warning(f"    No metrics returned for {platform}")
                        stats["failed_platforms"] += 1
                        user_success = False
                        continue
                    
                    # Insert each metric into database
                    inserted_count = 0
                    for metric_data in metrics:
                        success = insert_analytics_snapshot(
                            user_id=user_id,
                            platform=platform,
                            metric=metric_data["metric"],
                            value=metric_data["value"],
                            snapshot_date=snapshot_date,
                            metadata=metric_data.get("metadata")
                        )
                        
                        if success:
                            inserted_count += 1
                    
                    stats["total_metrics_inserted"] += inserted_count
                    stats["successful_platforms"] += 1
                    logger.info(f"    ✅ {platform}: Inserted {inserted_count} metrics")
                    
                except Exception as e:
                    logger.error(f"    ❌ {platform} failed: {e}", exc_info=True)
                    stats["failed_platforms"] += 1
                    user_success = False
                    # Continue to next platform (isolation)
            
            # Update user stats
            if user_success:
                stats["successful_users"] += 1
            else:
                stats["failed_users"] += 1
                
        except Exception as e:
            logger.error(f"User {user_id} processing failed: {e}", exc_info=True)
            stats["failed_users"] += 1
            # Continue to next user (isolation)
    
    # Final summary
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info("\n" + "=" * 80)
    logger.info("DAILY ANALYTICS COLLECTION COMPLETED")
    logger.info("=" * 80)
    logger.info(f"Date: {snapshot_date}")
    logger.info(f"Duration: {duration:.2f}s")
    logger.info(f"Users: {stats['successful_users']}/{stats['total_users']} successful")
    logger.info(f"Platforms: {stats['successful_platforms']}/{stats['total_platforms']} successful")
    logger.info(f"Total Metrics Inserted: {stats['total_metrics_inserted']}")
    logger.info("=" * 80)
    
    return stats


# ============================================================================
# CLI ENTRY POINT (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Run analytics collection manually for testing.
    
    Usage:
        python services/analytics_collector.py
    """
    import sys
    
    try:
        stats = collect_daily_analytics()
        
        # Exit with appropriate code
        if stats["failed_users"] > 0 or stats["failed_platforms"] > 0:
            logger.warning("Collection completed with some failures")
            sys.exit(1)
        else:
            logger.info("Collection completed successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"CRITICAL: Collection job failed: {e}", exc_info=True)
        sys.exit(2)
