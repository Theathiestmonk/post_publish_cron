"""
Chatbot API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import Optional, Generator, List, Dict
from datetime import datetime, timedelta, timezone, date, time, time
import logging

logger = logging.getLogger(__name__)
import os
import json
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()

# Import the chatbot agent
from agents.chatbot_agent import get_chatbot_response, get_chatbot_response_stream, search_business_news, get_user_profile
# Import the intent-based chatbot
from agents.emily import get_intent_based_response, get_intent_based_response_stream, clear_partial_payload_cache
from supabase import create_client, Client

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase_client: Client = create_client(supabase_url, supabase_key)

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

# Initialize OpenAI client for TTS
openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = None
if openai_api_key:
    openai_client = openai.OpenAI(api_key=openai_api_key)

class User(BaseModel):
    id: str
    email: str
    name: str
    created_at: str

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None  # Previous messages for context

class EveningNewsRequest(BaseModel):
    user_id: Optional[str] = None

class TTSRequest(BaseModel):
    text: str

class ChatResponse(BaseModel):
    response: str
    user_id: str
    timestamp: str

def get_current_user(authorization: str = Header(None)):
    """Get current user from Supabase JWT token"""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            logger.warning("Missing or invalid authorization header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header"
            )
        
        # Extract token
        try:
            token = authorization.split(" ")[1]
        except IndexError:
            logger.warning("Invalid authorization header format")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format"
            )
        
        # Verify token with Supabase
        try:
            response = supabase_client.auth.get_user(token)
            if not response or not response.user:
                logger.warning("Invalid token - no user found")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
        except Exception as auth_error:
            logger.error(f"Supabase auth error: {str(auth_error)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate token"
            )
        
        # Convert created_at to string if it's a datetime object
        try:
            created_at_str = response.user.created_at
            if hasattr(created_at_str, 'isoformat'):
                created_at_str = created_at_str.isoformat()
            else:
                created_at_str = str(created_at_str)
        except Exception:
            created_at_str = datetime.now().isoformat()
        
        user_obj = User(
            id=response.user.id,
            email=response.user.email or "unknown@example.com",
            name=response.user.user_metadata.get("name", response.user.email) if response.user.user_metadata else response.user.email or "Unknown",
            created_at=created_at_str
        )
        
        logger.debug(f"Authenticated user: {user_obj.id}")
        return user_obj
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating user token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

@router.post("/chat", response_model=ChatResponse)
async def chat_with_bot(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """Chat with the business assistant bot"""
    try:
        # Use the user_id from the request or fall back to current user
        user_id = request.user_id or current_user.id
        
        # Get response from chatbot
        response = get_chatbot_response(user_id, request.message, request.conversation_history)
        
        return ChatResponse(
            response=response,
            user_id=user_id,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat request: {str(e)}"
        )

@router.post("/chat/stream")
async def chat_with_bot_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """Stream chat response from the business assistant bot"""
    try:
        # Use the user_id from the request or fall back to current user
        user_id = request.user_id or current_user.id
        
        # Save user message to conversation history
        try:
            user_message_data = {
                "user_id": user_id,
                "message_type": "user",
                "content": request.message,
                "metadata": {}
            }
            supabase_client.table("chatbot_conversations").insert(user_message_data).execute()
        except Exception as e:
            logger.error(f"Error saving user message to conversation history: {e}")
        
        full_response = ""
        
        def generate_stream() -> Generator[str, None, None]:
            nonlocal full_response
            try:
                for chunk in get_chatbot_response_stream(user_id, request.message, request.conversation_history):
                    full_response += chunk
                    # Format as Server-Sent Events
                    yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                
                # Save bot response to conversation history after streaming completes
                try:
                    bot_message_data = {
                        "user_id": user_id,
                        "message_type": "bot",
                        "content": full_response,
                        "metadata": {}
                    }
                    supabase_client.table("chatbot_conversations").insert(bot_message_data).execute()
                except Exception as e:
                    logger.error(f"Error saving bot response to conversation history: {e}")
                
                # Send final done message
                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"
                
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                yield f"data: {json.dumps({'content': error_msg, 'done': True, 'error': True})}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing streaming chat request: {str(e)}"
        )

@router.post("/chat/v2")
async def chat_with_bot_v2(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """Chat with the intent-based business assistant bot (v2)"""
    try:
        # Use the user_id from the request or fall back to current user
        user_id = request.user_id or current_user.id
        
        # Get response from intent-based chatbot
        result = get_intent_based_response(user_id, request.message, request.conversation_history)
        
        return {
            "response": result.get("response", ""),
            "options": result.get("options"),
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in chat_with_bot_v2: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat request: {str(e)}"
        )

@router.post("/chat/v2/stream")
async def chat_with_bot_v2_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """Stream chat response from the intent-based business assistant bot (v2)"""
    try:
        # Use the user_id from the request or fall back to current user
        user_id = request.user_id or current_user.id
        
        # Save user message to conversation history
        try:
            user_message_data = {
                "user_id": user_id,
                "message_type": "user",
                "content": request.message,
                "metadata": {}
            }
            supabase_client.table("chatbot_conversations").insert(user_message_data).execute()
        except Exception as e:
            logger.error(f"Error saving user message to conversation history: {e}")
        
        full_response = ""
        
        def generate_stream() -> Generator[str, None, None]:
            nonlocal full_response
            options = None
            content_data = None
            try:
                for chunk in get_intent_based_response_stream(user_id, request.message, request.conversation_history):
                    # Check if chunk contains options
                    if chunk.startswith('\n\nOPTIONS:'):
                        try:
                            options_json = chunk.replace('\n\nOPTIONS:', '')
                            options = json.loads(options_json)
                            # Send options separately
                            yield f"data: {json.dumps({'options': options, 'done': False})}\n\n"
                            continue
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse options from chunk: {chunk}")
                    
                    # Check if chunk contains content_data
                    if chunk.startswith('\n\nCONTENT_DATA:'):
                        try:
                            content_data_json = chunk.replace('\n\nCONTENT_DATA:', '')
                            content_data = json.loads(content_data_json)
                            logger.info(f"📤 Parsed content_data from stream: {json.dumps(content_data, default=str)[:200]}...")
                            logger.info(f"   Images in content_data: {content_data.get('images')}")
                            # Send content_data separately
                            sse_data = {'content_data': content_data, 'done': False}
                            logger.info(f"📡 Sending content_data SSE event: {json.dumps(sse_data, default=str)[:200]}...")
                            yield f"data: {json.dumps(sse_data, default=str)}\n\n"
                            continue
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse content_data from chunk: {chunk[:200]}... Error: {e}")
                        except Exception as e:
                            logger.error(f"Error processing content_data chunk: {e}", exc_info=True)
                    
                    # Only add to full_response if it's not the OPTIONS or CONTENT_DATA chunk
                    if not chunk.startswith('\n\nOPTIONS:') and not chunk.startswith('\n\nCONTENT_DATA:'):
                        full_response += chunk
                        # Format as Server-Sent Events
                        yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                
                # Save bot response to conversation history after streaming completes
                try:
                    bot_message_data = {
                        "user_id": user_id,
                        "message_type": "bot",
                        "content": full_response,
                        "metadata": {
                            "options": options if options else None,
                            "content_data": content_data if content_data else None
                        }
                    }
                    supabase_client.table("chatbot_conversations").insert(bot_message_data).execute()
                except Exception as e:
                    logger.error(f"Error saving bot response to conversation history: {e}")
                
                # Send final done message with options and content_data if available
                done_message = {
                    'content': '', 
                    'done': True, 
                    'options': options, 
                    'content_data': content_data
                }
                logger.info(f"📤 Sending final done message with content_data: {content_data is not None}")
                if content_data:
                    logger.info(f"   Content_data images: {content_data.get('images')}")
                yield f"data: {json.dumps(done_message, default=str)}\n\n"
                
            except Exception as e:
                logger.error(f"Error in generate_stream: {e}", exc_info=True)
                # Send error but preserve any content we already sent
                error_msg = f"Error: {str(e)}"
                yield f"data: {json.dumps({'content': error_msg, 'done': True, 'error': True, 'options': options})}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
        
    except Exception as e:
        logger.error(f"Error in chat_with_bot_v2_stream: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing streaming chat request: {str(e)}"
        )

@router.post("/evening-news")
async def get_evening_news(
    request: EveningNewsRequest,
    current_user: User = Depends(get_current_user)
):
    """Get evening news for the user's business"""
    try:
        # Use the user_id from the request or fall back to current user
        user_id = request.user_id or current_user.id
        
        # Get user profile
        profile_result = get_user_profile.invoke({"user_id": user_id})
        
        if not profile_result.get("success") or not profile_result.get("profile"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        profile = profile_result["profile"]
        business_description = profile.get("business_description", "")
        industry = profile.get("industry", "technology")
        
        # Handle industry if it's a list
        if isinstance(industry, list) and len(industry) > 0:
            industry = industry[0]
        elif not isinstance(industry, str):
            industry = "technology"
        
        # Search for business news
        news_result = search_business_news.invoke({
            "business_description": business_description,
            "industry": industry
        })
        
        if news_result.get("success") and news_result.get("news"):
            news = news_result["news"]
            # Format the news message
            formatted_content = f"I found an exciting news update for you!\n\n**{news.get('title', 'Latest News')}**\n\n{news.get('content', '')}\n\nWould you like me to generate a social media post based on this news?"
            
            return {
                "success": True,
                "news": {
                    **news,
                    "formatted_content": formatted_content
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch news"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching evening news: {str(e)}"
        )

@router.post("/tts")
async def text_to_speech(
    request: TTSRequest,
    current_user: User = Depends(get_current_user)
):
    """Convert text to speech using OpenAI TTS API with a female voice"""
    try:
        if not openai_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenAI API key not configured"
            )
        
        # Clean text (remove markdown formatting)
        import re
        clean_text = re.sub(r'[#*_`\[\]()]', '', request.text).strip()
        
        if not clean_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text cannot be empty"
            )
        
        # Use OpenAI TTS API with "nova" voice (best female voice)
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice="nova",  # Best female voice
            input=clean_text,
            speed=1.0
        )
        
        # Get the audio data
        audio_data = response.content
        
        # Return audio as response
        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=speech.mp3"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating TTS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating speech: {str(e)}"
        )

