"""
ATSN Chatbot Router
Handles chat interactions with the ATSN agent (Content & Lead Management)
"""

import os
import sys
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import logging

# Add agents directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents.atsn import ATSNAgent
from supabase import create_client, Client
from auth import get_current_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase_client: Client = create_client(supabase_url, supabase_key)

router = APIRouter(prefix="/atsn", tags=["atsn"])


# Pydantic models for request/response
class ChatMessage(BaseModel):
    message: str
    conversation_history: Optional[List[str]] = None
    media_file: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    intent: Optional[str] = None
    payload: Optional[dict] = None
    payload_complete: bool = False
    waiting_for_user: bool = False
    clarification_question: Optional[str] = None
    clarification_options: Optional[List[dict]] = None  # Clickable options for clarification
    result: Optional[str] = None
    error: Optional[str] = None
    current_step: str
    content_id: Optional[str] = None  # Single content ID (UUID) for operations on specific content
    content_ids: Optional[List[str]] = None  # List of content IDs for selection
    lead_id: Optional[str] = None  # Single lead ID (UUID) for operations on specific lead
    content_items: Optional[List[dict]] = None  # Structured content data for frontend card rendering
    lead_items: Optional[List[dict]] = None  # Structured lead data for frontend card rendering
    needs_connection: Optional[bool] = None  # Whether user needs to connect account
    connection_platform: Optional[str] = None  # Platform to connect
    agent_name: Optional[str] = None  # Agent name for displaying appropriate icon


# Store agent instances per user session
user_agents = {}

# Store active conversation sessions per user
user_conversations = {}


def get_or_create_conversation(user_id: str, session_id: str = None) -> dict:
    """Get or create a conversation record for the user"""
    if session_id and session_id in user_conversations:
        return user_conversations[session_id]

    try:
        # If no session_id provided, check if user has an active conversation today
        if not session_id:
            today = datetime.now().date()
            result = supabase_client.table("atsn_conversations").select("id, session_id").eq("user_id", user_id).eq("conversation_date", today.isoformat()).eq("is_active", True).execute()

            if result.data and len(result.data) > 0:
                conversation = result.data[0]
                user_conversations[conversation["session_id"]] = conversation
                return conversation

        # Create new conversation
        session_id = session_id or str(uuid.uuid4())
        conversation_data = {
            "user_id": user_id,
            "session_id": session_id,
            "conversation_date": datetime.now().date().isoformat(),
            "primary_agent_name": "atsn",
            "is_active": True
        }

        result = supabase_client.table("atsn_conversations").insert(conversation_data).execute()
        conversation = result.data[0]
        user_conversations[session_id] = conversation

        logger.info(f"Created new conversation {conversation['id']} for user {user_id}")
        return conversation

    except Exception as e:
        logger.error(f"Error creating/getting conversation for user {user_id}: {e}")
        # Fallback to a dummy conversation for error resilience
        return {"id": str(uuid.uuid4()), "session_id": session_id or str(uuid.uuid4())}


def save_message_to_conversation(conversation_id: str, user_id: str, message_data: dict) -> None:
    """Save a message to the conversation messages table"""
    try:
        # Get message sequence number
        sequence_result = supabase_client.table("atsn_conversation_messages").select("message_sequence").eq("conversation_id", conversation_id).order("message_sequence", desc=True).limit(1).execute()

        sequence = 1
        if sequence_result.data and len(sequence_result.data) > 0:
            sequence = sequence_result.data[0]["message_sequence"] + 1

        message_record = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "message_sequence": sequence,
            **message_data
        }

        supabase_client.table("atsn_conversation_messages").insert(message_record).execute()
        logger.info(f"Saved {message_data.get('message_type', 'unknown')} message to conversation {conversation_id}")

    except Exception as e:
        logger.error(f"Error saving message to conversation {conversation_id}: {e}")


