"""
Orion Analytics Query Tool - FULL ANALYTICS ENGINE

This module contains ALL analytics business logic and execution.

Architecture:
- Emily (emily.py): Collects fields, normalizes payload, asks clarifying questions
- Orion (this file): Executes all analytics logic, applies defaults, formats responses

Orion Responsibilities:
1. Default metric assignment (insight mode)
2. Default platform inference (connected platforms, last post platform)
3. Multi-platform processing
4. Improvement generation
5. Insight computation
6. Watch time special handling
7. Blog analytics processing
8. Date range integration
9. Response formatting
10. Graceful error handling

Emily passes a clean AnalyticsPayload to Orion.
Orion returns formatted responses ready for display.

This module reuses functions from morning_scheduled_message.py to avoid code duplication.
"""

import os
import logging
import requests
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, date
from schemas.analytics import AnalyticsState
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Platform-specific post-level metrics (SOURCE OF TRUTH for execution)
# Must match Emily's PLATFORM_POST_METRICS exactly
PLATFORM_POST_METRICS = {
    "instagram": [
        "likes",
        "comments",
        "shares",
        "saves",
        "views",
        "engagement"
    ],
    "facebook": [
        "likes",
        "comments",
        "shares",
        "engagement"
    ],
    "youtube": [
        "views",
        "likes",
        "comments",
        "average_watch_time",
        "watch_time"
    ],
    "linkedin": [
        "likes",
        "comments",
        "shares",
        "impressions",
        "engagement"
    ],
    "twitter": [
        "likes",
        "comments",
        "shares",
        "views"
    ],
    "pinterest": [
        "saves",
        "views",
        "engagement"
    ]
}