@router.get("/post-reminder")
async def get_post_reminder(
    current_user: User = Depends(get_current_user)
):
    """Get post reminder for today - always generates and adds to conversation"""
    try:
        from agents.scheduled_messages import generate_post_reminder_message, get_user_timezone
        import pytz
        from datetime import datetime as dt
        
        user_id = current_user.id
        user_tz = get_user_timezone(user_id)
        
        # Check if reminder already exists in conversations for today
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        # Check if post_reminder message exists in conversations for today
        existing_response = supabase_client.table("chatbot_conversations").select("id").eq(
            "user_id", user_id
        ).eq("intent", "post_reminder").gte(
            "created_at", today_start.isoformat()
        ).lte(
            "created_at", today_end.isoformat()
        ).execute()
        
        if existing_response.data and len(existing_response.data) > 0:
            # Reminder already exists in conversations, return empty
            return {
                "success": True,
                "shown": True,
                "message": None,
                "posts": []
            }
        
        # Generate reminder message
        reminder_data = generate_post_reminder_message(user_id, user_tz)
        
        if not reminder_data.get("success"):
            return {
                "success": False,
                "error": reminder_data.get("error", "Failed to generate reminder")
            }
        
        # Create message content
        message_content = reminder_data.get("content", "Reminder for your posts for today:")
        if not reminder_data.get("has_posts", False):
            message_content += "\n\nNo posts for today. Generate one with Leo"
        
        # Add to conversation history (like other scheduled messages)
        now_utc = datetime.now(timezone.utc)
        conversation_data = {
            "user_id": user_id,
            "message_type": "bot",
            "content": message_content,
            "intent": "post_reminder",
            "created_at": now_utc.isoformat(),
            "metadata": {
                "has_posts": reminder_data.get("has_posts", False),
                "post_count": reminder_data.get("post_count", 0),
                "posts": reminder_data.get("posts", [])
            }
        }
        
        try:
            conversation_response = supabase_client.table("chatbot_conversations").insert(conversation_data).execute()
            logger.info(f"Post reminder added to conversations for user {user_id}")
        except Exception as e:
            logger.error(f"Error saving post reminder to conversations: {e}")
        
        return {
            "success": True,
            "shown": False,
            "message": message_content,
            "posts": reminder_data.get("posts", []),
            "has_posts": reminder_data.get("has_posts", False),
            "post_count": reminder_data.get("post_count", 0)
        }
        
    except Exception as e:
        logger.error(f"Error getting post reminder: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting post reminder: {str(e)}"
        )

