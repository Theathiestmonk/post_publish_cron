"""
Analytics Insights Module - Facebook & Instagram Insights Storage
This module fetches insights using read_insights and instagram_manage_insights scopes
and stores them in the analytics_snapshots table for historical tracking.
"""

import os
import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from supabase import create_client, Client
import httpx
from dotenv import load_dotenv

# Import auth utilities
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth import get_current_user, User

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/analytics-insights", tags=["analytics-insights"])


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt access token - reusing the same encryption method used in connections"""
    try:
        from cryptography.fernet import Fernet
        
        # Get encryption key from environment
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            logger.warning("No encryption key found, returning token as-is")
            return encrypted_token
        
        # Decrypt token
        fernet = Fernet(encryption_key.encode())
        decrypted = fernet.decrypt(encrypted_token.encode())
        return decrypted.decode()
    except Exception as e:
        logger.warning(f"Failed to decrypt token: {e}, returning as-is")
        return encrypted_token


async def get_facebook_connection(user_id: str) -> Optional[Dict[str, Any]]:
    """Get active Facebook connection for a user"""
    try:
        result = supabase.table("social_media_connections").select("*").eq(
            "user_id", user_id
        ).eq("platform", "facebook").eq("is_active", True).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching Facebook connection: {e}")
        return None


async def get_instagram_connection(user_id: str) -> Optional[Dict[str, Any]]:
    """Get active Instagram connection for a user"""
    try:
        result = supabase.table("social_media_connections").select("*").eq(
            "user_id", user_id
        ).eq("platform", "instagram").eq("is_active", True).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching Instagram connection: {e}")
        return None


async def fetch_facebook_page_insights(
    page_id: str, 
    access_token: str, 
    metrics: List[str],
    period: str = "day",
    since: Optional[str] = None,
    until: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch Facebook Page insights using the Graph API with read_insights scope
    
    Args:
        page_id: Facebook Page ID
        access_token: Page access token with read_insights permission
        metrics: List of metrics to fetch (e.g., ['page_impressions', 'page_engaged_users'])
        period: Time period ('day', 'week', 'days_28')
        since: Start date (YYYY-MM-DD format or Unix timestamp)
        until: End date (YYYY-MM-DD format or Unix timestamp)
    
    Returns:
        Dictionary containing insights data
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://graph.facebook.com/v18.0/{page_id}/insights"
            
            params = {
                "access_token": access_token,
                "metric": ",".join(metrics),
                "period": period
            }
            
            # Add date range if provided
            if since:
                params["since"] = since
            if until:
                params["until"] = until
            
            logger.info(f"📊 Fetching Facebook insights for page {page_id}")
            logger.info(f"   Metrics: {metrics}")
            logger.info(f"   Period: {period}, Since: {since}, Until: {until}")
            
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Facebook API error: {response.status_code} - {response.text}")
                return {"error": f"Failed to fetch insights: {response.text}"}
            
            data = response.json()
            logger.info(f"✅ Successfully fetched {len(data.get('data', []))} metric(s)")
            
            return data
            
    except Exception as e:
        logger.error(f"Error fetching Facebook insights: {e}")
        return {"error": str(e)}


async def fetch_instagram_account_insights(
    instagram_account_id: str,
    access_token: str,
    metrics: List[str],
    period: str = "day",
    since: Optional[str] = None,
    until: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch Instagram Business account insights using instagram_manage_insights scope
    
    Args:
        instagram_account_id: Instagram Business Account ID
        access_token: Access token with instagram_manage_insights permission
        metrics: List of metrics to fetch (e.g., ['impressions', 'reach', 'profile_views'])
        period: Time period ('day', 'week', 'days_28', 'lifetime')
        since: Start date (Unix timestamp)
        until: End date (Unix timestamp)
    
    Returns:
        Dictionary containing insights data
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://graph.facebook.com/v18.0/{instagram_account_id}/insights"
            
            params = {
                "access_token": access_token,
                "metric": ",".join(metrics),
                "period": period
            }
            
            # Add date range if provided
            if since:
                params["since"] = since
            if until:
                params["until"] = until
            
            logger.info(f"📊 Fetching Instagram insights for account {instagram_account_id}")
            logger.info(f"   Metrics: {metrics}")
            logger.info(f"   Period: {period}, Since: {since}, Until: {until}")
            
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Instagram API error: {response.status_code} - {response.text}")
                return {"error": f"Failed to fetch insights: {response.text}"}
            
            data = response.json()
            logger.info(f"✅ Successfully fetched {len(data.get('data', []))} metric(s)")
            
            return data
            
    except Exception as e:
        logger.error(f"Error fetching Instagram insights: {e}")
        return {"error": str(e)}


async def store_insights_in_snapshots(
    user_id: str,
    platform: str,
    insights_data: Dict[str, Any],
    post_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Store insights data in the analytics_snapshots table
    
    Args:
        user_id: User ID
        platform: Platform name ('facebook' or 'instagram')
        insights_data: Insights data from Facebook/Instagram API
        post_id: Optional post ID for post-level metrics
    
    Returns:
        Dictionary with storage results
    """
    try:
        stored_count = 0
        errors = []
        
        # Parse insights data
        insights_list = insights_data.get("data", [])
        
        for insight in insights_list:
            metric_name = insight.get("name")
            period = insight.get("period")
            values = insight.get("values", [])
            
            # Process each value entry
            for value_entry in values:
                value = value_entry.get("value", 0)
                end_time = value_entry.get("end_time")
                
                # Parse date from end_time
                if end_time:
                    try:
                        # Handle both ISO format and Unix timestamp
                        if isinstance(end_time, str):
                            snapshot_date = datetime.fromisoformat(end_time.replace('Z', '+00:00')).date()
                        else:
                            snapshot_date = datetime.fromtimestamp(end_time).date()
                    except:
                        snapshot_date = date.today()
                else:
                    snapshot_date = date.today()
                
                # Handle nested value dictionaries (e.g., demographic breakdowns)
                if isinstance(value, dict):
                    # Store aggregate or skip detailed breakdowns for now
                    # You can customize this to store breakdowns in metadata
                    value = sum(value.values()) if value else 0
                
                # Prepare snapshot record
                snapshot_record = {
                    "user_id": user_id,
                    "platform": platform,
                    "source": "social_media",
                    "metric": metric_name,
                    "value": float(value) if value is not None else 0.0,
                    "date": snapshot_date.isoformat(),
                    "post_id": post_id,
                    "metadata": {
                        "period": period,
                        "api_response": value_entry
                    }
                }
                
                try:
                    # Use upsert to handle duplicates (unique constraint)
                    result = supabase.table("analytics_snapshots").upsert(
                        snapshot_record,
                        on_conflict="user_id,platform,source,metric,date,post_id"
                    ).execute()
                    
                    stored_count += 1
                    logger.info(f"✅ Stored {metric_name} for {snapshot_date}")
                    
                except Exception as e:
                    error_msg = f"Failed to store {metric_name}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        
        return {
            "success": True,
            "stored_count": stored_count,
            "errors": errors if errors else None,
            "message": f"Successfully stored {stored_count} analytics snapshot(s)"
        }
        
    except Exception as e:
        logger.error(f"Error storing insights in snapshots: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/fetch-facebook-insights")
