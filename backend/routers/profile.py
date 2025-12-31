"""
Profile API endpoints
Handles profile-related operations including usage tracking
"""

import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client, Client

from routers.connections import get_current_user, User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_service_key:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

supabase_client: Client = create_client(supabase_url, supabase_service_key)

@router.get("/usage-counts")
async def get_usage_counts(current_user: User = Depends(get_current_user)):
    """Get current month's usage counts for tasks and images"""
    try:
        user_id = current_user.id

        # Simple direct query to get usage counts
        response = supabase_client.table('profiles').select('tasks_completed_this_month, images_generated_this_month').eq('id', user_id).execute()

        if response.data and len(response.data) > 0:
            profile = response.data[0]
            return {
                "tasks_count": profile.get('tasks_completed_this_month', 0),
                "images_count": profile.get('images_generated_this_month', 0)
            }
        else:
            logger.warning(f"No profile found for user {user_id}")
            return {
                "tasks_count": 0,
                "images_count": 0
            }

    except Exception as e:
        logger.error(f"Error fetching usage counts for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching usage counts: {str(e)}")

@router.post("/agents/{agent_name}/like")
async def increment_agent_likes(agent_name: str, current_user: User = Depends(get_current_user)):
    """Increment the likes count for a specific agent"""
    try:
        # Validate agent name
        valid_agents = ['emily', 'leo', 'chase', 'atsn']
        if agent_name.lower() not in valid_agents:
            raise HTTPException(status_code=400, detail=f"Invalid agent name. Must be one of: {', '.join(valid_agents)}")

        # First get current likes count
        current_response = supabase_client.table('agent_profiles').select('likes_count').eq('agent_name', agent_name.lower()).execute()

        if not current_response.data or len(current_response.data) == 0:
            raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")

        current_likes = current_response.data[0]['likes_count'] or 0

        # Increment likes count
        response = supabase_client.table('agent_profiles').update({
            'likes_count': current_likes + 1
        }).eq('agent_name', agent_name.lower()).execute()

        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to update likes count")

        logger.info(f"Incremented likes count for agent {agent_name} by user {current_user.id} (from {current_likes} to {current_likes + 1})")
        return {"success": True, "agent_name": agent_name, "new_likes_count": current_likes + 1}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error incrementing likes for agent {agent_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error incrementing likes count: {str(e)}")

@router.post("/increment-task")
async def increment_task_count(current_user: User = Depends(get_current_user)):
    """Increment task count when a task is actually completed and displayed"""
    try:
        # Read current task count and increment
        current_response = supabase_client.table('profiles').select('tasks_completed_this_month').eq('id', current_user.id).execute()

        if not current_response.data or len(current_response.data) == 0:
            raise HTTPException(status_code=404, detail="User profile not found")

        current_count = current_response.data[0]['tasks_completed_this_month'] or 0

        # Increment task count
        update_response = supabase_client.table('profiles').update({
            'tasks_completed_this_month': current_count + 1
        }).eq('id', current_user.id).execute()

        if not update_response.data:
            raise HTTPException(status_code=500, detail="Failed to update task count")

        logger.info(f"Incremented task count for user {current_user.id} after task completion (from {current_count} to {current_count + 1})")
        return {"success": True, "new_task_count": current_count + 1}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error incrementing task count for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error incrementing task count: {str(e)}")