@router.post("/chat/v2/refresh")
async def refresh_chat_v2(
    current_user: User = Depends(get_current_user)
):
    """Clear the partial payload cache and reset the intent-based chatbot state for a user"""
    try:
        user_id = current_user.id
        clear_partial_payload_cache(user_id)
        logger.info(f"Refreshed chat state for user {user_id}")
        return {
            "success": True,
            "message": "Chat state refreshed successfully"
        }
    except Exception as e:
        logger.error(f"Error refreshing chat state: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error refreshing chat state: {str(e)}"
        )

@router.get("/health")
async def chatbot_health():
    """Health check for chatbot service"""
    return {
        "status": "healthy",
        "service": "business_chatbot",
        "capabilities": [
            "scheduled_posts",
            "performance_insights", 
            "industry_trends"
        ]
    }

@router.get("/capabilities")
async def get_capabilities():
    """Get chatbot capabilities"""
    return {
        "capabilities": {
            "scheduled_posts": {
                "description": "Tell you about your next scheduled posts",
                "example_queries": [
                    "What's my next scheduled post?",
                    "When is my next Facebook post?",
                    "Show me my upcoming content"
                ]
            },
            "performance_insights": {
                "description": "Analyze your social media performance",
                "example_queries": [
                    "How are my posts performing?",
                    "Show me my latest Instagram insights",
                    "What's my engagement rate?"
                ]
            },
            "industry_trends": {
                "description": "Get latest trends in your industry",
                "example_queries": [
                    "What are the latest trends in my industry?",
                    "Tell me about current marketing trends",
                    "What's new in social media?"
                ]
            }
        }
    }