async def fetch_and_store_facebook_insights(
    days_back: int = 7,
    current_user: User = Depends(get_current_user)
):
    """
    Fetch Facebook Page insights and store them in analytics_snapshots
    
    Args:
        days_back: Number of days of historical data to fetch (default: 7)
    """
    try:
        user_id = current_user.id
        logger.info(f"📊 Fetching Facebook insights for user {user_id}")
        
        # Get Facebook connection
        connection = await get_facebook_connection(user_id)
        if not connection:
            raise HTTPException(status_code=404, detail="No active Facebook connection found")
        
        # Decrypt access token
        access_token = decrypt_token(connection["access_token"])
        page_id = connection["account_id"]
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Convert to Unix timestamps
        since = int(start_date.timestamp())
        until = int(end_date.timestamp())
        
        # Define metrics to fetch
        # Page-level metrics available with read_insights
        facebook_metrics = [
            "page_impressions",           # Total impressions
            "page_impressions_unique",    # Reach (unique impressions)
            "page_engaged_users",         # Users who engaged
            "page_post_engagements",      # Total engagements on posts
            "page_fans",                  # Total page likes
            "page_views_total",           # Page views
            "page_video_views",           # Video views
            "page_posts_impressions",     # Post impressions
        ]
        
        # Fetch insights
        insights_data = await fetch_facebook_page_insights(
            page_id=page_id,
            access_token=access_token,
            metrics=facebook_metrics,
            period="day",
            since=str(since),
            until=str(until)
        )
        
        if "error" in insights_data:
            raise HTTPException(status_code=400, detail=insights_data["error"])
        
        # Store in analytics_snapshots
        storage_result = await store_insights_in_snapshots(
            user_id=user_id,
            platform="facebook",
            insights_data=insights_data
        )
        
        # Update last sync time
        supabase.table("social_media_connections").update({
            "last_sync_at": datetime.utcnow().isoformat()
        }).eq("id", connection["id"]).execute()
        
        return {
            "success": True,
            "platform": "facebook",
            "page_id": page_id,
            "days_fetched": days_back,
            "storage_result": storage_result,
            "raw_insights": insights_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in fetch_and_store_facebook_insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fetch-instagram-insights")
async def fetch_and_store_instagram_insights(
    days_back: int = 7,
    current_user: User = Depends(get_current_user)
):
    """
    Fetch Instagram Business account insights and store them in analytics_snapshots
    
    Args:
        days_back: Number of days of historical data to fetch (default: 7)
    """
    try:
        user_id = current_user.id
        logger.info(f"📊 Fetching Instagram insights for user {user_id}")
        
        # Get Instagram connection
        connection = await get_instagram_connection(user_id)
        if not connection:
            raise HTTPException(status_code=404, detail="No active Instagram connection found")
        
        # Decrypt access token
        access_token = decrypt_token(connection["access_token"])
        instagram_account_id = connection["account_id"]
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Convert to Unix timestamps
        since = int(start_date.timestamp())
        until = int(end_date.timestamp())
        
        # Define metrics to fetch
        # Account-level metrics available with instagram_manage_insights
        instagram_metrics = [
            "impressions",                # Total impressions
            "reach",                      # Reach (unique accounts)
            "profile_views",              # Profile views
            "follower_count",             # Total followers
            "email_contacts",             # Email contacts
            "phone_call_clicks",          # Phone call clicks
            "text_message_clicks",        # Text message clicks
            "get_directions_clicks",      # Get directions clicks
            "website_clicks",             # Website clicks
        ]
        
        # Fetch insights
        insights_data = await fetch_instagram_account_insights(
            instagram_account_id=instagram_account_id,
            access_token=access_token,
            metrics=instagram_metrics,
            period="day",
            since=str(since),
            until=str(until)
        )
        
        if "error" in insights_data:
            raise HTTPException(status_code=400, detail=insights_data["error"])
        
        # Store in analytics_snapshots
        storage_result = await store_insights_in_snapshots(
            user_id=user_id,
            platform="instagram",
            insights_data=insights_data
        )
        
        # Update last sync time
        supabase.table("social_media_connections").update({
            "last_sync_at": datetime.utcnow().isoformat()
        }).eq("id", connection["id"]).execute()
        
        return {
            "success": True,
            "platform": "instagram",
            "account_id": instagram_account_id,
            "days_fetched": days_back,
            "storage_result": storage_result,
            "raw_insights": insights_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in fetch_and_store_instagram_insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fetch-all-insights")
async def fetch_and_store_all_insights(
    days_back: int = 7,
    current_user: User = Depends(get_current_user)
):
    """
    Fetch insights from both Facebook and Instagram and store in analytics_snapshots
    
    Args:
        days_back: Number of days of historical data to fetch (default: 7)
    """
    try:
        user_id = current_user.id
        results = {
            "facebook": None,
            "instagram": None
        }
        
        # Try to fetch Facebook insights
        try:
            facebook_result = await fetch_and_store_facebook_insights(days_back, current_user)
            results["facebook"] = facebook_result
        except HTTPException as e:
            results["facebook"] = {"error": e.detail}
        except Exception as e:
            results["facebook"] = {"error": str(e)}
        
        # Try to fetch Instagram insights
        try:
            instagram_result = await fetch_and_store_instagram_insights(days_back, current_user)
            results["instagram"] = instagram_result
        except HTTPException as e:
            results["instagram"] = {"error": e.detail}
        except Exception as e:
            results["instagram"] = {"error": str(e)}
        
        return {
            "success": True,
            "message": "Completed fetching insights for available platforms",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in fetch_and_store_all_insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query-snapshots")
async def query_analytics_snapshots(
    platform: Optional[str] = None,
    metric: Optional[str] = None,
    days_back: int = 30,
    current_user: User = Depends(get_current_user)
):
    """
    Query analytics snapshots from the database
    
    Args:
        platform: Filter by platform ('facebook' or 'instagram')
        metric: Filter by specific metric
        days_back: Number of days to query (default: 30)
    """
    try:
        user_id = current_user.id
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        # Build query
        query = supabase.table("analytics_snapshots").select("*").eq(
            "user_id", user_id
        ).eq("source", "social_media").gte(
            "date", start_date.isoformat()
        ).lte(
            "date", end_date.isoformat()
        )
        
        # Apply filters
        if platform:
            query = query.eq("platform", platform.lower())
        if metric:
            query = query.eq("metric", metric)
        
        # Execute query
        result = query.order("date", desc=True).execute()
        
        return {
            "success": True,
            "count": len(result.data),
            "snapshots": result.data,
            "filters": {
                "platform": platform,
                "metric": metric,
                "days_back": days_back
            }
        }
        
    except Exception as e:
        logger.error(f"Error querying analytics snapshots: {e}")
        raise HTTPException(status_code=500, detail=str(e))

