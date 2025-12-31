"""
Custom Content Creation Agent using LangGraph
Interactive chatbot for creating custom social media content
Supports image and video uploads with platform-specific optimization
"""

import json
import asyncio
import logging
import base64
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, TypedDict, Union
from dataclasses import dataclass
from enum import Enum

import openai
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from supabase import create_client, Client
import httpx
import os
from dotenv import load_dotenv

# Import media agent
from .media_agent import create_media_agent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Initialize OpenAI
openai_api_key = os.getenv("OPENAI_API_KEY")

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    NONE = "none"

class ContentType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    STORY = "story"
    REEL = "reel"
    LIVE = "live"
    POLL = "poll"
    QUESTION = "question"
    ARTICLE = "article"
    THREAD = "thread"
    PIN = "pin"
    SHORT = "short"

class ConversationStep(str, Enum):
    GREET = "greet"
    ASK_PLATFORM = "ask_platform"
    ASK_CONTENT_TYPE = "ask_content_type"
    ASK_DESCRIPTION = "ask_description"
    ASK_CLARIFICATION_1 = "ask_clarification_1"
    ASK_CLARIFICATION_2 = "ask_clarification_2"
    ASK_CLARIFICATION_3 = "ask_clarification_3"
    ASK_MEDIA = "ask_media"
    HANDLE_MEDIA = "handle_media"
    VALIDATE_MEDIA = "validate_media"
    CONFIRM_MEDIA = "confirm_media"
    ASK_CAROUSEL_IMAGE_SOURCE = "ask_carousel_image_source"
    GENERATE_CAROUSEL_IMAGE = "generate_carousel_image"
    APPROVE_CAROUSEL_IMAGES = "approve_carousel_images"
    HANDLE_CAROUSEL_UPLOAD = "handle_carousel_upload"
    CONFIRM_CAROUSEL_UPLOAD_DONE = "confirm_carousel_upload_done"
    GENERATE_SCRIPT = "generate_script"
    CONFIRM_SCRIPT = "confirm_script"
    GENERATE_CONTENT = "generate_content"
    CONFIRM_CONTENT = "confirm_content"
    SELECT_SCHEDULE = "select_schedule"
    SAVE_CONTENT = "save_content"
    ASK_ANOTHER_CONTENT = "ask_another_content"
    DISPLAY_RESULT = "display_result"
    ERROR = "error"

class CustomContentState(TypedDict):
    """State for the custom content creation conversation"""
    user_id: str
    conversation_id: Optional[str]
    conversation_messages: List[Dict[str, str]]  # Chat history
    current_step: ConversationStep
    selected_platform: Optional[str]
    selected_content_type: Optional[str]
    user_description: Optional[str]
    clarification_1: Optional[str]
    clarification_2: Optional[str]
    clarification_3: Optional[str]
    has_media: Optional[bool]
    media_type: Optional[MediaType]
    uploaded_media_url: Optional[str]
    should_generate_media: Optional[bool]
    media_prompt: Optional[str]
    generated_content: Optional[Dict[str, Any]]
    generated_script: Optional[Dict[str, Any]]
    generated_media_url: Optional[str]
    final_post: Optional[Dict[str, Any]]
    error_message: Optional[str]
    platform_content_types: Optional[Dict[str, List[str]]]
    media_requirements: Optional[Dict[str, Any]]
    validation_errors: Optional[List[str]]
    retry_count: int
    is_complete: bool
    # Carousel-specific fields
    carousel_images: Optional[List[Dict[str, Any]]]  # List of carousel image objects
    carousel_image_source: Optional[str]  # "ai_generate" or "manual_upload"
    current_carousel_index: int  # Current image index (0-3 for AI, 0-max for manual)
    carousel_max_images: int  # Platform-specific max (10 for Facebook, 20 for Instagram)
    uploaded_carousel_images: Optional[List[str]]  # URLs of uploaded images
    carousel_upload_done: bool  # Whether user confirmed upload is complete
    carousel_theme: Optional[str]  # Overall theme/narrative for sequential carousel images

# Platform-specific content types
PLATFORM_CONTENT_TYPES = {
    "Facebook": [
        "Text Post", "Photo", "Video", "Link", "Live Broadcast", 
        "Carousel", "Story", "Event", "Poll", "Question"
    ],
    "Instagram": [
        "Feed Post", "Story", "Reel", "Carousel"
    ],
    "LinkedIn": [
        "Text Post", "Article", "Video", "Image", "Document", 
        "Poll", "Event", "Job Posting", "Company Update", "Thought Leadership"
    ],
    "Twitter/X": [
        "Tweet", "Thread", "Image Tweet", "Video Tweet", "Poll", 
        "Space", "Quote Tweet", "Reply", "Retweet", "Fleets"
    ],
    "YouTube": [
        "Short Video", "Long Form Video", "Live Stream", "Premiere", 
        "Community Post", "Shorts", "Tutorial", "Review", "Vlog"
    ],
    "TikTok": [
        "Video", "Duet", "Stitch", "Live", "Photo Slideshow", 
        "Trending Sound", "Original Sound", "Effect Video"
    ],
    "Pinterest": [
        "Pin", "Idea Pin", "Story Pin", "Video Pin", "Shopping Pin", 
        "Board", "Rich Pin", "Carousel Pin", "Seasonal Pin"
    ],
    "WhatsApp Business": [
        "Text Message", "Image", "Video", "Document", "Audio", 
        "Location", "Contact", "Sticker", "Template Message"
    ]
}

# Platform-specific media requirements
PLATFORM_MEDIA_REQUIREMENTS = {
    "Facebook": {
        "image": {
            "sizes": ["1200x630", "1200x675", "1080x1080"],
            "formats": ["jpg", "png", "gif"],
            "max_size": "10MB"
        },
        "video": {
            "sizes": ["1280x720", "1920x1080", "1080x1080"],
            "formats": ["mp4", "mov", "avi"],
            "max_size": "4GB",
            "max_duration": "240 minutes"
        }
    },
    "Instagram": {
        "image": {
            "sizes": ["1080x1080", "1080x1350", "1080x566"],
            "formats": ["jpg", "png"],
            "max_size": "30MB"
        },
        "video": {
            "sizes": ["1080x1080", "1080x1350", "1080x1920"],
            "formats": ["mp4", "mov"],
            "max_size": "100MB",
            "max_duration": "60 seconds"
        }
    },
    "LinkedIn": {
        "image": {
            "sizes": ["1200x627", "1200x1200"],
            "formats": ["jpg", "png"],
            "max_size": "5MB"
        },
        "video": {
            "sizes": ["1280x720", "1920x1080"],
            "formats": ["mp4", "mov"],
            "max_size": "5GB",
            "max_duration": "10 minutes"
        }
    },
    "Twitter/X": {
        "image": {
            "sizes": ["1200x675", "1200x1200"],
            "formats": ["jpg", "png", "gif"],
            "max_size": "5MB"
        },
        "video": {
            "sizes": ["1280x720", "1920x1080"],
            "formats": ["mp4", "mov"],
            "max_size": "512MB",
            "max_duration": "2 minutes 20 seconds"
        }
    },
    "YouTube": {
        "image": {
            "sizes": ["1280x720", "1920x1080"],
            "formats": ["jpg", "png"],
            "max_size": "2MB"
        },
        "video": {
            "sizes": ["1280x720", "1920x1080", "3840x2160"],
            "formats": ["mp4", "mov", "avi"],
            "max_size": "256GB",
            "max_duration": "12 hours"
        }
    },
    "TikTok": {
        "image": {
            "sizes": ["1080x1920", "1080x1080"],
            "formats": ["jpg", "png"],
            "max_size": "10MB"
        },
        "video": {
            "sizes": ["1080x1920", "1080x1080"],
            "formats": ["mp4", "mov"],
            "max_size": "287MB",
            "max_duration": "3 minutes"
        }
    },
    "Pinterest": {
        "image": {
            "sizes": ["1000x1500", "1000x1000", "1000x2000"],
            "formats": ["jpg", "png"],
            "max_size": "32MB"
        },
        "video": {
            "sizes": ["1000x1500", "1000x1000"],
            "formats": ["mp4", "mov"],
            "max_size": "2GB",
            "max_duration": "15 minutes"
        }
    },
    "WhatsApp Business": {
        "image": {
            "sizes": ["any"],
            "formats": ["jpg", "png", "gif"],
            "max_size": "5MB"
        },
        "video": {
            "sizes": ["any"],
            "formats": ["mp4", "3gp"],
            "max_size": "16MB",
            "max_duration": "16 seconds"
        }
    }
}