def get_user_agent(user_id: str) -> ATSNAgent:
    """Get or create ATSN agent for user"""
    if user_id not in user_agents:
        user_agents[user_id] = ATSNAgent(user_id=user_id)
        logger.info(f"Created new ATSN agent for user {user_id}")
    return user_agents[user_id]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    chat_message: ChatMessage,
    current_user=Depends(get_current_user)
):
    """
    Handle chat messages with ATSN agent
    """
    try:
        user_id = current_user.id
        logger.info(f"ATSN chat request from user {user_id}: {chat_message.message}")

        # Get or create conversation for this user
        conversation = get_or_create_conversation(user_id)

        # Save user message to conversation history
        try:
            user_message_data = {
                "message_type": "user",
                "content": chat_message.message,
                "agent_name": "atsn"
            }
            save_message_to_conversation(conversation["id"], user_id, user_message_data)
        except Exception as e:
            logger.error(f"Error saving ATSN user message to conversation history: {e}")

        # Get user's agent instance
        agent = get_user_agent(user_id)
        
        # Process the query
        response = agent.process_query(
            user_query=chat_message.message,
            conversation_history=chat_message.conversation_history,
            user_id=user_id,
            media_file=chat_message.media_file
        )
        
        # Format response - ensure we always have a valid response string
        response_text = (
            response.get('clarification_question') or 
            response.get('result') or 
            response.get('error') or 
            'I received your message. How can I help you?'
        )
        
        # Determine agent name based on intent
        agent_name = 'emily'  # default
        intent = response.get('intent')
        if intent:
            if 'lead' in intent.lower():
                agent_name = 'chase'
            elif intent.lower() in ['view_content', 'publish_content', 'delete_content']:
                agent_name = 'emily'
            elif intent.lower() in ['create_content', 'edit_content', 'schedule_content']:
                agent_name = 'leo'
            elif 'orio' in intent.lower() or 'analytics' in intent.lower():
                agent_name = 'orio'

        chat_response = ChatResponse(
            response=response_text,
            intent=response.get('intent'),
            payload=response.get('payload'),
            payload_complete=response.get('payload_complete', False),
            waiting_for_user=response.get('waiting_for_user', False),
            clarification_question=response.get('clarification_question'),
            clarification_options=response.get('clarification_options', []),
            result=response.get('result'),
            error=response.get('error'),
            current_step=response.get('current_step', 'unknown'),
            content_id=response.get('content_id'),  # Single content ID (UUID)
            content_ids=response.get('content_ids'),  # List of content IDs for selection
            lead_id=response.get('lead_id'),  # Single lead ID (UUID)
            content_items=response.get('content_items'),  # Structured content data for frontend cards
            lead_items=response.get('lead_items'),  # Structured lead data for frontend cards
            needs_connection=response.get('needs_connection'),  # Whether user needs to connect account
            connection_platform=response.get('connection_platform'),  # Platform to connect
            agent_name=agent_name
        )

        # Save bot response to conversation history
        try:
            bot_message_data = {
                "message_type": "bot",
                "content": response_text,
                "agent_name": agent_name,
                "intent": response.get('intent'),
                "current_step": response.get('current_step', 'unknown'),
                "clarification_question": response.get('clarification_question'),
                "clarification_options": response.get('clarification_options'),
                "content_items": response.get('content_items'),
                "lead_items": response.get('lead_items')
            }
            save_message_to_conversation(conversation["id"], user_id, bot_message_data)

            # Note: Task count increment moved to frontend after task completion display
            # Note: Image count increment moved to after successful image generation in atsn.py

        except Exception as e:
            logger.error(f"Error saving ATSN bot response to conversation history: {e}")
        
        logger.info(f"ATSN response - Intent: {chat_response.intent}, Step: {chat_response.current_step}, Waiting: {chat_response.waiting_for_user}")
        
        return chat_response
        
    except Exception as e:
        logger.error(f"Error in ATSN chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@router.post("/reset")
async def reset_agent(current_user=Depends(get_current_user)):
    """
    Reset the agent for the current user
    """
    try:
        user_id = current_user.id
        
        if user_id in user_agents:
            user_agents[user_id].reset()
            logger.info(f"Reset ATSN agent for user {user_id}")
            return {"message": "Agent reset successfully"}
        else:
            return {"message": "No active agent to reset"}
            
    except Exception as e:
        logger.error(f"Error resetting ATSN agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


@router.get("/status")
async def get_status(current_user=Depends(get_current_user)):
    """
    Get current agent status
    """
    try:
        user_id = current_user.id
        
        if user_id in user_agents:
            agent = user_agents[user_id]
            state = agent.state
            
            if state:
                return {
                    "active": True,
                    "intent": state.intent,
                    "current_step": state.current_step,
                    "waiting_for_user": state.waiting_for_user,
                    "payload_complete": state.payload_complete
                }
        
        return {
            "active": False,
            "message": "No active agent session"
        }
        
    except Exception as e:
        logger.error(f"Error getting ATSN status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    from agents.atsn import supabase

    return {
        "status": "healthy",
        "service": "atsn_chatbot",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "supabase_configured": bool(supabase)
    }


@router.get("/conversations")
async def get_atsn_conversations(
    current_user=Depends(get_current_user),
    date: str = Query(None, description="Get conversations for specific date (YYYY-MM-DD)"),
    all: bool = Query(False, description="Get all conversations instead of just today's")
):
    """Get ATSN conversations for current user"""
    try:
        user_id = current_user.id
        logger.info(f"Fetching ATSN conversations for user {user_id}, date={date}, all={all}")

        # Get conversations
        query = supabase_client.table("atsn_conversations").select("*").eq("user_id", user_id)

        if not all:
            target_date = date if date else datetime.now().date().isoformat()
            query = query.eq("conversation_date", target_date)

        conversations_result = query.order("created_at", desc=True).execute()
        conversations = conversations_result.data if conversations_result.data else []

        # For each conversation, get the messages
        conversations_with_messages = []
        for conv in conversations:
            # Get messages for this conversation
            messages_result = supabase_client.table("atsn_conversation_messages").select("*").eq("conversation_id", conv["id"]).order("message_sequence", desc=False).execute()
            messages = messages_result.data if messages_result.data else []

            # Convert messages to frontend format
            formatted_messages = []
            for msg in messages:
                formatted_msg = {
                    "id": f"msg-{msg['id']}",
                    "sender": msg["message_type"],
                    "text": msg["content"],
                    "timestamp": msg["created_at"],
                    "intent": msg.get("intent"),
                    "agent_name": msg.get("agent_name"),
                    "current_step": msg.get("current_step"),
                    "clarification_question": msg.get("clarification_question"),
                    "clarification_options": msg.get("clarification_options"),
                    "content_items": msg.get("content_items"),
                    "lead_items": msg.get("lead_items")
                }
                formatted_messages.append(formatted_msg)

            conversations_with_messages.append({
                "id": conv["id"],
                "session_id": conv["session_id"],
                "conversation_date": conv["conversation_date"],
                "primary_agent_name": conv["primary_agent_name"],
                "total_messages": len(formatted_messages),
                "messages": formatted_messages,
                "created_at": conv["created_at"],
                "updated_at": conv["updated_at"]
            })

        logger.info(f"Returning {len(conversations_with_messages)} ATSN conversations for user {user_id}")
        return {
            "conversations": conversations_with_messages,
            "count": len(conversations_with_messages)
        }

    except Exception as e:
        logger.error(f"Error fetching ATSN conversations: {str(e)}", exc_info=True)
        return {
            "conversations": [],
            "count": 0
        }
