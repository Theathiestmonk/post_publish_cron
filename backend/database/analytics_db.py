"""
Analytics Database Module - Real-time Platform API Integration

This module fetches real-time analytics data from platform APIs by reusing existing API code.
All functions return data in the format expected by Orion_Analytics_query.py
"""

import os
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Initialize Supabase client (reuse existing pattern)
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Reuse decrypt_token from existing code (matches morning_scheduled_message.py pattern)
def decrypt_token(encrypted_token: str) -> str:
    """Decrypt access token - reuses existing encryption logic"""
    from cryptography.fernet import Fernet
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key or not encrypted_token:
        return encrypted_token or ""
    try:
        cipher_suite = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        return cipher_suite.decrypt(encrypted_token.encode()).decode()
    except Exception:
        return encrypted_token  # Return as-is if decryption fails


def get_connected_platforms_from_db(user_id: str) -> List[str]:
    """
    Fetch all connected social media platforms for a user.
    
    Returns:
        List of platform names (e.g., ["instagram", "facebook", "youtube"])
    """
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
    """
    Get platform connection details (OAuth or token-based).
    
    Returns:
        Connection dict with access_token, account_id, etc.
    """
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
            else:
                logger.info(f"No OAuth connection found for {platform_lower}")
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
            else:
                logger.info(f"No token connection found for {platform_lower}")
        except Exception as e:
            logger.error(f"Error fetching token connection: {e}", exc_info=True)
        
        logger.warning(f"❌ No connection found for platform {platform_lower}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting platform connection: {e}", exc_info=True)
        return None