@router.get("/conversations")
async def get_conversations(
    current_user: User = Depends(get_current_user),
    all: bool = Query(False, description="Get all conversations instead of just today's"),
    agent: str = Query(None, description="Filter by agent type (e.g., 'atsn')")
):
    """Get conversations for current user - today's by default, or all if all=true"""
    try:
        user_id = current_user.id
        logger.info(f"Fetching conversations for user {user_id}, all={all}")
        
        conversations = []
        try:
            query = supabase_client.table("chatbot_conversations").select("*").eq("user_id", user_id)

            if not all:
                # Get today's date in UTC
                today_utc = datetime.now(timezone.utc).date()
                today_start = datetime.combine(today_utc, datetime.min.time()).replace(tzinfo=timezone.utc)
                today_end = datetime.combine(today_utc, datetime.max.time()).replace(tzinfo=timezone.utc)

                # Format as ISO strings for Supabase query
                today_start_str = today_start.isoformat()
                today_end_str = today_end.isoformat()

                logger.info(f"Date range (UTC): {today_start_str} to {today_end_str}")
                query = query.gte("created_at", today_start_str).lt("created_at", today_end_str)

            # Filter by agent if specified
            if agent:
                logger.info(f"Filtering conversations by agent: {agent}")
                query = query.contains("metadata", {"agent": agent})
            else:
                # When no agent is specified, exclude ATSN conversations to keep them separate
                logger.info("Excluding ATSN conversations for general chatbot")
                # Use a more complex query to exclude ATSN conversations
                # This will include conversations with no agent metadata or different agent metadata
            
            response = query.order("created_at", desc=False).execute()

            if response and hasattr(response, 'data'):
                conversations = response.data if response.data else []

            # Filter conversations based on agent parameter
            if agent:
                # When filtering for a specific agent, only include conversations with that agent
                conversations = [conv for conv in conversations if
                    conv.get("metadata", {}).get("agent") == agent]
            else:
                # When no agent is specified, exclude ATSN conversations
                conversations = [conv for conv in conversations if
                    conv.get("metadata", {}).get("agent") != "atsn"]

            logger.info(f"Found {len(conversations)} conversations for user {user_id} (agent filter: {agent or 'non-atsn'})")
        except Exception as db_error:
            logger.error(f"Database error fetching conversations: {str(db_error)}", exc_info=True)
            # Return empty list instead of crashing
            conversations = []
        
        # Remove duplicates based on scheduled_message_id
        seen_scheduled_ids = set()
        unique_conversations = []
        
        for conv in conversations:
            try:
                # Handle metadata - it might be None, dict, or string
                metadata = conv.get("metadata") if isinstance(conv, dict) else None
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                elif metadata is None:
                    metadata = {}
                
                scheduled_id = metadata.get("scheduled_message_id") if isinstance(metadata, dict) else None
                if scheduled_id:
                    if scheduled_id in seen_scheduled_ids:
                        continue  # Skip duplicate
                    seen_scheduled_ids.add(scheduled_id)
                unique_conversations.append(conv)
            except Exception as conv_error:
                logger.warning(f"Error processing conversation {conv.get('id', 'unknown') if isinstance(conv, dict) else 'unknown'}: {str(conv_error)}")
                # Still add the conversation even if metadata parsing fails
                unique_conversations.append(conv)
        
        result = {
            "success": True,
            "conversations": unique_conversations,
            "count": len(unique_conversations)
        }
        logger.info(f"Returning {len(unique_conversations)} unique conversations for user {user_id}")
        return result
        
    except HTTPException as http_ex:
        logger.error(f"HTTP exception in get_conversations: {http_ex.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching conversations: {str(e)}", exc_info=True)
        # Return empty result instead of crashing
        return {
            "success": True,
            "conversations": [],
            "count": 0,
            "error": str(e)
        }

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a conversation message from Supabase"""
    try:
        user_id = current_user.id
        
        # Verify message belongs to user and delete
        response = supabase_client.table("chatbot_conversations").delete().eq(
            "id", conversation_id
        ).eq("user_id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        return {
            "success": True,
            "message": "Message deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting message: {str(e)}"
        )

@router.get("/scheduled-messages")
async def get_scheduled_messages(
    current_user: User = Depends(get_current_user)
):
    """Get undelivered scheduled messages for current user up to current time, or delivered ones not in conversations"""
    try:
        import pytz
        from agents.scheduled_messages import get_user_timezone
        
        user_id = current_user.id
        user_tz = get_user_timezone(user_id)
        
        # Get current time in user's timezone
        try:
            user_timezone = pytz.timezone(user_tz)
        except:
            user_timezone = pytz.UTC
        
        now_utc = datetime.now(pytz.UTC)
        now_user_tz = now_utc.astimezone(user_timezone)
        current_time_user_tz = now_user_tz.time()
        current_hour = current_time_user_tz.hour
        current_minute = current_time_user_tz.minute
        current_minutes = current_hour * 60 + current_minute
        
        logger.info(f"Fetching scheduled messages for user {user_id} in timezone {user_tz}. Current time: {current_hour}:{current_minute:02d}")
        
        # Get today's date in user's timezone, then convert to UTC for query
        today_user_tz = now_user_tz.date()
        # Create start and end of day in user's timezone, then convert to UTC
        today_start_user_tz = user_timezone.localize(datetime.combine(today_user_tz, datetime.min.time()))
        today_end_user_tz = user_timezone.localize(datetime.combine(today_user_tz, datetime.max.time()))
        # Convert to UTC for database query
        today_start = today_start_user_tz.astimezone(pytz.UTC)
        today_end = today_end_user_tz.astimezone(pytz.UTC)
        
        logger.info(f"Querying messages between {today_start.isoformat()} and {today_end.isoformat()} (user's today: {today_user_tz})")
        
        # Get undelivered scheduled messages for today
        undelivered_response = supabase_client.table("chatbot_scheduled_messages").select("*").eq(
            "user_id", user_id
        ).eq("is_delivered", False).gte("scheduled_time", today_start.isoformat()).lt(
            "scheduled_time", today_end.isoformat()
        ).order("scheduled_time", desc=False).execute()
        
        undelivered_messages = undelivered_response.data if undelivered_response.data else []
        logger.info(f"Found {len(undelivered_messages)} undelivered scheduled messages for user {user_id}")
        # Log morning messages specifically
        morning_msgs = [msg for msg in undelivered_messages if msg.get("message_type") == "morning"]
        if morning_msgs:
            logger.info(f"Found {len(morning_msgs)} undelivered morning message(s): {[msg.get('id') for msg in morning_msgs]}")
        else:
            logger.info(f"No undelivered morning messages found in undelivered_messages")
        
        # Also check for delivered messages that might not be in conversations yet
        # Get all delivered messages for today
        delivered_response = supabase_client.table("chatbot_scheduled_messages").select("*").eq(
            "user_id", user_id
        ).eq("is_delivered", True).gte("scheduled_time", today_start.isoformat()).lt(
            "scheduled_time", today_end.isoformat()
        ).order("scheduled_time", desc=False).execute()
        
        delivered_messages = delivered_response.data if delivered_response.data else []
        logger.info(f"Found {len(delivered_messages)} delivered scheduled messages for user {user_id}")
        # Log morning messages in delivered
        delivered_morning_msgs = [msg for msg in delivered_messages if msg.get("message_type") == "morning"]
        if delivered_morning_msgs:
            logger.info(f"Found {len(delivered_morning_msgs)} delivered morning message(s): {[msg.get('id') for msg in delivered_morning_msgs]}")
        
        # Check which delivered messages are in conversations
        if delivered_messages:
            delivered_ids = [msg["id"] for msg in delivered_messages]
            # Check conversations for these scheduled message IDs
            conversations_response = supabase_client.table("chatbot_conversations").select("metadata").eq(
                "user_id", user_id
            ).gte("created_at", today_start.isoformat()).lt(
                "created_at", today_end.isoformat()
            ).execute()
            
            conversations = conversations_response.data if conversations_response.data else []
            # Extract scheduled_message_id from conversation metadata
            conversation_scheduled_ids = set()
            for conv in conversations:
                metadata = conv.get("metadata", {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                scheduled_id = metadata.get("scheduled_message_id") if isinstance(metadata, dict) else None
                if scheduled_id:
                    conversation_scheduled_ids.add(scheduled_id)
            
            # Add delivered messages that are NOT in conversations
            for msg in delivered_messages:
                if msg["id"] not in conversation_scheduled_ids:
                    logger.info(f"Delivered message {msg.get('message_type')} (id: {msg['id']}) not found in conversations, adding to return list")
                    undelivered_messages.append(msg)
        
        # Filter messages to only include those scheduled up to current time
        filtered_messages = []
        for msg in undelivered_messages:
            # Parse scheduled_time (stored in UTC)
            scheduled_time_str = msg.get("scheduled_time")
            if scheduled_time_str:
                try:
                    # Parse the scheduled time (it's in UTC)
                    if isinstance(scheduled_time_str, str):
                        # Handle timezone-aware datetime string
                        if scheduled_time_str.endswith('Z'):
                            scheduled_time_str = scheduled_time_str.replace('Z', '+00:00')
                        scheduled_time_utc = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
                        if scheduled_time_utc.tzinfo is None:
                            scheduled_time_utc = pytz.UTC.localize(scheduled_time_utc)
                    else:
                        scheduled_time_utc = scheduled_time_str
                    
                    # Convert to user's timezone
                    scheduled_time_user_tz = scheduled_time_utc.astimezone(user_timezone)
                    scheduled_time = scheduled_time_user_tz.time()
                    scheduled_hour = scheduled_time.hour
                    scheduled_minute = scheduled_time.minute
                    scheduled_minutes = scheduled_hour * 60 + scheduled_minute
                    message_type = msg.get("message_type", "")
                    
                    # Special handling for morning messages: show if current time is before 9:00 AM
                    if message_type == "morning":
                        morning_time_minutes = 9 * 60  # 9:00 AM
                        logger.info(f"Processing morning message: scheduled at {scheduled_hour}:{scheduled_minute:02d}, current time: {current_hour}:{current_minute:02d} ({current_minutes} minutes)")
                        if current_minutes < morning_time_minutes:
                            # It's before 9:00 AM, show the morning message
                            filtered_messages.append(msg)
                            logger.info(f"✓ Including morning message (before 9:00 AM) - scheduled at {scheduled_hour}:{scheduled_minute:02d}, current: {current_hour}:{current_minute:02d}")
                        elif scheduled_minutes <= current_minutes:
                            # It's 9:00 AM or later, show if scheduled time has passed
                            filtered_messages.append(msg)
                            logger.info(f"✓ Including morning message (after 9:00 AM) - scheduled at {scheduled_hour}:{scheduled_minute:02d}, current: {current_hour}:{current_minute:02d}")
                        else:
                            logger.info(f"✗ Excluding morning message - scheduled at {scheduled_hour}:{scheduled_minute:02d} hasn't passed yet, current: {current_hour}:{current_minute:02d}")
                    else:
                        # For other messages, only include if scheduled time has passed
                        if scheduled_minutes <= current_minutes:
                            filtered_messages.append(msg)
                            logger.debug(f"Including message {message_type} scheduled at {scheduled_hour}:{scheduled_minute:02d} (current: {current_hour}:{current_minute:02d})")
                        else:
                            logger.debug(f"Excluding message {message_type} scheduled at {scheduled_hour}:{scheduled_minute:02d} (current: {current_hour}:{current_minute:02d})")
                except Exception as e:
                    logger.warning(f"Error parsing scheduled_time for message {msg.get('id')}: {e}, including anyway")
                    filtered_messages.append(msg)
            else:
                # If no scheduled_time, include it (shouldn't happen but be safe)
                filtered_messages.append(msg)
        
        logger.info(f"Filtered to {len(filtered_messages)} messages scheduled up to current time ({current_hour}:{current_minute:02d})")
        
        return {
            "success": True,
            "messages": filtered_messages,
            "count": len(filtered_messages)
        }
        
    except Exception as e:
        logger.error(f"Error fetching scheduled messages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching scheduled messages: {str(e)}"
        )

@router.post("/scheduled-messages/generate-today")
async def generate_today_messages(
    current_user: User = Depends(get_current_user)
):
    """Generate today's scheduled messages up to current time if they don't exist (fallback)"""
    try:
        from datetime import date, time, datetime as dt
        import pytz
        from agents.morning_scheduled_message import generate_morning_message
        from agents.scheduled_messages import (
            generate_leads_reminder_message,
            generate_mid_morning_message,
            generate_afternoon_message,
            generate_evening_message,
            generate_night_message,
            get_user_timezone
        )
        
        user_id = current_user.id
        user_tz = get_user_timezone(user_id)
        
        # Get current time in user's timezone
        try:
            user_timezone = pytz.timezone(user_tz)
        except:
            user_timezone = pytz.UTC
        
        # Get current time in user's timezone
        now_utc = datetime.now(pytz.UTC)
        now_user_tz = now_utc.astimezone(user_timezone)
        current_time = now_user_tz.time()
        current_hour = current_time.hour
        current_minute = current_time.minute
        today = now_user_tz.date()
        
        logger.info(f"Generating messages for user {user_id} in timezone {user_tz}. Current time: {current_hour}:{current_minute:02d}")
        
        # Check if messages already exist for today (using UTC date range)
        today_utc = now_utc.date()
        today_start_utc = datetime.combine(today_utc, datetime.min.time()).replace(tzinfo=pytz.UTC)
        today_end_utc = datetime.combine(today_utc, datetime.max.time()).replace(tzinfo=pytz.UTC)
        
        existing_response = supabase_client.table("chatbot_scheduled_messages").select("message_type").eq(
            "user_id", user_id
        ).gte("scheduled_time", today_start_utc.isoformat()).lt(
            "scheduled_time", today_end_utc.isoformat()
        ).execute()
        
        existing_types = {msg["message_type"] for msg in (existing_response.data or [])}
        
        # Define message types and their target times (in user's timezone)
        message_configs = [
            ("morning", 9, 0, generate_morning_message),
            ("leads_reminder", 10, 0, generate_leads_reminder_message),
            ("mid_morning", 11, 30, generate_mid_morning_message),
            ("afternoon", 14, 0, generate_afternoon_message),
            ("evening", 18, 0, generate_evening_message),
            ("night", 21, 30, generate_night_message)
        ]
        
        generated_messages = []
        
        for msg_type, hour, minute, generator_func in message_configs:
            # Skip if message already exists
            if msg_type in existing_types:
                logger.info(f"Skipping {msg_type} message - already exists")
                continue
            
            # Check if the scheduled time has already passed today
            # Convert current time and scheduled time to minutes for comparison
            current_minutes = current_hour * 60 + current_minute
            scheduled_minutes = hour * 60 + minute
            
            if scheduled_minutes > current_minutes:
                logger.info(f"Skipping {msg_type} message - scheduled for {hour}:{minute:02d}, current time is {current_hour}:{current_minute:02d}")
                continue
            
            try:
                logger.info(f"Generating {msg_type} message (scheduled for {hour}:{minute:02d})")
                # Generate message
                result = generator_func(user_id, user_tz)
                
                if result and result.get("success"):
                    # Create scheduled time for today at the target time
                    scheduled_time = user_timezone.localize(
                        dt.combine(today, time(hour, minute))
                    )
                    
                    # Convert to UTC for storage
                    scheduled_time_utc = scheduled_time.astimezone(pytz.UTC)
                    
                    message_data = {
                        "user_id": user_id,
                        "message_type": msg_type,
                        "content": result["content"],
                        "scheduled_time": scheduled_time_utc.isoformat(),
                        "metadata": result.get("metadata", {}),
                        "is_delivered": False
                    }
                    
                    insert_result = supabase_client.table("chatbot_scheduled_messages").insert(message_data).execute()
                    
                    if insert_result.data:
                        generated_messages.append({
                            "type": msg_type,
                            "id": insert_result.data[0]["id"],
                            "content": result["content"]
                        })
                        logger.info(f"Successfully generated and saved {msg_type} message")
                        
            except Exception as e:
                logger.error(f"Error generating {msg_type} message for user {user_id}: {e}", exc_info=True)
                continue
        
        logger.info(f"Generated {len(generated_messages)} scheduled messages for user {user_id}")
        return {
            "success": True,
            "message": f"Generated {len(generated_messages)} scheduled messages for today",
            "messages": generated_messages,
            "count": len(generated_messages)
        }
        
    except Exception as e:
        logger.error(f"Error generating today's messages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating today's messages: {str(e)}"
        )

@router.post("/scheduled-messages/check-morning-on-login")
async def check_morning_message_on_login(
    current_user: User = Depends(get_current_user)
):
    """Check and generate morning message on login if needed (before 9:00 AM)"""
    try:
        from agents.morning_scheduled_message import ensure_morning_message_on_login
        from agents.scheduled_messages import get_user_timezone
        
        user_id = current_user.id
        user_tz = get_user_timezone(user_id)
        
        result = ensure_morning_message_on_login(user_id, user_tz)
        
        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "generated": result.get("generated", False)
        }
        
    except Exception as e:
        logger.error(f"Error checking morning message on login: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking morning message: {str(e)}"
        )

@router.post("/scheduled-messages/regenerate-morning")
async def regenerate_morning_message(
    current_user: User = Depends(get_current_user)
):
    """Delete today's morning message and regenerate it with the new format"""
    try:
        import pytz
        from agents.morning_scheduled_message import generate_morning_message
        from agents.scheduled_messages import get_user_timezone
        
        user_id = current_user.id
        user_tz = get_user_timezone(user_id)
        
        # Get today's date range in user's timezone, then convert to UTC
        user_tz = get_user_timezone(user_id)
        try:
            user_timezone = pytz.timezone(user_tz)
        except:
            user_timezone = pytz.UTC
        
        now_utc = datetime.now(pytz.UTC)
        now_user_tz = now_utc.astimezone(user_timezone)
        today_user_tz = now_user_tz.date()
        
        # Create start and end of day in user's timezone, then convert to UTC
        today_start_user_tz = user_timezone.localize(datetime.combine(today_user_tz, datetime.min.time()))
        today_end_user_tz = user_timezone.localize(datetime.combine(today_user_tz, datetime.max.time()))
        # Convert to UTC for database query
        today_start = today_start_user_tz.astimezone(pytz.UTC)
        today_end = today_end_user_tz.astimezone(pytz.UTC)
        
        # Delete existing morning messages for today (using user's timezone date)
        delete_response = supabase_client.table("chatbot_scheduled_messages").delete().eq(
            "user_id", user_id
        ).eq("message_type", "morning").gte(
            "scheduled_time", today_start.isoformat()
        ).lt(
            "scheduled_time", today_end.isoformat()
        ).execute()
        
        logger.info(f"Deleted {len(delete_response.data) if delete_response.data else 0} existing morning messages for user {user_id}")
        
        # Generate new morning message
        result = generate_morning_message(user_id, user_tz)
        
        if result and result.get("success"):
            # Get current time in user's timezone
            try:
                user_timezone = pytz.timezone(user_tz)
            except:
                user_timezone = pytz.UTC
            
            now_user_tz = now_utc.astimezone(user_timezone)
            today = now_user_tz.date()
            
            # Save to database with scheduled time of 9:00 AM today
            from datetime import time as dt_time
            # Use today's date, not tomorrow
            scheduled_time = user_timezone.localize(
                datetime.combine(today, dt_time(9, 0))
            )
            
            # If the scheduled time is in the past (e.g., it's already past 9 AM today), 
            # we still want to show it, so keep it as today
            logger.info(f"Setting scheduled_time to {scheduled_time} (today: {today}, 9:00 AM in {user_tz})")
            
            # Convert to UTC for storage
            scheduled_time_utc = scheduled_time.astimezone(pytz.UTC)
            
            message_data = {
                "user_id": user_id,
                "message_type": "morning",
                "content": result["content"],
                "scheduled_time": scheduled_time_utc.isoformat(),
                "metadata": result.get("metadata", {}),
                "is_delivered": False
            }
            
            insert_result = supabase_client.table("chatbot_scheduled_messages").insert(message_data).execute()
            
            if insert_result.data:
                logger.info(f"Successfully regenerated morning message for user {user_id}")
                # Return the full message data so frontend can display it immediately
                return {
                    "success": True,
                    "message": "Morning message regenerated successfully",
                    "content": result["content"],
                    "message_data": insert_result.data[0]  # Return the full message object
                }
            else:
                logger.error(f"Failed to save regenerated morning message for user {user_id}")
                return {"success": False, "error": "Failed to save message"}
        else:
            logger.error(f"Failed to generate morning message for user {user_id}: {result.get('error', 'Unknown error') if result else 'No result'}")
            return {"success": False, "error": result.get("error", "Failed to generate message") if result else "No result"}
        
    except Exception as e:
        logger.error(f"Error regenerating morning message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error regenerating morning message: {str(e)}"
        )