# PHASE 8: Trend Memory - Derived from analytics_snapshots (NO in-memory storage)
def get_trend_memory(user_id: str, platform: str, metric: str, days_back: int = 14) -> Optional[Dict[str, Any]]:
    """
    PHASE 8: Get trend memory by querying analytics_snapshots.
    
    Instead of storing trends in memory, we derive them from historical data.
    Compares last 7 days vs previous 7 days to determine trend.
    
    Args:
        user_id: User ID
        platform: Platform name
        metric: Metric name (e.g., "likes", "comments")
        days_back: How many days back to look (default: 14 for 7-day comparison)
    
    Returns:
        Dict with trend info: {"trend": "up"/"down"/"stable", "percent_change": float}
        or None if insufficient data
    """
    try:
        if not supabase:
            return None
        
        # Get date range for comparison (last 7 days vs previous 7 days)
        today = date.today()
        current_end = today.isoformat()
        current_start = (today - timedelta(days=6)).isoformat()  # Last 7 days
        prev_end = (today - timedelta(days=7)).isoformat()
        prev_start = (today - timedelta(days=13)).isoformat()  # Previous 7 days
        
        # Fetch current period data
        current_cached = get_cached_metrics(
            user_id, platform.lower(), "social_media", [metric], current_start, current_end
        )
        
        # Fetch previous period data
        prev_cached = get_cached_metrics(
            user_id, platform.lower(), "social_media", [metric], prev_start, prev_end
        )
        
        if not current_cached or not prev_cached:
            logger.debug(f"📊 Trend memory: Insufficient data for {platform}/{metric}")
            return None
        
        # Aggregate both periods
        current_agg = aggregate_metrics_by_date_range(current_cached, current_start, current_end, "sum")
        prev_agg = aggregate_metrics_by_date_range(prev_cached, prev_start, prev_end, "sum")
        
        if not current_agg or not prev_agg:
            return None
        
        # Calculate change
        current_value = current_agg.get(metric, 0)
        prev_value = prev_agg.get(metric, 0)
        
        if prev_value == 0:
            return None
        
        percent_change = ((current_value - prev_value) / prev_value) * 100
        
        # Determine trend
        if percent_change > 5:
            trend = "up"
        elif percent_change < -5:
            trend = "down"
        else:
            trend = "stable"
        
        logger.debug(f"📊 Trend memory derived: {platform}/{metric} = {trend} ({percent_change:.1f}%)")
        
        return {
            "trend": trend,
            "percent_change": percent_change,
            "current_value": current_value,
            "prev_value": prev_value,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error deriving trend memory: {e}", exc_info=True)
        return None

# Initialize Supabase client (reuse existing pattern)
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Import reusable functions from morning_scheduled_message.py
try:
    from agents.morning_scheduled_message import (
        decrypt_token,
        fetch_latest_post_metrics,
        fetch_platform_follower_count
    )
    logger.info("✅ Successfully imported functions from morning_scheduled_message.py")
except ImportError as e:
    logger.error(f"❌ Failed to import from morning_scheduled_message.py: {e}")
    # Fallback decrypt_token if import fails
    def decrypt_token(encrypted_token: str) -> str:
        """Fallback decrypt token - should not be used if import succeeds"""
        from cryptography.fernet import Fernet
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key or not encrypted_token:
            return encrypted_token or ""
        try:
            cipher_suite = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            return cipher_suite.decrypt(encrypted_token.encode()).decode()
        except Exception:
            return encrypted_token


def execute_analytics_query(state: AnalyticsState, user_id: str = None) -> Dict[str, Any]:
    """
    Execute analytics query - FULL ANALYTICS ENGINE.
    
    Architecture:
    - Pure Execution: No clarifying questions, no assumption of intent.
    - Validated State: Accepts strictly typed AnalyticsState.
    - Structured Output: Returns Dict only, no text formatting.
    """
    try:
        # Use user_id from state if not provided
        uid = user_id or state.user_id
        
        # CRITICAL: Expand "all metrics" to platform-specific metrics for post-level insights
        if state.analytics_level == "post" and state.intent == "insight":
            if state.metrics == ["all"]:
                # Expand "all" to platform-specific metrics
                expanded_metrics = []
                platforms = state.platforms if isinstance(state.platforms, list) else [state.platforms] if state.platforms else []
                
                for platform in platforms:
                    platform_normalized = platform.lower() if platform else ""
                    if platform_normalized in PLATFORM_POST_METRICS:
                        expanded_metrics.extend(PLATFORM_POST_METRICS[platform_normalized])
                
                if expanded_metrics:
                    state.metrics = list(set(expanded_metrics))  # Remove duplicates
                    logger.info(f"Expanded 'all metrics' to platform-specific: {state.metrics}")
                else:
                    return {
                        "success": False,
                        "error": "Post-level insights are not available for the selected platform(s)."
                    }
        
        # CRITICAL: Metrics are ALWAYS required (both analytics and insight)
        # Emily should have already asked for metrics before reaching Orion
        # If metrics are empty here, it's an error condition
        if not state.metrics or len(state.metrics) == 0:
            return {
                "success": False,
                "error": "Metrics are required. Please specify which metrics you want to analyze."
            }

        # Route to appropriate handler
        if state.source == "social_media":
            return _handle_social_media_analytics(state, uid)
        elif state.source == "blog":
            return _handle_blog_analytics(state, uid)
        else:
            return {
                "success": False,
                "error": f"Unsupported source: {state.source}"
            }

    except Exception as e:
        logger.error("Error in execute_analytics_query", exc_info=True)
        return {
            "success": False,
            "error": f"I couldn't complete your analytics request due to a technical issue ({str(e)}). Please try again or check your connections."
        }


# -------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------




def _is_post_level_metrics(metrics: List[str]) -> bool:
    """Check if metrics are post-level (likes, comments, shares)."""
    post_level_metrics = ["likes", "comments", "shares", "like", "comment", "share"]
    return any(m.lower() in post_level_metrics for m in metrics)


def _transform_post_metrics(post_metrics: Dict[str, Any], requested_metrics: List[str]) -> Dict[str, Any]:
    """Transform post metrics from API format (likes_count) to user format (likes)."""
    result = {}
    
    if "likes" in requested_metrics or "like" in [m.lower() for m in requested_metrics]:
        result["likes"] = post_metrics.get("likes_count", 0) or 0
    
    if "comments" in requested_metrics or "comment" in [m.lower() for m in requested_metrics]:
        result["comments"] = post_metrics.get("comments_count", 0) or 0
    
    if "shares" in requested_metrics or "share" in [m.lower() for m in requested_metrics]:
        result["shares"] = post_metrics.get("shares_count", 0) or 0
    
    return result


def _calculate_period(date_range: Optional[str]) -> str:
    """Calculate API period from date_range string."""
    if not date_range:
        return "day"
    
    date_lower = date_range.lower()
    if "month" in date_lower or "30" in date_range:
        return "days_28"
    elif "week" in date_lower or "7" in date_range:
        return "week"
    else:
        return "day"


def _route_to_platform_fetcher(platform: str, connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None, analytics_level: str = "account") -> Optional[Dict[str, Any]]:
    """
    Route to platform-specific fetcher based on platform name.
    
    Args:
        platform: Platform name
        connection: Connection data
        metrics: List of metrics to fetch
        date_range: Optional date range
        analytics_level: "account" or "post" - determines which fetcher to use
    """
    platform_lower = platform.lower()
    
    # CRITICAL: Respect analytics_level - don't auto-switch based on metric names
    # If analytics_level is "account", always use account-level fetchers
    # If analytics_level is "post", use post-level fetchers (handled separately)
    
    if platform_lower == "instagram":
        return fetch_instagram_insights(connection, metrics, date_range, analytics_level)
    elif platform_lower == "facebook":
        return fetch_facebook_insights(connection, metrics, date_range, analytics_level)
    elif platform_lower == "youtube":
        return fetch_youtube_insights(connection, metrics, date_range)
    elif platform_lower == "linkedin":
        return fetch_linkedin_insights(connection, metrics, date_range)
    elif platform_lower in ["twitter", "x"]:
        return fetch_twitter_insights(connection, metrics, date_range)
    else:
        logger.warning(f"Unsupported platform: {platform}")
        return None





def _handle_social_media_analytics(state: AnalyticsState, user_id: str) -> Dict[str, Any]:
    """
    Handle social media analytics using AnalyticsState.
    """
    # CRITICAL: Check analytics_level (already in state)
    analytics_level = state.analytics_level
    
    if analytics_level == "post":
        # POST-LEVEL: Fetch and rank individual posts
        logger.info(f"🎯 POST-LEVEL analytics requested")
        return _handle_post_level_analytics(state, user_id)
    else:
        # ACCOUNT-LEVEL: Aggregated metrics
        logger.info(f"📊 ACCOUNT-LEVEL analytics requested")
        return _handle_account_analytics(state, user_id)


def _handle_post_level_analytics(state: AnalyticsState, user_id: str) -> Dict[str, Any]:
    """
    Handle POST-LEVEL analytics: Route based on post_selector (deterministic).
    """
    try:
        selector = state.post_selector
        
        # Route based on post_selector (STRICT ROUTING - NO DEFAULT RANKING)
        if selector == "latest":
            return _handle_latest_post_insight(state, user_id)
        elif selector == "top":
            return _handle_top_posts(state, user_id)
        elif selector == "recent_n":
            return _handle_recent_n_posts(state, user_id)
        elif selector == "specific_id":
            return _handle_specific_post(state, user_id)
        else:
            # Fallback: If no selector specified, default to latest (most common case)
            logger.warning(f"⚠️ No post_selector specified, defaulting to 'latest'")
            return _handle_latest_post_insight(state, user_id)
        
    except Exception as e:
        logger.error(f"Error in _handle_post_level_analytics: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"I couldn't fetch post data due to an error ({str(e)})."
        }





def _handle_latest_post_insight(state: AnalyticsState, user_id: str) -> Dict[str, Any]:
    """
    Handle LATEST POST insight: Fetch most recent post only (NO RANKING).
    """
    try:
        platforms = state.platforms
        metrics = state.metrics or ["likes", "comments", "engagement"]
        
        if not platforms:
            return {"success": False, "error": "No platforms specified."}
        
        platform = platforms[0] if isinstance(platforms, list) else platforms
        platform_str = str(platform).strip().lower()
        
        # Get platform connection
        connection = get_platform_connection(user_id, platform_str)
        if not connection:
            return {"success": False, "error": f"No connection found for {platform_str}."}
        
        # Fetch latest post only (limit=1, NO SORTING)
        posts = None
        if platform_str == "instagram":
            posts = fetch_instagram_posts(connection, metrics, limit=1)
        elif platform_str == "facebook":
            posts = fetch_facebook_posts(connection, metrics, limit=1)
        else:
            return {"success": False, "error": f"Platform {platform_str} not supported for latest post."}
        
        if not posts or len(posts) == 0:
            return {"success": False, "error": "No posts found."}
        
        # Return latest post with metrics (numbers first)
        latest_post = posts[0]
        post_metrics = {}
        for metric in metrics:
            if metric in latest_post:
                post_metrics[metric] = latest_post[metric]
            elif metric == "engagement":
                # Calculate engagement if not present
                post_metrics["engagement"] = (latest_post.get("likes", 0) or 0) + (latest_post.get("comments", 0) or 0)
        
        return {
            "success": True,
            "type": "latest_post",
            "data": {
                platform_str: {
                    "post_id": latest_post.get("post_id"),
                    "caption": latest_post.get("caption", "")[:100] if latest_post.get("caption") else "",
                    "permalink": latest_post.get("permalink", ""),
                    "timestamp": latest_post.get("timestamp", ""),
                    "metrics": post_metrics  # Numbers first
                }
            },
            "confidence": "LOW",
            "note": "Live snapshot of most recent post"
        }
        
    except Exception as e:
        logger.error(f"Error in _handle_latest_post_insight: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _handle_top_posts(state: AnalyticsState, user_id: str) -> Dict[str, Any]:
    """
    Handle TOP POSTS: Explicit ranking by metrics (ONLY when explicitly requested).
    """
    try:
        metrics = state.metrics or ["likes", "comments", "engagement"]
        top_n = state.top_n or 5
        sort_order = state.sort_order or "desc"
        platforms = state.platforms
        
        logger.info(f"🔍 Top Posts Analysis for {platforms}, top_n={top_n}, sort={sort_order}")
        
        if not platforms:
            return {"success": False, "error": "No platforms specified for post analysis."}
        
        # Determine primary metric for sorting
        primary_metric = metrics[0] if metrics else "engagement"
        logger.info(f"🎯 Sorting posts by: {primary_metric} (order: {sort_order})")
        
        all_ranked_posts = {}
        platforms_with_data = []
        platforms_without_data = []
        
        for platform in platforms:
            platform_str = str(platform).strip().lower()
            if not platform_str:
                continue
            
            # Get platform connection
            connection = get_platform_connection(user_id, platform_str)
            if not connection:
                platforms_without_data.append(platform_str)
                logger.warning(f"❌ No connection for {platform_str}")
                continue
            
            # Fetch posts based on platform
            posts = None
            if platform_str == "instagram":
                posts = fetch_instagram_posts(connection, metrics, limit=20)
            elif platform_str == "facebook":
                posts = fetch_facebook_posts(connection, metrics, limit=20)
            else:
                logger.warning(f"⚠️ Post-level analytics not yet supported for {platform_str}")
                platforms_without_data.append(platform_str)
                continue
            
            if not posts or len(posts) == 0:
                logger.warning(f"❌ No posts found for {platform_str}")
                platforms_without_data.append(platform_str)
                continue
            
            # Sort posts by primary metric (EXPLICIT RANKING)
            reverse_sort = (sort_order == "desc")
            sorted_posts = sorted(
                posts,
                key=lambda p: p.get(primary_metric, 0),
                reverse=reverse_sort
            )
            
            # Take top N
            top_posts = sorted_posts[:top_n]
            
            all_ranked_posts[platform_str] = {
                "ranked_posts": top_posts,
                "total_posts_analyzed": len(posts),
                "primary_metric": primary_metric,
                "sort_order": sort_order
            }
            platforms_with_data.append(platform_str)
            
            logger.info(f"✅ Ranked {len(top_posts)} posts for {platform_str} (from {len(posts)} total)")
        
        # Handle no data case
        if not all_ranked_posts:
            return {
                "success": False,
                "error": "No posts found with sufficient data to determine ranking."
            }
        
        return {
            "success": True,
            "type": "top_posts",
            "data": all_ranked_posts
        }
        
    except Exception as e:
        logger.error(f"Error in _handle_top_posts: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _handle_recent_n_posts(state: AnalyticsState, user_id: str) -> Dict[str, Any]:
    """
    Handle RECENT N POSTS: Chronological order (NO RANKING, NO SORTING).
    """
    try:
        platforms = state.platforms
        metrics = state.metrics or ["likes", "comments", "engagement"]
        recent_n = state.recent_n or 5
        
        logger.info(f"🔍 Recent {recent_n} Posts Analysis for {platforms}")
        
        if not platforms:
            return {"success": False, "error": "No platforms specified."}
        
        all_posts = {}
        
        for platform in platforms:
            platform_str = str(platform).strip().lower()
            if not platform_str:
                continue
            
            # Get platform connection
            connection = get_platform_connection(user_id, platform_str)
            if not connection:
                logger.warning(f"❌ No connection for {platform_str}")
                continue
            
            # Fetch posts (DO NOT SORT, DO NOT RANK - chronological order)
            posts = None
            if platform_str == "instagram":
                posts = fetch_instagram_posts(connection, metrics, limit=recent_n)
            elif platform_str == "facebook":
                posts = fetch_facebook_posts(connection, metrics, limit=recent_n)
            else:
                logger.warning(f"⚠️ Platform {platform_str} not supported")
                continue
            
            if not posts or len(posts) == 0:
                logger.warning(f"❌ No posts found for {platform_str}")
                continue
            
            # Return posts in chronological order (as fetched, NO SORTING)
            all_posts[platform_str] = {
                "posts": posts[:recent_n],
                "total_posts": len(posts)
            }
        
        if not all_posts:
            return {"success": False, "error": "No posts found."}
        
        return {
            "success": True,
            "type": "recent_n_posts",
            "data": all_posts
        }
        
    except Exception as e:
        logger.error(f"Error in _handle_recent_n_posts: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _handle_specific_post(state: AnalyticsState, user_id: str) -> Dict[str, Any]:
    """
    Handle SPECIFIC POST: Fetch by post_id only.
    """
    try:
        platforms = state.platforms
        metrics = state.metrics or ["likes", "comments", "engagement"]
        post_id = state.post_id
        
        if not post_id:
            return {"success": False, "error": "No post_id specified."}
        
        if not platforms:
            return {"success": False, "error": "No platforms specified."}
        
        platform = platforms[0] if isinstance(platforms, list) else platforms
        platform_str = str(platform).strip().lower()
        
        # Get platform connection
        connection = get_platform_connection(user_id, platform_str)
        if not connection:
            return {"success": False, "error": f"No connection found for {platform_str}."}
        
        # Fetch specific post by ID
        # Note: This requires platform-specific implementation
        # For now, fetch all posts and filter by post_id
        posts = None
        if platform_str == "instagram":
            posts = fetch_instagram_posts(connection, metrics, limit=100)
        elif platform_str == "facebook":
            posts = fetch_facebook_posts(connection, metrics, limit=100)
        else:
            return {"success": False, "error": f"Platform {platform_str} not supported."}
        
        if not posts:
            return {"success": False, "error": "No posts found."}
        
        # Find post by ID
        specific_post = None
        for post in posts:
            if post.get("post_id") == post_id:
                specific_post = post
                break
        
        if not specific_post:
            return {"success": False, "error": f"Post with ID {post_id} not found."}
        
        # Return specific post with metrics (numbers first)
        post_metrics = {}
        for metric in metrics:
            if metric in specific_post:
                post_metrics[metric] = specific_post[metric]
            elif metric == "engagement":
                # Calculate engagement if not present
                post_metrics["engagement"] = (specific_post.get("likes", 0) or 0) + (specific_post.get("comments", 0) or 0)
        
        return {
            "success": True,
            "type": "specific_post",
            "data": {
                platform_str: {
                    "post_id": specific_post.get("post_id"),
                    "caption": specific_post.get("caption", "")[:100] if specific_post.get("caption") else "",
                    "permalink": specific_post.get("permalink", ""),
                    "timestamp": specific_post.get("timestamp", ""),
                    "metrics": post_metrics  # Numbers first
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error in _handle_specific_post: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _handle_account_analytics(state: AnalyticsState, user_id: str) -> Dict[str, Any]:
    """
    Handle ACCOUNT-LEVEL analytics (Aggregated metrics).
    STRICT SEPARATION:
    - Analytics: Use Cache (History, Comparison).
    - Insight: Use Live API (Snapshot, Real-time).
    """
    try:
        platforms = state.platforms
        metrics = state.metrics
        data_by_platform = {}
        
        for platform in platforms:
            p_str = platform.lower()
            
            # --- INSIGHT MODE (LIVE) ---
            if state.intent == "insight":
                logger.info(f"🔴 INSIGHT MODE: Fetching LIVE data for {p_str}")
                connection = get_platform_connection(user_id, p_str)
                if not connection:
                    data_by_platform[p_str] = {"_warning": "Platform not connected."}
                    continue
                    
                # Direct API Call - pass analytics_level to ensure correct fetcher
                live_data = _route_to_platform_fetcher(p_str, connection, metrics, None, state.analytics_level)
                if live_data:
                    data_by_platform[p_str] = live_data
                else:
                     data_by_platform[p_str] = {"_warning": "No live data available."}

            # --- ANALYTICS MODE (HISTORY) ---
            else:
                logger.info(f"📊 ANALYTICS MODE: Fetching CACHED data for {p_str}")
                
                # Determine Date Range
                defaults = "last 7 days"
                date_range = state.date_range or defaults
                parsed = parse_date_range(date_range)
                
                if not parsed:
                    data_by_platform[p_str] = {"_warning": f"Could not parse date range: {date_range}"}
                    continue
                    
                start, end = parsed
                
                # 1. Get Current Period Data
                cached = get_cached_metrics(user_id, p_str, state.source, metrics, start, end)
                
                if not cached:
                    data_by_platform[p_str] = {"_warning": "No historical data tracked yet. Try 'Insight' mode for live data."}
                    continue
                    
                # Aggregate
                aggregated = aggregate_metrics_by_date_range(cached, start, end, "sum")
                platform_result = {"metrics": aggregated}
                
                # 2. Get Previous Period (for Comparison)
                # Simple logic: shift back by (end - start) days
                s_date = datetime.strptime(start, "%Y-%m-%d").date()
                e_date = datetime.strptime(end, "%Y-%m-%d").date()
                days = (e_date - s_date).days + 1
                
                prev_start = (s_date - timedelta(days=days)).isoformat()
                prev_end = (s_date - timedelta(days=1)).isoformat()
                
                prev_cached = get_cached_metrics(user_id, p_str, state.source, metrics, prev_start, prev_end)
                if prev_cached:
                    prev_agg = aggregate_metrics_by_date_range(prev_cached, prev_start, prev_end, "sum")
                    comparison = compare_with_previous_period(aggregated, prev_agg)
                    platform_result["comparison"] = comparison
                
                data_by_platform[p_str] = platform_result

        # Construct Response
        return {
            "success": True,
            "data": data_by_platform
        }

    except Exception as e:
        logger.error(f"Error in _handle_account_analytics: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"I encountered an issue analyzing your account data ({str(e)}). Please check your platform connections."
        }





def _handle_watch_time_insight(user_id: str, metrics: List[str]) -> Dict[str, Any]:
    """Handle special watch time insight request for YouTube videos."""
    
    video_post = fetch_latest_video_post(user_id)
    if not video_post:
        return {
            "success": False,
            "error": "No video post found to calculate average view time."
        }
    
    avg_time = compute_avg_watch_time(video_post)
    quality_assessment = "great" if avg_time > 30 else "good" if avg_time >= 15 else "something to work on"
    
    return {
        "success": True,
        "data": {
            "type": "insight",
            "avg_view_time": avg_time,
            "quality_assessment": quality_assessment,
            "metrics": metrics
        }
    }


def _handle_blog_analytics(state: AnalyticsState, user_id: str) -> Dict[str, Any]:
    """
    Handle blog analytics - EXCLUSIVELY supports live PSI insights.
    No historical trends or comparisons.
    """
    try:
        from agents.tools.blog_performance_insight import get_blog_insight_tool
        import asyncio
        
        # 1. Get Blog URL for user (from latest published post)
        blog_url = _fetch_user_blog_url(user_id)
        
        if not blog_url:
            return {
                "success": False,
                "error": "I couldn't find a published blog URL for your account. Please provide a URL or ensure you have published blogs."
            }
        
        # 2. Call PSI Live Snapshot (Synchronous wrapper for async tool)
        logger.info(f"🚀 Orion: Fetching LIVE PSI insight for blog: {blog_url}")
        
        async def fetch_psi():
            tool = get_blog_insight_tool()
            return await tool.get_live_insight(blog_url)
            
        try:
            # Handle potential event loop issues in various environments
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            blog_data = loop.run_until_complete(fetch_psi())
            loop.close()
        except Exception as loop_err:
            logger.warning(f"Event loop issue: {loop_err}, trying fallback run")
            blog_data = asyncio.run(fetch_psi())
        
        if "error" in blog_data:
            return {
                "success": False,
                "error": f"PageSpeed API Error: {blog_data['error']}"
            }
        
        # 3. Return structured insight data only
        # Emily will format this via _format_blog_insight_response
        return {
            "success": True,
            "data": {
                "blog": blog_data
            }
        }
            
    except Exception as e:
        logger.error(f"Error in blog analytics execution: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"I couldn't complete the performance check ({str(e)})."
        }

def _fetch_user_blog_url(user_id: str) -> Optional[str]:
    """Fetch the latest published blog URL for the user from blog_posts table."""
    try:
        if not supabase:
            logger.warning("Supabase client not initialized in Orion")
            return None
            
        logger.info(f"Fetching latest published blog URL for user {user_id}")
        
        # Query blog_posts for the latest published URL
        response = supabase.table("blog_posts") \
            .select("blog_url") \
            .eq("author_id", user_id) \
            .eq("status", "published") \
            .not_.is_("blog_url", "null") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
            
        if response.data and len(response.data) > 0:
            url = response.data[0].get("blog_url")
            logger.info(f"Found blog URL: {url}")
            return url
            
        logger.info(f"No published blog URL found for user {user_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching user blog URL: {e}")
        return None



# -------------------------------------------------------------
# DATE RANGE PARSING (Phase 3 - Natural language time range normalization)
# -------------------------------------------------------------

def parse_date_range(date_range_str: Optional[str]) -> Optional[Tuple[str, str]]:
    """
    Parse natural language date range into start_date and end_date.
    
    Supports:
    - English: "last 7 days", "last week", "last month", "this month", "today", "yesterday"
    - Hindi: "pichle 7 din", "pichle hafta", "pichle mahina", "aaj", "kal"
    
    Args:
        date_range_str: Natural language date range string
    
    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format, or None if invalid
    """
    if not date_range_str:
        return None
    
    try:
        today = date.today()
        date_lower = date_range_str.lower().strip()
        
        # English patterns
        if date_lower in ["today", "aaj"]:
            return (today.isoformat(), today.isoformat())
        
        if date_lower in ["yesterday", "kal"]:
            yesterday = today - timedelta(days=1)
            return (yesterday.isoformat(), yesterday.isoformat())
        
        # Last N days (English and Hindi)
        import re
        days_match = re.search(r'(last|pichle)\s*(\d+)\s*(days?|din)', date_lower)
        if days_match:
            days = int(days_match.group(2))
            end_date = today
            start_date = today - timedelta(days=days - 1)  # Include today
            return (start_date.isoformat(), end_date.isoformat())
        
        # Last week / pichle hafta
        if "last week" in date_lower or "pichle hafta" in date_lower or "pichle hafte" in date_lower:
            end_date = today
            start_date = today - timedelta(days=6)  # Last 7 days including today
            return (start_date.isoformat(), end_date.isoformat())
        
        # Last month / pichle mahina
        if "last month" in date_lower or "pichle mahina" in date_lower or "pichle mahine" in date_lower:
            end_date = today
            start_date = today - timedelta(days=29)  # Last 30 days
            return (start_date.isoformat(), end_date.isoformat())
        
        # This month / is mahina
        if "this month" in date_lower or "is mahina" in date_lower:
            start_date = date(today.year, today.month, 1)
            end_date = today
            return (start_date.isoformat(), end_date.isoformat())
        
        # Last 30 days (explicit)
        if "30" in date_range_str and ("day" in date_lower or "din" in date_lower):
            end_date = today
            start_date = today - timedelta(days=29)
            return (start_date.isoformat(), end_date.isoformat())
        
        # Default: try to parse as "last N days" where N is any number
        default_days_match = re.search(r'(\d+)', date_range_str)
        if default_days_match:
            days = int(default_days_match.group(1))
            if days <= 365:  # Reasonable limit
                end_date = today
                start_date = today - timedelta(days=days - 1)
                return (start_date.isoformat(), end_date.isoformat())
        
        logger.warning(f"⚠️ Could not parse date range: {date_range_str}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error parsing date range '{date_range_str}': {e}", exc_info=True)
        return None


def should_use_cache(date_range_str: Optional[str]) -> bool:
    """
    Determine if cache should be used based on date range.
    
    Rules:
    - Cache for date ranges <= 30 days
    - API-only for date ranges > 30 days
    
    Args:
        date_range_str: Natural language date range string
    
    Returns:
        True if cache should be used, False for API-only
    """
    if not date_range_str:
        return True  # Default to cache for no date range
    
    parsed = parse_date_range(date_range_str)
    if not parsed:
        return True  # Default to cache if parsing fails
    
    start_date, end_date = parsed
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    days_diff = (end_dt - start_dt).days + 1
    
    return days_diff <= 30


# -------------------------------------------------------------
# ANALYTICS CACHE FUNCTIONS (Phase 2 - Cache-first strategy)
# -------------------------------------------------------------

def get_cached_metrics(
    user_id: str,
    platform: str,
    source: str,
    metrics: List[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get cached metrics from analytics_snapshots table.
    
    Args:
        user_id: User ID
        platform: Platform name
        source: 'social_media' or 'blog'
        metrics: List of metrics to fetch
        start_date: Start date (YYYY-MM-DD format)
        end_date: End date (YYYY-MM-DD format)
    
    Returns:
        Dict with cached metrics or None if insufficient cache
    """
    try:
        # STEP 1: Validate Supabase client
        if not supabase:
            logger.error("❌ SUPABASE FETCH FAILED: Supabase client not initialized")
            logger.error("   → Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
            return None
        
        # STEP 2: Validate date range
        if not start_date or not end_date:
            logger.error("❌ SUPABASE FETCH FAILED: No date range provided")
            logger.error(f"   → start_date={start_date}, end_date={end_date}")
            return None
        
        # STEP 3: Log query details
        logger.info("=" * 80)
        logger.info("🔍 SUPABASE CACHE QUERY - STARTING")
        logger.info("=" * 80)
        logger.info(f"📋 Query Parameters:")
        logger.info(f"   • user_id: {user_id}")
        logger.info(f"   • platform: {platform} → {platform.lower()} (lowercase)")
        logger.info(f"   • source: {source}")
        logger.info(f"   • metrics: {metrics}")
        logger.info(f"   • date_range: {start_date} to {end_date}")
        
        # STEP 4: Check if user has ANY data in analytics_snapshots
        logger.info(f"\n🔍 Step 1: Checking if user has ANY analytics data...")
        user_check = supabase.table("analytics_snapshots").select("id").eq("user_id", user_id).limit(1).execute()
        
        if not user_check.data or len(user_check.data) == 0:
            logger.error("❌ SUPABASE FETCH FAILED: User has NO data in analytics_snapshots")
            logger.error(f"   → user_id: {user_id}")
            logger.error(f"   → Reason: No records found for this user_id in database")
            logger.error(f"   → Solution: Insert test data using quick_insert_analytics.py")
            logger.info("=" * 80)
            return None
        
        logger.info(f"   ✅ User has data in analytics_snapshots")
        
        # STEP 5: Check if platform has data for this user
        logger.info(f"\n🔍 Step 2: Checking if platform '{platform}' has data...")
        platform_check = supabase.table("analytics_snapshots").select("id").eq(
            "user_id", user_id
        ).eq("platform", platform.lower()).limit(1).execute()
        
        if not platform_check.data or len(platform_check.data) == 0:
            logger.error(f"❌ SUPABASE FETCH FAILED: No data for platform '{platform}'")
            logger.error(f"   → user_id: {user_id}")
            logger.error(f"   → platform: {platform} (searching as: {platform.lower()})")
            logger.error(f"   → Reason: User has data, but not for this platform")
            
            # Show what platforms ARE available
            all_platforms = supabase.table("analytics_snapshots").select("platform").eq("user_id", user_id).execute()
            if all_platforms.data:
                unique_platforms = list(set(row['platform'] for row in all_platforms.data))
                logger.error(f"   → Available platforms for this user: {unique_platforms}")
            logger.error(f"   → Solution: Insert data for '{platform}' or check platform name spelling")
            logger.info("=" * 80)
            return None
        
        logger.info(f"   ✅ Platform '{platform}' has data")
        
        # STEP 6: Execute main query
        logger.info(f"\n🔍 Step 3: Executing main query for date range...")
        logger.info(f"   SQL equivalent:")
        logger.info(f"   SELECT * FROM analytics_snapshots")
        logger.info(f"   WHERE user_id = '{user_id}'")
        logger.info(f"     AND platform = '{platform.lower()}'")
        logger.info(f"     AND source = '{source}'")
        logger.info(f"     AND metric IN {metrics}")
        logger.info(f"     AND date >= '{start_date}'")
        logger.info(f"     AND date <= '{end_date}'")
        logger.info(f"   ORDER BY date ASC")
        
        query = supabase.table("analytics_snapshots").select("*").eq(
            "user_id", user_id
        ).eq("platform", platform.lower()).eq("source", source).in_(
            "metric", metrics
        ).gte("date", start_date).lte("date", end_date).order("date", desc=False)
        
        result = query.execute()
        
        # STEP 7: Check results
        if not result.data or len(result.data) == 0:
            logger.error("❌ SUPABASE FETCH FAILED: Query returned 0 rows")
            logger.error(f"   → user_id: {user_id}")
            logger.error(f"   → platform: {platform.lower()}")
            logger.error(f"   → source: {source}")
            logger.error(f"   → metrics: {metrics}")
            logger.error(f"   → date_range: {start_date} to {end_date}")
            logger.error(f"   → Reason: No data in this specific date range")
            
            # Check what date range IS available
            logger.info(f"\n🔍 Checking what dates ARE available for this platform...")
            date_check = supabase.table("analytics_snapshots").select("date").eq(
                "user_id", user_id
            ).eq("platform", platform.lower()).order("date", desc=False).execute()
            
            if date_check.data:
                dates = [row['date'] for row in date_check.data]
                min_date = min(dates)
                max_date = max(dates)
                logger.error(f"   → Available date range: {min_date} to {max_date}")
                logger.error(f"   → Requested range: {start_date} to {end_date}")
                logger.error(f"   → Solution: Request dates within available range")
            else:
                logger.error(f"   → No dates found (this shouldn't happen if platform check passed)")
            
            logger.info("=" * 80)
            return None
        
        logger.info(f"\n✅ SUCCESS: Query returned {len(result.data)} rows")
        logger.info(f"   Sample data:")
        for row in result.data[:3]:
            logger.info(f"      {row['date']} | {row['metric']} = {row['value']}")
        if len(result.data) > 3:
            logger.info(f"      ... and {len(result.data) - 3} more rows")
        
        # Group by metric and date
        cached_data = {}
        for row in result.data:
            metric = row.get("metric")
            date = row.get("date")
            value = row.get("value", 0)
            
            if metric not in cached_data:
                cached_data[metric] = {}
            cached_data[metric][date] = value
        
        # STEP 8: Check data coverage (at least 50% required)
        logger.info(f"\n🔍 Step 4: Checking data coverage...")
        total_days = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days + 1
        min_required_days = max(1, int(total_days * 0.5))  # At least 50% coverage
        
        logger.info(f"   • Date range: {total_days} days ({start_date} to {end_date})")
        logger.info(f"   • Minimum required: {min_required_days} days (50% coverage)")
        logger.info(f"   • Requested metrics: {metrics}")
        
        sufficient_data = True
        coverage_details = {}
        
        for metric in metrics:
            if metric not in cached_data:
                sufficient_data = False
                coverage_details[metric] = {"days": 0, "coverage": 0}
                logger.error(f"   ❌ {metric}: NO DATA (0/{total_days} days = 0%)")
                break
            
            metric_days = len(cached_data[metric])
            coverage_pct = (metric_days / total_days) * 100
            coverage_details[metric] = {"days": metric_days, "coverage": coverage_pct}
            
            if metric_days < min_required_days:
                sufficient_data = False
                logger.error(f"   ❌ {metric}: INSUFFICIENT ({metric_days}/{total_days} days = {coverage_pct:.1f}% < 50%)")
                break
            else:
                logger.info(f"   ✅ {metric}: SUFFICIENT ({metric_days}/{total_days} days = {coverage_pct:.1f}%)")
        
        if not sufficient_data:
            logger.error("\n❌ SUPABASE FETCH FAILED: Insufficient data coverage")
            logger.error(f"   → Required: At least {min_required_days} days of data (50% coverage)")
            logger.error(f"   → Coverage details:")
            for metric, details in coverage_details.items():
                logger.error(f"      • {metric}: {details['days']}/{total_days} days ({details['coverage']:.1f}%)")
            logger.error(f"   → Solution: Insert more data or request a shorter date range")
            logger.info("=" * 80)
            return None
        
        logger.info(f"\n✅ Data coverage is sufficient for all metrics")
        
        if sufficient_data:
            logger.info(f"\n" + "=" * 80)
            logger.info(f"✅ SUPABASE FETCH SUCCESS")
            logger.info(f"=" * 80)
            logger.info(f"   • Platform: {platform}")
            logger.info(f"   • Metrics: {metrics}")
            logger.info(f"   • Date range: {start_date} to {end_date} ({total_days} days)")
            logger.info(f"   • Total rows: {len(result.data)}")
            logger.info(f"   • Cache quality: Excellent (>50% coverage for all metrics)")
            
            # Show aggregated totals
            for metric, dates in cached_data.items():
                total_value = sum(dates.values())
                logger.info(f"   • {metric}: {total_value:,.0f} (aggregated)")
            
            logger.info(f"=" * 80)
            return cached_data
        else:
            # This shouldn't happen as we already checked above
            logger.info(f"📭 Cache insufficient: Partial data found but not enough")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error fetching cached metrics: {e}", exc_info=True)
        return None


def save_metrics_snapshot(
    user_id: str,
    platform: str,
    source: str,
    metrics_data: Dict[str, Any],
    snapshot_date: Optional[str] = None,
    post_id: Optional[str] = None
) -> bool:
    """
    Save metrics snapshot to analytics_snapshots table.
    
    Args:
        user_id: User ID
        platform: Platform name
        source: 'social_media' or 'blog'
        metrics_data: Dict of {metric: value} or {metric: {date: value}}
        snapshot_date: Date for snapshot (YYYY-MM-DD), defaults to today
        post_id: Optional post ID for post-level metrics
    
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        if not supabase:
            logger.warning("Supabase client not initialized for saving snapshot")
            return False
        
        if not snapshot_date:
            from datetime import date
            snapshot_date = date.today().isoformat()
        
        saved_count = 0
        errors = []
        
        # Handle both formats: {metric: value} and {metric: {date: value}}
        for metric, value_or_dict in metrics_data.items():
            if isinstance(value_or_dict, dict):
                # Multiple dates: {date: value}
                for date_str, value in value_or_dict.items():
                    try:
                        result = supabase.table("analytics_snapshots").upsert({
                            "user_id": user_id,
                            "platform": platform.lower(),
                            "source": source,
                            "metric": metric,
                            "value": float(value) if value is not None else 0,
                            "date": date_str,
                            "post_id": post_id,
                            "metadata": {}
                        }, on_conflict="user_id,platform,source,metric,date,post_id").execute()
                        
                        if result.data:
                            saved_count += 1
                    except Exception as e:
                        errors.append(f"{metric}@{date_str}: {str(e)}")
            else:
                # Single value
                try:
                    result = supabase.table("analytics_snapshots").upsert({
                        "user_id": user_id,
                        "platform": platform.lower(),
                        "source": source,
                        "metric": metric,
                        "value": float(value_or_dict) if value_or_dict is not None else 0,
                        "date": snapshot_date,
                        "post_id": post_id,
                        "metadata": {}
                    }, on_conflict="user_id,platform,source,metric,date,post_id").execute()
                    
                    if result.data:
                        saved_count += 1
                except Exception as e:
                    errors.append(f"{metric}: {str(e)}")
        
        if saved_count > 0:
            logger.info(f"✅ Saved {saved_count} metric snapshot(s) for {platform}")
            if errors:
                logger.warning(f"⚠️ Some snapshots failed to save: {errors}")
            return True
        else:
            logger.warning(f"⚠️ No snapshots saved for {platform}")
            if errors:
                logger.error(f"❌ Errors: {errors}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error saving metrics snapshot: {e}", exc_info=True)
        return False


def aggregate_metrics_by_date_range(
    cached_data: Dict[str, Dict[str, float]],
    start_date: str,
    end_date: str,
    aggregation_type: str = "sum",
    metric_semantic: Optional[Dict[str, str]] = None
) -> Dict[str, float]:
    """
    PHASE 2: Aggregate cached metrics by date range with semantic awareness.
    
    Args:
        cached_data: Dict of {metric: {date: value}}
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        aggregation_type: 'sum', 'avg', 'max', 'min'
        metric_semantic: Optional dict of {metric: "delta" | "snapshot"}
    
    Returns:
        Dict of {metric: aggregated_value}
    """
    try:
        aggregated = {}
        metric_semantic = metric_semantic or {}
        
        for metric, date_values in cached_data.items():
            semantic = metric_semantic.get(metric, "snapshot")  # Default to snapshot
            
            # PHASE 2: For snapshot, use latest value; for delta, sum daily gains
            if semantic == "snapshot":
                # Use latest available value (cumulative total)
                sorted_dates = sorted(date_values.keys(), reverse=True)
                if sorted_dates:
                    aggregated[metric] = float(date_values.get(sorted_dates[0], 0))
                else:
                    aggregated[metric] = 0
            else:
                # Delta: sum all daily values (new gains)
                values = []
                current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                
                while current_date <= end_dt:
                    date_str = current_date.isoformat()
                    value = date_values.get(date_str, 0)
                    values.append(float(value))
                    current_date += timedelta(days=1)
                
                if not values:
                    aggregated[metric] = 0
                    continue
                
                if aggregation_type == "sum":
                    aggregated[metric] = sum(values)
                elif aggregation_type == "avg":
                    aggregated[metric] = sum(values) / len(values) if values else 0
                elif aggregation_type == "max":
                    aggregated[metric] = max(values)
                elif aggregation_type == "min":
                    aggregated[metric] = min(values)
                else:
                    aggregated[metric] = sum(values)  # Default to sum
        
        return aggregated
        
    except Exception as e:
        logger.error(f"❌ Error aggregating metrics: {e}", exc_info=True)
        return {}


def get_day_wise_breakdown(
    cached_data: Dict[str, Dict[str, float]],
    start_date: str,
    end_date: str
) -> Dict[str, List[Dict[str, Any]]]:
    """
    PHASE 5: Get day-wise breakdown of metrics.
    
    Args:
        cached_data: Dict of {metric: {date: value}}
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        Dict of {metric: [{"date": "YYYY-MM-DD", "value": float}, ...]}
    """
    try:
        breakdown = {}
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        for metric, date_values in cached_data.items():
            daily_values = []
            current_date = start_dt
            
            while current_date <= end_dt:
                date_str = current_date.isoformat()
                value = float(date_values.get(date_str, 0))
                daily_values.append({
                    "date": date_str,
                    "value": value
                })
                current_date += timedelta(days=1)
            
            breakdown[metric] = daily_values
        
        return breakdown
        
    except Exception as e:
        logger.error(f"❌ Error getting day-wise breakdown: {e}", exc_info=True)
        return {}


def compare_with_previous_period(
    current_data: Dict[str, float],
    previous_data: Dict[str, float]
) -> Dict[str, Dict[str, Any]]:
    """
    PHASE 5: Compare current period metrics with previous period.
    
    Args:
        current_data: Dict of {metric: value} for current period
        previous_data: Dict of {metric: value} for previous period
    
    Returns:
        Dict of {metric: {"current": float, "previous": float, "delta": float, "percent_change": float}}
    """
    try:
        comparison = {}
        
        for metric, current_value in current_data.items():
            previous_value = previous_data.get(metric, 0)
            delta = current_value - previous_value
            
            if previous_value > 0:
                percent_change = (delta / previous_value) * 100
            elif current_value > 0:
                percent_change = 100.0  # New metric
            else:
                percent_change = 0.0
            
            comparison[metric] = {
                "current": current_value,
                "previous": previous_value,
                "delta": delta,
                "percent_change": round(percent_change, 2),
                "trend": "up" if delta > 0 else "down" if delta < 0 else "stable"
            }
        
        return comparison
        
    except Exception as e:
        logger.error(f"❌ Error comparing periods: {e}", exc_info=True)
        return {}


def compute_cache_quality_score(
    cached_data: Dict[str, Dict[str, float]],
    start_date: str,
    end_date: str,
    metrics: List[str]
) -> float:
    """
    PHASE 4: Compute cache quality score (0.0 to 1.0).
    
    Args:
        cached_data: Dict of {metric: {date: value}}
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        metrics: List of requested metrics
    
    Returns:
        Cache quality score (0.0 to 1.0)
    """
    try:
        if not cached_data or not metrics:
            return 0.0
        
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        total_days = (end_dt - start_dt).days + 1
        
        if total_days == 0:
            return 0.0
        
        total_coverage = 0.0
        for metric in metrics:
            if metric in cached_data:
                metric_days = len(cached_data[metric])
                metric_coverage = metric_days / total_days if total_days > 0 else 0.0
                total_coverage += metric_coverage
        
        avg_coverage = total_coverage / len(metrics) if metrics else 0.0
        logger.info(f"📊 cache_quality_computed: {avg_coverage:.2%} coverage for {len(metrics)} metrics")
        return avg_coverage
        
    except Exception as e:
        logger.error(f"❌ Error computing cache quality: {e}", exc_info=True)
        return 0.0


def compute_insight_confidence(
    cached_data: Optional[Dict[str, Dict[str, float]]],
    start_date: Optional[str],
    end_date: Optional[str],
    metrics: List[str],
    is_api_fetch: bool = False
) -> Tuple[str, str]:
    """
    PHASE 1: Compute insight confidence score and reasoning.
    
    Args:
        cached_data: Cached metrics data or None
        start_date: Start date (YYYY-MM-DD) or None
        end_date: End date (YYYY-MM-DD) or None
        metrics: List of requested metrics
        is_api_fetch: Whether data came from API (not cache)
    
    Returns:
        Tuple of (confidence_level, confidence_reasoning)
        confidence_level: "HIGH", "MEDIUM", "LOW"
        confidence_reasoning: Human-readable explanation
    """
    try:
        # Default to LOW if no data
        if not cached_data or not start_date or not end_date:
            if is_api_fetch:
                confidence = "LOW"
                reasoning = "based on limited recent data"
            else:
                confidence = "LOW"
                reasoning = "based on sparse data"
            logger.info(f"📊 insight_confidence_computed: {confidence} - {reasoning}")
            return confidence, reasoning
        
        # Calculate data points
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        total_days = (end_dt - start_dt).days + 1
        
        # Compute cache quality
        cache_quality = compute_cache_quality_score(cached_data, start_date, end_date, metrics)
        
        # Check metric coverage
        metrics_with_data = sum(1 for m in metrics if m in cached_data and len(cached_data[m]) > 0)
        metric_coverage = metrics_with_data / len(metrics) if metrics else 0.0
        
        # Determine confidence
        if cache_quality >= 0.7 and total_days >= 7 and metric_coverage >= 1.0 and not is_api_fetch:
            confidence = "HIGH"
            reasoning = "based on comprehensive recent data"
        elif cache_quality >= 0.4 and total_days >= 3 and metric_coverage >= 0.6:
            confidence = "MEDIUM"
            if cache_quality < 0.7:
                reasoning = "based on partial recent data"
            elif total_days < 7:
                reasoning = "based on limited recent data"
            else:
                reasoning = "based on moderate data coverage"
        else:
            confidence = "LOW"
            if is_api_fetch:
                reasoning = "based on limited recent data"
            elif total_days < 3:
                reasoning = "based on insufficient data points"
            elif cache_quality < 0.4:
                reasoning = "based on sparse data"
            else:
                reasoning = "based on limited recent data"
        
        logger.info(f"📊 insight_confidence_computed: {confidence} - {reasoning} (quality={cache_quality:.2%}, days={total_days}, coverage={metric_coverage:.2%})")
        return confidence, reasoning
        
    except Exception as e:
        logger.error(f"❌ Error computing insight confidence: {e}", exc_info=True)
        return "LOW", "based on limited data"


def detect_metric_semantic(user_query: str, metric: str) -> str:
    """
    PHASE 2: Detect if user wants delta (gained) or snapshot (total) for a metric.
    
    Args:
        user_query: User's query string
        metric: Metric name being queried
    
    Returns:
        "delta" for gained/new values, "snapshot" for total/cumulative values
    """
    try:
        query_lower = user_query.lower()
        
        # Delta keywords (new/gained/increase)
        delta_keywords = [
            "naye", "new", "gained", "gain", "increase", "increased", "added",
            "kitne naye", "how many new", "kitne mile", "kitne aaye",
            "growth", "change", "difference"
        ]
        
        # Snapshot keywords (total/cumulative)
        snapshot_keywords = [
            "total", "kitne hai", "how many", "current", "abhi",
            "kitne", "count", "number", "overall"
        ]
        
        # Check for delta keywords first (more specific)
        for keyword in delta_keywords:
            if keyword in query_lower:
                logger.info(f"📊 metric_semantic_detected: delta for {metric} (keyword: {keyword})")
                return "delta"
        
        # Check for snapshot keywords
        for keyword in snapshot_keywords:
            if keyword in query_lower:
                logger.info(f"📊 metric_semantic_detected: snapshot for {metric} (keyword: {keyword})")
                return "snapshot"
        
        # Default to snapshot (safer - shows current state)
        return "snapshot"
        
    except Exception as e:
        logger.error(f"❌ Error detecting metric semantic: {e}", exc_info=True)
        return "snapshot"


def compute_data_quality_flag(
    cached_data: Optional[Dict[str, Dict[str, float]]],
    start_date: Optional[str],
    end_date: Optional[str],
    metrics: List[str],
    is_api_fetch: bool = False
) -> str:
    """
    PHASE 7: Compute data quality flag.
    
    Args:
        cached_data: Cached metrics data or None
        start_date: Start date (YYYY-MM-DD) or None
        end_date: End date (YYYY-MM-DD) or None
        metrics: List of requested metrics
        is_api_fetch: Whether data came from API (not cache)
    
    Returns:
        Data quality flag: "normal", "partial", or "estimated"
    """
    try:
        if is_api_fetch:
            return "estimated"
        
        if not cached_data or not start_date or not end_date:
            return "estimated"
        
        # Compute cache quality
        cache_quality = compute_cache_quality_score(cached_data, start_date, end_date, metrics)
        
        if cache_quality >= 0.7:
            return "normal"
        elif cache_quality >= 0.4:
            return "partial"
        else:
            return "estimated"
            
    except Exception as e:
        logger.error(f"❌ Error computing data quality flag: {e}", exc_info=True)
        return "estimated"


def check_minimum_data_for_insight(
    cached_data: Optional[Dict[str, Dict[str, float]]],
    start_date: Optional[str],
    end_date: Optional[str],
    metrics: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    PHASE 3: Check if we have minimum data for generating insights.
    
    Args:
        cached_data: Cached metrics data or None
        start_date: Start date (YYYY-MM-DD) or None
        end_date: End date (YYYY-MM-DD) or None
        metrics: List of requested metrics
    
    Returns:
        Tuple of (has_sufficient_data, error_message)
        has_sufficient_data: True if we can generate insights
        error_message: Human-readable message if insufficient data
    """
    try:
        if not cached_data or not start_date or not end_date:
            logger.warning(f"⚠️ insufficient_data_for_insight: No cached data available")
            return False, "Abhi kaafi data nahi hai reliable insight ke liye. Kuch aur din ka data collect karein."
        
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        total_days = (end_dt - start_dt).days + 1
        
        # Check data points
        min_data_points = 3
        if total_days < min_data_points:
            logger.warning(f"⚠️ insufficient_data_for_insight: Only {total_days} days of data (minimum: {min_data_points})")
            return False, f"Abhi sirf {total_days} din ka data hai. Reliable insight ke liye kam se kam {min_data_points} din ka data chahiye."
        
        # Check metric coverage
        metrics_with_data = 0
        for metric in metrics:
            if metric in cached_data and len(cached_data[metric]) > 0:
                metrics_with_data += 1
        
        metric_coverage = metrics_with_data / len(metrics) if metrics else 0.0
        min_coverage = 0.4  # 40%
        
        if metric_coverage < min_coverage:
            logger.warning(f"⚠️ insufficient_data_for_insight: Only {metric_coverage:.1%} metric coverage (minimum: {min_coverage:.1%})")
            return False, f"Abhi kaafi metrics ke liye data nahi hai. Reliable insight ke liye zyada data collect karein."
        
        return True, None
        
    except Exception as e:
        logger.error(f"❌ Error checking minimum data: {e}", exc_info=True)
        return False, "Data check mein error aaya. Please try again."


def calculate_growth_rate(
    cached_data: Dict[str, Dict[str, float]],
    start_date: str,
    end_date: str
) -> Dict[str, float]:
    """
    PHASE 5: Calculate growth rate for metrics over date range.
    
    Args:
        cached_data: Dict of {metric: {date: value}}
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        Dict of {metric: growth_rate_percentage}
    """
    try:
        growth_rates = {}
        
        for metric, date_values in cached_data.items():
            start_value = float(date_values.get(start_date, 0))
            end_value = float(date_values.get(end_date, 0))
            
            if start_value > 0:
                growth_rate = ((end_value - start_value) / start_value) * 100
            elif end_value > 0:
                growth_rate = 100.0  # Started from 0
            else:
                growth_rate = 0.0
            
            growth_rates[metric] = round(growth_rate, 2)
        
        return growth_rates
        
    except Exception as e:
        logger.error(f"❌ Error calculating growth rate: {e}", exc_info=True)
        return {}


# -------------------------------------------------------------
# DATABASE/API FUNCTIONS (reusing morning_scheduled_message.py patterns)
# -------------------------------------------------------------

def fetch_connected_platforms(user_id: str) -> List[str]:
    """Fetch all connected social media platforms."""
    try:
        if not supabase:
            logger.error("Supabase client not initialized")
            return []
        
        platforms = []
        
        # Check platform_connections table (OAuth connections)
        try:
            oauth_result = supabase.table("platform_connections").select("platform").eq(
                "user_id", user_id
            ).eq("is_active", True).execute()
            
            if oauth_result.data:
                for conn in oauth_result.data:
                    platform = conn.get("platform", "").lower()
                    if platform and platform not in platforms:
                        platforms.append(platform)
        except Exception as e:
            logger.warning(f"Error fetching OAuth connections: {e}")
        
        # Check social_media_connections table (token connections)
        try:
            token_result = supabase.table("social_media_connections").select("platform").eq(
                "user_id", user_id
            ).eq("is_active", True).execute()
            
            if token_result.data:
                for conn in token_result.data:
                    platform = conn.get("platform", "").lower()
                    if platform and platform not in platforms:
                        platforms.append(platform)
        except Exception as e:
            logger.warning(f"Error fetching token connections: {e}")
        
        logger.info(f"Found connected platforms for user {user_id}: {platforms}")
        return platforms
        
    except Exception as e:
        logger.error(f"Error fetching connected platforms: {e}")
        return []


def get_platform_connection(user_id: str, platform: str) -> Optional[Dict[str, Any]]:
    """Get platform connection details (OAuth or token-based)."""
    try:
        if not supabase:
            logger.warning("Supabase client not initialized")
            return None
        
        platform_lower = platform.lower()
        logger.info(f"🔍 Fetching connection for platform: {platform_lower}, user_id: {user_id}")
        
        # Try OAuth connections first (platform_connections table)
        try:
            oauth_result = supabase.table("platform_connections").select("*").eq(
                "user_id", user_id
            ).eq("platform", platform_lower).eq("is_active", True).execute()
            
            if oauth_result.data and len(oauth_result.data) > 0:
                connection = oauth_result.data[0]
                # Normalize connection data
                connection = {
                    **connection,
                    'access_token': connection.get('access_token_encrypted') or connection.get('access_token', ''),
                    'account_id': connection.get('page_id') or connection.get('account_id', ''),
                    'account_name': connection.get('page_name') or connection.get('account_name', ''),
                    'connection_type': 'oauth'
                }
                logger.info(f"✅ Found OAuth connection for {platform_lower}: account_id={connection.get('account_id')}")
                return connection
        except Exception as e:
            logger.error(f"Error fetching OAuth connection: {e}", exc_info=True)
        
        # Try token connections (social_media_connections table)
        try:
            token_result = supabase.table("social_media_connections").select("*").eq(
                "user_id", user_id
            ).eq("platform", platform_lower).eq("is_active", True).execute()
            
            if token_result.data and len(token_result.data) > 0:
                connection = token_result.data[0]
                connection['connection_type'] = 'token'
                logger.info(f"✅ Found token connection for {platform_lower}: account_id={connection.get('account_id')}")
                return connection
        except Exception as e:
            logger.error(f"Error fetching token connection: {e}", exc_info=True)
        
        logger.warning(f"❌ No connection found for platform {platform_lower}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting platform connection: {e}", exc_info=True)
        return None


def _aggregate_instagram_post_metrics_for_account(connection: Dict[str, Any], instagram_account_id: str, access_token: str, metrics: List[str]) -> Dict[str, Any]:
    """
    Aggregate post-level metrics from recent Instagram posts for account-level insights.
    
    Instagram account-level Insights API doesn't support likes/comments/shares directly.
    This function aggregates these metrics from recent posts to provide account-level totals.
    """
    try:
        # Fetch recent posts (last 30 posts for aggregation)
        media_url = f"https://graph.facebook.com/v18.0/{instagram_account_id}/media"
        params = {
            "access_token": access_token,
            "fields": "like_count,comments_count,shares_count",
            "limit": 30
        }
        
        resp = requests.get(media_url, params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"⚠️ Could not fetch Instagram posts for aggregation: {resp.status_code}")
            return {}
        
        data = resp.json()
        posts = data.get('data', [])
        
        if not posts:
            logger.warning("⚠️ No posts found for aggregation")
            return {}
        
        # Aggregate metrics
        aggregated = {}
        total_likes = sum(post.get('like_count', 0) or 0 for post in posts)
        total_comments = sum(post.get('comments_count', 0) or 0 for post in posts)
        total_shares = sum(post.get('shares_count', 0) or 0 for post in posts)
        
        if "likes" in metrics:
            aggregated["likes"] = total_likes
        if "comments" in metrics:
            aggregated["comments"] = total_comments
        if "shares" in metrics:
            aggregated["shares"] = total_shares
        
        # Include post count for display in account-level analytics
        aggregated["_post_count"] = len(posts)
        
        logger.info(f"📊 Aggregated from {len(posts)} posts: likes={total_likes}, comments={total_comments}, shares={total_shares}")
        return aggregated
        
    except Exception as e:
        logger.error(f"Error aggregating Instagram post metrics: {e}", exc_info=True)
        return {}


def fetch_instagram_post_metrics(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch Instagram POST-LEVEL metrics (likes, comments, shares) from latest post."""
    try:
        post_metrics = fetch_latest_post_metrics(connection, "instagram")
        if not post_metrics:
            return None
        
        result = _transform_post_metrics(post_metrics, metrics)
        logger.info(f"✅ Fetched Instagram post metrics: {result}")
        return result if result else None
        
    except Exception as e:
        logger.error(f"Error fetching Instagram post metrics: {e}", exc_info=True)
        return None


def fetch_instagram_insights(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None, analytics_level: str = "account") -> Optional[Dict[str, Any]]:
    """
    Fetch Instagram ACCOUNT-LEVEL insights - reuses existing API pattern
    
    CRITICAL: Respect analytics_level parameter. Do NOT auto-switch to post metrics
    based on metric names. If analytics_level is "account", fetch account-level data.
    """
    try:
        # CRITICAL FIX: Only switch to post metrics if explicitly requested
        # Do NOT auto-detect based on metric names - respect analytics_level
        if analytics_level == "post":
            logger.info(f"📸 Post-level requested, fetching post metrics: {metrics}")
            return fetch_instagram_post_metrics(connection, metrics, date_range)
        
        access_token = decrypt_token(connection.get('access_token', ''))
        account_id = connection.get('account_id', '') or connection.get('page_id', '')
        
        if not access_token or not account_id:
            logger.warning(f"Missing access_token or account_id for Instagram. account_id={account_id}, has_token={bool(access_token)}")
            return None
        
        logger.info(f"🔍 Instagram account_id: {account_id} (length: {len(str(account_id))})")
        
        # Get Instagram Business account ID
        instagram_account_id = account_id
        if str(account_id).isdigit() and len(str(account_id)) <= 15:
            logger.info(f"🔍 account_id looks like Facebook Page ID, fetching Instagram Business account...")
            page_resp = requests.get(
                f"https://graph.facebook.com/v18.0/{account_id}",
                params={"access_token": access_token, "fields": "instagram_business_account"},
                timeout=10
            )
            if page_resp.status_code == 200:
                page_data = page_resp.json()
                instagram_business_account = page_data.get('instagram_business_account')
                if instagram_business_account:
                    instagram_account_id = instagram_business_account.get('id')
                    logger.info(f"✅ Found Instagram Business account ID: {instagram_account_id}")
                else:
                    logger.warning(f"❌ No Instagram Business account found for Facebook Page {account_id}")
                    return None
            else:
                logger.error(f"❌ Error fetching Instagram account: {page_resp.status_code} - {page_resp.text}")
                return None
        else:
            logger.info(f"✅ Using account_id as Instagram account ID: {instagram_account_id}")
        
        # Map metrics to Instagram API metrics (using valid Instagram insights metrics)
        metric_map = {
            "reach": "reach",
            "impressions": "impressions", 
            "engagement": "profile_views",
            "profile_visits": "profile_views",
            "website_clicks": "website_clicks",
            "email_contacts": "email_contacts",
            "phone_call_clicks": "phone_call_clicks",
            "text_message_clicks": "text_message_clicks",
            "get_directions_clicks": "get_directions_clicks"
        }
        
        # CRITICAL: Separate account-level metrics from post-level metrics
        # Post-level metrics (likes, comments, shares) need to be aggregated from posts
        post_level_metrics = ["likes", "comments", "shares", "saves", "views"]
        account_level_metrics = []
        needs_post_aggregation = []
        
        for m in metrics:
            if m in metric_map:
                account_level_metrics.append(metric_map[m])
            elif m in post_level_metrics:
                needs_post_aggregation.append(m)
        
        # Build API metrics list for account-level insights
        api_metrics = account_level_metrics
        
        # Default metrics if none specified
        if not api_metrics and not needs_post_aggregation:
            api_metrics = ["profile_views", "website_clicks"]
        
        # Determine period
        period = _calculate_period(date_range)
        
        # Fetch insights (only if we have account-level metrics to fetch)
        result = {}
        insights_api_success = False  # Track if primary API call succeeded

        if api_metrics:
            insights_url = f"https://graph.facebook.com/v18.0/{instagram_account_id}/insights"
            params = {"access_token": access_token, "metric": ",".join(api_metrics), "period": period}
            logger.info(f"🌐 Fetching Instagram insights from: {insights_url}")
            logger.info(f"   Metrics: {api_metrics}, Period: {period}")

            resp = requests.get(insights_url, params=params, timeout=15)
            if resp.status_code != 200:
                logger.error(f"❌ Instagram API error: {resp.status_code} - {resp.text}")
                # Mark that primary API failed - we'll still try post aggregation but mark data as partial
                result["_insights_api_failed"] = True
                result["_api_error"] = f"Instagram insights API failed: {resp.status_code} - {resp.text}"
            else:
                insights_api_success = True
                insights = resp.json()

                # Transform response
                if insights.get('data'):
                    for metric_data in insights.get('data', []):
                        name = metric_data.get('name', '')
                        values = metric_data.get('values', [])
                        if values:
                            latest_value = values[-1].get('value', 0)
                            for our_metric, api_metric in metric_map.items():
                                if api_metric == name:
                                    result[our_metric] = latest_value
        else:
            logger.info(f"📊 No account-level metrics to fetch (only post-level metrics requested)")
        
        # Fetch followers count separately (reuse fetch_platform_follower_count)
        if "followers" in metrics or "follower_count" in metrics:
            logger.info(f"🔍 Fetching followers count...")
            try:
                followers_count = fetch_platform_follower_count(connection, "instagram")
                if followers_count > 0:
                    result["followers"] = followers_count
                    logger.info(f"✅ Fetched followers count: {followers_count}")
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch followers count: {e}")
        
        # CRITICAL: Aggregate post-level metrics if requested for account-level insights
        # Instagram account-level Insights API doesn't support likes/comments/shares
        # So we aggregate from recent posts to provide account-level totals
        if needs_post_aggregation:
            logger.info(f"📊 Aggregating post-level metrics for account-level insights: {needs_post_aggregation}")
            try:
                post_aggregated = _aggregate_instagram_post_metrics_for_account(connection, instagram_account_id, access_token, needs_post_aggregation)
                if post_aggregated:
                    result.update(post_aggregated)
                    # Include post count for display
                    if "_post_count" in post_aggregated:
                        result["_post_count"] = post_aggregated["_post_count"]
                    logger.info(f"✅ Aggregated post-level metrics: {list(post_aggregated.keys())}")
            except Exception as e:
                logger.warning(f"⚠️ Could not aggregate post-level metrics: {e}")
        
        # Check if we have any meaningful data
        if result:
            # If insights API failed but we have post-aggregated data, mark as partial
            if result.get("_insights_api_failed") and any(k for k in result.keys() if not k.startswith("_")):
                logger.warning(f"⚠️ Instagram insights API failed, but post-aggregated data available: {list(result.keys())}")
                result["_data_quality"] = "partial"
                return result
            elif insights_api_success or any(k for k in result.keys() if not k.startswith("_") and k not in ["_insights_api_failed", "_api_error"]):
                logger.info(f"✅ Successfully fetched Instagram insights: {list(result.keys())} = {result}")
                return result
            else:
                logger.warning(f"⚠️ No insights data extracted from Instagram API response")
                return None
        else:
            logger.warning(f"⚠️ No insights data extracted from Instagram API response")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching Instagram insights: {e}")
        return None


def fetch_facebook_post_metrics(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch Facebook POST-LEVEL metrics (likes, comments, shares) from latest post"""
    try:
        post_metrics = fetch_latest_post_metrics(connection, "facebook")
        if not post_metrics:
            return None
        
        result = _transform_post_metrics(post_metrics, metrics)
        logger.info(f"✅ Fetched Facebook post metrics: {result}")
        return result if result else None
        
    except Exception as e:
        logger.error(f"Error fetching Facebook post metrics: {e}", exc_info=True)
        return None


def fetch_facebook_insights(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None, analytics_level: str = "account") -> Optional[Dict[str, Any]]:
    """
    Fetch Facebook ACCOUNT-LEVEL insights
    
    CRITICAL: Respect analytics_level parameter. Do NOT auto-switch to post metrics
    based on metric names. If analytics_level is "account", fetch account-level data.
    """
    try:
        # CRITICAL FIX: Only switch to post metrics if explicitly requested
        # Do NOT auto-detect based on metric names - respect analytics_level
        if analytics_level == "post":
            logger.info(f"📘 Post-level requested, fetching post metrics: {metrics}")
            return fetch_facebook_post_metrics(connection, metrics, date_range)
        
        access_token = decrypt_token(connection.get('access_token', ''))
        account_id = connection.get('account_id', '') or connection.get('page_id', '')
        
        if not access_token or not account_id:
            return None
        
        # Map metrics to Facebook API metrics
        metric_map = {
            "reach": "page_impressions_unique", "impressions": "page_impressions",
            "engagement": "page_engaged_users", "views": "page_video_views",
            "followers": "page_fans", "profile_visits": "page_profile_views"
        }
        api_metrics = [metric_map.get(m, m) for m in metrics if m in metric_map] or \
                      ["page_impressions_unique", "page_impressions", "page_engaged_users"]
        
        period = _calculate_period(date_range)
        
        # Fetch insights
        resp = requests.get(
            f"https://graph.facebook.com/v18.0/{account_id}/insights",
            params={"access_token": access_token, "metric": ",".join(api_metrics), "period": period},
            timeout=15
        )
        if resp.status_code != 200:
            return None
        
        insights = resp.json()
        result = {}
        for metric_data in insights.get('data', []):
            name = metric_data.get('name', '')
            values = metric_data.get('values', [])
            if values:
                value = values[-1].get('value', 0)
                for our_metric, api_metric in metric_map.items():
                    if api_metric == name:
                        result[our_metric] = value
        
        return result if result else None
            
    except Exception as e:
        logger.error(f"Error fetching Facebook insights: {e}")
        return None


def fetch_platform_insights(platform: str, user_id: str, date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch platform analytics with cache-first strategy.
    
    Cache Strategy:
    - If date_range <= 30 days: Check cache first, fallback to API
    - If date_range > 30 days: API-only (no cache)
    
    Args:
        platform: Platform name (instagram, facebook, etc.)
        user_id: User ID
        date_range: Optional date range filter (e.g., "last 7 days", "last month")
    
    Returns:
        Dict with platform insights or None if no data
    """
    try:
        connection = get_platform_connection(user_id, platform)
        if not connection:
            logger.warning(f"❌ No active connection found for {platform}")
            return None
        
        platform_lower = platform.lower()
        
        # Default metrics per platform
        default_metrics = {
            "instagram": ["comments", "likes"],
            "facebook": ["reach", "impressions", "engagement"],
            "youtube": ["views", "likes", "comments"],
            "linkedin": ["impressions", "clicks", "engagement"],
            "twitter": ["impressions", "likes", "retweets"],
            "x": ["impressions", "likes", "retweets"]
        }
        
        metrics = default_metrics.get(platform_lower, [])
        
        # Phase 2: Cache-first strategy
        use_cache = should_use_cache(date_range)
        
        cached_data = None
        start_date = None
        end_date = None
        
        if use_cache and date_range:
            # Try cache first
            parsed_dates = parse_date_range(date_range)
            if parsed_dates:
                start_date, end_date = parsed_dates
                cached_data = get_cached_metrics(
                    user_id, platform_lower, "social_media", metrics, start_date, end_date
                )
                
        if cached_data and start_date and end_date:
            # Aggregate cached data
            logger.info(f"🔍 DEBUG: About to aggregate cached data for {platform}")
            logger.info(f"   Date range: {start_date} to {end_date}")
            logger.info(f"   Cached data: {cached_data}")
            aggregated = aggregate_metrics_by_date_range(cached_data, start_date, end_date, "sum")
            if aggregated:
                logger.info(f"✅ analytics_cache_hit: Using cached data for {platform} ({date_range})")
                logger.info(f"📊 analytics_cache_hit: Aggregated Metrics: {list(aggregated.keys())}, Aggregated Values: {aggregated}")
                # Save snapshot for today if not already saved
                save_metrics_snapshot(user_id, platform_lower, "social_media", aggregated)
                return aggregated
            else:
                logger.warning(f"⚠️ Aggregation returned empty for {platform} with cached_data: {cached_data}")
        
        logger.info(f"📭 analytics_cache_miss: No cached data for {platform} ({date_range})")
        
        # Cache miss or > 30 days: Fetch from API
        # CRITICAL: Always use account-level fetcher (this function is for account-level analytics)
        logger.info(f"🌐 analytics_api_fetch: Fetching from API for {platform} ({date_range or 'no date range'})")
        api_data = _route_to_platform_fetcher(platform_lower, connection, metrics, date_range, analytics_level="account")
        
        if api_data and use_cache:
            # Save to cache for future use
            saved = save_metrics_snapshot(user_id, platform_lower, "social_media", api_data)
            if saved:
                logger.info(f"💾 analytics_snapshot_saved: Saved {len(api_data)} metrics for {platform}")
            else:
                logger.warning(f"⚠️ analytics_snapshot_save_failed: Failed to save snapshots for {platform}")
        
        return api_data
            
    except Exception as e:
        logger.error(f"Error fetching platform insights: {e}")
        return None


def fetch_youtube_insights(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch YouTube channel analytics (placeholder - requires YouTube Data API v3)"""
    logger.info("YouTube insights fetching - requires YouTube Data API v3 implementation")
    return None


def fetch_linkedin_insights(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch LinkedIn page analytics (placeholder - requires LinkedIn API)"""
    logger.info("LinkedIn insights fetching - requires LinkedIn API implementation")
    return None


def fetch_twitter_insights(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch Twitter/X analytics (placeholder - requires Twitter API v2)"""
    logger.info("Twitter insights fetching - requires Twitter API v2 implementation")
    return None


def generate_improvements(data: Dict[str, Any], metrics: List[str]) -> Optional[Dict[str, Any]]:
    """Generate personalized improvement suggestions based on analytics data."""
    # TODO: Import or implement generate_improvements_from_data function
    # Example: from your_ai_module import generate_improvements_from_data
    # This could use AI/ML to generate suggestions or query a recommendations DB
    try:
        # Try to import and use real AI function if available
        from services.improvement_service import generate_improvements_from_data
        improvements = generate_improvements_from_data(data, metrics)
    except ImportError:
        # Fallback: Return None if improvement service not implemented yet
        logger.warning("generate_improvements_from_data not implemented, returning None")
        return None
    
    if not improvements:
        return None  # important: return None when NO DATA
    
    return improvements  # return dict when VALID data


def fetch_latest_video_post(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the latest video post from database."""
    try:
        if not supabase:
            return None
        
        # Try to get latest video post
        try:
            posts_result = supabase.table("content_posts").select("*").eq(
                "user_id", user_id
            ).eq("content_type", "video").eq("status", "published").order(
                "published_at", desc=True
            ).limit(1).execute()
            
            if posts_result.data and len(posts_result.data) > 0:
                post = posts_result.data[0]
                return {
                    "views": post.get("views_count", 0) or 0,
                    "total_watch_time": post.get("total_watch_time", 0) or 0
                }
        except Exception as e:
            logger.warning(f"Error fetching video post: {e}")
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting latest video post: {e}")
        return None


def compute_avg_watch_time(post: Dict[str, Any]) -> float:
    """Compute average watch time from total_watch_time and views."""
    views = post.get("views", 0)
    total = post.get("total_watch_time", 0)
    if views == 0:
        return 0.0
    return total / views


def fetch_last_post_platform(user_id: str) -> Optional[str]:
    """Fetch the platform of the last published post."""
    try:
        if not supabase:
            return None
        
        # Try to get latest post from content_posts or social_media_posts
        try:
            posts_result = supabase.table("content_posts").select("platform").eq(
                "user_id", user_id
            ).eq("status", "published").order("published_at", desc=True).limit(1).execute()
            
            if posts_result.data and len(posts_result.data) > 0:
                return posts_result.data[0].get("platform", "").lower()
        except Exception as e:
            logger.warning(f"Error fetching from content_posts: {e}")
        
        try:
            posts_result = supabase.table("social_media_posts").select("platform").eq(
                "user_id", user_id
            ).order("created_at", desc=True).limit(1).execute()
            
            if posts_result.data and len(posts_result.data) > 0:
                return posts_result.data[0].get("platform", "").lower()
        except Exception as e:
            logger.warning(f"Error fetching from social_media_posts: {e}")
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting last post platform: {e}")
        return None


def fetch_insights_for_metrics(platform: str, user_id: str, metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch insights for specified metrics with cache-first strategy.
    
    Cache Strategy:
    - If date_range <= 30 days: Check cache first, fallback to API
    - If date_range > 30 days: API-only (no cache)
    
    Args:
        platform: Platform name (instagram, facebook, etc.)
        user_id: User ID
        metrics: List of metrics to fetch
        date_range: Optional date range filter (e.g., "last 7 days", "last month")
    
    Returns:
        Dict with insights or None if no data
    """
    try:
        connection = get_platform_connection(user_id, platform)
        if not connection:
            logger.warning(f"No active connection found for {platform}")
            return None
        
        platform_lower = platform.lower()
        
        # Phase 2: Cache-first strategy
        use_cache = should_use_cache(date_range)
        
        if use_cache and date_range:
            # Try cache first
            parsed_dates = parse_date_range(date_range)
            if parsed_dates:
                start_date, end_date = parsed_dates
                cached_data = get_cached_metrics(
                    user_id, platform_lower, "social_media", metrics, start_date, end_date
                )
                
                if cached_data:
                    # Aggregate cached data
                    aggregated = aggregate_metrics_by_date_range(cached_data, start_date, end_date, "sum")
                    if aggregated:
                        logger.info(f"✅ analytics_cache_hit: Using cached data for {platform} metrics {metrics} ({date_range})")
                        logger.info(f"📊 analytics_cache_hit: Aggregated values: {aggregated}")
                        # Save snapshot for today if not already saved
                        save_metrics_snapshot(user_id, platform_lower, "social_media", aggregated)
                        return aggregated
        
        logger.info(f"📭 analytics_cache_miss: No cached data for {platform} metrics {metrics} ({date_range or 'no date range'})")
        
        # Cache miss or > 30 days: Fetch from API
        # CRITICAL: Always use account-level fetcher (this function is for account-level analytics)
        logger.info(f"🌐 analytics_api_fetch: Fetching from API for {platform} metrics {metrics} ({date_range or 'no date range'})")
        api_data = _route_to_platform_fetcher(platform_lower, connection, metrics, date_range, analytics_level="account")
        
        if api_data and use_cache:
            # Save to cache for future use
            saved = save_metrics_snapshot(user_id, platform_lower, "social_media", api_data)
            if saved:
                logger.info(f"💾 analytics_snapshot_saved: Saved {len(api_data)} metrics for {platform}")
            else:
                logger.warning(f"⚠️ analytics_snapshot_save_failed: Failed to save snapshots for {platform}")
        
        return api_data
            
    except Exception as e:
        logger.error(f"Error fetching data from API: {e}")
        return None


def fetch_blog_insights(user_id: str, metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch blog insights based on metrics (placeholder - requires blog analytics API).
    
    Args:
        user_id: User ID
        metrics: List of blog metrics to fetch
        date_range: Optional date range filter (e.g., "last 7 days", "last month")
    
    Returns:
        Dict with blog insights or None if no data
    """
    logger.info("Blog insights fetching - requires blog analytics API implementation")
    return None


# -------------------------------------------------------------
# POST-LEVEL ANALYTICS FUNCTIONS
# -------------------------------------------------------------

def fetch_instagram_posts(
    connection: Dict[str, Any],
    metrics: List[str],
    limit: int = 10
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch Instagram posts with per-post metrics for ranking.
    
    Args:
        connection: Platform connection details
        metrics: List of metrics to fetch (likes, comments, shares, views, engagement)
        limit: Maximum number of posts to fetch (default: 10)
    
    Returns:
        List of posts with standardized metrics or None if error
    """
    try:
        access_token = decrypt_token(connection.get('access_token', ''))
        account_id = connection.get('account_id', '') or connection.get('page_id', '')
        
        if not access_token or not account_id:
            logger.warning(f"Missing access_token or account_id for Instagram")
            return None
        
        logger.info(f"🔍 Fetching Instagram posts for ranking (limit={limit})")
        
        # Get Instagram Business account ID
        instagram_account_id = account_id
        if str(account_id).isdigit() and len(str(account_id)) <= 15:
            logger.info(f"🔍 Fetching Instagram Business account ID from Facebook Page...")
            page_resp = requests.get(
                f"https://graph.facebook.com/v18.0/{account_id}",
                params={"access_token": access_token, "fields": "instagram_business_account"},
                timeout=10
            )
            if page_resp.status_code == 200:
                page_data = page_resp.json()
                instagram_business_account = page_data.get('instagram_business_account')
                if instagram_business_account:
                    instagram_account_id = instagram_business_account.get('id')
                    logger.info(f"✅ Found Instagram Business account ID: {instagram_account_id}")
                else:
                    logger.warning(f"❌ No Instagram Business account found")
                    return None
            else:
                logger.error(f"❌ Error fetching Instagram account: {page_resp.text}")
                return None
        
        # Fetch media (posts)
        media_url = f"https://graph.facebook.com/v18.0/{instagram_account_id}/media"
        # Try with insights first (requires instagram_manage_insights permission)
        # If that fails, fallback to basic fields without insights
        media_fields_with_insights = "id,caption,media_type,permalink,timestamp,like_count,comments_count,insights.metric(impressions,reach)"
        media_fields_basic = "id,caption,media_type,permalink,timestamp,like_count,comments_count"
        
        # Try with insights first
        media_resp = requests.get(
            media_url,
            params={
                "access_token": access_token,
                "fields": media_fields_with_insights,
                "limit": limit
            },
            timeout=15
        )
        
        # If insights request fails due to permissions, fallback to basic fields
        if media_resp.status_code != 200:
            error_data = media_resp.json() if media_resp.text else {}
            error_code = error_data.get("error", {}).get("code", 0)
            
            # Check if it's a permissions error (code 10 = OAuthException)
            if error_code == 10:
                logger.warning(f"⚠️ Instagram insights permission not available, falling back to basic fields")
                # Retry with basic fields only
                media_resp = requests.get(
                    media_url,
                    params={
                        "access_token": access_token,
                        "fields": media_fields_basic,
                        "limit": limit
                    },
                    timeout=15
                )
            
            if media_resp.status_code != 200:
                logger.error(f"❌ Instagram API error: {media_resp.status_code} - {media_resp.text}")
                return None
        
        media_data = media_resp.json()
        posts = []
        
        for post in media_data.get('data', []):
            post_id = post.get('id')
            caption = post.get('caption', '')
            permalink = post.get('permalink', '')
            timestamp = post.get('timestamp', '')
            
            likes = post.get('like_count', 0) or 0
            comments = post.get('comments_count', 0) or 0
            
            # Extract insights for sorting (reach/impressions)
            reach = 0
            impressions = 0
            insights = post.get('insights', {}).get('data', [])
            for insight in insights:
                name = insight.get('name')
                val = insight.get('values', [{}])[0].get('value', 0)
                if name == 'reach': reach = val
                elif name == 'impressions': impressions = val

            # Engagement = likes + comments (as per requirement)
            engagement = likes + comments
            
            # MUST return: post_id, caption, likes, comments, shares, engagement, permalink, timestamp
            # We add reach/impressions to support sorting in Orion's _handle_post_level_analytics
            post_metrics = {
                "post_id": post_id,
                "caption": caption[:100] + "..." if len(caption) > 100 else caption,
                "likes": likes,
                "comments": comments,
                "shares": 0,
                "engagement": engagement,
                "reach": reach,
                "impressions": impressions,
                "permalink": permalink,
                "timestamp": timestamp
            }
            
            posts.append(post_metrics)
        
        logger.info(f"✅ Fetched {len(posts)} Instagram posts with metrics")
        return posts if posts else None
        
    except Exception as e:
        logger.error(f"Error fetching Instagram posts: {e}", exc_info=True)
        return None


def fetch_facebook_posts(
    connection: Dict[str, Any],
    metrics: List[str],
    limit: int = 10
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch Facebook posts with per-post metrics for ranking.
    """
    try:
        access_token = decrypt_token(connection.get('access_token', ''))
        page_id = connection.get('account_id', '') or connection.get('page_id', '')
        
        if not access_token or not page_id:
            logger.warning(f"Missing access_token or page_id for Facebook")
            return None
        
        logger.info(f"🔍 Fetching Facebook posts for ranking (limit={limit})")
        
        # Fetch posts
        posts_url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
        # Try with insights first (requires read_insights permission)
        posts_fields_with_insights = "id,message,created_time,permalink_url,shares,reactions.summary(true),comments.summary(true),insights.metric(post_impressions,post_engaged_users)"
        posts_fields_basic = "id,message,created_time,permalink_url,shares,reactions.summary(true),comments.summary(true)"
        
        # Try with insights first
        posts_resp = requests.get(
            posts_url,
            params={
                "access_token": access_token,
                "fields": posts_fields_with_insights,
                "limit": limit
            },
            timeout=15
        )
        
        # If insights request fails, fallback to basic fields
        if posts_resp.status_code != 200:
            error_data = posts_resp.json() if posts_resp.text else {}
            error_code = error_data.get("error", {}).get("code", 0)
            
            # Check if it's a permissions or invalid metric error (code 100 or 10)
            if error_code in [10, 100]:
                logger.warning(f"⚠️ Facebook insights permission/metric not available, falling back to basic fields")
                # Retry with basic fields only
                posts_resp = requests.get(
                    posts_url,
                    params={
                        "access_token": access_token,
                        "fields": posts_fields_basic,
                        "limit": limit
                    },
                    timeout=15
                )
            
            if posts_resp.status_code != 200:
                logger.error(f"❌ Facebook API error: {posts_resp.status_code} - {posts_resp.text}")
                return None
        
        posts_data = posts_resp.json()
        posts = []
        
        for post in posts_data.get('data', []):
            post_id = post.get('id')
            message = post.get('message', '')
            created_time = post.get('created_time', '')
            permalink = post.get('permalink_url', '')
            
            # Extract metrics
            reactions = post.get('reactions', {}).get('summary', {}).get('total_count', 0) or 0
            comments_count = post.get('comments', {}).get('summary', {}).get('total_count', 0) or 0
            shares_count = post.get('shares', {}).get('count', 0) or 0
            
            reach = 0
            impressions = 0
            insights = post.get('insights', {}).get('data', [])
            for insight in insights:
                name = insight.get('name')
                val = insight.get('values', [{}])[0].get('value', 0)
                if name == 'post_impressions': impressions = val
                elif name == 'post_engaged_users': reach = val # Mapping engaged users to reach if reach is not available or as a signal

            # Engagement = likes + comments + shares (as per requirement)
            engagement = reactions + comments_count + shares_count
            
            # MUST return: post_id, caption, likes, comments, shares, engagement, permalink, timestamp
            post_metrics = {
                "post_id": post_id,
                "caption": message[:100] + "..." if len(message) > 100 else message,
                "likes": reactions,
                "comments": comments_count,
                "shares": shares_count,
                "engagement": engagement,
                "reach": reach,
                "impressions": impressions,
                "permalink": permalink,
                "timestamp": created_time
            }
            
            posts.append(post_metrics)
        
        logger.info(f"✅ Fetched {len(posts)} Facebook posts with metrics")
        return posts if posts else None
        
    except Exception as e:
        logger.error(f"Error fetching Facebook posts: {e}", exc_info=True)
        return None


# ============================================================================
# POST-WISE PERFORMANCE COMPARISON SYSTEM
# ============================================================================
# This module implements explainable, post-level analytics for users asking:
# "Last 5 posts ne kaisa perform kiya?"
#
# Architecture:
# - Orion: Computation engine (returns structured JSON, no human language)
# - Emily: Presentation layer (converts to human-friendly language)
#
# Data source: analytics_snapshots table
# Key principles:
# - Deterministic calculations (no ML)
# - Only detect patterns when data supports it
# - Transparent confidence scoring
# - Never guess or make assumptions
# ============================================================================

def analyze_post_performance(
    user_id: str,
    platform: str,
    num_posts: int = 1,
    metrics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    PART 1-7: Complete post-performance comparison system.
    
    Analyzes last N posts for a user on a platform and returns structured
    performance analytics with labels, scores, and detected patterns.
    
    Args:
        user_id: User ID
        platform: Platform name (facebook, instagram, etc.)
        num_posts: Number of recent posts to analyze (default: 5)
    
    Returns:
        Structured JSON with:
        - posts: List of posts with scores and labels
        - comparison: Performance comparison data
        - reasons: Detected patterns (only if data supports)
        - confidence: Overall confidence level
    
    Implements:
    - PART 1: Data selection from analytics_snapshots
    - PART 2: Performance score calculation
    - PART 3: Average & comparison
    - PART 4: Label assignment
    - PART 5: Reason detection
    - PART 6: Confidence scoring
    - PART 7: Structured output
    """
    try:
        logger.info(f"📊 Analyzing post performance for user {user_id}, platform {platform}")
        
        if not supabase:
            return _error_response("Database connection not available")
        
        # ===================================================================
        # PART 1: DATA SELECTION
        # ===================================================================
        # CRITICAL: Post-level analytics/insights MUST always fetch LIVE data from API
        # Do NOT use cached data - post-level queries need real-time post metrics
        
        logger.info(f"   Fetching live post data from API for post-level analysis...")
        connection = get_platform_connection(user_id, platform.lower())
        if not connection:
            return _error_response("No connection found for platform", "low")
        
        # Default to 1 post if num_posts not specified
        fetch_limit = num_posts if num_posts and num_posts > 0 else 1
        
        # Use requested metrics, or default to common metrics if not specified
        if not metrics or len(metrics) == 0:
            if platform.lower() == "instagram":
                metrics = ["likes", "comments", "shares", "engagement"]
            elif platform.lower() == "facebook":
                metrics = ["likes", "comments", "shares"]
            else:
                metrics = ["likes", "comments", "shares"]
        
        # Fetch live posts from API with only requested metrics
        if platform.lower() == "instagram":
            api_posts = fetch_instagram_posts(connection, metrics, limit=fetch_limit)
        elif platform.lower() == "facebook":
            api_posts = fetch_facebook_posts(connection, metrics, limit=fetch_limit)
        else:
            return _error_response(f"Live data fetching not supported for {platform}", "low")
        
        if not api_posts or len(api_posts) == 0:
            return _error_response("No posts found from API", "low")
        
        # Convert API format to internal format expected by _calculate_performance_scores
        posts_data = []
        for post in api_posts[:num_posts]:
            # Extract metadata if available
            metadata = {}
            if post.get("caption"):
                metadata["caption"] = post.get("caption")
            timestamp = post.get("timestamp", "")
            if timestamp:
                metadata["posted_at"] = timestamp
            
            # Use timestamp as latest_date (required by _calculate_performance_scores)
            latest_date = timestamp if timestamp else datetime.now().isoformat()
            
            posts_data.append({
                "post_id": post.get("post_id"),
                "metrics": {
                    "engagement": post.get("engagement", 0),
                    "likes": post.get("likes", 0),
                    "comments": post.get("comments", 0),
                    "shares": post.get("shares", 0),
                    "reach": post.get("reach", 0) or post.get("impressions", 0)
                },
                "metadata": metadata,
                "latest_date": latest_date  # Required by _calculate_performance_scores
            })
        
        logger.info(f"   Fetched {len(posts_data)} posts from API")
        
        num_posts_found = len(posts_data)
        logger.info(f"   Aggregated data for {num_posts_found} unique posts")
        
        # ===================================================================
        # CRITICAL: Only calculate scores/comparisons if multiple posts exist
        # ===================================================================
        if num_posts_found < 2:
            # Single post: Return raw metrics only, NO scores/averages
            single_post = posts_data[0]
            return {
                "type": "post_comparison",
                "posts": [{
                    "post_id": single_post.get("post_id", "latest"),
                    "metrics": single_post.get("metrics", {}),
                    "metadata": single_post.get("metadata", {})
                }],
                "num_posts_found": num_posts_found,
                "num_posts_requested": num_posts,
                "comparison": None,  # No comparison for single post
                "reasons": [],  # No reasons for single post
                "confidence": "low"
            }
        
        # Multiple posts: Calculate comparisons (but only if >= 2 posts)
        # ===================================================================
        # PART 2: PERFORMANCE SCORE CALCULATION (ONLY for multiple posts)
        # ===================================================================
        posts_with_scores = _calculate_performance_scores(posts_data)
        
        # ===================================================================
        # PART 3: AVERAGE & COMPARISON (ONLY for multiple posts)
        # ===================================================================
        avg_score = sum(p["score"] for p in posts_with_scores) / len(posts_with_scores)
        
        # Calculate ratio vs average for each post
        for post in posts_with_scores:
            post["ratio_vs_avg"] = round(post["score"] / avg_score, 2) if avg_score > 0 else 1.0
        
        logger.info(f"   Average score: {avg_score:.2f}")
        
        # ===================================================================
        # PART 4: LABEL ASSIGNMENT (ONLY for multiple posts)
        # ===================================================================
        posts_with_labels = _assign_labels(posts_with_scores)
        
        # Sort by score descending
        posts_with_labels.sort(key=lambda x: x["score"], reverse=True)
        
        # ===================================================================
        # PART 5: REASON DETECTION (ONLY if >= 3 posts)
        # ===================================================================
        reasons = []
        if num_posts_found >= 3:
            # Pass posts_with_scores (which has scores) instead of posts_data (raw)
            reasons = _detect_patterns(posts_with_scores, num_posts_found)
        
        # ===================================================================
        # PART 6: CONFIDENCE SCORING
        # ===================================================================
        confidence = _calculate_confidence(posts_data, num_posts_found, reasons)
        
        # ===================================================================
        # PART 7: STRUCTURED OUTPUT (Orion Contract)
        # ===================================================================
        
        # Establish best and worst for structured summary
        best_post = posts_with_labels[0]
        worst_post = posts_with_labels[-1]
        
        # Build return object (STRICT CONTRACT - NO FABRICATED SCORES)
        return {
            "type": "post_comparison",
            "summary": {
                "num_posts_found": num_posts_found,
                "num_posts_requested": num_posts
            },
            "posts": posts_with_labels,
            "comparison": {
                "best_post_id": best_post.get("post_id"),
                "worst_post_id": worst_post.get("post_id"),
                "best_vs_worst_ratio": round(best_post["score"] / worst_post["score"], 2) if worst_post["score"] > 0 else None,
                "best_vs_avg_ratio": best_post.get("ratio_vs_avg")
            } if num_posts_found >= 2 else None,
            "reasons": reasons if num_posts_found >= 3 else [],
            "confidence": confidence,
            "metadata": {
                "total_posts_analyzed": num_posts_found,
                "platform": platform
            }
        }
        
    except Exception as e:
        logger.error(f"Error in analyze_post_performance: {e}", exc_info=True)
        return _error_response(f"Analysis failed: {str(e)}", "low")


def _aggregate_post_metrics(snapshots: List[Dict], num_posts: int) -> List[Dict]:
    """
    PART 1: Aggregate metrics by post_id.
    
    Takes raw snapshots and groups them by post_id, aggregating:
    - engagement
    - reach
    - comments
    - likes
    - impressions
    
    Returns list of post dictionaries with aggregated metrics.
    """
    from collections import defaultdict
    
    # Group snapshots by post_id
    posts_dict = defaultdict(lambda: {
        "metrics": {},
        "metadata": {},
        "latest_date": None
    })
    
    for snapshot in snapshots:
        post_id = snapshot.get("post_id")
        if not post_id:
            continue
        
        metric = snapshot.get("metric", "")
        value = float(snapshot.get("value", 0))
        date_str = snapshot.get("date", "")
        metadata = snapshot.get("metadata", {})
        
        # Track latest date for this post
        if not posts_dict[post_id]["latest_date"] or date_str > posts_dict[post_id]["latest_date"]:
            posts_dict[post_id]["latest_date"] = date_str
            # Update metadata from most recent snapshot
            if metadata:
                posts_dict[post_id]["metadata"] = metadata
        
        # Aggregate metrics (sum values across dates for same metric)
        if metric not in posts_dict[post_id]["metrics"]:
            posts_dict[post_id]["metrics"][metric] = 0
        posts_dict[post_id]["metrics"][metric] += value
    
    # Convert to list and sort by latest_date (most recent first)
    posts_list = []
    for post_id, data in posts_dict.items():
        posts_list.append({
            "post_id": post_id,
            "metrics": data["metrics"],
            "metadata": data["metadata"],
            "latest_date": data["latest_date"]
        })
    
    # Sort by latest_date descending and take top N
    posts_list.sort(key=lambda x: x["latest_date"] or "", reverse=True)
    return posts_list[:num_posts]


def _calculate_performance_scores(posts: List[Dict]) -> List[Dict]:
    """
    PART 2: Calculate performance score for each post.
    
    Uses weighted formula:
    score = 0.5 * engagement_rate + 0.3 * normalized_reach + 0.2 * normalized_comments
    
    If metrics are missing, redistributes weights proportionally.
    
    Returns posts with added "score" and "metrics_used" fields.
    """
    # Extract metrics for normalization
    all_engagement = []
    all_reach = []
    all_comments = []
    all_likes = []
    
    for post in posts:
        metrics = post["metrics"]
        
        # Calculate engagement (likes + comments + shares + other interactions)
        engagement = metrics.get("engagement", 0)
        if engagement == 0:
            # Fallback: sum common engagement metrics
            engagement = (
                metrics.get("likes", 0) +
                metrics.get("comments", 0) +
                metrics.get("shares", 0) +
                metrics.get("reactions", 0)
            )
        
        all_engagement.append(engagement)
        all_reach.append(metrics.get("reach", 0))
        all_comments.append(metrics.get("comments", 0))
        all_likes.append(metrics.get("likes", 0))
    
    # Find max values for normalization (avoid division by zero)
    max_engagement = max(all_engagement) if max(all_engagement) > 0 else 1
    max_reach = max(all_reach) if max(all_reach) > 0 else 1
    max_comments = max(all_comments) if max(all_comments) > 0 else 1
    
    # Calculate scores
    scored_posts = []
    for i, post in enumerate(posts):
        metrics = post["metrics"]
        
        # Get normalized values
        engagement = all_engagement[i]
        reach = all_reach[i]
        comments = all_comments[i]
        
        normalized_engagement = engagement / max_engagement
        normalized_reach = reach / max_reach if reach > 0 else 0
        normalized_comments = comments / max_comments if comments > 0 else 0
        
        # Determine which metrics are available
        has_reach = reach > 0
        has_comments = comments > 0
        
        # Calculate weighted score with dynamic weight redistribution
        if has_reach and has_comments:
            # All metrics available
            score = (
                0.5 * normalized_engagement +
                0.3 * normalized_reach +
                0.2 * normalized_comments
            )
            metrics_used = ["engagement", "reach", "comments"]
        elif has_reach:
            # No comments data, redistribute weight
            score = (
                0.7 * normalized_engagement +  # 0.5 + 0.2
                0.3 * normalized_reach
            )
            metrics_used = ["engagement", "reach"]
        elif has_comments:
            # No reach data, redistribute weight
            score = (
                0.8 * normalized_engagement +  # 0.5 + 0.3
                0.2 * normalized_comments
            )
            metrics_used = ["engagement", "comments"]
        else:
            # Only engagement available
            score = normalized_engagement
            metrics_used = ["engagement"]
        
        # Convert to 0-100 scale
        score = round(score * 100, 1)
        
        scored_posts.append({
            "post_id": post["post_id"],
            "score": score,
            "metrics": {
                "engagement": int(engagement),
                "reach": int(reach) if has_reach else None,
                "comments": int(comments) if has_comments else None,
                "likes": int(all_likes[i])
            },
            "metrics_used": metrics_used,
            "metadata": post["metadata"],
            "latest_date": post.get("latest_date", "")  # Use get() to avoid KeyError
        })
    
    return scored_posts


def _assign_labels(posts: List[Dict]) -> List[Dict]:
    """
    PART 4: Assign performance labels based on fixed thresholds.
    
    Thresholds:
    - >= 1.5: Best (clear standout)
    - 1.1-1.49: Good (above average)
    - 0.8-1.09: Average (normal)
    - < 0.8: Poor (needs improvement)
    """
    for post in posts:
        ratio = post.get("ratio_vs_avg", 1.0)
        
        if ratio >= 1.5:
            label = "Best"
            meaning = "Clear standout"
        elif ratio >= 1.1:
            label = "Good"
            meaning = "Above average"
        elif ratio >= 0.8:
            label = "Average"
            meaning = "Normal performance"
        else:
            label = "Poor"
            meaning = "Needs improvement"
        
        post["label"] = label
        post["label_meaning"] = meaning
    
    return posts


def _detect_patterns(posts: List[Dict], num_posts: int) -> List[Dict]:
    """
    PART 5: Detect patterns and reasons from metadata.
    
    ONLY detects reasons if:
    - At least 3 posts exist
    - Metadata is available
    - Difference is >= 1.5x (meaningful)
    
    Analyzes:
    - Caption length (short/medium/long)
    - Content type (reel, post, carousel)
    - Posting time (morning/afternoon/evening/night)
    - Hook presence (question marks, numbers, trigger words)
    
    Returns list of detected patterns with evidence.
    """
    reasons = []
    
    # Require minimum 3 posts for pattern detection
    if num_posts < 3:
        return [{
            "signal": "insufficient_data",
            "evidence": f"Only {num_posts} posts available (minimum 3 required)",
            "confidence": "low"
        }]
    
    # Extract features from metadata
    posts_with_features = []
    for post in posts:
        metadata = post.get("metadata", {})
        
        # Skip if no metadata
        if not metadata or not isinstance(metadata, dict):
            continue
        
        caption = metadata.get("caption", "")
        content_type = metadata.get("content_type", "")
        posted_at = metadata.get("posted_at", "")
        
        # Extract features
        features = {
            "post_id": post["post_id"],
            "score": post["score"],
            "caption_length": len(caption) if caption else 0,
            "content_type": content_type.lower() if content_type else "unknown",
            "has_hook": _detect_hook(caption),
            "posting_time": _extract_time_bucket(posted_at)
        }
        
        # Caption bucket
        if features["caption_length"] < 80:
            features["caption_bucket"] = "short"
        elif features["caption_length"] <= 150:
            features["caption_bucket"] = "medium"
        else:
            features["caption_bucket"] = "long"
        
        posts_with_features.append(features)
    
    # Need at least 3 posts with metadata
    if len(posts_with_features) < 3:
        return [{
            "signal": "insufficient_metadata",
            "evidence": f"Only {len(posts_with_features)} posts have metadata",
            "confidence": "low"
        }]
    
    # Analyze caption length pattern
    caption_pattern = _analyze_categorical_pattern(
        posts_with_features, "caption_bucket", "Caption length"
    )
    if caption_pattern:
        reasons.append(caption_pattern)
    
    # Analyze content type pattern
    content_pattern = _analyze_categorical_pattern(
        posts_with_features, "content_type", "Content type"
    )
    if content_pattern:
        reasons.append(content_pattern)
    
    # Analyze posting time pattern
    time_pattern = _analyze_categorical_pattern(
        posts_with_features, "posting_time", "Posting time"
    )
    if time_pattern:
        reasons.append(time_pattern)
    
    # Analyze hook presence
    hook_pattern = _analyze_boolean_pattern(
        posts_with_features, "has_hook", "Hook in caption"
    )
    if hook_pattern:
        reasons.append(hook_pattern)
    
    # If no patterns detected
    if not reasons:
        reasons.append({
            "signal": "no_clear_pattern",
            "evidence": "No consistent patterns detected across posts",
            "confidence": "medium"
        })
    
    return reasons


def _detect_hook(caption: str) -> bool:
    """
    Detect if caption has a hook (engaging first line).
    
    Looks for:
    - Question marks
    - Numbers
    - Trigger words: how, why, mistake, secret, hack, tip
    """
    if not caption:
        return False
    
    # Get first line (up to 100 chars or first newline)
    first_line = caption.split('\n')[0][:100].lower()
    
    # Check for hooks
    has_question = '?' in first_line
    has_number = any(char.isdigit() for char in first_line)
    
    trigger_words = ['how', 'why', 'mistake', 'secret', 'hack', 'tip', 'trick', 'warning']
    has_trigger = any(word in first_line for word in trigger_words)
    
    return has_question or has_number or has_trigger


def _extract_time_bucket(posted_at: str) -> str:
    """
    Extract time bucket from timestamp.
    
    Buckets:
    - morning: 6-12
    - afternoon: 12-17
    - evening: 17-21
    - night: 21-6
    """
    if not posted_at:
        return "unknown"
    
    try:
        # Parse timestamp
        from datetime import datetime
        if isinstance(posted_at, str):
            # Try common formats
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(posted_at.split('.')[0].split('+')[0], fmt)
                    hour = dt.hour
                    
                    if 6 <= hour < 12:
                        return "morning"
                    elif 12 <= hour < 17:
                        return "afternoon"
                    elif 17 <= hour < 21:
                        return "evening"
                    else:
                        return "night"
                except:
                    continue
    except:
        pass
    
    return "unknown"


def _analyze_categorical_pattern(
    posts: List[Dict],
    feature: str,
    feature_name: str
) -> Optional[Dict]:
    """
    Analyze if a categorical feature shows meaningful pattern.
    
    Returns pattern if:
    - At least 2 different categories exist
    - Top category avg is >= 1.5x bottom category avg
    """
    from collections import defaultdict
    
    # Group by feature value
    groups = defaultdict(list)
    for post in posts:
        value = post.get(feature, "unknown")
        if value != "unknown":
            groups[value].append(post["score"])
    
    # Need at least 2 categories
    if len(groups) < 2:
        return None
    
    # Calculate average score per category
    avgs = {}
    for category, scores in groups.items():
        avgs[category] = sum(scores) / len(scores)
    
    # Find best and worst
    sorted_categories = sorted(avgs.items(), key=lambda x: x[1], reverse=True)
    best_cat, best_avg = sorted_categories[0]
    worst_cat, worst_avg = sorted_categories[-1]
    
    # Check if difference is meaningful (>= 1.5x)
    if worst_avg > 0 and best_avg / worst_avg >= 1.5:
        ratio = best_avg / worst_avg
        return {
            "signal": f"{feature}_{best_cat}",
            "evidence": {
                "feature": feature,
                "feature_name": feature_name,
                "best_category": best_cat,
                "worst_category": worst_cat,
                "ratio": round(ratio, 2)
            },
            "confidence": "high" if len(groups[best_cat]) >= 2 else "medium"
        }
    
    return None


def _analyze_boolean_pattern(
    posts: List[Dict],
    feature: str,
    feature_name: str
) -> Optional[Dict]:
    """
    Analyze if a boolean feature shows meaningful pattern.
    """
    true_scores = [p["score"] for p in posts if p.get(feature) == True]
    false_scores = [p["score"] for p in posts if p.get(feature) == False]
    
    # Need posts in both categories
    if not true_scores or not false_scores:
        return None
    
    true_avg = sum(true_scores) / len(true_scores)
    false_avg = sum(false_scores) / len(false_scores)
    
    # Check for meaningful difference
    if false_avg > 0 and true_avg / false_avg >= 1.5:
        ratio = true_avg / false_avg
        return {
            "signal": f"{feature}_yes",
            "evidence": {
                "feature": feature,
                "feature_name": feature_name,
                "has_feature": True,
                "ratio": round(ratio, 2)
            },
            "confidence": "high" if len(true_scores) >= 2 else "medium"
        }
    elif true_avg > 0 and false_avg / true_avg >= 1.5:
        ratio = false_avg / true_avg
        return {
            "signal": f"{feature}_no",
            "evidence": {
                "feature": feature,
                "feature_name": feature_name,
                "has_feature": False,
                "ratio": round(ratio, 2)
            },
            "confidence": "high" if len(false_scores) >= 2 else "medium"
        }
    
    return None


def _calculate_confidence(posts: List[Dict], num_posts: int, reasons: List[Dict]) -> str:
    """
    PART 6: Calculate overall confidence level.
    
    Rules:
    - HIGH: >= 5 posts, consistent patterns, metadata mostly present
    - MEDIUM: 3-4 posts, partial patterns
    - LOW: < 3 posts OR missing metadata
    """
    # Check metadata availability
    posts_with_metadata = sum(
        1 for p in posts
        if p.get("metadata") and isinstance(p.get("metadata"), dict) and p["metadata"]
    )
    metadata_coverage = posts_with_metadata / num_posts if num_posts > 0 else 0
    
    # Check for clear patterns
    clear_patterns = sum(
        1 for r in reasons
        if r.get("confidence") == "high" and r.get("signal") not in ["insufficient_data", "no_clear_pattern", "insufficient_metadata"]
    )
    
    # Determine confidence
    if num_posts >= 5 and metadata_coverage >= 0.6 and clear_patterns >= 1:
        return "high"
    elif num_posts >= 3 and metadata_coverage >= 0.4:
        return "medium"
    else:
        return "low"


def _error_response(message: str, confidence: str = "low") -> Dict:
    """
    Generate error response in standard format.
    """
    return {
        "type": "post_comparison",
        "summary": message,
        "posts": [],
        "comparison": {},
        "reasons": [{
            "signal": "error",
            "evidence": message,
            "confidence": confidence
        }],
        "confidence": confidence,
        "metadata": {}
    }