def fetch_instagram_post_metrics(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch Instagram POST-LEVEL metrics (likes, comments, shares) from latest post.
    This is used when user asks for "likes on my last post" or "comments on yesterday's post".
    """
    try:
        access_token = decrypt_token(connection.get('access_token', ''))
        account_id = connection.get('account_id', '') or connection.get('page_id', '')
        
        if not access_token or not account_id:
            logger.warning(f"Missing access_token or account_id for Instagram post metrics")
            return None
        
        # Get Instagram Business account ID
        instagram_account_id = account_id
        if str(account_id).isdigit() and len(str(account_id)) <= 15:
            page_resp = requests.get(
                f"https://graph.facebook.com/v18.0/{account_id}",
                params={"access_token": access_token, "fields": "instagram_business_account"},
                timeout=10
            )
            if page_resp.status_code == 200:
                instagram_business_account = page_resp.json().get('instagram_business_account')
                if instagram_business_account:
                    instagram_account_id = instagram_business_account.get('id')
        
        # Fetch latest post(s) - get more posts if date_range is specified
        limit = 10 if date_range and ("week" in date_range.lower() or "month" in date_range.lower()) else 1
        
        logger.info(f"📸 Fetching latest Instagram post(s) for metrics: {metrics}")
        response = requests.get(
            f"https://graph.facebook.com/v18.0/{instagram_account_id}/media",
            params={
                "access_token": access_token,
                "fields": "id,like_count,comments_count,timestamp,caption",
                "limit": limit
            },
            timeout=15
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Instagram media API error: {response.status_code} - {response.text}")
            return None
        
        data = response.json()
        posts = data.get('data', [])
        
        if not posts:
            logger.warning("No posts found for Instagram account")
            return None
        
        # For single post queries, return latest post metrics
        if limit == 1 or len(posts) == 1:
            latest_post = posts[0]
            result = {}
            
            if "likes" in metrics or "like" in [m.lower() for m in metrics]:
                result["likes"] = latest_post.get('like_count', 0) or 0
            
            if "comments" in metrics or "comment" in [m.lower() for m in metrics]:
                result["comments"] = latest_post.get('comments_count', 0) or 0
            
            if "shares" in metrics or "share" in [m.lower() for m in metrics]:
                result["shares"] = 0  # Instagram doesn't have shares
            
            logger.info(f"✅ Fetched post metrics: {result}")
            return result if result else None
        
        # For date range queries, aggregate metrics from multiple posts
        result = {"likes": 0, "comments": 0, "shares": 0}
        for post in posts:
            result["likes"] += post.get('like_count', 0) or 0
            result["comments"] += post.get('comments_count', 0) or 0
        
        logger.info(f"✅ Aggregated post metrics from {len(posts)} posts: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error fetching Instagram post metrics: {e}", exc_info=True)
        return None


def fetch_instagram_insights(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch Instagram ACCOUNT-LEVEL insights - reuses existing API pattern"""
    try:
        # Check if user is asking for post-level metrics (likes, comments, shares)
        post_level_metrics = ["likes", "comments", "shares", "like", "comment", "share"]
        if any(m.lower() in post_level_metrics for m in metrics):
            logger.info(f"📸 Detected post-level metrics request: {metrics}, fetching post metrics instead")
            return fetch_instagram_post_metrics(connection, metrics, date_range)
        
        access_token = decrypt_token(connection.get('access_token', ''))
        account_id = connection.get('account_id', '') or connection.get('page_id', '')
        
        if not access_token or not account_id:
            logger.warning(f"Missing access_token or account_id for Instagram. account_id={account_id}, has_token={bool(access_token)}")
            return None
        
        logger.info(f"🔍 Instagram account_id: {account_id} (length: {len(str(account_id))})")
        
        # Get Instagram Business account ID (reuse existing logic from morning_scheduled_message.py)
        instagram_account_id = account_id
        # Check if this is a Facebook Page ID (typically 10-15 digits) vs Instagram Business account ID (typically 15+ digits)
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
                    logger.warning(f"   Page data: {page_data}")
                    return None
            else:
                logger.error(f"❌ Error fetching Instagram account: {page_resp.status_code} - {page_resp.text}")
                return None
        else:
            logger.info(f"✅ Using account_id as Instagram account ID: {instagram_account_id}")
        
        # Map metrics to Instagram API metrics (using valid Instagram insights metrics)
        # Valid Instagram insights metrics: impressions, reach, profile_views, website_clicks, etc.
        metric_map = {
            "reach": "reach",
            "impressions": "impressions", 
            "engagement": "profile_views",  # profile_views is closest to engagement
            "profile_visits": "profile_views",
            "website_clicks": "website_clicks",
            "email_contacts": "email_contacts",
            "phone_call_clicks": "phone_call_clicks",
            "text_message_clicks": "text_message_clicks",
            "get_directions_clicks": "get_directions_clicks"
        }
        
        # Build API metrics list - use valid Instagram metrics only (exclude post-level metrics)
        api_metrics = []
        for m in metrics:
            if m in metric_map:
                api_metrics.append(metric_map[m])
        
        # Default metrics if none specified or none valid
        if not api_metrics:
            api_metrics = ["profile_views", "website_clicks"]  # Engagement-focused defaults
        
        # Determine period (Instagram supports: day, week, days_28)
        period = "days_28" if date_range and ("month" in date_range.lower() or "30" in date_range) else \
                 "week" if date_range and ("week" in date_range.lower() or "7" in date_range) else "day"
        
        # Fetch insights (reuse existing API call pattern from social_media_connections.py)
        insights_url = f"https://graph.facebook.com/v18.0/{instagram_account_id}/insights"
        params = {"access_token": access_token, "metric": ",".join(api_metrics), "period": period}
        logger.info(f"🌐 Fetching Instagram insights from: {insights_url}")
        logger.info(f"   Metrics: {api_metrics}, Period: {period}")
        
        resp = requests.get(insights_url, params=params, timeout=15)
        if resp.status_code != 200:
            error_text = resp.text
            logger.error(f"❌ Instagram API error: {resp.status_code}")
            logger.error(f"   Error details: {error_text}")
            # Try to parse error for more details
            try:
                error_json = resp.json()
                if error_json.get('error'):
                    logger.error(f"   API Error: {error_json['error'].get('message', 'Unknown error')}")
                    logger.error(f"   Error type: {error_json['error'].get('type', 'Unknown')}")
            except:
                pass
            return None
        
        insights = resp.json()
        logger.info(f"📊 Instagram insights API response status: {resp.status_code}")
        logger.info(f"📊 Response keys: {list(insights.keys())}")
        
        result = {}
        
        # Transform response - Instagram insights API returns data as array of metric objects
        if insights.get('data'):
            logger.info(f"📊 Found {len(insights.get('data', []))} metric(s) in response")
            for metric_data in insights.get('data', []):
                name = metric_data.get('name', '')
                values = metric_data.get('values', [])
                logger.info(f"   Processing metric: {name}, has {len(values)} value(s)")
                
                if values:
                    # Get the latest value (last in array)
                    latest_value = values[-1].get('value', 0)
                    # Map back to our metric names
                    for our_metric, api_metric in metric_map.items():
                        if api_metric == name:
                            result[our_metric] = latest_value
                            logger.info(f"   ✅ Mapped {name} -> {our_metric} = {latest_value}")
                else:
                    logger.warning(f"   ⚠️ Metric {name} has no values")
        else:
            logger.warning(f"⚠️ No 'data' field in Instagram insights response")
            logger.warning(f"⚠️ Full response: {insights}")
        
        # Fetch followers count separately (not available in insights endpoint)
        if "followers" in metrics or "follower_count" in metrics:
            logger.info(f"🔍 Fetching followers count...")
            account_resp = requests.get(
                f"https://graph.facebook.com/v18.0/{instagram_account_id}",
                params={"access_token": access_token, "fields": "followers_count"},
                timeout=10
            )
            if account_resp.status_code == 200:
                account_data = account_resp.json()
                followers_count = account_data.get('followers_count', 0)
                result["followers"] = followers_count
                logger.info(f"✅ Fetched followers count: {followers_count}")
            else:
                logger.warning(f"⚠️ Could not fetch followers count: {account_resp.status_code} - {account_resp.text}")
        
        if result:
            logger.info(f"✅ Successfully fetched Instagram insights: {list(result.keys())} = {result}")
            return result
        else:
            logger.warning(f"⚠️ No insights data extracted from Instagram API response")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching Instagram insights: {e}")
        return None


def fetch_facebook_post_metrics(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch Facebook POST-LEVEL metrics (likes, comments, shares) from latest post"""
    try:
        access_token = decrypt_token(connection.get('access_token', ''))
        account_id = connection.get('account_id', '') or connection.get('page_id', '')
        
        if not access_token or not account_id:
            return None
        
        limit = 10 if date_range and ("week" in date_range.lower() or "month" in date_range.lower()) else 1
        
        logger.info(f"📘 Fetching latest Facebook post(s) for metrics: {metrics}")
        response = requests.get(
            f"https://graph.facebook.com/v18.0/{account_id}/posts",
            params={
                "access_token": access_token,
                "fields": "id,likes.summary(true),comments.summary(true),shares",
                "limit": limit
            },
            timeout=15
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Facebook posts API error: {response.status_code} - {response.text}")
            return None
        
        data = response.json()
        posts = data.get('data', [])
        
        if not posts:
            logger.warning("No posts found for Facebook page")
            return None
        
        # For single post queries
        if limit == 1 or len(posts) == 1:
            latest_post = posts[0]
            result = {}
            
            if "likes" in metrics or "like" in [m.lower() for m in metrics]:
                result["likes"] = latest_post.get('likes', {}).get('summary', {}).get('total_count', 0) or 0
            
            if "comments" in metrics or "comment" in [m.lower() for m in metrics]:
                result["comments"] = latest_post.get('comments', {}).get('summary', {}).get('total_count', 0) or 0
            
            if "shares" in metrics or "share" in [m.lower() for m in metrics]:
                result["shares"] = latest_post.get('shares', {}).get('count', 0) or 0
            
            logger.info(f"✅ Fetched Facebook post metrics: {result}")
            return result if result else None
        
        # Aggregate for date range
        result = {"likes": 0, "comments": 0, "shares": 0}
        for post in posts:
            result["likes"] += post.get('likes', {}).get('summary', {}).get('total_count', 0) or 0
            result["comments"] += post.get('comments', {}).get('summary', {}).get('total_count', 0) or 0
            result["shares"] += post.get('shares', {}).get('count', 0) or 0
        
        logger.info(f"✅ Aggregated Facebook post metrics from {len(posts)} posts: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error fetching Facebook post metrics: {e}", exc_info=True)
        return None


def fetch_facebook_insights(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch Facebook ACCOUNT-LEVEL insights - reuses existing API pattern (sync requests)"""
    try:
        # Check if user is asking for post-level metrics (likes, comments, shares)
        post_level_metrics = ["likes", "comments", "shares", "like", "comment", "share"]
        if any(m.lower() in post_level_metrics for m in metrics):
            logger.info(f"📘 Detected post-level metrics request: {metrics}, fetching post metrics instead")
            return fetch_facebook_post_metrics(connection, metrics, date_range)
        
        access_token = decrypt_token(connection.get('access_token', ''))
        account_id = connection.get('account_id', '') or connection.get('page_id', '')
        
        if not access_token or not account_id:
            return None
        
        # Map metrics to Facebook API metrics (exclude post-level metrics)
        metric_map = {
            "reach": "page_impressions_unique", "impressions": "page_impressions",
            "engagement": "page_engaged_users", "views": "page_video_views",
            "followers": "page_fans", "profile_visits": "page_profile_views"
        }
        api_metrics = [metric_map.get(m, m) for m in metrics if m in metric_map] or \
                      ["page_impressions_unique", "page_impressions", "page_engaged_users"]
        
        period = "days_28" if date_range and "month" in date_range.lower() else \
                 "week" if date_range and "week" in date_range.lower() else "day"
        
        # Fetch insights (sync requests)
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


def fetch_youtube_insights(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch YouTube channel analytics using YouTube Data API.
    
    Args:
        connection: Connection dict with access_token
        metrics: List of metrics to fetch
        date_range: Optional date range filter
    
    Returns:
        Dict with insights data or None if error
    """
    try:
        # YouTube API requires OAuth2 and different approach
        # For now, return placeholder - implement when YouTube OAuth is set up
        logger.info("YouTube insights fetching - requires YouTube Data API v3 implementation")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching YouTube insights: {e}")
        return None


def fetch_linkedin_insights(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch LinkedIn page analytics using LinkedIn API.
    
    Args:
        connection: Connection dict with access_token
        metrics: List of metrics to fetch
        date_range: Optional date range filter
    
    Returns:
        Dict with insights data or None if error
    """
    try:
        # LinkedIn API requires different OAuth flow
        # For now, return placeholder - implement when LinkedIn API is set up
        logger.info("LinkedIn insights fetching - requires LinkedIn API implementation")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching LinkedIn insights: {e}")
        return None


def fetch_twitter_insights(connection: Dict[str, Any], metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch Twitter/X analytics using Twitter API v2.
    
    Args:
        connection: Connection dict with access_token
        metrics: List of metrics to fetch
        date_range: Optional date range filter
    
    Returns:
        Dict with insights data or None if error
    """
    try:
        # Twitter API v2 requires different authentication
        # For now, return placeholder - implement when Twitter API is set up
        logger.info("Twitter insights fetching - requires Twitter API v2 implementation")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching Twitter insights: {e}")
        return None


def get_platform_insights_from_db(platform: str, user_id: str, date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch platform insights from API (main entry point for Orion).
    
    Args:
        platform: Platform name (instagram, facebook, youtube, linkedin, twitter)
        user_id: User ID
        date_range: Optional date range filter
    
    Returns:
        Dict with platform insights or None if no data/error
    """
    try:
        logger.info(f"🔍 get_platform_insights_from_db called: platform={platform}, user_id={user_id}, date_range={date_range}")
        
        # Get connection for this platform
        connection = get_platform_connection(user_id, platform)
        
        if not connection:
            logger.warning(f"❌ No active connection found for {platform}")
            return None
        
        logger.info(f"✅ Connection found for {platform}, fetching insights...")
        
        platform_lower = platform.lower()
        
        # Route to platform-specific fetcher
        if platform_lower == "instagram":
            # Use default metrics if not specified (comments and likes - mapped to engagement metrics)
            return fetch_instagram_insights(connection, ["comments", "likes"], date_range)
        elif platform_lower == "facebook":
            return fetch_facebook_insights(connection, ["reach", "impressions", "engagement"], date_range)
        elif platform_lower == "youtube":
            return fetch_youtube_insights(connection, ["views", "likes", "comments"], date_range)
        elif platform_lower == "linkedin":
            return fetch_linkedin_insights(connection, ["impressions", "clicks", "engagement"], date_range)
        elif platform_lower in ["twitter", "x"]:
            return fetch_twitter_insights(connection, ["impressions", "likes", "retweets"], date_range)
        else:
            logger.warning(f"Unsupported platform: {platform}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching platform insights: {e}")
        return None


def get_data_from_db(platform: str, user_id: str, metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch insights for specific metrics from platform API.
    
    Args:
        platform: Platform name
        user_id: User ID
        metrics: List of specific metrics to fetch
        date_range: Optional date range filter
    
    Returns:
        Dict with insights data or None if error
    """
    try:
        # Get connection
        connection = get_platform_connection(user_id, platform)
        
        if not connection:
            logger.warning(f"No active connection found for {platform}")
            return None
        
        platform_lower = platform.lower()
        
        # Route to platform-specific fetcher with specified metrics
        if platform_lower == "instagram":
            return fetch_instagram_insights(connection, metrics, date_range)
        elif platform_lower == "facebook":
            return fetch_facebook_insights(connection, metrics, date_range)
        elif platform_lower == "youtube":
            return fetch_youtube_insights(connection, metrics, date_range)
        elif platform_lower == "linkedin":
            return fetch_linkedin_insights(connection, metrics, date_range)
        elif platform_lower in ["twitter", "x"]:
            return fetch_twitter_insights(connection, metrics, date_range)
        else:
            logger.warning(f"Unsupported platform: {platform}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching data from DB: {e}")
        return None


def get_last_post_platform_from_db(user_id: str) -> Optional[str]:
    """
    Get the platform of the user's last published post.
    
    Returns:
        Platform name or None
    """
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


def get_latest_video_post_from_db(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the latest video post for watch time calculation.
    
    Returns:
        Post dict with views and total_watch_time or None
    """
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


def get_blog_insights_from_db(user_id: str, metrics: List[str], date_range: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch blog analytics (placeholder - implement when blog analytics API is available).

    Returns:
        Dict with blog insights or None
    """
    try:
        # TODO: Implement blog analytics fetching
        # This could query WordPress API, Medium API, or custom blog analytics
        logger.info("Blog insights fetching - requires blog analytics API implementation")
        return None

    except Exception as e:
        logger.error(f"Error fetching blog insights: {e}")
        return None


# ============================================================================
# ANALYTICS SNAPSHOTS - Historical Data Querying
# ============================================================================

def get_analytics_snapshots(
    user_id: str,
    platform: Optional[str] = None,
    metric: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    source: str = "social_media",
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """
    Query stored analytics snapshots from the database.

    Args:
        user_id: User ID to query snapshots for
        platform: Optional platform filter (instagram, facebook, etc.)
        metric: Optional metric filter (impressions, reach, etc.)
        date_from: Optional start date (YYYY-MM-DD)
        date_to: Optional end date (YYYY-MM-DD)
        source: Source filter (social_media or blog)
        limit: Maximum number of records to return

    Returns:
        List of analytics snapshot records
    """
    try:
        if not supabase:
            logger.error("Supabase client not initialized")
            return []

        # Build query
        query = supabase.table("analytics_snapshots").select("*").eq(
            "user_id", user_id
        ).eq("source", source)

        # Apply filters
        if platform:
            query = query.eq("platform", platform.lower())
        if metric:
            query = query.eq("metric", metric)
        if date_from:
            query = query.gte("date", date_from)
        if date_to:
            query = query.lte("date", date_to)

        # Execute query with ordering and limit
        result = query.order("date", desc=True).order("platform").order("metric").limit(limit).execute()

        logger.info(f"📊 Queried {len(result.data)} analytics snapshots for user {user_id}")
        return result.data or []

    except Exception as e:
        logger.error(f"Error querying analytics snapshots: {e}")
        return []


def get_latest_analytics_snapshot(
    user_id: str,
    platform: str,
    metric: str,
    source: str = "social_media"
) -> Optional[Dict[str, Any]]:
    """
    Get the most recent analytics snapshot for a specific metric.

    Args:
        user_id: User ID
        platform: Platform name
        metric: Metric name
        source: Source type (social_media or blog)

    Returns:
        Latest snapshot record or None
    """
    try:
        if not supabase:
            logger.error("Supabase client not initialized")
            return None

        result = supabase.table("analytics_snapshots").select("*").eq(
            "user_id", user_id
        ).eq("platform", platform.lower()).eq(
            "metric", metric
        ).eq("source", source).order("date", desc=True).limit(1).execute()

        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    except Exception as e:
        logger.error(f"Error getting latest analytics snapshot: {e}")
        return None


def get_analytics_summary(
    user_id: str,
    platform: Optional[str] = None,
    days_back: int = 30
) -> Dict[str, Any]:
    """
    Get a summary of analytics data for a user.

    Args:
        user_id: User ID
        platform: Optional platform filter
        days_back: Number of days to look back

    Returns:
        Summary dictionary with platform metrics and date ranges
    """
    try:
        from datetime import datetime, timedelta

        if not supabase:
            logger.error("Supabase client not initialized")
            return {"error": "Database not available"}

        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)

        # Query snapshots
        snapshots = get_analytics_snapshots(
            user_id=user_id,
            platform=platform,
            date_from=start_date.isoformat(),
            date_to=end_date.isoformat(),
            limit=5000  # Higher limit for summary
        )

        if not snapshots:
            return {
                "user_id": user_id,
                "platform": platform,
                "date_range": f"{start_date} to {end_date}",
                "total_snapshots": 0,
                "platforms": [],
                "metrics": [],
                "data": {}
            }

        # Analyze the data
        platforms = set()
        metrics = set()
        platform_data = {}

        for snapshot in snapshots:
            platform_name = snapshot["platform"]
            metric_name = snapshot["metric"]
            date = snapshot["date"]
            value = snapshot["value"]

            platforms.add(platform_name)
            metrics.add(metric_name)

            # Group by platform
            if platform_name not in platform_data:
                platform_data[platform_name] = {
                    "metrics": {},
                    "date_range": {"start": date, "end": date},
                    "total_records": 0
                }

            platform_data[platform_name]["total_records"] += 1

            # Update date range
            if date < platform_data[platform_name]["date_range"]["start"]:
                platform_data[platform_name]["date_range"]["start"] = date
            if date > platform_data[platform_name]["date_range"]["end"]:
                platform_data[platform_name]["date_range"]["end"] = date

            # Group metrics
            if metric_name not in platform_data[platform_name]["metrics"]:
                platform_data[platform_name]["metrics"][metric_name] = {
                    "count": 0,
                    "latest_value": value,
                    "latest_date": date,
                    "values": []
                }

            platform_data[platform_name]["metrics"][metric_name]["count"] += 1

            # Keep only recent values for summary (last 7 days)
            snapshot_date = datetime.fromisoformat(date).date()
            if snapshot_date >= (end_date - timedelta(days=7)):
                platform_data[platform_name]["metrics"][metric_name]["values"].append({
                    "date": date,
                    "value": value
                })

            # Update latest value
            if date > platform_data[platform_name]["metrics"][metric_name]["latest_date"]:
                platform_data[platform_name]["metrics"][metric_name]["latest_value"] = value
                platform_data[platform_name]["metrics"][metric_name]["latest_date"] = date

        return {
            "user_id": user_id,
            "platform_filter": platform,
            "date_range": f"{start_date} to {end_date}",
            "total_snapshots": len(snapshots),
            "platforms": sorted(list(platforms)),
            "metrics": sorted(list(metrics)),
            "platform_data": platform_data
        }

    except Exception as e:
        logger.error(f"Error generating analytics summary: {e}")
        return {"error": str(e)}


def store_analytics_snapshot(
    user_id: str,
    platform: str,
    metric: str,
    value: float,
    date: str,
    source: str = "social_media",
    post_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Store a single analytics snapshot in the database.

    Args:
        user_id: User ID
        platform: Platform name
        metric: Metric name
        value: Metric value
        date: Date in YYYY-MM-DD format
        source: Source type (social_media or blog)
        post_id: Optional post ID for post-level metrics
        metadata: Optional metadata dictionary

    Returns:
        True if successful, False otherwise
    """
    try:
        if not supabase:
            logger.error("Supabase client not initialized")
            return False

        # Prepare snapshot data
        snapshot = {
            "user_id": user_id,
            "platform": platform.lower(),
            "source": source,
            "metric": metric,
            "value": float(value) if value is not None else 0.0,
            "date": date,
            "post_id": post_id,
            "metadata": metadata or {}
        }

        # Use UPSERT to handle duplicates gracefully
        result = supabase.table("analytics_snapshots").upsert(
            snapshot,
            on_conflict="user_id,platform,source,metric,date,post_id"
        ).execute()

        success = bool(result.data)
        if success:
            logger.info(f"✅ Stored analytics snapshot: {platform}/{metric} = {value} on {date}")
        else:
            logger.warning(f"❌ Failed to store analytics snapshot: {platform}/{metric}")

        return success

    except Exception as e:
        logger.error(f"Error storing analytics snapshot: {e}")
        return False


def fetch_and_store_platform_analytics(
    user_id: str,
    platform: str,
    metrics: List[str],
    date_range: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch analytics from platform API and store in snapshots.

    This combines real-time API fetching with snapshot storage.

    Args:
        user_id: User ID
        platform: Platform name
        metrics: List of metrics to fetch
        date_range: Optional date range for historical data

    Returns:
        Dictionary with fetch and storage results
    """
    try:
        result = {
            "success": False,
            "platform": platform,
            "metrics_requested": metrics,
            "api_fetch_success": False,
            "snapshots_stored": 0,
            "errors": []
        }

        # Get platform connection
        connection = get_platform_connection(user_id, platform)
        if not connection:
            result["errors"].append(f"No active connection found for {platform}")
            return result

        # Fetch data from platform API
        platform_data = None
        if platform.lower() == "instagram":
            platform_data = fetch_instagram_insights(connection, metrics, date_range)
        elif platform.lower() == "facebook":
            platform_data = fetch_facebook_insights(connection, metrics, date_range)
        else:
            result["errors"].append(f"Platform {platform} not supported for analytics fetching")
            return result

        if not platform_data:
            result["errors"].append(f"Failed to fetch analytics data from {platform} API")
            return result

        result["api_fetch_success"] = True

        # Store each metric as a snapshot
        from datetime import datetime
        today = datetime.now().date().isoformat()
        stored_count = 0

        for metric_name, value in platform_data.items():
            if isinstance(value, (int, float)):
                success = store_analytics_snapshot(
                    user_id=user_id,
                    platform=platform,
                    metric=metric_name,
                    value=value,
                    date=today,
                    source="social_media",
                    metadata={
                        "fetched_at": datetime.now().isoformat(),
                        "date_range": date_range,
                        "fetch_method": "api_direct"
                    }
                )
                if success:
                    stored_count += 1

        result["snapshots_stored"] = stored_count
        result["success"] = stored_count > 0

        logger.info(f"📊 {platform}: Fetched {len(platform_data)} metrics, stored {stored_count} snapshots")

        return result

    except Exception as e:
        logger.error(f"Error in fetch_and_store_platform_analytics: {e}")
        return {
            "success": False,
            "platform": platform,
            "error": str(e)
        }


# ============================================================================
# UTILITY FUNCTIONS FOR MANUAL OPERATIONS
# ============================================================================

def test_token_decryption(user_id: str, platform: str) -> Dict[str, Any]:
    """
    Test token decryption for a user's platform connection.

    Returns:
        Dictionary with decryption test results
    """
    try:
        connection = get_platform_connection(user_id, platform)
        if not connection:
            return {"success": False, "error": f"No connection found for {platform}"}

        access_token = connection.get('access_token', '')
        if not access_token:
            return {"success": False, "error": "No access token found"}

        # Test decryption
        decrypted_token = decrypt_token(access_token)

        # Don't log the actual token for security
        token_length = len(decrypted_token)
        token_prefix = decrypted_token[:10] + "..." if len(decrypted_token) > 10 else decrypted_token

        return {
            "success": True,
            "platform": platform,
            "token_encrypted": bool(access_token and access_token != decrypted_token),
            "token_length": token_length,
            "token_prefix": token_prefix,
            "decryption_success": True
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def bulk_store_analytics_snapshots(
    user_id: str,
    snapshots_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Bulk store multiple analytics snapshots.

    Args:
        user_id: User ID
        snapshots_data: List of snapshot dictionaries with keys:
            - platform, metric, value, date, source, post_id, metadata

    Returns:
        Dictionary with bulk storage results
    """
    try:
        stored_count = 0
        errors = []

        for snapshot in snapshots_data:
            try:
                success = store_analytics_snapshot(
                    user_id=user_id,
                    platform=snapshot["platform"],
                    metric=snapshot["metric"],
                    value=snapshot["value"],
                    date=snapshot["date"],
                    source=snapshot.get("source", "social_media"),
                    post_id=snapshot.get("post_id"),
                    metadata=snapshot.get("metadata")
                )
                if success:
                    stored_count += 1
                else:
                    errors.append(f"Failed to store: {snapshot['platform']}/{snapshot['metric']}")
            except Exception as e:
                errors.append(f"Error storing {snapshot.get('platform', 'unknown')}/{snapshot.get('metric', 'unknown')}: {str(e)}")

        return {
            "success": stored_count > 0,
            "total_requested": len(snapshots_data),
            "stored_count": stored_count,
            "failed_count": len(errors),
            "errors": errors if errors else None
        }

    except Exception as e:
        return {"success": False, "error": str(e)}