@router.post("/scheduled-messages/{message_id}/deliver")
async def deliver_scheduled_message(
    message_id: str,
    current_user: User = Depends(get_current_user)
):
    """Mark message as delivered and add to conversation history"""
    try:
        user_id = current_user.id
        
        # Verify message belongs to user
        message_response = supabase_client.table("chatbot_scheduled_messages").select("*").eq(
            "id", message_id
        ).eq("user_id", user_id).execute()
        
        if not message_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        message = message_response.data[0]
        
        # Check if already delivered
        if message.get("is_delivered"):
            logger.info(f"Message {message_id} already delivered, checking if in conversations")
            # Check if it's already in conversations
            existing_conv = supabase_client.table("chatbot_conversations").select("id").eq(
                "user_id", user_id
            ).contains("metadata", {"scheduled_message_id": message_id}).execute()
            
            if existing_conv.data and len(existing_conv.data) > 0:
                logger.info(f"Message {message_id} already in conversations")
                return {
                    "success": True,
                    "message": "Message already delivered and in conversation history",
                    "conversation_id": existing_conv.data[0]["id"]
                }
        
        # Mark as delivered
        update_response = supabase_client.table("chatbot_scheduled_messages").update({
            "is_delivered": True,
            "delivered_at": datetime.now().isoformat()
        }).eq("id", message_id).execute()
        
        # Check if already in conversations before adding
        existing_conv_check = supabase_client.table("chatbot_conversations").select("id").eq(
            "user_id", user_id
        ).contains("metadata", {"scheduled_message_id": message_id}).execute()
        
        if existing_conv_check.data and len(existing_conv_check.data) > 0:
            logger.info(f"Message {message_id} already in conversations, skipping insert")
            conversation_id = existing_conv_check.data[0]["id"]
        else:
            # Add to conversation history
            conversation_data = {
                "user_id": user_id,
                "message_type": "bot",
                "content": message["content"],
                "intent": "scheduled_message",
                "metadata": {
                    "scheduled_message_id": message_id,
                    "message_type": message["message_type"],
                    **message.get("metadata", {})
                }
            }
            
            conversation_response = supabase_client.table("chatbot_conversations").insert(conversation_data).execute()
            conversation_id = conversation_response.data[0]["id"] if conversation_response.data else None
        
        return {
            "success": True,
            "message": "Message delivered and added to conversation history",
            "conversation_id": conversation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error delivering message: {str(e)}"
        )

@router.post("/scheduled-messages/generate-test")
async def generate_test_message(
    message_type: str,
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Manually trigger message generation for testing"""
    try:
        from scheduler.daily_messages_scheduler import trigger_message_manually
        
        target_user_id = user_id or current_user.id
        
        result = await trigger_message_manually(message_type, target_user_id)
        
        if result.get("success"):
            return {
                "success": True,
                "message": f"Test {message_type} message generated successfully",
                "data": result
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate message")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating test message: {str(e)}"
        )