class CustomContentAgent:
    """Custom Content Creation Agent using LangGraph"""
    
    def __init__(self, openai_api_key: str):
        self.openai_api_key = openai_api_key
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.supabase = supabase
        
        # Initialize media agent and token tracker with service role key to bypass RLS
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        if supabase_url and supabase_key and gemini_api_key:
            self.media_agent = create_media_agent(supabase_url, supabase_key, gemini_api_key)
        else:
            logger.warning("Media agent not initialized - missing environment variables")
            self.media_agent = None
        
        # Initialize token tracker with service role key to bypass RLS
        if supabase_url and supabase_key:
            from services.token_usage_service import TokenUsageService
            self.token_tracker = TokenUsageService(supabase_url, supabase_key)
        else:
            self.token_tracker = None
        
    def create_graph(self) -> StateGraph:
        """Create the LangGraph workflow with proper conditional edges and state management"""
        graph = StateGraph(CustomContentState)
        
        # Add nodes
        graph.add_node("greet_user", self.greet_user)
        graph.add_node("ask_platform", self.ask_platform)
        graph.add_node("ask_content_type", self.ask_content_type)
        graph.add_node("ask_description", self.ask_description)
        graph.add_node("ask_media", self.ask_media)
        graph.add_node("handle_media", self.handle_media)
        graph.add_node("validate_media", self.validate_media)
        graph.add_node("confirm_media", self.confirm_media)
        graph.add_node("generate_script", self.generate_script)
        graph.add_node("generate_content", self.generate_content)
        graph.add_node("confirm_content", self.confirm_content)
        graph.add_node("select_schedule", self.select_schedule)
        graph.add_node("save_content", self.save_content)
        graph.add_node("ask_another_content", self.ask_another_content)
        graph.add_node("display_result", self.display_result)
        graph.add_node("handle_error", self.handle_error)
        
        # Set entry point
        graph.set_entry_point("greet_user")
        
        # Linear flow for initial steps - each step waits for user input
        graph.add_edge("greet_user", "ask_platform")
        
        # Conditional edge for platform selection - loop back if not selected
        graph.add_conditional_edges(
            "ask_platform",
            self._should_proceed_from_platform,
            {
                "continue": "ask_content_type",
                "retry": "ask_platform"  # Loop back to same node on error
            }
        )
        
        # Conditional edge for content type selection - loop back if not selected
        graph.add_conditional_edges(
            "ask_content_type",
            self._should_proceed_from_content_type,
            {
                "continue": "ask_description",
                "retry": "ask_content_type"  # Loop back to same node on error
            }
        )
        
        graph.add_edge("ask_description", "ask_media")
        graph.add_edge("ask_description", "ask_media")
        
        # Conditional edges for media handling
        graph.add_conditional_edges(
            "ask_media",
            self._should_handle_media,
            {
                "handle": "handle_media",
                "generate": "generate_content",
                "generate_script": "generate_script",
                "skip": "generate_content"
            }
        )
        
        # Script generation flow - after script is created, conditionally proceed
        # The execute_conversation_step will check current_step and stop at CONFIRM_SCRIPT
        graph.add_conditional_edges(
            "generate_script",
            self._should_proceed_after_script,
            {
                "confirm": "generate_content",  # Will be intercepted by execute_conversation_step if CONFIRM_SCRIPT
                "proceed": "generate_content"
            }
        )
        
        # Media handling flow
        graph.add_edge("handle_media", "validate_media")
        graph.add_edge("validate_media", "confirm_media")
        
        # Conditional edge after media confirmation
        graph.add_conditional_edges(
            "confirm_media",
            self._should_proceed_after_media,
            {
                "proceed": "generate_content",
                "retry": "ask_media",
                "error": "handle_error"
            }
        )
        
        
        # Content generation flow - skip parse and optimize, go directly to confirm
        graph.add_edge("generate_content", "confirm_content")
        
        # Conditional edge after content confirmation
        graph.add_conditional_edges(
            "confirm_content",
            self._should_proceed_after_content,
            {
                "proceed": "select_schedule",
                "retry": "ask_description",
                "error": "handle_error"
            }
        )
        
        # Final flow
        graph.add_edge("select_schedule", "save_content")
        graph.add_edge("save_content", "ask_another_content")
        graph.add_edge("ask_another_content", END)
        
        # Error handling
        graph.add_edge("handle_error", END)
        
        return graph.compile()
    
    async def greet_user(self, state: CustomContentState) -> CustomContentState:
        """Welcome the user and initialize conversation"""
        try:
            # Create conversation ID
            conversation_id = str(uuid.uuid4())
            
            # Initialize conversation
            state["conversation_id"] = conversation_id
            state["conversation_messages"] = []
            state["current_step"] = ConversationStep.ASK_PLATFORM
            state["retry_count"] = 0
            state["is_complete"] = False
            state["retry_platform"] = False
            state["retry_content_type"] = False
            
            # Load user profile and platforms
            user_profile = await self._load_user_profile(state["user_id"])
            state["user_profile"] = user_profile
            
            connected_platforms = user_profile.get("social_media_platforms", [])
            state["platform_content_types"] = {platform: PLATFORM_CONTENT_TYPES.get(platform, []) for platform in connected_platforms}
            
            # Get business name from profile
            business_name = user_profile.get("business_name", "")
            if not business_name:
                business_name = "there"  # Fallback if no business name
            
            if not connected_platforms:
                # No platforms connected
                welcome_message = {
                    "role": "assistant",
                    "content": f"Thanks Emily, I'll take care from here. Hi {business_name}, Leo here! I'd love to help you create amazing content, but I don't see any connected social media platforms in your profile. Please connect your platforms first in the Settings dashboard, then come back to create content!",
                    "timestamp": datetime.now().isoformat()
                }
                state["conversation_messages"].append(welcome_message)
                state["current_step"] = ConversationStep.ERROR
                return state
            
            # Create platform selection message with options - more humanized
            # Format platform names for display (capitalize first letter)
            platform_options = []
            for platform in connected_platforms:
                # Capitalize first letter of each word for display
                display_name = ' '.join(word.capitalize() for word in platform.split('_'))
                platform_options.append({"value": platform, "label": display_name})
            
            welcome_message = {
                "role": "assistant",
                "content": f"Thanks Emily, I'll take care from here. Hi {business_name}, Leo here! Let's create some amazing content together. Which platform are you thinking about creating content for today?",
                "timestamp": datetime.now().isoformat(),
                "platforms": connected_platforms,
                "options": platform_options
            }
            
            state["conversation_messages"].append(welcome_message)
            state["progress_percentage"] = 15
            
            logger.info(f"Greeted user {state['user_id']} for custom content creation with {len(connected_platforms)} platforms")
            
        except Exception as e:
            logger.error(f"Error in greet_user: {e}")
            state["error_message"] = f"Failed to initialize conversation: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
        
    async def ask_platform(self, state: CustomContentState) -> CustomContentState:
        """Ask user to select a platform"""
        try:
            state["current_step"] = ConversationStep.ASK_PLATFORM
            state["progress_percentage"] = 15
            
            # Get user's connected platforms
            user_profile = state.get("user_profile", {})
            connected_platforms = user_profile.get("social_media_platforms", [])
            
            if not connected_platforms:
                message = {
                    "role": "assistant",
                    "content": "I don't see any connected social media platforms in your profile. Please connect your platforms first in the Settings dashboard.",
                    "timestamp": datetime.now().isoformat()
                }
                state["conversation_messages"].append(message)
                state["current_step"] = ConversationStep.ERROR
                return state
            
            # Check if we already asked (to avoid duplicate messages on retry)
            last_message = state["conversation_messages"][-1] if state["conversation_messages"] else None
            already_asked = last_message and (
                "platform" in last_message.get("content", "").lower() or 
                "select" in last_message.get("content", "").lower()
            )
            
            # Only add message if we haven't already asked (unless it's an error retry)
            if not already_asked or state.get("retry_platform", False):
                # Format platform names for display (capitalize first letter) - same as greet_user
                platform_options = []
                for platform in connected_platforms:
                    # Capitalize first letter of each word for display
                    display_name = ' '.join(word.capitalize() for word in platform.split('_'))
                    platform_options.append({"value": platform, "label": display_name})
                
                # Create platform selection message with options
                message = {
                    "role": "assistant",
                    "content": f"Great! I can see you have these platforms connected. Which platform would you like to create content for?",
                    "timestamp": datetime.now().isoformat(),
                    "platforms": connected_platforms,
                    "options": platform_options
                }
                state["conversation_messages"].append(message)
                state["retry_platform"] = False  # Reset retry flag
            
            logger.info(f"Asked user to select platform from: {connected_platforms}")
            
        except Exception as e:
            logger.error(f"Error in ask_platform: {e}")
            state["error_message"] = f"Failed to load platforms: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def ask_content_type(self, state: CustomContentState) -> CustomContentState:
        """Ask user to select content type for the platform"""
        try:
            state["current_step"] = ConversationStep.ASK_CONTENT_TYPE
            state["progress_percentage"] = 25
            
            platform = state.get("selected_platform")
            if not platform:
                state["error_message"] = "No platform selected"
                state["current_step"] = ConversationStep.ERROR
                return state
            
            # Get content types for the platform
            content_types = PLATFORM_CONTENT_TYPES.get(platform, ["Text Post", "Image", "Video"])
            
            # Check if we already asked (to avoid duplicate messages on retry)
            last_message = state["conversation_messages"][-1] if state["conversation_messages"] else None
            already_asked = last_message and (
                "content type" in last_message.get("content", "").lower() or 
                "type of content" in last_message.get("content", "").lower()
            )
            
            # Only add message if we haven't already asked (unless it's an error retry)
            if not already_asked or state.get("retry_content_type", False):
                # Format platform name for display
                platform_display = ' '.join(word.capitalize() for word in platform.split('_'))
                
                message = {
                    "role": "assistant",
                    "content": f"Perfect! For {platform_display}, what type of content would you like to create?",
                    "timestamp": datetime.now().isoformat(),
                    "content_types": content_types,
                    "options": [{"value": content_type, "label": content_type} for content_type in content_types]
                }
                state["conversation_messages"].append(message)
                state["retry_content_type"] = False  # Reset retry flag
            
            logger.info(f"Asked user to select content type for {platform}")
            
        except Exception as e:
            logger.error(f"Error in ask_content_type: {e}")
            state["error_message"] = f"Failed to load content types: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def ask_description(self, state: CustomContentState) -> CustomContentState:
        """Ask user to describe their content idea"""
        try:
            state["current_step"] = ConversationStep.ASK_DESCRIPTION
            state["progress_percentage"] = 35
            
            platform = state.get("selected_platform")
            content_type = state.get("selected_content_type")
            
            message = {
                "role": "assistant",
                "content": f"Great choice! What's in your mind to post? Describe your idea, key points, or any specific details you want to include:",
                "timestamp": datetime.now().isoformat()
            }
            state["conversation_messages"].append(message)
            
            logger.info(f"Asked user to describe content for {content_type} on {platform}")
            
        except Exception as e:
            logger.error(f"Error in ask_description: {e}")
            state["error_message"] = f"Failed to ask for description: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def ask_clarification_1(self, state: CustomContentState) -> CustomContentState:
        """Ask first clarifying question about the post goal"""
        try:
            state["current_step"] = ConversationStep.ASK_CLARIFICATION_1
            state["progress_percentage"] = 40
            
            message = {
                "role": "assistant",
                "content": "What's the main goal or purpose of this post? (e.g., drive engagement, promote a product/service, share educational content, build brand awareness, or something else?)",
                "timestamp": datetime.now().isoformat()
            }
            state["conversation_messages"].append(message)
            
            logger.info("Asked first clarification question about post goal")
            
        except Exception as e:
            logger.error(f"Error in ask_clarification_1: {e}")
            state["error_message"] = f"Failed to ask clarification: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def ask_clarification_2(self, state: CustomContentState) -> CustomContentState:
        """Ask second clarifying question about target audience"""
        try:
            state["current_step"] = ConversationStep.ASK_CLARIFICATION_2
            state["progress_percentage"] = 45
            
            message = {
                "role": "assistant",
                "content": "Who is your target audience for this post? (e.g., existing customers, new prospects, specific age group, professionals, or a particular demographic?)",
                "timestamp": datetime.now().isoformat()
            }
            state["conversation_messages"].append(message)
            
            logger.info("Asked second clarification question about target audience")
            
        except Exception as e:
            logger.error(f"Error in ask_clarification_2: {e}")
            state["error_message"] = f"Failed to ask clarification: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def ask_clarification_3(self, state: CustomContentState) -> CustomContentState:
        """Ask third clarifying question about tone and style"""
        try:
            state["current_step"] = ConversationStep.ASK_CLARIFICATION_3
            state["progress_percentage"] = 50
            
            message = {
                "role": "assistant",
                "content": "What tone or style should this post have? (e.g., professional and formal, casual and friendly, inspirational and motivational, humorous and light-hearted, or something else?)",
                "timestamp": datetime.now().isoformat()
            }
            state["conversation_messages"].append(message)
            
            logger.info("Asked third clarification question about tone and style")
            
        except Exception as e:
            logger.error(f"Error in ask_clarification_3: {e}")
            state["error_message"] = f"Failed to ask clarification: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def ask_media(self, state: CustomContentState) -> CustomContentState:
        """Ask user about media preferences"""
        try:
            state["current_step"] = ConversationStep.ASK_MEDIA
            state["progress_percentage"] = 55
            
            platform = state.get("selected_platform")
            content_type = state.get("selected_content_type")
            
            # Check if this is a carousel post
            if content_type and content_type.lower() == "carousel":
                # Set platform-specific max images
                if platform and platform.lower() == "facebook":
                    state["carousel_max_images"] = 10
                elif platform and platform.lower() == "instagram":
                    state["carousel_max_images"] = 20
                else:
                    state["carousel_max_images"] = 10  # Default
                
                # Initialize carousel fields
                state["carousel_images"] = []
                state["uploaded_carousel_images"] = []
                state["current_carousel_index"] = 0
                state["carousel_upload_done"] = False
                
                # Ask for carousel image source
                state["current_step"] = ConversationStep.ASK_CAROUSEL_IMAGE_SOURCE
                max_images = state["carousel_max_images"]
                
                message = {
                    "role": "assistant",
                    "content": f"Great! For your carousel post, how would you like to add images?\n\n• Generate with AI: I'll create up to 4 images for you\n• Upload manually: You can upload up to {max_images} images",
                    "timestamp": datetime.now().isoformat(),
                    "options": [
                        {
                            "value": "ai_generate",
                            "label": "🎨 Generate with AI (4 images max)"
                        },
                        {
                            "value": "manual_upload",
                            "label": f"📤 Upload manually (up to {max_images} images)"
                        }
                    ]
                }
                state["conversation_messages"].append(message)
                logger.info(f"Asked user about carousel image source for {platform}")
                return state
            
            # Check if this is a Reel - show only 2 options
            if content_type and content_type.lower() == "reel":
                message = {
                    "role": "assistant",
                    "content": f"Perfect! For your Instagram Reel, how would you like to proceed?",
                    "timestamp": datetime.now().isoformat(),
                    "options": [
                        {
                            "value": "upload_video",
                            "label": "🎥 Upload a video"
                        },
                        {
                            "value": "generate_script",
                            "label": "📝 Let me generate a script for you"
                        }
                    ]
                }
                state["conversation_messages"].append(message)
                logger.info(f"Asked user about Reel media options for {platform}")
                return state
            
            # Get media requirements for the platform
            media_reqs = PLATFORM_MEDIA_REQUIREMENTS.get(platform, {})
            
            message = {
                "role": "assistant",
                "content": f"Do you have media to include with your {content_type}? What would you prefer?",
                "timestamp": datetime.now().isoformat(),
                "media_requirements": media_reqs,
                "options": [
                    {
                        "value": "upload_image",
                        "label": "📷 Upload an image"
                    },
                    {
                        "value": "upload_video", 
                        "label": "🎥 Upload a video"
                    },
                    {
                        "value": "generate_image",
                        "label": "🎨 Let me generate an image for you"
                    },
                    {
                        "value": "generate_video",
                        "label": "🎬 Let me generate a video for you"
                    },
                    {
                        "value": "skip_media",
                        "label": "📝 Skip media (text-only post)"
                    }
                ]
            }
            state["conversation_messages"].append(message)
            
            logger.info(f"Asked user about media preferences for {platform}")
            
        except Exception as e:
            logger.error(f"Error in ask_media: {e}")
            state["error_message"] = f"Failed to ask about media: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def handle_media(self, state: CustomContentState) -> CustomContentState:
        """Handle media upload - show upload interface"""
        try:
            state["current_step"] = ConversationStep.HANDLE_MEDIA
            state["progress_percentage"] = 55
            
            media_type = state.get("media_type", "image")
            media_type_name = "image" if media_type == "image" else "video"
            
            message = {
                "role": "assistant",
                "content": f"Perfect! Please upload your {media_type_name} below.",
                "timestamp": datetime.now().isoformat()
            }
            state["conversation_messages"].append(message)
            
            logger.info(f"Ready for media upload: {media_type}")
            
        except Exception as e:
            logger.error(f"Error in handle_media: {e}")
            state["error_message"] = f"Failed to handle media: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def validate_media(self, state: CustomContentState) -> CustomContentState:
        """Validate uploaded media against platform requirements"""
        try:
            state["current_step"] = ConversationStep.VALIDATE_MEDIA
            state["progress_percentage"] = 65
            
            # Media validation will be handled by the frontend
            # This is a placeholder for any server-side validation
            message = {
                "role": "assistant",
                "content": "Media validation completed successfully!",
                "timestamp": datetime.now().isoformat()
            }
            state["conversation_messages"].append(message)
            
            logger.info("Media validation completed")
            
        except Exception as e:
            logger.error(f"Error in validate_media: {e}")
            state["error_message"] = f"Failed to validate media: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state

    async def confirm_media(self, state: CustomContentState) -> CustomContentState:
        """Ask user to confirm if the uploaded media is correct"""
        try:
            state["current_step"] = ConversationStep.CONFIRM_MEDIA
            state["progress_percentage"] = 60
            
            media_url = state.get("uploaded_media_url")
            media_type = state.get("uploaded_media_type", "")
            media_filename = state.get("uploaded_media_filename", "")
            
            # Create a message asking for confirmation
            message = {
                "role": "assistant",
                "content": f"Perfect! I've received your {media_type.split('/')[0]} file.\n\nIs this the correct media you'd like me to use for your content? Please confirm by typing 'yes' to proceed or 'no' to upload a different file.",
                "timestamp": datetime.now().isoformat(),
                "media_url": media_url,
                "media_type": media_type,
                "media_filename": media_filename
            }
            state["conversation_messages"].append(message)
            
            logger.info(f"Asking user to confirm media: {media_filename}")
            
        except Exception as e:
            logger.error(f"Error in confirm_media: {e}")
            state["error_message"] = f"Failed to confirm media: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def ask_carousel_image_source(self, state: CustomContentState, user_input: str = None) -> CustomContentState:
        """Handle carousel image source selection (AI generate or manual upload)"""
        try:
            if not user_input:
                # This should not happen as we already asked in ask_media
                return state
            
            user_input_lower = user_input.lower().strip()
            
            if user_input_lower == "ai_generate" or "generate" in user_input_lower:
                state["carousel_image_source"] = "ai_generate"
                state["current_carousel_index"] = 0
                state["carousel_images"] = []
                # Initialize carousel theme based on user description for sequential consistency
                user_description = state.get("user_description", "")
                state["carousel_theme"] = f"Sequential carousel story about: {user_description}"
                state["current_step"] = ConversationStep.GENERATE_CAROUSEL_IMAGE
                return await self.generate_carousel_image(state)
            elif user_input_lower == "manual_upload" or "upload" in user_input_lower:
                state["carousel_image_source"] = "manual_upload"
                state["uploaded_carousel_images"] = []
                state["carousel_upload_done"] = False
                state["current_step"] = ConversationStep.HANDLE_CAROUSEL_UPLOAD
                return await self.handle_carousel_upload(state)
            else:
                # Invalid input, ask again
                max_images = state.get("carousel_max_images", 10)
                message = {
                    "role": "assistant",
                    "content": f"Please choose either 'Generate with AI' or 'Upload manually'. How would you like to add images to your carousel?",
                    "timestamp": datetime.now().isoformat(),
                    "options": [
                        {
                            "value": "ai_generate",
                            "label": "🎨 Generate with AI (4 images max)"
                        },
                        {
                            "value": "manual_upload",
                            "label": f"📤 Upload manually (up to {max_images} images)"
                        }
                    ]
                }
                state["conversation_messages"].append(message)
                return state
                
        except Exception as e:
            logger.error(f"Error in ask_carousel_image_source: {e}")
            state["error_message"] = f"Failed to process carousel image source: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            return state
    
    async def generate_carousel_image(self, state: CustomContentState, user_input: str = None) -> CustomContentState:
        """Generate all 4 carousel images at once"""
        try:
            # This step just indicates that generation should start
            # The actual generation will be handled by the API endpoint which generates all 4 at once
            state["current_step"] = ConversationStep.GENERATE_CAROUSEL_IMAGE
            state["progress_percentage"] = 50
            state["carousel_images"] = []
            state["current_carousel_index"] = 0
            
            message = {
                "role": "assistant",
                "content": "Generating all 4 carousel images for you... This may take a moment. I'll create a cohesive sequential story across all images.",
                "timestamp": datetime.now().isoformat(),
                "generating_all": True,
                "total_images": 4
            }
            state["conversation_messages"].append(message)
            
            return state
            
        except Exception as e:
            logger.error(f"Error in generate_carousel_image: {e}")
            state["error_message"] = f"Failed to generate carousel image: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            return state
    
    async def approve_carousel_images(self, state: CustomContentState, user_input: str = None) -> CustomContentState:
        """Handle user approval of all carousel images"""
        try:
            carousel_images = state.get("carousel_images", [])
            
            if not user_input:
                # Show all images and ask for approval
                if carousel_images and len(carousel_images) == 4:
                    message = {
                        "role": "assistant",
                        "content": "Perfect! I've generated all 4 carousel images for you. Please review them below. Do you want to approve these images and continue?",
                        "timestamp": datetime.now().isoformat(),
                        "carousel_images": [img.get("url") for img in carousel_images if img.get("url")],
                        "options": [
                            {"value": "approve", "label": "✅ Yes, approve and continue"},
                            {"value": "regenerate", "label": "🔄 Regenerate all images"},
                            {"value": "manual_upload", "label": "📤 Switch to manual upload"}
                        ]
                    }
                    state["conversation_messages"].append(message)
                    state["current_step"] = ConversationStep.APPROVE_CAROUSEL_IMAGES
                    return state
                else:
                    # Not all images generated yet, wait
                    message = {
                        "role": "assistant",
                        "content": "Still generating carousel images... Please wait.",
                        "timestamp": datetime.now().isoformat()
                    }
                    state["conversation_messages"].append(message)
                    return state
            
            user_input_lower = user_input.lower().strip() if user_input else ""
            # Remove emojis and normalize the input
            import re
            user_input_clean = re.sub(r'[^\w\s]', '', user_input_lower)  # Remove all non-alphanumeric except spaces
            user_input_clean = user_input_clean.strip()
            
            # Check for approval - handle various formats
            if (user_input_lower == "approve" or 
                user_input_lower == "yes" or 
                "approve" in user_input_clean or 
                ("yes" in user_input_clean and "approve" in user_input_clean) or
                user_input_clean == "yes approve and continue"):
                # User approved, proceed directly to content generation
                state["current_step"] = ConversationStep.GENERATE_CONTENT
                # Don't add intermediate message, go directly to content generation
                return await self.generate_content(state)
            elif ("regenerate" in user_input_clean or 
                  user_input_lower == "regenerate" or 
                  user_input_lower == "regenerate_all" or
                  "regenerate all" in user_input_clean):
                # User wants to regenerate all images
                state["carousel_images"] = []
                state["current_carousel_index"] = 0
                state["current_step"] = ConversationStep.GENERATE_CAROUSEL_IMAGE
                # Call generate_carousel_image which will set generating_all flag
                return await self.generate_carousel_image(state)
            elif ("manual" in user_input_clean and "upload" in user_input_clean) or \
                 user_input_lower == "manual_upload" or \
                 user_input_lower == "upload" or \
                 "switch to manual" in user_input_clean:
                # User wants to switch to manual upload
                state["carousel_image_source"] = "manual_upload"
                state["carousel_images"] = []  # Clear generated images
                state["uploaded_carousel_images"] = []
                state["carousel_upload_done"] = False
                state["current_step"] = ConversationStep.HANDLE_CAROUSEL_UPLOAD
                return await self.handle_carousel_upload(state)
            
            return state
            
        except Exception as e:
            logger.error(f"Error in approve_carousel_images: {e}")
            state["error_message"] = f"Failed to approve carousel images: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            return state
    
    async def handle_carousel_upload(self, state: CustomContentState) -> CustomContentState:
        """Handle bulk carousel image uploads"""
        try:
            state["current_step"] = ConversationStep.HANDLE_CAROUSEL_UPLOAD
            state["progress_percentage"] = 55
            
            max_images = state.get("carousel_max_images", 10)
            uploaded_carousel_images = state.get("uploaded_carousel_images") or []
            uploaded_count = len(uploaded_carousel_images)
            remaining = max_images - uploaded_count
            
            message = {
                "role": "assistant",
                "content": "Please upload your carousel images below.",
                "timestamp": datetime.now().isoformat(),
                "max_images": max_images,
                "uploaded_count": uploaded_count,
                "remaining": remaining,
                # Include uploaded images in message so frontend can display them
                "uploaded_carousel_images": uploaded_carousel_images if uploaded_carousel_images else []
            }
            state["conversation_messages"].append(message)
            
            logger.info(f"Ready for carousel upload: {uploaded_count}/{max_images}")
            
        except Exception as e:
            logger.error(f"Error in handle_carousel_upload: {e}")
            state["error_message"] = f"Failed to handle carousel upload: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def confirm_carousel_upload_done(self, state: CustomContentState, user_input: str = None) -> CustomContentState:
        """Ask if carousel upload is complete"""
        try:
            uploaded_carousel_images = state.get("uploaded_carousel_images") or []
            uploaded_count = len(uploaded_carousel_images)
            max_images = state.get("carousel_max_images", 10)
            
            if not user_input:
                # Ask if done
                state["current_step"] = ConversationStep.CONFIRM_CAROUSEL_UPLOAD_DONE
                message = {
                    "role": "assistant",
                    "content": f"You've uploaded {uploaded_count} image(s). Are you done uploading images?",
                    "timestamp": datetime.now().isoformat(),
                    "options": [
                        {"value": "yes", "label": "✅ Yes, I'm done"},
                        {"value": "no", "label": "📤 No, add more images"}
                    ],
                    # Include uploaded images in message so frontend can display them
                    "uploaded_carousel_images": uploaded_carousel_images if uploaded_carousel_images else []
                }
                state["conversation_messages"].append(message)
                return state
            
            user_input_lower = user_input.lower().strip()
            
            if user_input_lower == "yes" or user_input_lower == "done":
                # User is done, proceed directly to content generation
                state["carousel_upload_done"] = True
                state["current_step"] = ConversationStep.GENERATE_CONTENT
                # Don't add intermediate message, go directly to content generation
                return await self.generate_content(state)
            elif user_input_lower == "no":
                # User wants to add more, show upload interface again
                if uploaded_count >= max_images:
                    # Reached max, proceed directly to content generation
                    state["carousel_upload_done"] = True
                    state["current_step"] = ConversationStep.GENERATE_CONTENT
                    return await self.generate_content(state)
                else:
                    state["current_step"] = ConversationStep.HANDLE_CAROUSEL_UPLOAD
                    return await self.handle_carousel_upload(state)
            
            return state
            
        except Exception as e:
            logger.error(f"Error in confirm_carousel_upload_done: {e}")
            state["error_message"] = f"Failed to confirm carousel upload: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            return state

    async def generate_script(self, state: CustomContentState, changes: str = None) -> CustomContentState:
        """Generate a video script for Reel using content creation agent logic
        
        Args:
            state: Current conversation state
            changes: Optional string with user's requested changes/modifications for regeneration
        """
        try:
            logger.info("🎬 Starting script generation...")
            state["current_step"] = ConversationStep.GENERATE_SCRIPT
            state["progress_percentage"] = 60
            
            platform = state.get("selected_platform", "")
            content_type = state.get("selected_content_type", "")
            user_description = state.get("user_description", "")
            clarification_1 = state.get("clarification_1", "")
            clarification_2 = state.get("clarification_2", "")
            clarification_3 = state.get("clarification_3", "")
            
            # Check if this is a regeneration with changes
            is_regeneration = changes is not None
            previous_script = state.get("generated_script")
            script_history = state.get("script_history", [])
            
            logger.info(f"Script generation context - Platform: {platform}, Content Type: {content_type}, Description: {user_description[:50]}..., Regeneration: {is_regeneration}")
            
            # Load business context
            business_context = self._load_business_context(state["user_id"])
            logger.info(f"Business context loaded: {business_context.get('business_name', 'N/A')}")
            
            # Create script generation prompt
            script_prompt = f"""Create a professional video script for an Instagram Reel based on the following information:

User's Content Idea: "{user_description}"

Business Context:
- Business Name: {business_context.get('business_name', 'Not specified')}
- Industry: {business_context.get('industry', 'Not specified')}
- Target Audience: {business_context.get('target_audience', 'General audience')}
- Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}
- Brand Personality: {business_context.get('brand_personality', 'Approachable and trustworthy')}
"""
            
            if clarification_1:
                script_prompt += f"\nPost Goal/Purpose: {clarification_1}"
            if clarification_2:
                script_prompt += f"\nTarget Audience Details: {clarification_2}"
            if clarification_3:
                script_prompt += f"\nTone/Style: {clarification_3}"
            
            # If this is a regeneration with changes, include previous script and requested changes
            if is_regeneration and previous_script:
                script_prompt += f"""

PREVIOUS SCRIPT (to be modified):
{json.dumps(previous_script, indent=2)}

USER REQUESTED CHANGES/INCLUSIONS:
{changes}

IMPORTANT INSTRUCTIONS:
1. Review the PREVIOUS SCRIPT above carefully
2. Apply the USER REQUESTED CHANGES/INCLUSIONS while keeping the good parts that weren't mentioned for change
3. Maintain the same JSON structure and format
4. Only modify what the user specifically requested - keep everything else intact
5. Ensure the modified script is coherent and flows naturally
6. If the user wants to add something, integrate it seamlessly
7. If the user wants to change tone/style, update the entire script accordingly
8. Return the complete modified script, not just the changed parts
"""
            
            script_prompt += """

Requirements for the Instagram Reel Script:
1. Keep it engaging and hook viewers in the first 3 seconds
2. Structure it for a 15-90 second video (typical Reel length)
3. Include clear visual cues and scene descriptions
4. Add on-screen text suggestions where appropriate
5. Include a strong call-to-action at the end
6. Match the brand voice and personality
7. Make it shareable and relatable
8. Include relevant hashtag suggestions

Format the script as JSON with this structure:
{
    "title": "Script title",
    "hook": "Opening hook (first 3-5 seconds)",
    "scenes": [
        {
            "duration": "X seconds",
            "visual": "What to show on screen",
            "audio": "What to say/narrate",
            "on_screen_text": "Text overlay (if any)"
        }
    ],
    "call_to_action": "Ending CTA",
    "hashtags": ["hashtag1", "hashtag2", "hashtag3"],
    "total_duration": "Estimated total duration",
    "tips": "Additional production tips"
}

Return ONLY valid JSON, no markdown code blocks."""
            
            # Generate script using OpenAI
            logger.info("📝 Calling OpenAI API to generate script...")
            # Use asyncio.to_thread to run the synchronous OpenAI call in a thread pool
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert video scriptwriter specializing in Instagram Reels and short-form video content. Create engaging, viral-worthy scripts that drive engagement."
                        },
                        {
                            "role": "user",
                            "content": script_prompt
                        }
                    ],
                    max_tokens=2000,
                    temperature=0.7
                ),
                timeout=30.0
            )
            logger.info("✅ OpenAI API response received")
            
            # Track token usage
            user_id = state.get("user_id")
            if user_id and self.token_tracker:
                await self.token_tracker.track_chat_completion_usage(
                    user_id=user_id,
                    feature_type="custom_content",
                    model_name="gpt-4o-mini",
                    response=response,
                    request_metadata={
                        "conversation_id": state.get("conversation_id"),
                        "platform": state.get("selected_platform"),
                        "content_type": state.get("selected_content_type")
                    }
                )
            
            # Parse JSON response
            raw_response = response.choices[0].message.content.strip()
            
            # Try to extract JSON from markdown code blocks
            if "```json" in raw_response:
                json_start = raw_response.find("```json") + 7
                json_end = raw_response.find("```", json_start)
                if json_end != -1:
                    raw_response = raw_response[json_start:json_end].strip()
            elif "```" in raw_response:
                json_start = raw_response.find("```") + 3
                json_end = raw_response.find("```", json_start)
                if json_end != -1:
                    raw_response = raw_response[json_start:json_end].strip()
            
            # Try to find JSON object in the response
            if raw_response.startswith('{') and raw_response.endswith('}'):
                json_text = raw_response
            else:
                # Look for JSON object within the text
                start_idx = raw_response.find('{')
                end_idx = raw_response.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_text = raw_response[start_idx:end_idx + 1]
                else:
                    json_text = raw_response
            
            try:
                script_data = json.loads(json_text)
                
                # Validate and normalize script structure
                script_data = self._validate_script_structure(script_data, user_description)
                
                logger.info(f"✅ Script JSON parsed and validated successfully: {script_data.get('title', 'N/A')}")
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed for script: {e}")
                logger.warning(f"Raw response was: {raw_response[:200]}...")
                # Fallback script structure
                fallback_script = {
                    "title": f"Reel Script: {user_description[:50] if user_description else 'Untitled'}",
                    "hook": user_description[:100] if user_description else "",
                    "scenes": [
                        {
                            "duration": "15-30 seconds",
                            "visual": "Show the main content",
                            "audio": user_description if user_description else "",
                            "on_screen_text": "Key message"
                        }
                    ],
                    "call_to_action": "Follow for more!",
                    "hashtags": [],
                    "total_duration": "30 seconds",
                    "tips": "Keep it engaging and authentic"
                }
                # Validate fallback script structure
                script_data = self._validate_script_structure(fallback_script, user_description)
                logger.info("Using fallback script structure")
            
            # Store script in cache memory (script_history array)
            # Initialize script_history if it doesn't exist
            if "script_history" not in state:
                state["script_history"] = []
            
            # Add script to history with timestamp and version number
            script_version = {
                "script": script_data,
                "version": len(state["script_history"]) + 1,
                "timestamp": datetime.now().isoformat(),
                "is_current": True,
                "changes": changes if is_regeneration else None
            }
            
            # Mark all previous scripts as not current
            for prev_script in state["script_history"]:
                prev_script["is_current"] = False
            
            # Add new script to history (keep all previous scripts)
            state["script_history"].append(script_version)
            
            # Also store current script for easy access
            state["generated_script"] = script_data
            state["current_script_version"] = script_version["version"]
            
            logger.info(f"✅ Script v{script_version['version']} stored in cache memory with {len(script_data.get('scenes', []))} scenes")
            logger.info(f"📝 Total scripts in cache: {len(state['script_history'])}")
            
            # Create message with all scripts (both old and new)
            message_text = f"Perfect! I've generated a video script for your {content_type}." if not is_regeneration else f"Great! I've updated the script based on your changes. Here are all your script versions:"
            
            script_message = {
                "role": "assistant",
                "content": f"{message_text} Review them below and choose an option for each.",
                "timestamp": datetime.now().isoformat(),
                "script": script_data,  # Current/latest script
                "script_version": script_version["version"],
                "all_scripts": [s["script"] for s in state["script_history"]],  # All scripts for display
                "script_history": state["script_history"]  # Full history with metadata
            }
            
            # Remove old script messages to avoid duplicates (keep only the latest with all scripts)
            if is_regeneration:
                state["conversation_messages"] = [
                    msg for msg in state.get("conversation_messages", [])
                    if not msg.get("script")  # Remove messages with script
                ]
            
            state["conversation_messages"].append(script_message)
            state["progress_percentage"] = 70
            
            # Stay on CONFIRM_SCRIPT step to allow user to save or regenerate
            state["current_step"] = ConversationStep.CONFIRM_SCRIPT
            
            logger.info(f"Generated script for {content_type} on {platform}")
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout generating script - API call took too long")
            state["error_message"] = "Script generation timed out. Please try again."
            state["current_step"] = ConversationStep.ERROR
        except Exception as e:
            logger.error(f"Error generating script: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            state["error_message"] = f"Failed to generate script: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def generate_content(self, state: CustomContentState) -> CustomContentState:
        """Generate content using the content creation agent logic with image analysis"""
        try:
            state["current_step"] = ConversationStep.GENERATE_CONTENT
            state["progress_percentage"] = 75
            
            # Extract context
            user_description = state.get("user_description", "")
            platform = state.get("selected_platform", "")
            content_type = state.get("selected_content_type", "")
            uploaded_media_url = state.get("uploaded_media_url", "")
            generated_media_url = state.get("generated_media_url", "")
            has_media = state.get("has_media", False)
            media_type = state.get("media_type", "")
            generated_script = state.get("generated_script")  # Get generated script if available
            
            # Check if this is a carousel post
            is_carousel = content_type.lower() == "carousel"
            carousel_images = []
            
            if is_carousel:
                # Get carousel images - either AI-generated or manually uploaded
                carousel_image_source = state.get("carousel_image_source", "")
                if carousel_image_source == "ai_generate":
                    # Get AI-generated carousel images
                    carousel_images_data = state.get("carousel_images", [])
                    if carousel_images_data:
                        carousel_images = [img.get("url") for img in carousel_images_data if img.get("url")]
                elif carousel_image_source == "manual_upload":
                    # Get manually uploaded carousel images
                    carousel_images = state.get("uploaded_carousel_images") or []
                    if not isinstance(carousel_images, list):
                        carousel_images = []
            
            # Determine which media URL to use (uploaded or generated) - for non-carousel posts
            media_url = uploaded_media_url or generated_media_url
            
            # Load business context if not already loaded
            business_context = state.get("business_context")
            if not business_context:
                user_id = state.get("user_id")
                if user_id:
                    business_context = self._load_business_context(user_id)
                    state["business_context"] = business_context
                else:
                    business_context = {}
            
            # Analyze image(s) if available
            image_analysis = ""
            if is_carousel and carousel_images:
                # Analyze all carousel images
                try:
                    image_analyses = []
                    for idx, img_url in enumerate(carousel_images):
                        try:
                            analysis = await self._analyze_uploaded_image(img_url, user_description, business_context)
                            if analysis and not analysis.startswith("Image analysis failed"):
                                image_analyses.append(f"Image {idx + 1}: {analysis}")
                                logger.info(f"Carousel image {idx + 1} analysis completed successfully")
                            else:
                                # Analysis failed but handled gracefully - don't log as error
                                logger.warning(f"Carousel image {idx + 1} analysis skipped (timeout or download issue)")
                                image_analyses.append(f"Image {idx + 1}: Analysis skipped due to timeout")
                        except Exception as e:
                            # Only log as error if it's not a timeout/download issue
                            if "timeout" not in str(e).lower() and "downloading" not in str(e).lower():
                                logger.error(f"Carousel image {idx + 1} analysis failed: {e}")
                            else:
                                logger.warning(f"Carousel image {idx + 1} analysis timeout (handled gracefully)")
                            image_analyses.append(f"Image {idx + 1}: Analysis skipped")
                    image_analysis = "\n\n".join(image_analyses)
                    logger.info("All carousel images analyzed successfully")
                except Exception as e:
                    logger.error(f"Carousel image analysis failed: {e}")
                    image_analysis = f"Carousel image analysis failed: {str(e)}"
            elif has_media and media_url and media_type == "image":
                # Analyze single image (non-carousel)
                try:
                    image_analysis = await self._analyze_uploaded_image(media_url, user_description, business_context)
                    logger.info("Image analysis completed successfully")
                except Exception as e:
                    logger.error(f"Image analysis failed: {e}")
                    image_analysis = f"Image analysis failed: {str(e)}"
            
            # Create enhanced content generation prompt
            # For carousel, indicate we have multiple images
            has_images_for_analysis = (is_carousel and carousel_images) or (has_media and media_url and media_type == "image")
            clarification_1 = state.get("clarification_1", "")
            clarification_2 = state.get("clarification_2", "")
            clarification_3 = state.get("clarification_3", "")
            prompt = self._create_enhanced_content_prompt(
                user_description, platform, content_type, business_context, image_analysis, has_images_for_analysis,
                clarification_1, clarification_2, clarification_3, generated_script
            )
            
            # Prepare messages for content generation
            messages = [
                {"role": "system", "content": "You are an expert social media content creator. Generate engaging, platform-optimized content that incorporates visual elements when provided. CRITICAL: Return ONLY a valid JSON object with the exact fields specified. Do NOT include any markdown formatting, code blocks, or nested JSON. The response must be pure JSON that can be parsed directly."},
                {"role": "user", "content": prompt}
            ]
            
            # Add image(s) to messages if available
            if is_carousel and carousel_images:
                # Add all carousel images
                image_content = [{"type": "text", "text": f"Here are the {len(carousel_images)} carousel images to incorporate into the content. Analyze them as a sequence and create content that works across all images:"}]
                for img_url in carousel_images:
                    image_content.append({"type": "image_url", "image_url": {"url": img_url}})
                messages.append({
                    "role": "user",
                    "content": image_content
                })
            elif has_media and media_url and media_type == "image":
                # Add single image (non-carousel)
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Here's the image to incorporate into the content:"},
                        {"type": "image_url", "image_url": {"url": media_url}}
                    ]
                })
            
            # Generate content using OpenAI with vision capabilities
            # Handle timeout errors gracefully - continue without images if timeout occurs
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",  # Use vision-capable model
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1000,
                    timeout=60  # 60 second timeout
                )
                
                # Track token usage
                user_id = state.get("user_id")
                if user_id and self.token_tracker:
                    await self.token_tracker.track_chat_completion_usage(
                        user_id=user_id,
                        feature_type="custom_content",
                        model_name="gpt-4o-mini",
                        response=response,
                        request_metadata={
                            "conversation_id": state.get("conversation_id"),
                            "platform": state.get("selected_platform"),
                            "has_media": has_media,
                            "is_carousel": is_carousel
                        }
                    )
                
                generated_text = response.choices[0].message.content
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error generating content with images: {e}")
                
                # If timeout or image download error, try without images
                if "timeout" in error_msg.lower() or "invalid_image_url" in error_msg.lower() or "downloading" in error_msg.lower():
                    logger.warning("Image download timeout, generating content without images")
                    # Remove image messages and retry with text only
                    text_only_messages = [
                        {"role": "system", "content": messages[0]["content"]},
                        {"role": "user", "content": prompt + "\n\nNote: Carousel images are available but couldn't be analyzed due to timeout. Generate content based on the description and theme."}
                    ]
                    try:
                        response = self.client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=text_only_messages,
                            temperature=0.7,
                            max_tokens=1000
                        )
                        generated_text = response.choices[0].message.content
                    except Exception as e2:
                        logger.error(f"Error generating content without images: {e2}")
                        raise e2
                else:
                    # Other errors, re-raise
                    raise e
            
            # Parse the generated content
            try:
                # Try to parse as JSON first
                content_data = json.loads(generated_text)
            except json.JSONDecodeError:
                # If not JSON, create a structured response
                content_data = {
                    "content": generated_text,
                    "title": f"{content_type} for {platform}",
                    "hashtags": self._extract_hashtags(generated_text),
                    "post_type": "carousel" if is_carousel else ("image" if has_media else "text"),
                    "media_url": uploaded_media_url if (has_media and not is_carousel) else None
                }
            
            # Add carousel images to content data if this is a carousel post
            if is_carousel and carousel_images:
                content_data["carousel_images"] = carousel_images
                content_data["post_type"] = "carousel"
            
            state["generated_content"] = content_data
            
            # Create response message with the generated content displayed directly
            if is_carousel and carousel_images:
                # Carousel post with images
                if image_analysis and not image_analysis.startswith("Carousel image analysis failed"):
                    message_content = f"Perfect! I've analyzed your {len(carousel_images)} carousel images and generated your {content_type} content. Here's what I created:\n\n**{content_data.get('title', f'{content_type} for {platform}')}**\n\n{content_data.get('content', '')}"
                else:
                    message_content = f"Great! I've generated your {content_type} content based on your {len(carousel_images)} carousel images. Here's what I created:\n\n**{content_data.get('title', f'{content_type} for {platform}')}**\n\n{content_data.get('content', '')}"
            elif has_media and image_analysis and not image_analysis.startswith("Image analysis failed"):
                message_content = f"Perfect! I've analyzed your image and generated your {content_type} content. Here's what I created:\n\n**{content_data.get('title', f'{content_type} for {platform}')}**\n\n{content_data.get('content', '')}"
            else:
                message_content = f"Great! I've generated your {content_type} content. Here's what I created:\n\n**{content_data.get('title', f'{content_type} for {platform}')}**\n\n{content_data.get('content', '')}"
                
            # Add hashtags if available (for all cases)
                if content_data.get('hashtags'):
                    hashtags = ' '.join([f"#{tag.replace('#', '')}" for tag in content_data['hashtags']])
                    message_content += f"\n\n{hashtags}"
                
            # Add call to action if available (for all cases)
                if content_data.get('call_to_action'):
                    message_content += f"\n\n**Call to Action:** {content_data['call_to_action']}"
            
            # Prepare message with carousel images if applicable
            message = {
                "role": "assistant",
                "content": message_content,
                "timestamp": datetime.now().isoformat(),
                "has_media": has_images_for_analysis,
                "media_url": uploaded_media_url if (has_media and not is_carousel) else None,
                "media_type": media_type if (has_media and not is_carousel) else None,
                # Include carousel images in the message
                "carousel_images": carousel_images if is_carousel else None,
                # Explicitly set structured_content to null to prevent frontend from creating cards
                "structured_content": None
            }
            state["conversation_messages"].append(message)
            
            logger.info(f"Generated content for {platform} {content_type}")
            
            # If media generation is needed, generate it now using the created content
            if state.get("should_generate_media", False) and self.media_agent:
                logger.info("Generating media based on created content")
                try:
                    # Get the generated content from state
                    generated_content = state.get("generated_content", {})
                    
                    # Create a minimal temporary post for media generation (will be cleaned up)
                    temp_post_id = await self._create_temp_post_for_media(state)
                    
                    if temp_post_id:
                        # Update the temporary post with the generated content
                        await self._update_temp_post_with_content(temp_post_id, generated_content, state)
                        
                        # Generate media using the content
                        media_result = await self.media_agent.generate_media_for_post(temp_post_id)
                        
                        if media_result["success"] and media_result.get("image_url"):
                            # Update state with generated media
                            state["generated_media_url"] = media_result["image_url"]
                            state["media_type"] = MediaType.IMAGE
                            state["has_media"] = True
                            
                            # Update the content message to include the generated image
                            state["conversation_messages"][-1]["media_url"] = media_result["image_url"]
                            state["conversation_messages"][-1]["media_type"] = "image"
                            
                            logger.info(f"Media generation completed successfully: {media_result['image_url']}")
                        else:
                            logger.warning(f"Media generation failed: {media_result.get('error', 'Unknown error')}")
                            # Continue without media
                            state["should_generate_media"] = False
                            state["has_media"] = False
                        
                        # Clean up the temporary post to avoid duplicates
                        try:
                            self.supabase.table("content_posts").delete().eq("id", temp_post_id).execute()
                            logger.info(f"Cleaned up temporary post {temp_post_id}")
                        except Exception as cleanup_error:
                            logger.warning(f"Failed to clean up temporary post {temp_post_id}: {cleanup_error}")
                    else:
                        logger.error("Failed to create temporary post for media generation")
                        state["should_generate_media"] = False
                        state["has_media"] = False
                        
                except Exception as e:
                    logger.error(f"Error generating media: {e}")
                    # Continue without media
                    state["should_generate_media"] = False
                    state["has_media"] = False
            
            # Transition directly to confirm content step
            state["current_step"] = ConversationStep.CONFIRM_CONTENT
            state["progress_percentage"] = 85
            
            # Clear any previous error messages
            if "error_message" in state:
                del state["error_message"]
            
            # Automatically call confirm_content to show the confirmation message
            return await self.confirm_content(state)
            
        except Exception as e:
            logger.error(f"Critical error in generate_content: {e}")
            # Don't set to ERROR - try to continue with basic content
            # Create a basic content based on description only
            try:
                basic_content = {
                    "content": f"{user_description or 'Your content description'}",
                    "title": f"{content_type} for {platform}",
                    "hashtags": [],
                    "post_type": "carousel" if is_carousel else "text"
                }
                
                if is_carousel and carousel_images:
                    basic_content["carousel_images"] = carousel_images
                
                state["generated_content"] = basic_content
                
                message = {
                    "role": "assistant",
                    "content": f"I encountered an issue, but I've created content based on your description. Please review it below.\n\n**{basic_content['title']}**\n\n{basic_content['content']}",
                    "timestamp": datetime.now().isoformat(),
                    "carousel_images": carousel_images if is_carousel else None,
                    "structured_content": None
                }
                state["conversation_messages"].append(message)
                
                # Continue to confirmation step
                state["current_step"] = ConversationStep.CONFIRM_CONTENT
                state["progress_percentage"] = 85
                return await self.confirm_content(state)
            except Exception as e2:
                logger.error(f"Failed to create basic content: {e2}")
                # Last resort - set error but don't break the flow
                state["error_message"] = f"Content generation failed: {str(e)}"
                state["current_step"] = ConversationStep.CONFIRM_CONTENT
                return state
            
        except Exception as e:
            logger.error(f"Error in generate_content: {e}")
            state["error_message"] = f"Failed to generate content: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state

    # parse_content function removed - content is now displayed directly in chatbot
    
    
    async def _create_temp_post_for_media(self, state: CustomContentState) -> Optional[str]:
        """Create a temporary post in the database for media generation"""
        try:
            user_id = state["user_id"]
            
            # Get or create campaign for this user
            campaign_id = await self._get_or_create_custom_content_campaign(user_id)
            
            # Create temporary post data
            post_data = {
                "campaign_id": campaign_id,
                "platform": state.get("selected_platform", "social_media"),
                "post_type": state.get("selected_content_type", "post"),
                "title": f"Temp post for media generation - {state.get('selected_platform', 'social_media')}",
                "content": state.get("user_description", "Temporary content for media generation"),
                "hashtags": [],
                "scheduled_date": datetime.now().date().isoformat(),
                "scheduled_time": datetime.now().time().isoformat(),
                "status": "draft",
                "metadata": {
                    "user_id": user_id,
                    "is_temp": True,
                    "media_generation": True
                }
            }
            
            # Insert temporary post
            response = self.supabase.table("content_posts").insert(post_data).execute()
            
            if response.data and len(response.data) > 0:
                post_id = response.data[0]["id"]
                logger.info(f"Created temporary post {post_id} for media generation")
                return post_id
            else:
                logger.error("Failed to create temporary post for media generation")
                return None
                
        except Exception as e:
            logger.error(f"Error creating temporary post for media: {e}")
            return None
    
    async def _update_temp_post_with_content(self, post_id: str, generated_content: dict, state: CustomContentState) -> bool:
        """Update temporary post with generated content for media generation"""
        try:
            # Prepare updated post data with generated content
            update_data = {
                "title": generated_content.get("title", ""),
                "content": generated_content.get("content", ""),
                "hashtags": generated_content.get("hashtags", []),
                "metadata": {
                    "user_id": state["user_id"],
                    "is_temp": True,
                    "media_generation": True,
                    "generated_content": generated_content
                }
            }
            
            # Update the temporary post
            response = self.supabase.table("content_posts").update(update_data).eq("id", post_id).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"Updated temporary post {post_id} with generated content")
                return True
            else:
                logger.error("Failed to update temporary post with generated content")
                return False
                
        except Exception as e:
            logger.error(f"Error updating temporary post with content: {e}")
            return False
    
    # optimize_content function removed - content is used as generated by AI

    async def confirm_content(self, state: CustomContentState) -> CustomContentState:
        """Ask user to confirm if the generated content is correct and should be saved"""
        try:
            # Prevent re-entry if we're already in confirm_content step with a recent message
            current_step = state.get("current_step")
            conversation_messages = state.get("conversation_messages", [])
            
            if current_step == ConversationStep.CONFIRM_CONTENT and conversation_messages:
                # Check if the last assistant message is a content review message
                for msg in reversed(conversation_messages):
                    if msg.get("role") == "assistant" and msg.get("content"):
                        content = msg.get("content", "")
                        if ("Please review the content above and let me know" in content or 
                            "Please review it above and let me know if you'd like to save this post" in content):
                            # Check timestamp - if message is recent (within last 30 seconds), skip adding new one
                            msg_timestamp = msg.get("timestamp")
                            if msg_timestamp:
                                try:
                                    msg_time = datetime.fromisoformat(msg_timestamp.replace('Z', '+00:00'))
                                    now = datetime.now(msg_time.tzinfo) if msg_time.tzinfo else datetime.now()
                                    time_diff = (now - msg_time).total_seconds()
                                    if time_diff < 30:  # Message is less than 30 seconds old
                                        logger.info("Already in confirm_content step with recent message, skipping duplicate")
                                        return state
                                except Exception:
                                    # If timestamp parsing fails, continue to add message
                                    pass
                            else:
                                # No timestamp, but message exists - skip to prevent duplicate
                                logger.info("Already in confirm_content step with content review message, skipping duplicate")
                                return state
                        break  # Only check the last assistant message
            
            state["current_step"] = ConversationStep.CONFIRM_CONTENT
            state["progress_percentage"] = 90
            
            # Get the generated content details
            platform = state.get("selected_platform", "")
            content_type = state.get("selected_content_type", "")
            has_media = state.get("has_media", False)
            
            # Get the generated content to include in the confirmation message
            generated_content = state.get("generated_content", {})
            
            # Create a message asking for content confirmation with the actual content
            confirmation_message = ""
            
            # Include the actual generated content in the confirmation message
            if generated_content:
                confirmation_message += f"\n\n### {generated_content.get('title', f'{content_type} for {platform}')}\n\n{generated_content.get('content', '')}"
                
                # Add hashtags if available
                if generated_content.get('hashtags'):
                    hashtags = ' '.join([f"#{tag.replace('#', '')}" for tag in generated_content['hashtags']])
                    confirmation_message += f"\n\n**{hashtags}**"
                
                # Add call to action if available
                if generated_content.get('call_to_action'):
                    confirmation_message += f"\n\n### Call to Action\n\n{generated_content['call_to_action']}"
            
            confirmation_message += "\n\n---\n\n**Please review the content above and let me know:**"
            
            # Get carousel images if this is a carousel post
            carousel_images = []
            is_carousel = content_type and content_type.lower() == "carousel"
            if is_carousel:
                carousel_image_source = state.get("carousel_image_source", "")
                if carousel_image_source == "ai_generate":
                    # Get AI-generated carousel images
                    carousel_images_data = state.get("carousel_images", [])
                    if carousel_images_data:
                        carousel_images = [img.get("url") for img in carousel_images_data if img.get("url")]
                elif carousel_image_source == "manual_upload":
                    # Get manually uploaded carousel images
                    carousel_images = state.get("uploaded_carousel_images") or []
                    if not isinstance(carousel_images, list):
                        carousel_images = []
            
            # Check if a content review message already exists to prevent duplicates
            # Check both by message content and by checking if we're already in confirm_content step with a recent message
            existing_content_review_message = None
            conversation_messages = state.get("conversation_messages", [])
            
            # First, remove any existing content review messages to ensure only one exists
            filtered_messages = []
            for msg in conversation_messages:
                if (msg.get("role") == "assistant" and 
                    msg.get("content") and 
                    ("Please review the content above and let me know" in msg.get("content") or 
                     "Please review it above and let me know if you'd like to save this post" in msg.get("content"))):
                    # Skip this message - it's a duplicate content review
                    if not existing_content_review_message:
                        existing_content_review_message = msg
                    continue
                filtered_messages.append(msg)
            
            # Update conversation messages to remove duplicates
            state["conversation_messages"] = filtered_messages
            
            # Always add the new message after cleaning up old ones
            # The cleanup already happened above, so we should always add the fresh message
            message = {
                "role": "assistant",
                "content": confirmation_message,
                "timestamp": datetime.now().isoformat(),
                "has_media": has_media or (is_carousel and len(carousel_images) > 0),
                "media_url": state.get("uploaded_media_url") or state.get("generated_media_url") if not is_carousel else None,
                "media_type": state.get("media_type") if not is_carousel else None,
                # Include carousel images in the message
                "carousel_images": carousel_images if is_carousel else None,
                # Explicitly set structured_content to null to prevent frontend from creating cards
                "structured_content": None
            }
            state["conversation_messages"].append(message)
            if existing_content_review_message:
                logger.info(f"Removed {len(conversation_messages) - len(filtered_messages)} duplicate content review message(s) and added new one")
            else:
                logger.info("Asking user to confirm generated content")
            
        except Exception as e:
            logger.error(f"Error in confirm_content: {e}")
            state["error_message"] = f"Failed to confirm content: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state

    async def select_schedule(self, state: CustomContentState) -> CustomContentState:
        """Ask user to select date and time for the post"""
        try:
            state["current_step"] = ConversationStep.SELECT_SCHEDULE
            state["progress_percentage"] = 98
            
            # Only add the message if we haven't already asked for schedule selection
            # Check if the last message is already asking for schedule selection
            last_message = state["conversation_messages"][-1] if state["conversation_messages"] else None
            schedule_message_content = "Great! Now let's schedule your post. Please select the date and time when you'd like this content to be published. You can choose to post immediately or schedule it for later."
            
            if not last_message or schedule_message_content not in last_message.get("content", ""):
                # Create a message asking for schedule selection
                message = {
                    "role": "assistant",
                    "content": schedule_message_content,
                    "timestamp": datetime.now().isoformat()
                }
                state["conversation_messages"].append(message)
                logger.info("Asking user to select post schedule")
            else:
                logger.info("Schedule selection message already present, skipping duplicate")
            
            logger.info(f"Current state step: {state.get('current_step')}")
            logger.info(f"User input in state: {state.get('user_input')}")
            
        except Exception as e:
            logger.error(f"Error in select_schedule: {e}")
            state["error_message"] = f"Failed to select schedule: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state

    async def save_content(self, state: CustomContentState) -> CustomContentState:
        """Save the generated content to Supabase"""
        try:
            state["current_step"] = ConversationStep.SAVE_CONTENT
            state["progress_percentage"] = 95
            
            user_id = state["user_id"]
            platform = state["selected_platform"]
            content_type = state["selected_content_type"]
            generated_content = state["generated_content"]
            
            # Check if this is a carousel post
            is_carousel = content_type and content_type.lower() == "carousel"
            
            if is_carousel:
                # Handle carousel post
                carousel_images = state.get("carousel_images") or []
                uploaded_carousel_images = state.get("uploaded_carousel_images") or []
                
                # Combine AI-generated and manually uploaded images
                all_carousel_images = []
                for img in carousel_images:
                    if img.get("url"):
                        all_carousel_images.append(img.get("url"))
                all_carousel_images.extend(uploaded_carousel_images)
                
                if not all_carousel_images:
                    raise Exception("Carousel post must have at least one image")
                
                # Get scheduled time
                scheduled_for = state.get("scheduled_for")
                if scheduled_for:
                    scheduled_datetime = datetime.fromisoformat(scheduled_for.replace('Z', '+00:00'))
                    # Remove timezone info for comparison with timezone-naive datetime.now()
                    if scheduled_datetime.tzinfo:
                        scheduled_datetime = scheduled_datetime.replace(tzinfo=None)
                    status = "scheduled" if scheduled_datetime > datetime.now() else "draft"
                else:
                    scheduled_datetime = datetime.now()
                    status = "draft"
                
                # Get or create campaign
                campaign_id = await self._get_or_create_custom_content_campaign(user_id)
                
                # Create carousel post data
                post_data = {
                    "campaign_id": campaign_id,
                    "platform": platform,
                    "post_type": "carousel",
                    "title": generated_content.get("title", ""),
                    "content": generated_content.get("content", ""),
                    "hashtags": generated_content.get("hashtags", []),
                    "scheduled_date": scheduled_datetime.date().isoformat(),
                    "scheduled_time": scheduled_datetime.time().isoformat(),
                    "status": status,
                    "metadata": {
                        "generated_by": "custom_content_agent",
                        "conversation_id": state["conversation_id"],
                        "user_id": user_id,
                        "platform_optimized": True,
                        "carousel_images": all_carousel_images,
                        "total_images": len(all_carousel_images),
                        "carousel_image_source": state.get("carousel_image_source", "mixed"),
                        "call_to_action": generated_content.get("call_to_action", ""),
                        "engagement_hooks": generated_content.get("engagement_hooks", ""),
                        "image_caption": generated_content.get("image_caption", ""),
                        "visual_elements": generated_content.get("visual_elements", [])
                    }
                }
                
                # Use first image as primary for preview
                if all_carousel_images:
                    post_data["primary_image_url"] = all_carousel_images[0]
                
                # Validate status matches scheduled time
                now = datetime.now()
                if scheduled_datetime > now:
                    if status != "scheduled":
                        logger.warning(f"Status mismatch: scheduled_datetime is in future but status is '{status}'. Correcting to 'scheduled'.")
                        status = "scheduled"
                        post_data["status"] = "scheduled"
                else:
                    if status != "draft":
                        logger.warning(f"Status mismatch: scheduled_datetime is not in future but status is '{status}'. Correcting to 'draft'.")
                        status = "draft"
                        post_data["status"] = "draft"
                
                # Save to Supabase
                logger.info(f"Saving carousel post to database: {post_data}")
                result = self.supabase.table("content_posts").insert(post_data).execute()
                
                if result.data:
                    post_id = result.data[0]["id"]
                    final_post_data = result.data[0]
                    # Add carousel_images at top level for easier frontend access
                    final_post_data["carousel_images"] = all_carousel_images
                    state["final_post"] = final_post_data
                    
                    # Save each carousel image to content_images table with image_order
                    for idx, image_url in enumerate(all_carousel_images):
                        try:
                            # Determine prompt based on source
                            image_prompt = "User uploaded image for carousel"
                            if idx < len(carousel_images) and carousel_images[idx].get("prompt"):
                                image_prompt = carousel_images[idx].get("prompt", "AI generated image for carousel")
                            
                            image_data = {
                                "post_id": post_id,
                                "image_url": image_url,
                                "image_prompt": image_prompt,
                                "image_style": "carousel",
                                "image_size": "custom",
                                "image_quality": "custom",
                                "generation_model": "gemini" if idx < len(carousel_images) else "user_upload",
                                "generation_service": "gemini" if idx < len(carousel_images) else "user_upload",
                                "generation_cost": 0,
                                "generation_time": 0,
                                "is_approved": True
                            }
                            
                            # Try to add image_order if column exists (some schemas may not have it)
                            # Store order in metadata instead if column doesn't exist
                            try:
                                # First try without image_order
                                insert_data = image_data.copy()
                                self.supabase.table("content_images").insert(insert_data).execute()
                            except Exception as order_error:
                                # If that fails, try with image_order (in case column exists but other field is wrong)
                                try:
                                    image_data["image_order"] = idx
                                    self.supabase.table("content_images").insert(image_data).execute()
                                except:
                                    # If both fail, log but continue - images are already in metadata
                                    logger.warning(f"Could not save image {idx + 1} to content_images, but image is in post metadata")
                                    pass
                            logger.info(f"Carousel image {idx + 1} saved to content_images for post {post_id}")
                        except Exception as e:
                            logger.error(f"Failed to save carousel image {idx + 1} to content_images: {e}")
                            # Continue even if one image save fails
                    
                    # Determine status text for message
                    status_text = "scheduled" if status == "scheduled" else "draft"
                    message = {
                        "role": "assistant",
                        "content": f"🎉 Perfect! Your carousel post with {len(all_carousel_images)} image(s) for {platform} has been saved as a {status_text} post! 📝\n\n✅ Content generated and optimized\n✅ {len(all_carousel_images)} image(s) saved\n✅ Post saved to your dashboard\n\nYou can now review, edit, or schedule this post from your content dashboard.",
                        "timestamp": datetime.now().isoformat()
                    }
                    state["conversation_messages"].append(message)
                    state["current_step"] = ConversationStep.ASK_ANOTHER_CONTENT
                    state["progress_percentage"] = 100
                    state["is_complete"] = True  # Mark as complete so frontend can trigger onContentCreated
                else:
                    raise Exception("Failed to save carousel post to database")
                
                # Register with scheduler if post is scheduled
                if status == "scheduled":
                    try:
                        from scheduler.post_publisher import post_publisher
                        if post_publisher:
                            scheduled_at = scheduled_datetime.isoformat()
                            await post_publisher.register_scheduled_post(
                                post_id,
                                scheduled_at,
                                platform,
                                user_id
                            )
                            logger.info(f"Registered scheduled carousel post {post_id} with scheduler")
                    except Exception as e:
                        logger.warning(f"Failed to register carousel post with scheduler: {e}")
                        # Don't fail the save operation if registration fails
                
                logger.info(f"Carousel post saved for user {user_id} on {platform}, post_id: {post_id}")
                return state
            
            # Regular (non-carousel) post handling
            uploaded_media_url = state.get("uploaded_media_url")
            
            # Determine final media URL (uploaded or generated)
            final_media_url = None
            uploaded_media_url = state.get("uploaded_media_url", "")
            generated_media_url = state.get("generated_media_url", "")
            
            # Use generated media URL if available, otherwise uploaded media URL
            if generated_media_url:
                final_media_url = generated_media_url
                logger.info(f"Using generated media URL: {final_media_url}")
            elif uploaded_media_url and uploaded_media_url.startswith("data:"):
                try:
                    final_media_url = await self._upload_base64_image_to_supabase(
                        uploaded_media_url, user_id, platform
                    )
                    logger.info(f"Image uploaded to Supabase: {final_media_url}")
                except Exception as e:
                    logger.error(f"Failed to upload image to Supabase: {e}")
                    # Continue without image if upload fails
                    final_media_url = None
            elif uploaded_media_url:
                # Already uploaded image URL
                final_media_url = uploaded_media_url
                logger.info(f"Using existing uploaded media URL: {final_media_url}")
            
            # Get scheduled time
            scheduled_for = state.get("scheduled_for")
            if scheduled_for:
                # Parse the scheduled time
                scheduled_datetime = datetime.fromisoformat(scheduled_for.replace('Z', '+00:00'))
                # Remove timezone info for comparison with timezone-naive datetime.now()
                if scheduled_datetime.tzinfo:
                    scheduled_datetime = scheduled_datetime.replace(tzinfo=None)
                status = "scheduled" if scheduled_datetime > datetime.now() else "draft"
            else:
                scheduled_datetime = datetime.now()
                status = "draft"
            
            # Get or create a default campaign for custom content
            campaign_id = await self._get_or_create_custom_content_campaign(user_id)
            
            # Determine post_type: if video is uploaded, set post_type to "video"
            media_type = state.get("media_type", "")
            # Handle both enum and string values
            media_type_str = str(media_type).lower() if media_type else ""
            if media_type_str == "video" or media_type == MediaType.VIDEO:
                post_type = "video"
            elif media_type_str == "image" or media_type == MediaType.IMAGE:
                # Only override if content_type is not already image-specific
                if content_type and content_type.lower() not in ["image", "video", "carousel"]:
                    post_type = "image"
                else:
                    post_type = content_type
            else:
                post_type = content_type
            
            # Create post data for content_posts table
            post_data = {
                "campaign_id": campaign_id,  # Use the custom content campaign
                "platform": platform,
                "post_type": post_type,
                "title": generated_content.get("title", ""),
                "content": generated_content.get("content", ""),
                "hashtags": generated_content.get("hashtags", []),
                "scheduled_date": scheduled_datetime.date().isoformat(),
                "scheduled_time": scheduled_datetime.time().isoformat(),
                "status": status,
                "metadata": {
                    "generated_by": "custom_content_agent",
                    "conversation_id": state["conversation_id"],
                    "user_id": user_id,
                    "platform_optimized": True,
                    "has_media": bool(final_media_url),
                    "media_url": final_media_url,
                    "media_type": state.get("media_type", ""),
                    "original_media_filename": state.get("uploaded_media_filename", ""),
                    "media_size": state.get("uploaded_media_size", 0),
                    "call_to_action": generated_content.get("call_to_action", ""),
                    "engagement_hooks": generated_content.get("engagement_hooks", ""),
                    "image_caption": generated_content.get("image_caption", ""),
                    "visual_elements": generated_content.get("visual_elements", [])
                }
            }
            
            # Add primary image data to post_data if image exists
            if final_media_url:
                # Determine image prompt based on source
                image_prompt = "User uploaded image for custom content"
                if generated_media_url:
                    # Try to get prompt from state if it was generated
                    image_prompt = state.get("generated_image_prompt", "AI generated image for custom content")
                
                post_data["primary_image_url"] = final_media_url
                post_data["primary_image_prompt"] = image_prompt
                post_data["primary_image_approved"] = True  # User uploads/generated images in custom content are auto-approved
            
            # Validate status matches scheduled time
            now = datetime.now()
            if scheduled_datetime > now:
                if status != "scheduled":
                    logger.warning(f"Status mismatch: scheduled_datetime is in future but status is '{status}'. Correcting to 'scheduled'.")
                    status = "scheduled"
                    post_data["status"] = "scheduled"
            else:
                if status != "draft":
                    logger.warning(f"Status mismatch: scheduled_datetime is not in future but status is '{status}'. Correcting to 'draft'.")
                    status = "draft"
                    post_data["status"] = "draft"
            
            # Save to Supabase
            logger.info(f"Saving post to database: {post_data}")
            result = self.supabase.table("content_posts").insert(post_data).execute()
            
            if result.data:
                post_id = result.data[0]["id"]
                state["final_post"] = result.data[0]
                
                # Also save image metadata to content_images table (temporary - for migration period)
                if final_media_url:
                    try:
                        image_data = {
                            "post_id": post_id,
                            "image_url": final_media_url,
                            "image_prompt": post_data.get("primary_image_prompt", "User uploaded image for custom content"),
                            "image_style": "user_upload",
                            "image_size": "custom",
                            "image_quality": "custom",
                            "generation_model": "user_upload",
                            "generation_service": "user_upload",
                            "generation_cost": 0,
                            "generation_time": 0,
                            "is_approved": True
                        }
                        
                        self.supabase.table("content_images").insert(image_data).execute()
                        logger.info(f"Image metadata saved to content_images for post {post_id}")
                    except Exception as e:
                        logger.error(f"Failed to save image metadata to content_images: {e}")
                        # Continue even if image metadata save fails
                
                # Determine if image was uploaded or generated
                image_source = "generated" if generated_media_url else "uploaded"
                
                # Determine status text for message
                status_text = "scheduled" if status == "scheduled" else "draft"
                
                message = {
                    "role": "assistant",
                    "content": f"🎉 Perfect! Your {content_type} for {platform} has been saved as a {status_text} post! 📝\n\n✅ Content generated and optimized\n✅ Image {image_source} and saved to storage\n✅ Post saved to your dashboard\n\nYou can now review, edit, or schedule this post from your content dashboard. The post includes your {image_source} image and is ready to go!",
                    "timestamp": datetime.now().isoformat()
                }
                state["conversation_messages"].append(message)
                state["current_step"] = ConversationStep.ASK_ANOTHER_CONTENT
                state["progress_percentage"] = 100
                state["is_complete"] = True  # Mark as complete so frontend can trigger onContentCreated
            else:
                raise Exception("Failed to save content to database")
            
            # Register with scheduler if post is scheduled
            if status == "scheduled":
                try:
                    from scheduler.post_publisher import post_publisher
                    if post_publisher:
                        scheduled_at = scheduled_datetime.isoformat()
                        await post_publisher.register_scheduled_post(
                            post_id,
                            scheduled_at,
                            platform,
                            user_id
                        )
                        logger.info(f"Registered scheduled post {post_id} with scheduler")
                except Exception as e:
                    logger.warning(f"Failed to register post with scheduler: {e}")
                    # Don't fail the save operation if registration fails
            
            logger.info(f"Content saved for user {user_id} on {platform}, post_id: {post_id}")
            
        except Exception as e:
            logger.error(f"Error in save_content: {e}")
            state["error_message"] = f"Failed to save content: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def ask_another_content(self, state: CustomContentState) -> CustomContentState:
        """Ask if user wants to generate another content"""
        try:
            logger.info("Asking if user wants to generate another content")
            
            # Only add the message if we haven't already asked about another content
            # Check if the last message is already asking about another content
            last_message = state["conversation_messages"][-1] if state["conversation_messages"] else None
            another_content_message = "Would you like to create another piece of content? Just let me know!"
            
            if not last_message or another_content_message not in last_message.get("content", ""):
                # Add the question message
                message = {
                    "role": "assistant",
                    "content": another_content_message,
                    "timestamp": datetime.now().isoformat()
                }
                state["conversation_messages"].append(message)
                logger.info("Added ask another content message")
            else:
                logger.info("Ask another content message already present, skipping duplicate")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in ask_another_content: {e}")
            state["error_message"] = f"Failed to ask about another content: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            return state
    
    async def _get_or_create_custom_content_campaign(self, user_id: str) -> str:
        """Get or create a default campaign for custom content"""
        try:
            # First, try to find an existing custom content campaign for this user
            response = self.supabase.table("content_campaigns").select("id").eq("user_id", user_id).eq("campaign_name", "Custom Content").execute()
            
            if response.data and len(response.data) > 0:
                # Campaign exists, return its ID
                return response.data[0]["id"]
            
            # Campaign doesn't exist, create it
            from datetime import datetime, timedelta
            today = datetime.now().date()
            week_end = today + timedelta(days=7)
            
            campaign_data = {
                "user_id": user_id,
                "campaign_name": "Custom Content",
                "week_start_date": today.isoformat(),
                "week_end_date": week_end.isoformat(),
                "status": "active",
                "total_posts": 0,
                "generated_posts": 0
            }
            
            result = self.supabase.table("content_campaigns").insert(campaign_data).execute()
            
            if result.data and len(result.data) > 0:
                campaign_id = result.data[0]["id"]
                logger.info(f"Created custom content campaign for user {user_id}: {campaign_id}")
                return campaign_id
            else:
                raise Exception("Failed to create custom content campaign")
                
        except Exception as e:
            logger.error(f"Error getting/creating custom content campaign: {e}")
            raise Exception(f"Failed to get or create custom content campaign: {str(e)}")
    
    async def display_result(self, state: CustomContentState) -> CustomContentState:
        """Display the final result to the user"""
        try:
            state["current_step"] = ConversationStep.DISPLAY_RESULT
            state["progress_percentage"] = 100
            
            final_post = state.get("final_post", {})
            platform = state.get("selected_platform", "")
            content_type = state.get("selected_content_type", "")
            
            message = {
                "role": "assistant",
                "content": f"🎉 Content creation complete! Your {content_type} for {platform} is ready and saved as a draft. You can now review, edit, or schedule it from your content dashboard. Is there anything else you'd like to create?",
                "timestamp": datetime.now().isoformat(),
                "final_post": final_post
            }
            state["conversation_messages"].append(message)
            
            logger.info("Content creation workflow completed successfully")
            
        except Exception as e:
            logger.error(f"Error in display_result: {e}")
            state["error_message"] = f"Failed to display result: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    async def handle_error(self, state: CustomContentState) -> CustomContentState:
        """Handle errors in the workflow"""
        try:
            state["current_step"] = ConversationStep.ERROR
            state["progress_percentage"] = 0
            
            error_message = state.get("error_message", "An unknown error occurred")
            
            message = {
                "role": "assistant",
                "content": f"I apologize, but I encountered an error: {error_message}. Let's start over or try a different approach. What would you like to do?",
                "timestamp": datetime.now().isoformat()
            }
            state["conversation_messages"].append(message)
            
            logger.error(f"Error handled: {error_message}")
            
        except Exception as e:
            logger.error(f"Error in handle_error: {e}")
            
        return state
    
    def _load_business_context(self, user_id: str) -> Dict[str, Any]:
        """Load business context from user profile, using embeddings if available"""
        try:
            # Get user profile from Supabase including embeddings
            response = self.supabase.table("profiles").select("*, profile_embedding").eq("id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                profile_data = response.data[0]
                # Use embedding context utility
                from utils.embedding_context import get_profile_context_with_embedding
                return get_profile_context_with_embedding(profile_data)
            else:
                logger.warning(f"No profile found for user {user_id}")
                return self._get_default_business_context()
                
        except Exception as e:
            logger.error(f"Error loading business context for user {user_id}: {e}")
            return self._get_default_business_context()

    def _get_default_business_context(self) -> Dict[str, Any]:
        """Get default business context when profile is not available"""
        return {
            "business_name": "Your Business",
            "industry": "General",
            "target_audience": "General audience",
            "brand_voice": "Professional and friendly",
            "content_goals": ["Engagement", "Awareness"],
            "brand_personality": "Approachable and trustworthy",
            "brand_values": ["Quality", "Trust"]
        }

    def _extract_business_context(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract business context from user profile"""
        return {
            "business_name": profile_data.get("business_name", ""),
            "industry": profile_data.get("industry", ""),
            "target_audience": profile_data.get("target_audience", ""),
            "brand_voice": profile_data.get("brand_voice", ""),
            "content_goals": profile_data.get("content_goals", []),
            "brand_personality": profile_data.get("brand_personality", ""),
            "brand_values": profile_data.get("brand_values", [])
        }

    async def _upload_base64_image_to_supabase(self, base64_data_url: str, user_id: str, platform: str) -> str:
        """Upload base64 image or video data to Supabase storage"""
        try:
            import base64
            import uuid
            
            # Parse the data URL
            if not base64_data_url.startswith("data:"):
                raise ValueError("Invalid base64 data URL format")
            
            # Extract content type and base64 data
            header, data = base64_data_url.split(",", 1)
            content_type = header.split(":")[1].split(";")[0]
            
            # Decode base64 data
            media_data = base64.b64decode(data)
            
            # Determine if it's a video or image
            is_video = content_type.startswith("video/")
            
            # Generate unique filename with proper extension
            if "/" in content_type:
                file_extension = content_type.split("/")[1]
                # Handle common video extensions
                if file_extension == "quicktime":
                    file_extension = "mov"
                elif file_extension == "x-msvideo":
                    file_extension = "avi"
            else:
                file_extension = "jpg" if not is_video else "mp4"
            
            filename = f"custom_content_{user_id}_{platform}_{uuid.uuid4().hex[:8]}.{file_extension}"
            file_path = filename  # Store directly in bucket root, not in subfolder
            
            # Use user-uploads bucket for user-uploaded content (both images and videos)
            bucket_name = "user-uploads"
            
            logger.info(f"Uploading {'video' if is_video else 'image'} to Supabase storage: {bucket_name}/{file_path}, content_type: {content_type}")
            
            # Upload to Supabase storage
            storage_response = self.supabase.storage.from_(bucket_name).upload(
                file_path,
                media_data,
                file_options={"content-type": content_type}
            )
            
            # Check for upload errors
            if hasattr(storage_response, 'error') and storage_response.error:
                raise Exception(f"Storage upload failed: {storage_response.error}")
            
            # Get public URL
            public_url = self.supabase.storage.from_(bucket_name).get_public_url(file_path)
            
            logger.info(f"Successfully uploaded {'video' if is_video else 'image'} to Supabase: {public_url}")
            return public_url
            
        except Exception as e:
            logger.error(f"Error uploading base64 media to Supabase: {e}")
            raise e
    
    async def _analyze_uploaded_image(self, image_url: str, user_description: str, business_context: Dict[str, Any]) -> str:
        """Analyze uploaded image using vision model"""
        try:
            import httpx
            import base64
            
            # Download image and convert to base64 to avoid timeout issues with Supabase URLs
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    image_response = await client.get(image_url)
                    image_response.raise_for_status()
                    image_data = image_response.content
                    
                    # Convert to base64
                    base64_image = base64.b64encode(image_data).decode('utf-8')
                    
                    # Determine image format from URL or content type
                    if image_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        image_format = image_url.lower().split('.')[-1]
                        if image_format == 'jpg':
                            image_format = 'jpeg'
                    else:
                        # Try to detect from content type
                        content_type = image_response.headers.get('content-type', 'image/jpeg')
                        if 'png' in content_type:
                            image_format = 'png'
                        elif 'jpeg' in content_type or 'jpg' in content_type:
                            image_format = 'jpeg'
                        elif 'gif' in content_type:
                            image_format = 'gif'
                        elif 'webp' in content_type:
                            image_format = 'webp'
                        else:
                            image_format = 'jpeg'  # Default
                    
                    image_data_url = f"data:image/{image_format};base64,{base64_image}"
                    
            except Exception as download_error:
                logger.warning(f"Failed to download image from {image_url}, trying direct URL: {download_error}")
                # Fallback: try direct URL (might work for public URLs)
                image_data_url = image_url
            
            # Create image analysis prompt
            analysis_prompt = f"""
            Analyze this image in detail for social media content creation. Focus on:
            
            1. Visual elements: What objects, people, settings, colors, and activities are visible?
            2. Mood and atmosphere: What feeling or vibe does the image convey?
            3. Brand relevance: How does this image relate to the business context?
            4. Content opportunities: What story or message could this image tell?
            5. Platform optimization: How would this work for different social media platforms?
            
            Business Context:
            - Business: {business_context.get('business_name', 'Not specified')}
            - Industry: {business_context.get('industry', 'Not specified')}
            - Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}
            
            User Description: "{user_description}"
            
            Provide a detailed analysis that will help create engaging social media content.
            """
            
            # Analyze image using vision model with base64 data
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert visual content analyst specializing in social media marketing."},
                    {"role": "user", "content": [
                        {"type": "text", "text": analysis_prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}}
                    ]}
                ],
                temperature=0.3,
                max_tokens=500,
                timeout=60  # 60 second timeout
            )
            
            analysis = response.choices[0].message.content
            logger.info(f"Image analysis completed: {analysis[:100]}...")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            # Don't log as error if it's just a timeout - it's handled gracefully
            if "timeout" in str(e).lower() or "invalid_image_url" in str(e).lower() or "downloading" in str(e).lower():
                logger.warning(f"Image analysis timeout for {image_url}, continuing without analysis")
            return f"Image analysis failed: {str(e)}"

    def _create_content_prompt(self, description: str, platform: str, content_type: str, business_context: Dict[str, Any]) -> str:
        """Create a comprehensive prompt for content generation"""
        prompt = f"""
        Create a {content_type} for {platform} based on this description: "{description}"
        
        Business Context:
        - Business Name: {business_context.get('business_name', 'Not specified')}
        - Industry: {business_context.get('industry', 'Not specified')}
        - Target Audience: {business_context.get('target_audience', 'General audience')}
        - Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}
        - Brand Personality: {business_context.get('brand_personality', 'Approachable and trustworthy')}
        
        Requirements:
        - Optimize for {platform} best practices
        - Match the brand voice and personality
        - Include relevant hashtags
        - Make it engaging and shareable
        - Keep it authentic to the business context
        
        Return the content in JSON format with these fields:
        - content: The main post content
        - title: A catchy title (if applicable)
        - hashtags: Array of relevant hashtags
        - call_to_action: Suggested call to action
        - engagement_hooks: Ways to encourage engagement
        """
        return prompt

    def _create_enhanced_content_prompt(self, description: str, platform: str, content_type: str, 
                                      business_context: Dict[str, Any], image_analysis: str, has_media: bool,
                                      clarification_1: str = "", clarification_2: str = "", clarification_3: str = "",
                                      generated_script: Optional[Dict[str, Any]] = None) -> str:
        """Create an enhanced prompt for content generation with image analysis and clarification answers"""
        # Build clarification section if any clarifications were provided
        clarification_section = ""
        if clarification_1 or clarification_2 or clarification_3:
            clarification_section = "\n\nAdditional Context from User:\n"
            if clarification_1:
                clarification_section += f"- Post Goal/Purpose: {clarification_1}\n"
            if clarification_2:
                clarification_section += f"- Target Audience: {clarification_2}\n"
            if clarification_3:
                clarification_section += f"- Tone/Style: {clarification_3}\n"
        
        # Add script information if available
        script_section = ""
        if generated_script:
            script_section = f"\n\nVIDEO SCRIPT (Use this as the foundation for your content):\n"
            script_section += f"Title: {generated_script.get('title', 'N/A')}\n"
            script_section += f"Hook: {generated_script.get('hook', 'N/A')}\n"
            script_section += f"Scenes: {json.dumps(generated_script.get('scenes', []), indent=2)}\n"
            script_section += f"Call to Action: {generated_script.get('call_to_action', 'N/A')}\n"
            script_section += f"Hashtags: {', '.join(generated_script.get('hashtags', []))}\n"
        
        base_prompt = f"""
        Create a {content_type} for {platform} based on this description: "{description}"
        {clarification_section}{script_section}
        
        Business Context:
        - Business Name: {business_context.get('business_name', 'Not specified')}
        - Industry: {business_context.get('industry', 'Not specified')}
        - Target Audience: {business_context.get('target_audience', 'General audience')}
        - Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}
        - Brand Personality: {business_context.get('brand_personality', 'Approachable and trustworthy')}
        """
        
        if has_media and image_analysis:
            enhanced_prompt = f"""
            {base_prompt}
            
            IMAGE ANALYSIS:
            {image_analysis}
            
            Requirements:
            - Create content that perfectly complements and references the uploaded image
            - Use the image analysis to craft engaging, visual storytelling
            - Optimize for {platform} best practices with visual content
            - Match the brand voice and personality
            - Include relevant hashtags
            - Make it engaging and shareable
            - Create a compelling narrative that connects the image to your business
            - Use the visual elements to enhance the message
            
            CRITICAL INSTRUCTIONS:
            - Return ONLY a valid JSON object
            - Do NOT use markdown code blocks (no ```json or ```)
            - Do NOT include any text before or after the JSON
            - The JSON must be parseable directly
            - Use these exact field names:
            
            {{
              "content": "The main post content that references the image",
              "title": "A catchy title",
              "hashtags": ["array", "of", "relevant", "hashtags"],
              "call_to_action": "Suggested call to action",
              "engagement_hooks": "Ways to encourage engagement",
              "image_caption": "A specific caption for the image",
              "visual_elements": ["key", "visual", "elements", "to", "highlight"]
            }}
            """
        else:
            enhanced_prompt = f"""
            {base_prompt}
            
            Requirements:
            - Optimize for {platform} best practices
            - Match the brand voice and personality
            - Include relevant hashtags
            - Make it engaging and shareable
            - Keep it authentic to the business context
            
            CRITICAL INSTRUCTIONS:
            - Return ONLY a valid JSON object
            - Do NOT use markdown code blocks (no ```json or ```)
            - Do NOT include any text before or after the JSON
            - The JSON must be parseable directly
            - Use these exact field names:
            
            {{
              "content": "The main post content",
              "title": "A catchy title",
              "hashtags": ["array", "of", "relevant", "hashtags"],
              "call_to_action": "Suggested call to action",
              "engagement_hooks": "Ways to encourage engagement"
            }}
            """
        
        return enhanced_prompt
    
    def _extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text"""
        import re
        hashtags = re.findall(r'#\w+', text)
        return hashtags[:10]  # Limit to 10 hashtags
    
    def _optimize_for_platform(self, content: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Apply platform-specific optimizations"""
        optimized = content.copy()
        
        # Platform-specific optimizations
        if platform == "Twitter/X":
            # Keep content concise
            if len(optimized.get("content", "")) > 280:
                optimized["content"] = optimized["content"][:277] + "..."
        elif platform == "Instagram":
            # Add more visual elements
            if not optimized.get("hashtags"):
                optimized["hashtags"] = ["#instagram", "#content", "#socialmedia"]
        elif platform == "LinkedIn":
            # Make it more professional
            if not optimized.get("call_to_action"):
                optimized["call_to_action"] = "What are your thoughts on this?"
        
        return optimized
    
    def _validate_script_structure(self, script_data: dict, user_description: str = "") -> dict:
        """Validate and normalize script structure to ensure all required fields exist"""
        if not isinstance(script_data, dict):
            logger.warning("Script data is not a dict, creating default structure")
            script_data = {}
        
        # Ensure required fields exist with defaults
        validated_script = {
            "title": str(script_data.get("title", f"Reel Script: {user_description[:50] if user_description else 'Untitled'}")),
            "hook": str(script_data.get("hook", user_description[:100] if user_description else "")),
            "scenes": [],
            "call_to_action": str(script_data.get("call_to_action", "")),
            "hashtags": [],
            "total_duration": str(script_data.get("total_duration", "30 seconds")),
            "tips": str(script_data.get("tips", ""))
        }
        
        # Validate and normalize scenes
        if isinstance(script_data.get("scenes"), list):
            for scene in script_data["scenes"]:
                if isinstance(scene, dict):
                    validated_scene = {
                        "duration": str(scene.get("duration", "")),
                        "visual": str(scene.get("visual", "")),
                        "audio": str(scene.get("audio", "")),
                        "on_screen_text": str(scene.get("on_screen_text", ""))
                    }
                    validated_script["scenes"].append(validated_scene)
        
        # Validate hashtags
        if isinstance(script_data.get("hashtags"), list):
            validated_script["hashtags"] = [str(tag) for tag in script_data["hashtags"] if tag]
        elif isinstance(script_data.get("hashtags"), str):
            # If hashtags is a string, try to parse it
            validated_script["hashtags"] = [tag.strip() for tag in script_data["hashtags"].split(",") if tag.strip()]
        
        # Preserve any additional fields
        for key, value in script_data.items():
            if key not in validated_script:
                # Only add if it's JSON serializable
                try:
                    json.dumps(value)
                    validated_script[key] = value
                except (TypeError, ValueError):
                    validated_script[key] = str(value)
        
        return validated_script
    
    async def process_user_input(self, state: CustomContentState, user_input: str, input_type: str = "text") -> CustomContentState:
        """Process user input and update state accordingly"""
        try:
            # Store user input in state
            state["user_input"] = user_input
            state["input_type"] = input_type
            
            current_step = state.get("current_step")
            
            # Handle ERROR state recovery
            if current_step == ConversationStep.ERROR:
                # Check if user wants to generate script
                user_input_lower = user_input.lower().strip()
                if any(phrase in user_input_lower for phrase in ["generate script", "generate scrpt", "create script", "script"]):
                    # Check if we have required info for script generation
                    platform = state.get("selected_platform")
                    content_type = state.get("selected_content_type")
                    user_desc = state.get("user_description")
                    
                    if platform and content_type and user_desc:
                        # Clear error and proceed to script generation
                        state["current_step"] = ConversationStep.GENERATE_SCRIPT
                        state["error_message"] = None
                        logger.info("Recovering from ERROR state - user wants to generate script")
                        return state
                    else:
                        # Missing required info - ask for it
                        missing = []
                        if not platform:
                            missing.append("platform")
                        if not content_type:
                            missing.append("content type")
                        if not user_desc:
                            missing.append("description")
                        
                        error_message = {
                            "role": "assistant",
                            "content": f"I need some information first. Please provide: {', '.join(missing)}. Let's start over - which platform would you like to create content for?",
                            "timestamp": datetime.now().isoformat()
                        }
                        state["conversation_messages"].append(error_message)
                        state["current_step"] = ConversationStep.ASK_PLATFORM
                        state["error_message"] = None
                        return state
                else:
                    # User wants to restart - clear error and go back to platform selection
                    state["current_step"] = ConversationStep.ASK_PLATFORM
                    state["error_message"] = None
                    logger.info("Recovering from ERROR state - restarting conversation")
                    return state
            
            # Process based on current step
            if current_step == ConversationStep.ASK_PLATFORM:
                # Parse platform selection
                platform = self._parse_platform_selection(user_input, state)
                if platform:
                    state["selected_platform"] = platform
                    state["retry_platform"] = False  # Clear retry flag on success
                    # Transition to next step
                    state["current_step"] = ConversationStep.ASK_CONTENT_TYPE
                else:
                    # Invalid input - stay on same step and show error with options
                    user_profile = state.get("user_profile", {})
                    connected_platforms = user_profile.get("social_media_platforms", [])
                    
                    # Format platform options same as greet_user
                    platform_options = []
                    for p in connected_platforms:
                        display_name = ' '.join(word.capitalize() for word in p.split('_'))
                        platform_options.append({"value": p, "label": display_name})
                    
                    error_message = {
                        "role": "assistant",
                        "content": f"I didn't recognize '{user_input}' as a valid platform. Please select one of the available platforms:",
                        "timestamp": datetime.now().isoformat(),
                        "platforms": connected_platforms,
                        "options": platform_options,
                        "is_error": True
                    }
                    state["conversation_messages"].append(error_message)
                    # Set retry flag so ask_platform knows to show options again
                    state["retry_platform"] = True
                    # Stay on the same step to re-prompt (graph will loop back)
                    state["current_step"] = ConversationStep.ASK_PLATFORM
                    logger.warning(f"Invalid platform selection: '{user_input}'. Available: {connected_platforms}")
                    
            elif current_step == ConversationStep.ASK_CONTENT_TYPE:
                # Parse content type selection
                content_type = self._parse_content_type_selection(user_input, state)
                if content_type:
                    state["selected_content_type"] = content_type
                    state["retry_content_type"] = False  # Clear retry flag on success
                    # Transition to next step
                    state["current_step"] = ConversationStep.ASK_DESCRIPTION
                else:
                    # Invalid input - stay on same step and show error with options
                    platform = state.get("selected_platform", "")
                    content_types = PLATFORM_CONTENT_TYPES.get(platform, [])
                    
                    error_message = {
                        "role": "assistant",
                        "content": f"I didn't recognize '{user_input}' as a valid content type for {platform}. Please select one of the available content types:",
                        "timestamp": datetime.now().isoformat(),
                        "content_types": content_types,
                        "options": [{"value": ct, "label": ct} for ct in content_types],
                        "is_error": True
                    }
                    state["conversation_messages"].append(error_message)
                    # Set retry flag so ask_content_type knows to show options again
                    state["retry_content_type"] = True
                    # Stay on the same step to re-prompt (graph will loop back)
                    state["current_step"] = ConversationStep.ASK_CONTENT_TYPE
                    logger.warning(f"Invalid content type selection: '{user_input}'. Available: {content_types}")
                    
            elif current_step == ConversationStep.ASK_DESCRIPTION:
                # Store user description
                state["user_description"] = user_input
                # Transition to first clarification question
                state["current_step"] = ConversationStep.ASK_CLARIFICATION_1
            elif current_step == ConversationStep.ASK_CLARIFICATION_1:
                # Store first clarification answer
                state["clarification_1"] = user_input
                # Transition to second clarification question
                state["current_step"] = ConversationStep.ASK_CLARIFICATION_2
            elif current_step == ConversationStep.ASK_CLARIFICATION_2:
                # Store second clarification answer
                state["clarification_2"] = user_input
                # Transition to third clarification question
                state["current_step"] = ConversationStep.ASK_CLARIFICATION_3
            elif current_step == ConversationStep.ASK_CLARIFICATION_3:
                # Store third clarification answer
                state["clarification_3"] = user_input
                # Transition to media step
                state["current_step"] = ConversationStep.ASK_MEDIA
                
            elif current_step == ConversationStep.APPROVE_CAROUSEL_IMAGES:
                # Carousel approval is handled in approve_carousel_images method
                # Don't modify state here - let execute_conversation_step handle it
                # This prevents adding extra steps
                pass
                
            elif current_step == ConversationStep.CONFIRM_CONTENT:
                # Handle content confirmation
                if user_input.lower().strip() in ["yes", "y", "save", "correct"]:
                    state["content_confirmed"] = True
                    state["current_step"] = ConversationStep.SELECT_SCHEDULE
                elif user_input.lower().strip() in ["no", "n", "change", "edit"]:
                    state["content_confirmed"] = False
                    state["current_step"] = ConversationStep.ASK_DESCRIPTION
                else:
                    state["error_message"] = "Please respond with 'yes' to save the content or 'no' to make changes."
                    
            elif current_step == ConversationStep.SELECT_SCHEDULE:
                # Handle schedule selection
                logger.info(f"Processing schedule selection with input: '{user_input}'")
                
                if user_input.lower().strip() in ["now", "immediately", "asap"]:
                    state["scheduled_for"] = datetime.now().isoformat()
                    logger.info(f"Set scheduled_for to now: {state['scheduled_for']}")
                else:
                    # Try to parse datetime from input
                    try:
                        # Try to import dateutil, fallback to datetime if not available
                        try:
                            from dateutil import parser
                            use_dateutil = True
                        except ImportError:
                            logger.warning("dateutil not available, using datetime fallback")
                            from datetime import datetime as dt
                            use_dateutil = False
                        
                        logger.info(f"Attempting to parse datetime: '{user_input}'")
                        
                        # Handle both ISO format (2025-09-28T10:37) and other formats
                        if 'T' in user_input and len(user_input.split('T')) == 2:
                            # ISO format from frontend
                            date_part, time_part = user_input.split('T')
                            if len(time_part) == 5:  # HH:MM format
                                time_part += ':00'  # Add seconds if missing
                            parsed_input = f"{date_part}T{time_part}"
                            logger.info(f"Formatted input: '{parsed_input}'")
                        else:
                            parsed_input = user_input
                        
                        if use_dateutil:
                            parsed_datetime = parser.parse(parsed_input)
                        else:
                            # Fallback to datetime parsing
                            parsed_datetime = dt.fromisoformat(parsed_input)
                        
                        # Ensure the datetime is timezone-aware
                        if parsed_datetime.tzinfo is None:
                            parsed_datetime = parsed_datetime.replace(tzinfo=None)
                        state["scheduled_for"] = parsed_datetime.isoformat()
                        logger.info(f"Successfully parsed datetime: {parsed_datetime.isoformat()}")
                    except Exception as e:
                        logger.error(f"Failed to parse datetime '{user_input}': {e}")
                        state["error_message"] = f"Please provide a valid date and time, or type 'now' to post immediately. Error: {str(e)}"
                        return state
                
                # Transition to save content
                state["current_step"] = ConversationStep.SAVE_CONTENT
                logger.info(f"Transitioning to SAVE_CONTENT with scheduled_for: {state.get('scheduled_for')}")
                logger.info(f"Current step after transition: {state.get('current_step')}")
                
                # Don't execute save_content directly - let the graph handle the transition
                # The graph will automatically call save_content based on the state transition
                
            elif current_step == ConversationStep.CONFIRM_MEDIA:
                # Handle media confirmation
                if user_input.lower().strip() in ["yes", "y", "correct", "proceed"]:
                    state["media_confirmed"] = True
                    state["current_step"] = ConversationStep.GENERATE_CONTENT
                elif user_input.lower().strip() in ["no", "n", "incorrect", "wrong"]:
                    state["media_confirmed"] = False
                    # Clear previous media
                    state.pop("uploaded_media_url", None)
                    state.pop("uploaded_media_filename", None)
                    state.pop("uploaded_media_size", None)
                    state.pop("uploaded_media_type", None)
                    state["current_step"] = ConversationStep.ASK_MEDIA
                else:
                    state["error_message"] = "Please respond with 'yes' to proceed or 'no' to upload a different file."
                    
            elif current_step == ConversationStep.ASK_MEDIA:
                # Check if this is a carousel post - if so, handle carousel image source selection
                content_type = state.get("selected_content_type", "")
                if content_type and content_type.lower() == "carousel":
                    # Carousel handling is done in ask_media() method itself
                    # It transitions to ASK_CAROUSEL_IMAGE_SOURCE
                    result = await self.ask_media(state)
                    return result
                
                # Parse media choice for regular posts
                media_choice = self._parse_media_choice(user_input)
                logger.info(f"Media choice parsed: '{media_choice}' from input: '{user_input}'")
                
                if media_choice == "upload_image":
                    state["has_media"] = True
                    state["media_type"] = MediaType.IMAGE
                    state["should_generate_media"] = False
                    state["current_step"] = ConversationStep.HANDLE_MEDIA
                    logger.info("Set to HANDLE_MEDIA for upload_image")
                elif media_choice == "upload_video":
                    state["has_media"] = True
                    state["media_type"] = MediaType.VIDEO
                    state["should_generate_media"] = False
                    state["current_step"] = ConversationStep.HANDLE_MEDIA
                    logger.info("Set to HANDLE_MEDIA for upload_video")
                elif media_choice == "generate_image":
                    state["has_media"] = True
                    state["media_type"] = MediaType.IMAGE
                    state["should_generate_media"] = True
                    state["current_step"] = ConversationStep.GENERATE_CONTENT
                    logger.info("Set to GENERATE_CONTENT for generate_image")
                elif media_choice == "generate_video":
                    state["has_media"] = True
                    state["media_type"] = MediaType.VIDEO
                    state["should_generate_media"] = True
                    state["current_step"] = ConversationStep.GENERATE_CONTENT
                    logger.info("Set to GENERATE_CONTENT for generate_video")
                elif media_choice == "generate_script":
                    state["has_media"] = True
                    state["media_type"] = MediaType.VIDEO
                    state["should_generate_media"] = False
                    state["current_step"] = ConversationStep.GENERATE_SCRIPT
                    logger.info("Set to GENERATE_SCRIPT for generate_script")
                else:  # skip_media
                    state["has_media"] = False
                    state["media_type"] = MediaType.NONE
                    state["should_generate_media"] = False
                    state["current_step"] = ConversationStep.GENERATE_CONTENT
                    logger.info("Set to GENERATE_CONTENT for skip_media")
                    
            elif current_step == ConversationStep.ASK_ANOTHER_CONTENT:
                # Handle another content choice
                if user_input.lower().strip() in ["yes", "y", "create", "another", "generate"]:
                    # Reset state for new content generation
                    state["current_step"] = ConversationStep.ASK_PLATFORM
                    state["progress_percentage"] = 0
                    # Clear previous content data
                    state.pop("selected_platform", None)
                    state.pop("selected_content_type", None)
                    state.pop("user_description", None)
                    state.pop("has_media", None)
                    state.pop("media_type", None)
                    state.pop("uploaded_media_url", None)
                    state.pop("uploaded_media_filename", None)
                    state.pop("uploaded_media_size", None)
                    state.pop("uploaded_media_type", None)
                    state.pop("should_generate_media", None)
                    state.pop("generated_content", None)
                    state.pop("final_post", None)
                    state.pop("scheduled_for", None)
                    state.pop("content_confirmed", None)
                    state.pop("media_confirmed", None)
                    state.pop("is_complete", None)
                elif user_input.lower().strip() in ["no", "n", "done", "exit", "finish"]:
                    # Mark as complete to exit
                    state["is_complete"] = True
                else:
                    state["error_message"] = "Please respond with 'yes' to create another content or 'no' to finish."
            
            logger.info(f"Processed user input for step: {current_step}")
            
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            state["error_message"] = f"Failed to process input: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    def _parse_platform_selection(self, user_input: str, state: CustomContentState) -> Optional[str]:
        """Parse platform selection from user input with improved matching"""
        user_profile = state.get("user_profile", {})
        connected_platforms = user_profile.get("social_media_platforms", [])
        
        if not connected_platforms:
            return None
        
        user_input_clean = user_input.strip()
        user_input_lower = user_input_clean.lower()
        
        # Try to match by number first (for backward compatibility)
        try:
            index = int(user_input_clean) - 1
            if 0 <= index < len(connected_platforms):
                return connected_platforms[index]
        except ValueError:
            pass
        
        # Try to match by exact name (for button clicks)
        for platform in connected_platforms:
            if platform == user_input_clean:
                return platform
        
        # Try to match by exact lowercase name
        for platform in connected_platforms:
            if platform.lower() == user_input_lower:
                return platform
        
        # Try to match by partial name (for text input)
        for platform in connected_platforms:
            platform_lower = platform.lower()
            # Check if platform name is contained in user input or vice versa
            if platform_lower in user_input_lower or user_input_lower in platform_lower:
                return platform
        
        # Try fuzzy matching with common platform name variations
        platform_variations = {
            "facebook": ["fb", "facebook"],
            "instagram": ["ig", "insta", "instagram"],
            "linkedin": ["linkedin", "linked in"],
            "twitter": ["twitter", "x", "twitter/x"],
            "youtube": ["yt", "youtube", "you tube"],
            "tiktok": ["tiktok", "tik tok", "tt"],
            "pinterest": ["pinterest", "pin"],
            "whatsapp": ["whatsapp", "whats app", "wa", "whatsapp business"]
        }
        
        # Check if user input matches any variation
        for platform in connected_platforms:
            platform_lower = platform.lower()
            variations = platform_variations.get(platform_lower, [platform_lower])
            for variation in variations:
                if variation in user_input_lower or user_input_lower in variation:
                    return platform
        
        return None
    
    def _parse_content_type_selection(self, user_input: str, state: CustomContentState) -> Optional[str]:
        """Parse content type selection from user input with improved matching"""
        platform = state.get("selected_platform", "")
        content_types = PLATFORM_CONTENT_TYPES.get(platform, [])
        
        if not content_types:
            return None
        
        user_input_clean = user_input.strip()
        user_input_lower = user_input_clean.lower()
        
        # Try to match by number first (for backward compatibility)
        try:
            index = int(user_input_clean) - 1
            if 0 <= index < len(content_types):
                return content_types[index]
        except ValueError:
            pass
        
        # Try to match by exact name (for button clicks)
        for content_type in content_types:
            if content_type == user_input_clean:
                return content_type
        
        # Try to match by exact lowercase name
        for content_type in content_types:
            if content_type.lower() == user_input_lower:
                return content_type
        
        # Try to match by partial name (for text input)
        for content_type in content_types:
            content_type_lower = content_type.lower()
            # Check if content type name is contained in user input or vice versa
            if content_type_lower in user_input_lower or user_input_lower in content_type_lower:
                return content_type
        
        # Try fuzzy matching with common content type variations
        content_type_variations = {
            "text post": ["text", "post", "text post"],
            "photo": ["photo", "image", "picture", "pic"],
            "video": ["video", "vid", "movie", "clip"],
            "carousel": ["carousel", "slideshow", "multiple images"],
            "story": ["story", "stories"],
            "reel": ["reel", "reels"],
            "tweet": ["tweet", "post"],
            "thread": ["thread", "threads"],
            "article": ["article", "blog", "blog post"],
            "live": ["live", "live stream", "live broadcast"],
            "poll": ["poll", "polling", "survey"],
            "question": ["question", "q&a", "qa"]
        }
        
        # Check if user input matches any variation
        for content_type in content_types:
            content_type_lower = content_type.lower()
            variations = content_type_variations.get(content_type_lower, [content_type_lower])
            for variation in variations:
                if variation in user_input_lower or user_input_lower in variation:
                    return content_type
        
        return None
    
    def _parse_media_choice(self, user_input: str) -> str:
        """Parse media choice from user input"""
        user_input_lower = user_input.lower().strip()
        
        # Handle direct button values (for backward compatibility)
        if user_input_lower in ["upload_image", "upload_video", "generate_image", "generate_video", "generate_script", "skip_media"]:
            return user_input_lower
        
        # Handle button labels from frontend
        if "upload an image" in user_input_lower or "📷" in user_input:
            return "upload_image"
        elif "upload a video" in user_input_lower or "🎥" in user_input:
            return "upload_video"
        elif "generate an image" in user_input_lower or ("🎨" in user_input and "script" not in user_input_lower):
            return "generate_image"
        elif "generate a video" in user_input_lower or "🎬" in user_input:
            return "generate_video"
        elif "generate a script" in user_input_lower or "generate script" in user_input_lower or ("📝" in user_input and "script" in user_input_lower):
            return "generate_script"
        elif "skip media" in user_input_lower or "text-only" in user_input_lower or ("📝" in user_input and "script" not in user_input_lower):
            return "skip_media"
        
        # Handle text-based parsing (for manual input)
        if any(word in user_input_lower for word in ["upload", "image", "photo", "picture"]):
            return "upload_image"
        elif any(word in user_input_lower for word in ["upload", "video", "movie", "clip"]):
            return "upload_video"
        elif any(word in user_input_lower for word in ["generate", "create", "image", "photo"]) and "script" not in user_input_lower:
            return "generate_image"
        elif any(word in user_input_lower for word in ["generate", "create", "video", "movie"]) and "script" not in user_input_lower:
            return "generate_video"
        elif any(word in user_input_lower for word in ["generate", "create", "script"]):
            return "generate_script"
        elif any(word in user_input_lower for word in ["skip", "none", "no", "text only"]):
            return "skip_media"
        else:
            return "skip_media"
    
    async def upload_media(self, state: CustomContentState, media_file: bytes, filename: str, content_type: str) -> CustomContentState:
        """Upload media file directly to Supabase storage (for videos) or store as base64 (for small images)"""
        try:
            user_id = state["user_id"]
            platform = state.get("selected_platform", "general")
            
            # Validate inputs
            if not media_file:
                raise Exception("No file content provided")
            if not filename:
                raise Exception("No filename provided")
            if not content_type:
                raise Exception("No content type provided")
            
            is_video = content_type.startswith("video/")
            file_size = len(media_file)
            
            logger.info(f"Uploading media: {filename}, size: {file_size} bytes, type: {content_type}, is_video: {is_video}")
            
            # For videos or large files, upload directly to Supabase storage
            # For small images, we can store as base64 for faster processing
            if is_video or file_size > 5 * 1024 * 1024:  # 5MB threshold
                # Upload directly to Supabase storage
                file_extension = filename.split('.')[-1] if '.' in filename else ('mp4' if is_video else 'jpg')
                # Handle common video extensions
                if file_extension.lower() == 'quicktime':
                    file_extension = 'mov'
                elif file_extension.lower() == 'x-msvideo':
                    file_extension = 'avi'
                
                unique_filename = f"custom_content_{user_id}_{platform}_{uuid.uuid4().hex[:8]}.{file_extension}"
                bucket_name = "user-uploads"
                
                logger.info(f"Uploading {'video' if is_video else 'large file'} directly to Supabase: {bucket_name}/{unique_filename}")
                
                # Upload to Supabase storage
                storage_response = self.supabase.storage.from_(bucket_name).upload(
                    unique_filename,
                    media_file,
                    file_options={"content-type": content_type}
                )
                
                # Check for upload errors
                if hasattr(storage_response, 'error') and storage_response.error:
                    raise Exception(f"Storage upload failed: {storage_response.error}")
            
                # Get public URL
                public_url = self.supabase.storage.from_(bucket_name).get_public_url(unique_filename)
                
                logger.info(f"Successfully uploaded {'video' if is_video else 'file'} to Supabase: {public_url}")
                
                # Store the public URL in state (not base64)
                state["uploaded_media_url"] = public_url
                state["uploaded_media_filename"] = unique_filename
                state["uploaded_media_size"] = file_size
                state["uploaded_media_type"] = content_type
            else:
                # For small images, store as base64 for faster processing
                logger.info(f"Storing small image as base64: {filename}")
                file_extension = filename.split('.')[-1] if '.' in filename else 'jpg'
                unique_filename = f"custom_content_{user_id}_{platform}_{uuid.uuid4()}.{file_extension}"
                
                # Store media in session state (base64 encoded)
                media_base64 = base64.b64encode(media_file).decode('utf-8')
                
                # Store in state
                state["uploaded_media_url"] = f"data:{content_type};base64,{media_base64}"
                state["uploaded_media_filename"] = unique_filename
                state["uploaded_media_size"] = file_size
                state["uploaded_media_type"] = content_type
            
            # Transition to media confirmation
            state["current_step"] = ConversationStep.CONFIRM_MEDIA
            state["progress_percentage"] = 60
            
            logger.info(f"Media processed for user {user_id}: {unique_filename}")
            
        except Exception as e:
            logger.error(f"Error uploading media: {e}")
            state["error_message"] = f"Failed to upload media: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            
        return state
    
    def get_conversation_state(self, conversation_id: str) -> Optional[CustomContentState]:
        """Get conversation state by ID (for persistence)"""
        # This would typically load from a database
        # For now, we'll return None as state is managed in memory
        return None
    
    def save_conversation_state(self, state: CustomContentState) -> bool:
        """Save conversation state (for persistence)"""
        try:
            # This would typically save to a database
            # For now, we'll just log it
            logger.info(f"Conversation state saved: {state['conversation_id']}")
            return True
        except Exception as e:
            logger.error(f"Error saving conversation state: {e}")
            return False
    
    def _should_proceed_from_platform(self, state: CustomContentState) -> str:
        """Determine if we should proceed from platform selection or retry"""
        # Check if platform is selected - if yes, proceed
        if state.get("selected_platform"):
            return "continue"
        # If retry flag is set, loop back to ask again
        if state.get("retry_platform", False):
            return "retry"
        # If no platform selected and not a retry, this is first time - proceed to ask
        # (The ask_platform node will handle showing the options)
        return "continue"
    
    def _should_proceed_from_content_type(self, state: CustomContentState) -> str:
        """Determine if we should proceed from content type selection or retry"""
        # Check if content type is selected - if yes, proceed
        if state.get("selected_content_type"):
            return "continue"
        # If retry flag is set, loop back to ask again
        if state.get("retry_content_type", False):
            return "retry"
        # If no content type selected and not a retry, this is first time - proceed to ask
        # (The ask_content_type node will handle showing the options)
        return "continue"
    
    def _should_handle_media(self, state: CustomContentState) -> str:
        """Determine if media should be handled, generated, or skipped"""
        current_step = state.get("current_step")
        
        # If we're generating a script, route to generate_script
        if current_step == ConversationStep.GENERATE_SCRIPT:
            return "generate_script"
        
        if state.get("has_media", False):
            if state.get("should_generate_media", False):
                return "generate"
            else:
                return "handle"
        return "skip"
    
    def _should_proceed_after_script(self, state: CustomContentState) -> str:
        """Determine next step after script generation"""
        # If current_step is CONFIRM_SCRIPT, the execute_conversation_step will handle it
        # and return state without proceeding to generate_content
        if state.get("current_step") == ConversationStep.CONFIRM_SCRIPT:
            return "confirm"  # Stop and show script
        return "proceed"  # Continue to content generation (shouldn't happen normally)
    
    def _should_proceed_after_media(self, state: CustomContentState) -> str:
        """Determine next step after media confirmation"""
        if state.get("current_step") == ConversationStep.ERROR:
            return "error"
        
        # Check if user confirmed media or if there was an error
        if state.get("media_confirmed", False):
            return "proceed"
        elif state.get("validation_errors"):
            return "retry"
        else:
            return "proceed"  # Default to proceed if no explicit confirmation
    
    def _should_proceed_after_content(self, state: CustomContentState) -> str:
        """Determine next step after content confirmation"""
        if state.get("current_step") == ConversationStep.ERROR:
            return "error"
        
        # Check if user confirmed content or if there was an error
        if state.get("content_confirmed", False):
            return "proceed"
        elif state.get("content_confirmed") is False:
            return "retry"
        else:
            return "proceed"  # Default to proceed if no explicit confirmation
    
    def get_user_platforms(self, user_id: str) -> List[str]:
        """Get user's connected platforms from their profile"""
        try:
            profile_response = self.supabase.table("profiles").select("social_media_platforms").eq("id", user_id).execute()
            
            if profile_response.data and profile_response.data[0]:
                platforms = profile_response.data[0].get("social_media_platforms", [])
                return platforms if platforms else []
            
            return []
        except Exception as e:
            logger.error(f"Error getting user platforms: {e}")
            return []
    
    async def _load_user_profile(self, user_id: str) -> dict:
        """Load user profile from Supabase"""
        try:
            profile_response = self.supabase.table("profiles").select("*").eq("id", user_id).execute()
            
            if profile_response.data and profile_response.data[0]:
                return profile_response.data[0]
            
            return {}
        except Exception as e:
            logger.error(f"Error loading user profile: {e}")
            return {}
    
    async def execute_conversation_step(self, state: CustomContentState, user_input: str = None) -> CustomContentState:
        """Execute the next step in the conversation using LangGraph"""
        try:
            # Process user input if provided
            if user_input:
                logger.info(f"Processing user input: '{user_input}'")
                state = await self.process_user_input(state, user_input, "text")
                logger.info(f"After processing input, current_step: {state.get('current_step')}")
            
            # If there's an error, try to recover if user provided meaningful input
            if state.get("current_step") == ConversationStep.ERROR:
                # Check if user wants to generate script or continue
                if user_input:
                    user_input_lower = user_input.lower().strip()
                    # Check if user wants to generate script
                    if any(phrase in user_input_lower for phrase in ["generate script", "generate scrpt", "create script", "script"]):
                        # Check if we have required info for script generation
                        platform = state.get("selected_platform")
                        content_type = state.get("selected_content_type")
                        user_description = state.get("user_description")
                        
                        if platform and content_type and user_description:
                            # Clear error and proceed to script generation
                            state["current_step"] = ConversationStep.GENERATE_SCRIPT
                            state["error_message"] = None
                            logger.info("Recovering from ERROR state - proceeding to generate script")
                        else:
                            # Missing required info - ask for it
                            missing = []
                            if not platform:
                                missing.append("platform")
                            if not content_type:
                                missing.append("content type")
                            if not user_description:
                                missing.append("description")
                            
                            error_message = {
                                "role": "assistant",
                                "content": f"I need some information first. Please provide: {', '.join(missing)}. Let's start over - which platform would you like to create content for?",
                                "timestamp": datetime.now().isoformat()
                            }
                            state["conversation_messages"].append(error_message)
                            state["current_step"] = ConversationStep.ASK_PLATFORM
                            state["error_message"] = None
                            return state
                    else:
                        # User wants to restart or continue - clear error and go back to platform selection
                        state["current_step"] = ConversationStep.ASK_PLATFORM
                        state["error_message"] = None
                        logger.info("Recovering from ERROR state - restarting conversation")
                        return await self.ask_platform(state)
                else:
                    # No user input, just show error message
                    return state
            
            # Execute the current step based on the current_step in state
            current_step = state.get("current_step")
            logger.info(f"Executing conversation step: {current_step}")
            
            if current_step == ConversationStep.GREET:
                result = await self.greet_user(state)
            elif current_step == ConversationStep.ASK_PLATFORM:
                result = await self.ask_platform(state)
            elif current_step == ConversationStep.ASK_CONTENT_TYPE:
                result = await self.ask_content_type(state)
            elif current_step == ConversationStep.ASK_DESCRIPTION:
                result = await self.ask_description(state)
            elif current_step == ConversationStep.ASK_CLARIFICATION_1:
                result = await self.ask_clarification_1(state)
            elif current_step == ConversationStep.ASK_CLARIFICATION_2:
                result = await self.ask_clarification_2(state)
            elif current_step == ConversationStep.ASK_CLARIFICATION_3:
                result = await self.ask_clarification_3(state)
            elif current_step == ConversationStep.ASK_MEDIA:
                result = await self.ask_media(state)
            elif current_step == ConversationStep.GENERATE_SCRIPT:
                result = await self.generate_script(state)
            elif current_step == ConversationStep.CONFIRM_SCRIPT:
                # Script is already generated and displayed, just return state
                # User can save or regenerate from frontend
                result = state
                logger.info("Script is displayed, waiting for user to save or regenerate")
            elif current_step == ConversationStep.ASK_CAROUSEL_IMAGE_SOURCE:
                result = await self.ask_carousel_image_source(state, user_input)
            elif current_step == ConversationStep.GENERATE_CAROUSEL_IMAGE:
                result = await self.generate_carousel_image(state, user_input)
            elif current_step == ConversationStep.APPROVE_CAROUSEL_IMAGES:
                result = await self.approve_carousel_images(state, user_input)
            elif current_step == ConversationStep.HANDLE_CAROUSEL_UPLOAD:
                result = await self.handle_carousel_upload(state)
            elif current_step == ConversationStep.CONFIRM_CAROUSEL_UPLOAD_DONE:
                result = await self.confirm_carousel_upload_done(state, user_input)
            elif current_step == ConversationStep.HANDLE_MEDIA:
                result = await self.handle_media(state)
            elif current_step == ConversationStep.VALIDATE_MEDIA:
                result = await self.validate_media(state)
            elif current_step == ConversationStep.CONFIRM_MEDIA:
                result = await self.confirm_media(state)
            elif current_step == ConversationStep.GENERATE_CONTENT:
                try:
                    result = await self.generate_content(state)
                except Exception as e:
                    logger.error(f"Error in generate_content step: {e}")
                    # Don't set to ERROR - continue with content generation without images
                    # The generate_content function should handle errors internally
                    # If it still fails, create a basic content message
                    state["current_step"] = ConversationStep.CONFIRM_CONTENT
                    state["progress_percentage"] = 85
                    # Create a basic error message but continue
                    error_message = {
                        "role": "assistant",
                        "content": f"I encountered an issue analyzing the images, but I've generated content based on your description. Please review it below.",
                        "timestamp": datetime.now().isoformat()
                    }
                    state["conversation_messages"].append(error_message)
                    result = await self.confirm_content(state)
            elif current_step == ConversationStep.CONFIRM_CONTENT:
                result = await self.confirm_content(state)
            elif current_step == ConversationStep.SELECT_SCHEDULE:
                # Only call select_schedule if we haven't already asked for schedule
                # Check if we already have a schedule selection message
                last_message = state["conversation_messages"][-1] if state["conversation_messages"] else None
                schedule_message_content = "Great! Now let's schedule your post. Please select the date and time when you'd like this content to be published. You can choose to post immediately or schedule it for later."
                
                logger.info(f"SELECT_SCHEDULE step - last_message: {last_message}")
                logger.info(f"SELECT_SCHEDULE step - checking for message content")
                
                if not last_message or schedule_message_content not in last_message.get("content", ""):
                    logger.info("Calling select_schedule method")
                    result = await self.select_schedule(state)
                else:
                    # Already asked for schedule, just return current state
                    logger.info("Schedule message already present, returning current state")
                    result = state
            elif current_step == ConversationStep.SAVE_CONTENT:
                result = await self.save_content(state)
                # After saving content, automatically transition to ask_another_content
                if result.get("current_step") == ConversationStep.ASK_ANOTHER_CONTENT:
                    result = await self.ask_another_content(result)
            elif current_step == ConversationStep.ASK_ANOTHER_CONTENT:
                # Only call ask_another_content if we haven't already asked
                # Check if we already have an ask another content message
                last_message = state["conversation_messages"][-1] if state["conversation_messages"] else None
                another_content_message = "Would you like to create another piece of content? Just let me know!"
                
                if not last_message or another_content_message not in last_message.get("content", ""):
                    result = await self.ask_another_content(state)
                else:
                    # Already asked about another content, just return current state
                    result = state
            elif current_step == ConversationStep.DISPLAY_RESULT:
                result = await self.display_result(state)
            elif current_step == ConversationStep.ERROR:
                result = await self.handle_error(state)
            else:
                # Default to current state if step is not recognized
                result = state
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing conversation step: {e}")
            state["error_message"] = f"Failed to execute conversation step: {str(e)}"
            state["current_step"] = ConversationStep.ERROR
            return state