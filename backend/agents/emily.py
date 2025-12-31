"""
Intent-Based Chatbot Agent using LangGraph and Pydantic
Handles user queries by classifying intent and routing to appropriate tools
"""

import os
import json
import logging
import numpy as np
import re
from typing import Dict, List, Any, Optional, Literal, TypedDict, Tuple
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from supabase import create_client, Client
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
from services.token_usage_service import TokenUsageService
from utils.profile_embedding_helper import get_embedding_service
from utils.embedding_context import get_profile_context_with_embedding
from schemas.analytics import AnalyticsState

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Initialize OpenAI
openai_api_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
    openai_api_key=openai_api_key
)

# Embedding service will be loaded via get_embedding_service() when needed
# This matches the pattern used in profile_embedding_helper.py

logger = logging.getLogger(__name__)

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

# -----------------------------------------------------------------------------
# SOCIAL MEDIA
# -----------------------------------------------------------------------------

class SocialMediaPayload(BaseModel):
    platform: Optional[List[Literal[
        "facebook",
        "instagram",
        "youtube",
        "linkedin",
        "twitter",
        "pinterest"
    ]]] = None

    content_type: Optional[Literal["post", "reel", "video", "story", "carousel"]] = None
    idea: Optional[str] = None

    media: Optional[Literal["upload", "generate"]] = None
    media_file: Optional[str] = None

    date: Optional[datetime] = None
    task: Optional[Literal["draft", "schedule", "edit", "delete"]] = None
    content: Optional[str] = None  # Content ID from created_content table after generation

# -----------------------------------------------------------------------------
# BLOG
# -----------------------------------------------------------------------------

class BlogPayload(BaseModel):
    platform: Optional[Literal["wordpress", "shopify", "wix", "html"]] = None
    topic: Optional[str] = None
    length: Optional[Literal["short", "medium", "long"]] = None

    media: Optional[Literal["generate", "upload"]] = None
    media_file: Optional[str] = None

    date: Optional[datetime] = None
    task: Optional[Literal["draft", "schedule", "save"]] = None

# -----------------------------------------------------------------------------
# EMAIL
# -----------------------------------------------------------------------------

class EmailPayload(BaseModel):
    email_address: Optional[EmailStr] = None
    content: Optional[str] = None

    attachments: Optional[List[str]] = None

    task: Optional[Literal["send", "save", "schedule"]] = None
    date: Optional[datetime] = None

# -----------------------------------------------------------------------------
# WHATSAPP MESSAGE
# -----------------------------------------------------------------------------

class WhatsAppPayload(BaseModel):
    phone_number: Optional[str] = Field(
        default=None,
        description="Phone number with country code, e.g. +919876543210"
    )

    text: Optional[str] = None
    attachment: Optional[str] = None

    task: Optional[Literal["send", "schedule", "save"]] = None
    date: Optional[datetime] = None

# -----------------------------------------------------------------------------
# ADS
# -----------------------------------------------------------------------------

class AdsPayload(BaseModel):
    platform: Optional[Literal["meta", "google", "linkedin", "youtube"]] = None
    objective: Optional[str] = None
    audience: Optional[str] = None
    budget: Optional[str] = None
    creative: Optional[str] = None

    date: Optional[datetime] = None
    task: Optional[Literal["draft", "schedule", "launch"]] = None

# -----------------------------------------------------------------------------
# CONTENT GENERATION
# -----------------------------------------------------------------------------

class ContentGenerationPayload(BaseModel):
    type: Literal["social_media", "blog", "email", "whatsapp", "ads"]

    social_media: Optional[SocialMediaPayload] = None
    blog: Optional[BlogPayload] = None
    email: Optional[EmailPayload] = None
    whatsapp: Optional[WhatsAppPayload] = None
    ads: Optional[AdsPayload] = None

# =============================================================================
# ANALYTICS
# =============================================================================

class AnalyticsPayload(BaseModel):
    # User wants ANALYTICS or INSIGHT?
    # - analytics: Historical data from Supabase cache with comparative analysis
    # - insight: Live/latest data fetched directly from platform API (real-time)
    insight_type: Literal["analytics", "insight"]

    # Source of analytics
    source: Literal["social_media", "blog"]
    
    # CRITICAL: Analytics Level (account-level vs post-level)
    # - account: Overall performance, aggregated metrics (reach, impressions, growth)
    # - post: Individual post data, ranking, top/bottom posts (likes, comments per post)
    analytics_level: Optional[Literal["account", "post"]] = "post"

    # SOCIAL MEDIA FIELDS
    platform: Optional[List[Literal[
        "instagram",
        "facebook",
        "youtube",
        "linkedin",
        "twitter",
        "pinterest"
    ]]] = None

    metrics: Optional[List[Literal[
        # Social media metrics
        "reach",
        "impressions",
        "engagement",
        "likes",
        "comments",
        "shares",
        "saves",
        "views",
        "profile_visits",
        "followers",
        "avg_view_time",
        "average_watch_time",
        "watch_time",
        "growth",
        "top_posts",
        "all_posts"   # for "saare posts"
    ]]] = None

    # BLOG METRICS (Live PSI Only)
    blog_metrics: Optional[List[Literal[
        "performance_score",
        "lcp",
        "cls",
        "inp",
        "seo_score",
        "accessibility_score",
        "best_practices_score",
        "opportunities"
    ]]] = None

    # Applied to BOTH social + blog
    date_range: Optional[str] = None
    
    # POST-LEVEL SPECIFIC: Number of posts to return (default: 1 for "top post")
    top_n: Optional[int] = 1
    
    # POST-LEVEL SPECIFIC: Sort order ("desc" for top, "asc" for worst)
    sort_order: Optional[Literal["desc", "asc"]] = "desc"

# =============================================================================
# LEADS MANAGEMENT
# =============================================================================

class LeadsManagementPayload(BaseModel):
    action: Optional[
        Literal[
            "add_lead",
            "update_lead",
            "search_lead",
            "export_leads",
            "inquire_status",
            "inquire_status_summary"
        ]
    ] = None

    # For individual lead operations
    lead_name: Optional[str] = None
    lead_email: Optional[EmailStr] = None
    lead_phone: Optional[str] = None
    notes: Optional[str] = None
    lead_id: Optional[str] = None

    # For individual lead status questions
    status_query: Optional[str] = Field(
        default=None,
        description="User asking about a specific lead's status"
    )

    # For summary inquiries
    status_type: Optional[
        Literal[
            "new",
            "contacted",
            "responded",
            "qualified",
            "invalid",
            "lost",
            "converted",
            "followup"
        ]
    ] = Field(
        default=None,
        description="Lead pipeline stage for summary inquiry"
    )

    # Optional time filter
    date_range: Optional[str] = Field(
        default=None,
        description="Example: today, yesterday, last 7 days, this week, last month"
    )

# =============================================================================
# POSTING MANAGER
# =============================================================================

class PostingManagerPayload(BaseModel):
    platform: Optional[str] = None
    action: Optional[Literal["view_queue", "update_post", "delete_post"]] = None
    post_id: Optional[str] = None

# =============================================================================
# GENERAL TALK
# =============================================================================

class GeneralTalkPayload(BaseModel):
    message: Optional[str] = None

# =============================================================================
# FAQ
# =============================================================================

class FAQPayload(BaseModel):
    query: Optional[str] = None

# =============================================================================
# TOP-LEVEL INTENT PAYLOAD
# =============================================================================

class IntentPayload(BaseModel):
    intent: Literal[
        "content_generation",
        "analytics",
        "leads_management",
        "posting_manager",
        "general_talks",
        "faq"
    ]

    content: Optional[ContentGenerationPayload] = None
    analytics: Optional[AnalyticsPayload] = None
    leads: Optional[LeadsManagementPayload] = None
    posting: Optional[PostingManagerPayload] = None
    general: Optional[GeneralTalkPayload] = None
    faq: Optional[FAQPayload] = None

# Rebuild forward references
IntentPayload.model_rebuild()
ContentGenerationPayload.model_rebuild()
FAQPayload.model_rebuild()

# =============================================================================
# LANGGRAPH STATE
# =============================================================================

class IntentBasedChatbotState(TypedDict):
    """State for the intent-based chatbot conversation"""
    user_id: str
    current_query: str
    conversation_history: Optional[List[Dict[str, str]]]
    intent_payload: Optional[IntentPayload]  # The classified payload
    partial_payload: Optional[Dict[str, Any]]  # Accumulated partial payload data
    response: Optional[str]
    context: Dict[str, Any]
    needs_clarification: Optional[bool]  # Whether we're waiting for user input
    options: Optional[List[str]]  # Clickable options for user selection
    content_data: Optional[Dict[str, Any]]  # Structured content data (title, content, hashtags, images)

# =============================================================================
# INTENT-BASED CHATBOT CLASS
# =============================================================================

class IntentBasedChatbot:
    # Platform aliases mapping
    PLATFORM_ALIASES = {
        "insta": "instagram",
        "ig": "instagram",
        "fb": "facebook",
        "yt": "youtube",
        "ytube": "youtube",
        "x": "twitter",
        "linkedin": "linkedin",
        "pinterest": "pinterest",
        "pin": "pinterest"
    }
    
    # Valid platform names
    VALID_PLATFORMS = ["instagram", "facebook", "youtube", "linkedin", "twitter", "pinterest"]
    
    # Platform-specific post-level metrics (SOURCE OF TRUTH)
    # Only includes metrics that are actually fetchable from each platform's API
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
    
    # Valid social media metrics
    VALID_SOCIAL_METRICS = [
        "reach", "impressions", "engagement", "likes", "comments", "shares",
        "saves", "views", "profile_visits", "followers", "avg_view_time",
        "average_watch_time", "watch_time", "growth", "top_posts", "all_posts"
    ]
    
    # Metric synonyms mapping
    METRIC_SYNONYMS = {
        "profile visit": "profile_visits",
        "profile visits": "profile_visits",
        "avg view time": "avg_view_time",
        "average view time": "avg_view_time",
        "watch time": "watch_time",
        "average watch time": "average_watch_time",
        "top post": "top_posts",
        "top posts": "top_posts",
        "all post": "all_posts",
        "all posts": "all_posts",
        "saare posts": "all_posts"
    }
    
    # Valid blog metrics
    VALID_BLOG_METRICS = [
        "views", "read_time", "bounce_rate", "engagement",
        "traffic_sources", "top_articles", "all_articles"
    ]
    
    def __init__(self):
        self.llm = llm
        # Initialize token tracker for usage tracking
        supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if supabase_url and supabase_service_key:
            self.token_tracker = TokenUsageService(supabase_url, supabase_service_key)
        else:
            self.token_tracker = None
        self.setup_graph()
    
    def setup_graph(self):
        """Setup the LangGraph workflow"""
        workflow = StateGraph(IntentBasedChatbotState)
        
        # Add nodes
        workflow.add_node("classify_intent", self.classify_intent)
        workflow.add_node("handle_content_generation", self.handle_content_generation)
        workflow.add_node("handle_analytics", self.handle_analytics)
        workflow.add_node("handle_leads_management", self.handle_leads_management)
        workflow.add_node("handle_posting_manager", self.handle_posting_manager)
        workflow.add_node("handle_general_talks", self.handle_general_talks)
        workflow.add_node("handle_faq", self.handle_faq)
        workflow.add_node("generate_final_response", self.generate_final_response)
        
        # Set entry point
        workflow.set_entry_point("classify_intent")
        
        # Conditional routing based on intent
        workflow.add_conditional_edges(
            "classify_intent",
            self.route_by_intent,
            {
                "content_generation": "handle_content_generation",
                "analytics": "handle_analytics",
                "leads_management": "handle_leads_management",
                "posting_manager": "handle_posting_manager",
                "general_talks": "handle_general_talks",
                "faq": "handle_faq"
            }
        )
        
        # All handlers go to generate_final_response
        workflow.add_edge("handle_content_generation", "generate_final_response")
        workflow.add_edge("handle_analytics", "generate_final_response")
        workflow.add_edge("handle_leads_management", "generate_final_response")
        workflow.add_edge("handle_posting_manager", "generate_final_response")
        workflow.add_edge("handle_general_talks", "generate_final_response")
        workflow.add_edge("handle_faq", "generate_final_response")
        workflow.add_edge("generate_final_response", END)
        
        # Compile the graph
        self.graph = workflow.compile()
    
    def route_by_intent(self, state: IntentBasedChatbotState) -> str:
        """Route to appropriate handler based on intent"""
        if not state.get("intent_payload"):
            return "general_talks"
        
        # CRITICAL FIX: If we have partial_payload with analytics data, always route to analytics
        # This prevents losing context during multi-turn clarification conversations
        partial_payload = state.get("partial_payload")
        if partial_payload and "analytics" in partial_payload and partial_payload["analytics"]:
            # We have analytics data in progress - route to analytics handler
            analytics_dict = partial_payload["analytics"]
            if analytics_dict and isinstance(analytics_dict, dict) and len(analytics_dict) > 0:
                logger.info(f"🔒 Routing to analytics due to partial_payload with analytics data: {list(analytics_dict.keys())}")
                return "analytics"
        
        return state["intent_payload"].intent
    
    def _normalize_payload(self, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and fix payload structure before validation.
        
        FIX 6: Never overwrite existing valid fields.
        """
        # Fix analytics payload field mappings using comprehensive normalization
        if payload_dict.get("intent") == "analytics" and payload_dict.get("analytics"):
            analytics = payload_dict["analytics"]
            if isinstance(analytics, dict):
                # Use comprehensive normalization utility (user_query not available here, but that's OK)
                normalized_analytics = self._normalize_analytics_payload(analytics, user_query=None)
                # FIX 6: Merge normalized fields but preserve existing valid fields
                for key, value in normalized_analytics.items():
                    if value is not None:
                        existing_value = analytics.get(key)
                        # Preserve existing valid values
                        if key == "insight_type" and existing_value in ["analytics", "insight"]:
                            continue
                        elif key == "source" and existing_value in ["social_media", "blog"]:
                            continue
                        elif key in ["platform", "metrics", "blog_metrics"] and existing_value and isinstance(existing_value, list) and len(existing_value) > 0:
                            continue  # Preserve existing valid lists
                        else:
                            analytics[key] = value
                
                # Remove old fields that were normalized (only if they're not the canonical field)
                analytics.pop("type", None)
                analytics.pop("analysis_type", None)
                analytics.pop("mode", None)
                analytics.pop("analytics_type", None)
                analytics.pop("insight", None)
                analytics.pop("preference", None)
                analytics.pop("metric", None)
                analytics.pop("metric_type", None)
                analytics.pop("blog_metric", None)
                
                payload_dict["analytics"] = analytics
                logger.info(f"Normalized analytics payload: {json.dumps(analytics, indent=2, default=str)}")
        
        # Fix content_generation payload if type is missing or null
        if payload_dict.get("intent") == "content_generation" and payload_dict.get("content"):
            content = payload_dict["content"]
            
            if isinstance(content, dict):
                # Check if type is missing, None, or null
                content_type = content.get("type")
                
                # Handle None/null values
                if content_type is None or content_type == "null" or content_type == "":
                    content_type = None
                
                # If type is missing or null, try to infer it
                if not content_type:
                    # Try to infer type from existing nested objects
                    if content.get("social_media"):
                        content["type"] = "social_media"
                        content_type = "social_media"
                    elif content.get("blog"):
                        content["type"] = "blog"
                        content_type = "blog"
                    elif content.get("email"):
                        content["type"] = "email"
                        content_type = "email"
                    elif content.get("whatsapp"):
                        content["type"] = "whatsapp"
                        content_type = "whatsapp"
                    elif content.get("ads"):
                        content["type"] = "ads"
                        content_type = "ads"
                    else:
                        # Check for blog-like fields (topic, length, style) - these suggest blog type
                        if any(key in content for key in ["topic", "length", "style"]):
                            # These fields suggest it might be a blog, but we need to restructure
                            # For now, default to social_media as it's most common
                            content["type"] = "social_media"
                            content_type = "social_media"
                            logger.warning("Content type missing, detected blog-like fields but defaulting to social_media")
                        else:
                            # Default to social_media if we can't infer (most common use case)
                            # This handles the case where user says "create content" without specifying type
                            content["type"] = "social_media"
                            content_type = "social_media"
                            logger.warning("Content type missing or null, defaulting to social_media")
                
                # If we have social_media type, ensure social_media nested object exists
                if content_type == "social_media":
                    if "social_media" not in content:
                        content["social_media"] = {}
                    
                    social_media = content["social_media"]
                    if not isinstance(social_media, dict):
                        social_media = {}
                        content["social_media"] = social_media
                    
                    # Check if platform or content_type are at the wrong level (directly under content)
                    # Move them to social_media if found
                    if "platform" in content and "platform" not in social_media:
                        social_media["platform"] = content.pop("platform")
                        logger.info(f"Moved platform from content to social_media: {social_media.get('platform')}")
                    
                    if "content_type" in content and "content_type" not in social_media:
                        social_media["content_type"] = content.pop("content_type")
                        logger.info(f"Moved content_type from content to social_media: {social_media.get('content_type')}")
                    
                    if "idea" in content and "idea" not in social_media:
                        social_media["idea"] = content.pop("idea")
                        logger.info(f"Moved idea from content to social_media: {social_media.get('idea')}")
                    
                    # Move media and media_file fields if they're at the wrong level
                    if "media" in content and "media" not in social_media:
                        social_media["media"] = content.pop("media")
                        logger.info(f"Moved media from content to social_media: {social_media.get('media')}")
                    
                    if "media_file" in content and "media_file" not in social_media:
                        social_media["media_file"] = content.pop("media_file")
                        logger.info(f"Moved media_file from content to social_media: {social_media.get('media_file')}")
                    
                    # Move date and task fields if they're at the wrong level
                    if "date" in content and "date" not in social_media:
                        social_media["date"] = content.pop("date")
                        logger.info(f"Moved date from content to social_media: {social_media.get('date')}")
                    
                    if "task" in content and "task" not in social_media:
                        social_media["task"] = content.pop("task")
                        logger.info(f"Moved task from content to social_media: {social_media.get('task')}")
                    
                    # Move content field (for saved_content_id) if it's at the wrong level
                    if "content" in content and "content" not in social_media:
                        social_media["content"] = content.pop("content")
                        logger.info(f"Moved content (saved_content_id) from content to social_media: {social_media.get('content')}")
                
                # If we have email type, ensure email nested object exists and normalize field names
                elif content_type == "email":
                    if "email" not in content:
                        content["email"] = {}
                    
                    email = content["email"]
                    if not isinstance(email, dict):
                        email = {}
                        content["email"] = email
                    
                    # Map common field name variations to the correct field name
                    # LLM might use "recipient" but EmailPayload uses "email_address"
                    if "recipient" in email and "email_address" not in email:
                        email["email_address"] = email.pop("recipient")
                        logger.info(f"Mapped recipient to email_address: {email.get('email_address')}")
                    
                    # Also check if recipient is at the wrong level (directly under content)
                    if "recipient" in content and "email_address" not in email:
                        email["email_address"] = content.pop("recipient")
                        logger.info(f"Moved recipient from content to email.email_address: {email.get('email_address')}")
                    
                    # Map common email content field name variations
                    # LLM might use "body", "message", "text", "subject" but EmailPayload uses "content"
                    content_field_aliases = ["body", "message", "text", "subject", "topic", "about"]
                    for alias in content_field_aliases:
                        if alias in email and "content" not in email:
                            email["content"] = email.pop(alias)
                            logger.info(f"Mapped {alias} to content: {email.get('content')[:50] if email.get('content') else None}")
                            break
                        elif alias in content and "content" not in email:
                            email["content"] = content.pop(alias)
                            logger.info(f"Moved {alias} from content to email.content: {email.get('content')[:50] if email.get('content') else None}")
                            break
                    
                    # Handle attachment/attachments fields
                    # EmailPayload uses "attachments" (plural, List[str])
                    # LLM might use "attachment" (singular) - convert to list if needed
                    if "attachment" in email and "attachments" not in email:
                        attachment_value = email.pop("attachment")
                        # Convert to list if it's a string
                        if isinstance(attachment_value, str):
                            email["attachments"] = [attachment_value]
                        elif isinstance(attachment_value, list):
                            email["attachments"] = attachment_value
                        else:
                            email["attachments"] = [str(attachment_value)] if attachment_value else []
                        logger.info(f"Mapped attachment to attachments: {email.get('attachments')}")
                    
                    # Also check if attachment/attachments is at the wrong level (directly under content)
                    if "attachment" in content and "attachments" not in email:
                        attachment_value = content.pop("attachment")
                        if isinstance(attachment_value, str):
                            email["attachments"] = [attachment_value]
                        elif isinstance(attachment_value, list):
                            email["attachments"] = attachment_value
                        else:
                            email["attachments"] = [str(attachment_value)] if attachment_value else []
                        logger.info(f"Moved attachment from content to email.attachments: {email.get('attachments')}")
                    
                    if "attachments" in content and "attachments" not in email:
                        email["attachments"] = content.pop("attachments")
                        logger.info(f"Moved attachments from content to email.attachments: {email.get('attachments')}")
                
                # If we have blog type, ensure blog nested object exists and normalize field names
                elif content_type == "blog":
                    if "blog" not in content:
                        content["blog"] = {}
                    
                    blog = content["blog"]
                    if not isinstance(blog, dict):
                        blog = {}
                        content["blog"] = blog
                    
                    # Check if blog fields are at the wrong level (directly under content)
                    # Move them to blog if found
                    blog_field_mappings = {
                        "topic": "topic",
                        "platform": "platform",
                        "length": "length",
                        "media": "media",
                        "media_file": "media_file",
                        "task": "task"
                    }
                    for field_name, target_field in blog_field_mappings.items():
                        if field_name in content and target_field not in blog:
                            blog[target_field] = content.pop(field_name)
                            logger.info(f"Moved {field_name} from content to blog.{target_field}: {blog.get(target_field)}")
                
                # If we have whatsapp type, ensure whatsapp nested object exists and normalize field names
                elif content_type == "whatsapp":
                    if "whatsapp" not in content:
                        content["whatsapp"] = {}
                    
                    whatsapp = content["whatsapp"]
                    if not isinstance(whatsapp, dict):
                        whatsapp = {}
                        content["whatsapp"] = whatsapp
                    
                    # Map common field name variations
                    # LLM might use "phone" or "number" but WhatsAppPayload uses "phone_number"
                    if "phone" in whatsapp and "phone_number" not in whatsapp:
                        whatsapp["phone_number"] = whatsapp.pop("phone")
                        logger.info(f"Mapped phone to phone_number: {whatsapp.get('phone_number')}")
                    
                    if "number" in whatsapp and "phone_number" not in whatsapp:
                        whatsapp["phone_number"] = whatsapp.pop("number")
                        logger.info(f"Mapped number to phone_number: {whatsapp.get('phone_number')}")
                    
                    # Also check if phone/number is at the wrong level (directly under content)
                    if "phone" in content and "phone_number" not in whatsapp:
                        whatsapp["phone_number"] = content.pop("phone")
                        logger.info(f"Moved phone from content to whatsapp.phone_number: {whatsapp.get('phone_number')}")
                    
                    if "number" in content and "phone_number" not in whatsapp:
                        whatsapp["phone_number"] = content.pop("number")
                        logger.info(f"Moved number from content to whatsapp.phone_number: {whatsapp.get('phone_number')}")
                    
                    # Map common message field name variations
                    # LLM might use "message", "text", "content" but WhatsAppPayload uses "text"
                    message_field_aliases = ["message", "content", "body"]
                    for alias in message_field_aliases:
                        if alias in whatsapp and "text" not in whatsapp:
                            whatsapp["text"] = whatsapp.pop(alias)
                            logger.info(f"Mapped {alias} to text: {whatsapp.get('text')[:50] if whatsapp.get('text') else None}")
                            break
                        elif alias in content and "text" not in whatsapp:
                            whatsapp["text"] = content.pop(alias)
                            logger.info(f"Moved {alias} from content to whatsapp.text: {whatsapp.get('text')[:50] if whatsapp.get('text') else None}")
                            break
                    
                    # Handle attachment field
                    # WhatsAppPayload uses "attachment" (singular, str)
                    if "attachment" in content and "attachment" not in whatsapp:
                        whatsapp["attachment"] = content.pop("attachment")
                        logger.info(f"Moved attachment from content to whatsapp.attachment: {whatsapp.get('attachment')}")
                
                # Re-check content_type after inference (it should be set by now)
                content_type = content.get("type")
                logger.info(f"Content type after inference: {content_type}")
                
                # Ensure type is valid (handle case where type was set but invalid)
                if content_type and content_type not in [None, "null", ""]:
                    valid_types = ["social_media", "blog", "email", "whatsapp", "ads"]
                    if content_type not in valid_types:
                        logger.warning(f"Invalid content type '{content_type}', defaulting to social_media")
                        content["type"] = "social_media"
                        content_type = "social_media"
                    
                    # If type is set but the corresponding nested object doesn't exist, create an empty one
                    # This ensures the payload structure is valid for validation
                    if content_type == "social_media" and "social_media" not in content:
                        content["social_media"] = {}
                    elif content_type == "blog" and "blog" not in content:
                        content["blog"] = {}
                    elif content_type == "email" and "email" not in content:
                        content["email"] = {}
                    elif content_type == "whatsapp" and "whatsapp" not in content:
                        content["whatsapp"] = {}
                    elif content_type == "ads" and "ads" not in content:
                        content["ads"] = {}
                else:
                    # If type is still None/empty after all attempts, remove the content object entirely
                    # We'll ask the user for the type in the handler
                    logger.warning(f"Content type could not be determined (type={content_type}), removing content from payload")
                    payload_dict["content"] = None
                    # Return early since we've removed content
                    return payload_dict
                
                # Remove invalid fields that don't belong in ContentGenerationPayload
                # ContentGenerationPayload should only have: type, social_media, blog, email, whatsapp, ads
                # Only do this if content still exists and has a valid type
                if content and isinstance(content, dict) and content.get("type"):
                    valid_content_keys = ["type", "social_media", "blog", "email", "whatsapp", "ads"]
                    invalid_keys = [key for key in content.keys() if key not in valid_content_keys]
                    if invalid_keys:
                        logger.warning(f"Removing invalid fields from content payload: {invalid_keys}")
                        for key in invalid_keys:
                            content.pop(key, None)
                elif content and isinstance(content, dict) and not content.get("type"):
                    # If content exists but type is still None, remove it
                    logger.warning("Content object exists but type is None, removing content from payload")
                    payload_dict["content"] = None
        
        return payload_dict
    
    def _merge_payloads(self, existing: Optional[Dict[str, Any]], new: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge new payload data into existing partial payload.
        
        FIX 2: New non-null values override old ones, empty lists do NOT count as valid.
        FIX 6: Properly merge nested dicts without overwriting valid existing fields.
        For analytics, new values always override old ones (except when old value is valid and new is invalid).
        """
        if not existing:
            return new.copy()
        
        merged = existing.copy()
        
        # Recursively merge nested dictionaries
        for key, value in new.items():
            if value is not None:  # Only merge non-null values
                # FIX 2: Empty lists do NOT count as valid values - skip them
                if isinstance(value, list) and len(value) == 0:
                    continue
                
                if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                    # Special handling for analytics dict
                    if key == "analytics":
                        # Merge analytics dict - new values override old ones
                        merged_analytics = merged[key].copy()
                        for analytics_key, analytics_value in value.items():
                            if analytics_value is not None:
                                # FIX 2: Empty lists don't override existing values
                                if isinstance(analytics_value, list) and len(analytics_value) == 0:
                                    continue
                                
                                # FIX 2: New non-null values always override old ones
                                # Special case: preserve valid existing values only if new value is invalid
                                existing_analytics_value = merged_analytics.get(analytics_key)
                                
                                if analytics_key == "insight_type":
                                    if analytics_value in ["analytics", "insight"]:
                                        merged_analytics[analytics_key] = analytics_value
                                    # If new value is invalid but old is valid, keep old
                                    elif existing_analytics_value in ["analytics", "insight"]:
                                        continue  # Keep existing valid value
                                    else:
                                        merged_analytics[analytics_key] = analytics_value
                                elif analytics_key == "source":
                                    if analytics_value in ["social_media", "blog"]:
                                        merged_analytics[analytics_key] = analytics_value
                                    # If new value is invalid but old is valid, keep old
                                    elif existing_analytics_value in ["social_media", "blog"]:
                                        continue  # Keep existing valid value
                                    else:
                                        merged_analytics[analytics_key] = analytics_value
                                else:
                                    # For other fields, new value always overrides
                                    merged_analytics[analytics_key] = analytics_value
                        merged[key] = merged_analytics
                    else:
                        # Regular nested dict merge
                        merged[key] = self._merge_payloads(merged[key], value)
                else:
                    # Update top-level or non-dict values
                    # FIX 2: Empty lists don't override existing values
                    if isinstance(value, list) and len(value) == 0:
                        continue
                    merged[key] = value
        
        return merged
    
    def _normalize_platform(self, platform: Any) -> Optional[str]:
        """Normalize platform name to valid enum value"""
        if platform is None:
            return None
        
        if isinstance(platform, list):
            if len(platform) == 0:
                return None
            platform = platform[0]
        
        platform_str = str(platform).strip().lower()
        
        if platform_str in self.PLATFORM_ALIASES:
            platform_str = self.PLATFORM_ALIASES[platform_str]
        
        if platform_str in self.VALID_PLATFORMS:
            return platform_str
        
        logger.warning(f"Invalid platform: {platform}, normalized to None")
        return None
    
    def _normalize_platform_list(self, platforms: Any) -> List[str]:
        """Normalize a list of platforms to valid enum values"""
        if platforms is None:
            return []
        
        if isinstance(platforms, str):
            platforms = [platforms]
        
        if not isinstance(platforms, list):
            platforms = [platforms]
        
        normalized = []
        for p in platforms:
            norm_p = self._normalize_platform(p)
            if norm_p and norm_p not in normalized:
                normalized.append(norm_p)
        
        return normalized
    
    def _normalize_metric(self, metric: str) -> Optional[str]:
        """Normalize a single metric name to valid enum value"""
        if not metric:
            return None
        
        metric_str = str(metric).strip().lower()
        
        if metric_str in self.METRIC_SYNONYMS:
            metric_str = self.METRIC_SYNONYMS[metric_str]
        
        if metric_str in self.VALID_SOCIAL_METRICS:
            return metric_str
        
        logger.warning(f"Invalid metric: {metric}, normalized to None")
        return None
    
    def _normalize_metrics(self, metrics: Any) -> List[str]:
        """
        Normalize metrics list.
        
        CRITICAL: If user selects "all metrics", normalize to ["all"]
        Do NOT expand here - let Orion expand based on platform.
        """
        if metrics is None:
            return []
        
        # Handle string input (comma-separated or single value)
        if isinstance(metrics, str):
            metrics_str = metrics.strip().lower()
            if not metrics_str:
                return []
            
            # CRITICAL: Check for "all metrics" variants
            all_metrics_variants = ["all", "all metrics", "everything", "saare metrics", "saare"]
            if metrics_str in all_metrics_variants:
                return ["all"]
            
            if "," in metrics_str:
                metrics = [m.strip() for m in metrics_str.split(",")]
            else:
                metrics = [metrics_str]
        
        # Convert non-list to list
        if not isinstance(metrics, list):
            metrics = [metrics]
        
        # Check if any metric is "all metrics" variant
        all_metrics_variants = ["all", "all metrics", "everything", "saare metrics", "saare"]
        metrics_lower = [str(m).lower().strip() if m else "" for m in metrics]
        
        if any(m in all_metrics_variants for m in metrics_lower):
            return ["all"]
        
        # Normalize each metric and remove duplicates
        normalized = []
        for m in metrics:
            if m is None:
                continue
            norm_m = self._normalize_metric(m)
            if norm_m and norm_m not in normalized:
                normalized.append(norm_m)
        
        return normalized
    
    def _normalize_blog_metrics(self, metrics: Any) -> List[str]:
        """Normalize blog metrics list to valid enum values"""
        if not metrics:
            return []
            
        if isinstance(metrics, str):
            metrics = [metrics]
            
        if not isinstance(metrics, list):
            return []
            
        valid_metrics = [
            "performance_score", "lcp", "cls", "inp", 
            "seo_score", "accessibility_score", "best_practices_score", "opportunities"
        ]
        
        normalized = []
        for m in metrics:
            m_lower = str(m).lower().strip().replace(" ", "_")
            
            # Mapping
            if m_lower in ["performance", "speed"]: normalized.append("performance_score")
            elif m_lower in ["seo", "third_party", "search_optimization"]: normalized.append("seo_score")
            elif m_lower in ["accessibility"]: normalized.append("accessibility_score")
            elif m_lower in ["best_practices"]: normalized.append("best_practices_score")
            elif m_lower in ["lcp", "largest_contentful_paint"]: normalized.append("lcp")
            elif m_lower in ["cls", "cumulative_layout_shift"]: normalized.append("cls")
            elif m_lower in ["inp", "interaction_to_next_paint"]: normalized.append("inp")
            elif m_lower in ["ops", "opportunities", "fix", "fixes"]: normalized.append("opportunities")
            elif m_lower in valid_metrics: normalized.append(m_lower)
            
        return list(set(normalized))
    
    def _normalize_insight_type(self, insight_type: Any) -> Optional[str]:
        """
        Normalize insight_type to valid enum value.
        
        Handles multiple input formats:
        - String: "analytics", "insight"
        - List: ["analytics"], ["insight"]
        - Nested dict: {"type": "analytics"}
        - Various synonyms and aliases
        """
        if insight_type is None:
            return None
        
        # Handle list - take first element
        if isinstance(insight_type, list):
            if len(insight_type) == 0:
                return None
            insight_type = insight_type[0]
        
        # Handle dict - extract value
        if isinstance(insight_type, dict):
            # Try common keys
            insight_type = (
                insight_type.get("type") or
                insight_type.get("value") or
                insight_type.get("insight_type") or
                list(insight_type.values())[0] if insight_type else None
            )
            if insight_type is None:
                return None
        
        # Convert to string and normalize
        insight_str = str(insight_type).strip().lower()
        
        # Map synonyms to canonical values
        if insight_str in ["analytics", "analysis", "data", "historical", "compare", "comparison", "trend", "show data"]:
            return "analytics"
        
        if insight_str in ["insight", "insights", "live", "latest", "current", "real-time", "realtime", "now", "status"]:
            return "insight"
        
        logger.warning(f"Invalid insight_type: {insight_type}, normalized to None")
        return None
    
    def _normalize_source(self, source: Any) -> Optional[str]:
        """Normalize source to valid enum value"""
        if source is None:
            return None
        
        source_str = str(source).strip().lower()
        
        if source_str in ["social_media", "social", "social media", "sns"]:
            return "social_media"
        
        if source_str in ["blog", "blogs", "blogging"]:
            return "blog"
        
        logger.warning(f"Invalid source: {source}, normalized to None")
        return None
    
    def _normalize_analytics_payload(self, analytics_dict: Dict[str, Any], user_query: Optional[str] = None) -> Dict[str, Any]:
        """
        Comprehensive normalization of analytics payload from LLM.
        
        FIX 1: Strong canonical mapping for insight_type from multiple variants.
        FIX 3: Platform implies source - if platform provided, auto-assign source.
        FIX 6: Never overwrite existing valid fields.
        
        Args:
            analytics_dict: The analytics dictionary to normalize
            user_query: Optional user query to help with normalization when LLM extraction fails
        """
        if not analytics_dict:
            return {}
        
        normalized = {}
        
        # FIX 1: Strong canonical mapping for insight_type
        # Check multiple possible keys that might contain insight_type
        insight_type = (
            analytics_dict.get("insight_type") or
            analytics_dict.get("type") or
            analytics_dict.get("analysis_type") or
            analytics_dict.get("mode") or
            analytics_dict.get("analytics_type") or
            analytics_dict.get("insight") or
            analytics_dict.get("preference")
        )
        
        # FIX 1: Also check user_query if provided (fallback when LLM extraction fails)
        if not insight_type and user_query:
            user_query_lower = user_query.strip().lower()
            if user_query_lower in ["analytics", "insight"]:
                insight_type = user_query_lower
                logger.info(f"FIX 1: Extracted insight_type from user_query fallback: {insight_type}")
        
        # FIX 6: Only normalize if not already present and valid
        existing_insight_type = analytics_dict.get("insight_type")
        if existing_insight_type and existing_insight_type in ["analytics", "insight"]:
            # Already valid, don't override
            normalized["insight_type"] = existing_insight_type
            logger.info(f"Preserving existing valid insight_type: {existing_insight_type}")
        else:
            # Normalize from extracted value
            # Default to "insight" for post-level analytics if not specified
            normalized_insight_type = self._normalize_insight_type(insight_type)
            if normalized_insight_type:
                normalized["insight_type"] = normalized_insight_type
            elif analytics_dict.get("analytics_level") == "post":
                # Default to "insight" for post-level queries
                normalized["insight_type"] = "insight"
            # If None and not post-level, don't set it - let missing fields check handle it
        
        # 2. Normalize source (FIX 3: platform implies source, FIX 6: preserve if valid)
        existing_source = analytics_dict.get("source")
        if existing_source and existing_source in ["social_media", "blog"]:
            normalized["source"] = existing_source
        else:
            # FIX 3: Check if platform implies source
            platform = analytics_dict.get("platform")
            inferred_source = None
            
            if platform:
                # Handle both list and single platform
                platform_list = platform if isinstance(platform, list) else [platform] if platform else []
                # Filter out None/empty values and normalize
                platform_list = [str(p).strip().lower() for p in platform_list if p]
                
                if platform_list:  # Only proceed if we have valid platforms
                    # Social media platforms
                    social_media_platforms = ["instagram", "facebook", "twitter", "youtube", "linkedin", "tiktok", "snapchat", "pinterest"]
                    # Blog platforms
                    blog_platforms = ["wordpress", "medium", "substack", "blogger"]
                    
                    # Check if any platform is a social media platform
                    has_social_media = any(p in social_media_platforms for p in platform_list)
                    # Check if any platform is a blog platform
                    has_blog = any(p in blog_platforms for p in platform_list)
                    
                    # Priority: social_media platforms take precedence if mixed
                    if has_social_media:
                        inferred_source = "social_media"
                        logger.info(f"FIX 3: Platform {platform_list} implies source='social_media'")
                    elif has_blog:
                        inferred_source = "blog"
                        logger.info(f"FIX 3: Platform {platform_list} implies source='blog'")
            
            # Use inferred source if available, otherwise normalize from source field
            if inferred_source:
                normalized["source"] = inferred_source
            else:
                # CRITICAL FIX: If source was already set by direct answer detection, preserve it
                # Don't normalize it away if it's already valid
                if existing_source and existing_source in ["social_media", "blog"]:
                    normalized["source"] = existing_source
                else:
                    normalized["source"] = self._normalize_source(analytics_dict.get("source"))
        
        # 3. Normalize platform (FIX 6: preserve if valid list)
        existing_platform = analytics_dict.get("platform")
        if existing_platform and isinstance(existing_platform, list) and len(existing_platform) > 0:
            # Already valid list, normalize but preserve structure
            normalized["platform"] = self._normalize_platform_list(existing_platform)
        elif existing_platform:
            normalized["platform"] = self._normalize_platform_list(existing_platform)
        else:
            platform = analytics_dict.get("platform")
            if platform:
                normalized["platform"] = self._normalize_platform_list(platform)
            else:
                normalized["platform"] = None
        
        # 4. Normalize metrics (FIX 6: preserve if valid list)
        existing_metrics = analytics_dict.get("metrics")
        if existing_metrics and isinstance(existing_metrics, list) and len(existing_metrics) > 0:
            # Already valid list, normalize but preserve
            normalized["metrics"] = self._normalize_metrics(existing_metrics)
        else:
            metrics = (
                analytics_dict.get("metrics") or
                analytics_dict.get("metric") or
                analytics_dict.get("metric_type")
            )
            if metrics:
                normalized["metrics"] = self._normalize_metrics(metrics)
            else:
                normalized["metrics"] = None
        
        # 5. Normalize blog_metrics (FIX 6: preserve if valid list)
        existing_blog_metrics = analytics_dict.get("blog_metrics")
        if existing_blog_metrics and isinstance(existing_blog_metrics, list) and len(existing_blog_metrics) > 0:
            normalized["blog_metrics"] = self._normalize_blog_metrics(existing_blog_metrics)
        else:
            blog_metrics = (
                analytics_dict.get("blog_metrics") or
                analytics_dict.get("blog_metric")
            )
            if blog_metrics:
                normalized["blog_metrics"] = self._normalize_blog_metrics(blog_metrics)
            else:
                normalized["blog_metrics"] = None
        
        # 6. Normalize date_range (FIX 6: preserve if valid)
        existing_date_range = analytics_dict.get("date_range")
        if existing_date_range and isinstance(existing_date_range, str) and existing_date_range.strip():
            normalized["date_range"] = existing_date_range.strip()
        else:
            date_range = analytics_dict.get("date_range")
            if date_range:
                normalized["date_range"] = str(date_range).strip()
            else:
                normalized["date_range"] = None
        
        # 7. Normalize analytics_level, top_n, sort_order (DETECT from user_query)
        # CRITICAL: Preserve existing analytics_level if already set (from post-comparison detection)
        # Only detect if not already set
        existing_analytics_level = analytics_dict.get("analytics_level")
        if existing_analytics_level and existing_analytics_level in ["account", "post"]:
            # Already set (likely from post-comparison detection), preserve it
            normalized["analytics_level"] = existing_analytics_level
            if analytics_dict.get("top_n"): normalized["top_n"] = analytics_dict.get("top_n")
            if analytics_dict.get("sort_order"): normalized["sort_order"] = analytics_dict.get("sort_order")
            if analytics_dict.get("num_posts"): normalized["num_posts"] = analytics_dict.get("num_posts")
            logger.info(f"🔒 Preserving existing analytics_level in normalization: {existing_analytics_level}")
        elif user_query:
            # Not set yet, detect from query
            level, top_n, sort_order = self._detect_analytics_level(user_query)
            normalized["analytics_level"] = level
            if top_n: normalized["top_n"] = top_n
            if sort_order: normalized["sort_order"] = sort_order
        else:
            # Preserve existing if no query available
            if analytics_dict.get("analytics_level"): normalized["analytics_level"] = analytics_dict.get("analytics_level")
            if analytics_dict.get("top_n"): normalized["top_n"] = analytics_dict.get("top_n")
            if analytics_dict.get("sort_order"): normalized["sort_order"] = analytics_dict.get("sort_order")

        # Remove None values to allow Pydantic defaults (but preserve empty lists as they indicate "provided but empty")
        normalized = {k: v for k, v in normalized.items() if v is not None}
        
        logger.info(f"Normalized analytics payload: {normalized}")
        return normalized
    
    def _get_missing_fields_for_social_media(self, payload: Any) -> List[Dict[str, Any]]:
        """Get list of missing required fields for social media payload"""
        missing = []
        
        if not payload:
            return [{
                "field": "platform", 
                "question": "Which platform(s) would you like to create content for?", 
                "options": ["facebook", "instagram", "youtube", "linkedin", "twitter", "pinterest"],
                "priority": 1
            }]
        
        # Required fields in priority order
        if not payload.platform:
            missing.append({
                "field": "platform",
                "question": "Which platform(s) would you like to create content for?",
                "options": ["facebook", "instagram", "youtube", "linkedin", "twitter", "pinterest"],
                "priority": 1
            })
        
        if not payload.content_type:
            missing.append({
                "field": "content_type",
                "question": "What type of content would you like to create?",
                "options": ["post", "reel", "video", "story", "carousel"],
                "priority": 2
            })
        
        if not payload.idea:
            missing.append({
                "field": "idea",
                "question": "What would you like to share in this social media post?",
                "options": None,
                "priority": 3
            })
        
        # Sort by priority
        missing.sort(key=lambda x: x.get("priority", 999))
        return missing
    
    def _llm_classify_analytics_vs_insight(self, user_query: str) -> Optional[str]:
        """
        Use LLM to accurately classify analytics vs insight intent.
        
        This provides better accuracy than keyword matching for ambiguous queries.
        """
        try:
            classification_prompt = f"""You are an expert at classifying user queries for analytics systems.

Your task: Classify the user query as either "analytics" or "insight".

ANALYTICS means:
- User wants HISTORICAL data with TIME PERIODS (e.g., "last 7 days", "last month")
- User wants COMPARISONS or TRENDS over time (e.g., "compare", "growth", "trend")
- User wants AGGREGATED data from past periods (e.g., "how many likes in last week")
- User explicitly says "analytics", "analysis", "historical data"
- Examples: "last 7 days analytics", "compare last month", "growth trend", "historical performance"

INSIGHT means:
- User wants CURRENT/LIVE status (e.g., "current", "right now", "latest")
- User wants REAL-TIME data (e.g., "live", "real-time", "how is my post performing now")
- User asks about PRESENT state without time periods (e.g., "how is my Instagram doing?")
- User asks "how did my post perform?" (singular, present-focused)
- Examples: "current status", "latest post performance", "how is my Instagram doing?", "right now how many likes"

CRITICAL RULES:
1. If query mentions TIME PERIODS (last 7 days, last month, etc.) → ANALYTICS
2. If query mentions COMPARISON or GROWTH → ANALYTICS
3. If query asks about CURRENT/LIVE status without time periods → INSIGHT
4. If query asks "how did X perform?" (singular, present-focused) → INSIGHT
5. If query asks "how many X in last Y days?" → ANALYTICS

User Query: "{user_query}"

Respond with ONLY one word: "analytics" or "insight"
Do not include any explanation or additional text."""

            response = self.llm.invoke([HumanMessage(content=classification_prompt)])
            classified = response.content.strip().lower()
            
            # Validate response
            if classified in ["analytics", "insight"]:
                return classified
            else:
                logger.warning(f"LLM returned invalid classification: {classified}")
                return None
                
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}")
            return None

    def _detect_analytics_vs_insight(self, user_query: str) -> Optional[str]:
        """
        PHASE 4: Detect if user wants analytics or insight using LLM + keyword fallback.
        
        ANALYTICS (Historical + Comparative from Supabase Cache):
        - Historical data with period comparison from Supabase cache
        - Examples: "last 7 days", "compare", "trend", "growth", "historical data"
        
        INSIGHT (Live/Latest from Platform API):
        - Fresh data fetched directly from platform API (real-time status)
        - Examples: "current", "latest", "right now", "live", "how is my post performing"
        
        Args:
            user_query: User's query string
        
        Returns:
            "analytics" or "insight" if detected, None if ambiguous
        """
        if not user_query:
            return None
        
        query_lower = user_query.lower().strip()
        
        # First, try LLM-based classification for better accuracy
        try:
            llm_result = self._llm_classify_analytics_vs_insight(user_query)
            if llm_result:
                logger.info(f"🤖 LLM classified insight_type: {llm_result}")
                return llm_result
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}, falling back to keyword detection")
        
        # Fallback to keyword-based detection
        # STRONG ANALYTICS indicators (high weight)
        strong_analytics_patterns = [
            # Time period patterns (STRONGEST indicators)
            "last 7 day", "last 7 days", "pichle 7 din", "pichle 7 day",
            "last week", "pichle hafte", "pichle hafta", "past week",
            "last month", "pichle mahine", "pichle mahina", "past month",
            "last 30 day", "last 30 days", "pichle 30 din",
            "last 14 day", "last 14 days", "pichle 14 din",
            # Explicit analytics requests
            "analytics", "analysis", "analyse", "analyze",
            "ka analytics", "ka analysis", "ke analytics", "ke analysis",
            "analytics dikha", "analytics batao", "analytics de",
            "analysis dikha", "analysis batao", "analysis de",
            # Comparative/trend patterns
            "compare", "comparison", "trend", "trending", "growth",
            "compare karo", "compare kar", "trend dikha",
            # Historical patterns
            "historical", "history", "past performance", "past data",
            "itihaas", "purana data", "pehle ka data"
        ]
        
        # MODERATE ANALYTICS indicators (medium weight)
        moderate_analytics_patterns = [
            # Quantitative questions about past
            "kitne aaye", "kitne mile", "kitne hue", "kitne the",
            "how many came", "how many received", "how many gained",
            # Performance over time
            "performance", "perform kar raha", "perform kiya",
            # Data requests
            "data dikha", "data de", "data batao", "show data",
            # Aggregate patterns
            "total", "sum", "count", "average", "overall"
        ]
        
        # WEAK ANALYTICS indicators (low weight)
        weak_analytics_patterns = [
            "last", "pichle", "previous", "pehle",
            "show", "dikha", "batao", "bta", "de do"
        ]
        
        # STRONG INSIGHT indicators (high weight)
        strong_insight_patterns = [
            # Explicit Insight requests
            "insight", "insights", "insight dikha", "insights batao",
            # Real-time/current status (STRONGEST)
            "right now", "abhi", "abhi ke", "abhi ka",
            "current", "currently", "current status", "current ka",
            "real-time", "real time", "live", "live data",
            # Today/present
            "today", "aaj", "aaj ka", "aaj ke",
            "this moment", "is moment", "isi waqt",
            # Status checks
            "kaisa chal raha", "kaise chal raha", "how is going",
            "kaisa hai", "kaise hai", "how is it",
            # Latest/fresh
            "latest", "newest", "fresh", "taza", "naya"
        ]
        
        # MODERATE INSIGHT indicators (medium weight)
        moderate_insight_patterns = [
            # General status
            "status", "state", "condition", "sthiti",
            "what is", "what are", "kya hai", "kya he",
            # Current state questions
            "how is", "how are", "kaisa", "kaise"
        ]
        
        # Calculate scores with weights
        strong_analytics_score = sum(3 for pattern in strong_analytics_patterns if pattern in query_lower)
        moderate_analytics_score = sum(2 for pattern in moderate_analytics_patterns if pattern in query_lower)
        weak_analytics_score = sum(1 for pattern in weak_analytics_patterns if pattern in query_lower)
        
        strong_insight_score = sum(3 for pattern in strong_insight_patterns if pattern in query_lower)
        moderate_insight_score = sum(2 for pattern in moderate_insight_patterns if pattern in query_lower)
        
        # Total weighted scores
        total_analytics_score = strong_analytics_score + moderate_analytics_score + weak_analytics_score
        total_insight_score = strong_insight_score + moderate_insight_score
        
        # Log for debugging
        logger.info(f"🔍 Analytics vs Insight Detection:")
        logger.info(f"   Query: {query_lower}")
        logger.info(f"   Analytics score: {total_analytics_score} (strong={strong_analytics_score}, moderate={moderate_analytics_score}, weak={weak_analytics_score})")
        logger.info(f"   Insight score: {total_insight_score} (strong={strong_insight_score}, moderate={moderate_insight_score})")
        
        # Decision logic with clear priority
        
        # PSI/Blog keywords ALWAYS imply insight (Health/Speed checks are live)
        psi_keywords = ["page speed", "seo", "performance", "core web vitals", "lcp", "cls", "inp", "slow"]
        if any(kw in query_lower for kw in psi_keywords):
             logger.info(f"   🛡️ PSI-Only keywords detected. Forcing insight mode.")
             return "insight"

        if strong_insight_score > 0:
            # Strong insight indicators take highest priority
            logger.info(f"   ✅ INSIGHT detected (strong indicators present)")
            return "insight"
        elif strong_analytics_score > 0:
            # Strong analytics indicators (time periods, explicit analytics requests)
            logger.info(f"   ✅ ANALYTICS detected (strong indicators present)")
            return "analytics"
        elif total_insight_score > total_analytics_score and total_insight_score >= 2:
            # If insight has higher score and at least 2 points
            logger.info(f"   ✅ INSIGHT detected (higher weighted score)")
            return "insight"
        elif total_analytics_score > 0:
            # Any analytics score means analytics
            logger.info(f"   ✅ ANALYTICS detected (analytics indicators present)")
            return "analytics"
        else:
            # Default to analytics (safer - shows historical comparison)
            logger.info(f"   ⚠️ No clear indicators - defaulting to ANALYTICS")
            return "analytics"
    
    def _detect_analytics_level(self, user_query: str) -> Tuple[str, Optional[int], Optional[str]]:
        """
        CRITICAL: Detect if user wants ACCOUNT-LEVEL or POST-LEVEL analytics.
        
        POST-LEVEL triggers (individual post data, ranking, top/bottom):
        - "top post", "best post", "worst post"
        - "my posts", "recent posts", "all posts"
        - "most viewed", "most liked", "highest engagement"
        - "top viewed wali post", "sabse zyada likes wala"
        - "which post", "kaunsa post"
        - "ranking", "comparison between posts"
        
        ACCOUNT-LEVEL default (overall performance, aggregated):
        - "performance", "growth", "trend", "percentage change"
        - "last 7 days analytics", "overall metrics"
        
        Args:
            user_query: User's query string
        
        Returns:
            Tuple of (level, top_n, sort_order)
            - level: "post" or "account"
            - top_n: Number of posts to return (None for account-level)
            - sort_order: "desc" for top/best, "asc" for worst/bottom
        """
        if not user_query:
            return ("post", None, None)
        
        query_lower = user_query.lower().strip()
        
        # POST-LEVEL keywords (CRITICAL - these trigger post-level analytics)
        post_level_keywords = [
            # English
            "top post", "best post", "worst post", "bottom post",
            "my posts", "my post", "recent posts", "latest posts",
            "all posts", "show posts", "list posts",
            "most viewed post", "most liked post", "highest engagement post",
            "best performing post", "top performing post",
            "which post", "what post", "show post",
            "top viewed", "most viewed", "most liked", "most commented",
            "highest", "lowest", "best", "worst",
            "post ranking", "rank post", "compare posts",
            "posts analytics", "post analytics", "post performance",
            # Hindi
            "mere posts", "meri posts", "mera post",
            "kaunsa post", "kaun sa post", "konsa post",
            "sabse zyada likes wala", "sabse zyada views wala",
            "sabse zyada engagement wala", "sabse zyada share wala",
            "top wali post", "best wali post",
            "sabse accha post", "sabse bekar post"
        ]
        
        # Check for POST-LEVEL triggers
        for keyword in post_level_keywords:
            if keyword in query_lower:
                logger.info(f"🎯 POST-LEVEL detected: keyword='{keyword}'")
                
                # Determine sort order
                sort_order = "desc"  # Default to top/best
                if any(w in query_lower for w in ["worst", "bottom", "lowest", "bekar"]):
                    sort_order = "asc"
                
                # Determine top_n
                top_n = 5  # Default to top 5 for general post queries
                
                # Check for numbers like "top 5", "top 10", "all 20"
                import re
                match = re.search(r'(?:top|last|recent|latest|all)\s+(\d+)', query_lower)
                if match:
                    top_n = int(match.group(1))
                elif any(word in query_lower for word in ["top post", "best post", "which post"]):
                    top_n = 1  # For singular "top post", return just 1
                
                return ("post", top_n, sort_order)
        
        # Default to POST-LEVEL
        return ("post", None, None)
    
    def _detect_post_comparison_query(self, user_query: str) -> Tuple[bool, Optional[int]]:
        """
        CRITICAL: Detect if user wants POST-COMPARISON analytics.
        
        This has HIGHEST PRIORITY over other analytics types.
        
        POST-COMPARISON vs other types:
        - Post-comparison: "Last 5 posts ne kaisa perform kiya?" (comparing multiple posts)
        - Post-level: "Top post kaunsa hai?" (ranking/sorting - ONE post)
        - Account-level: "last 7 days ka performance" (date-based aggregation)
        
        POST-COMPARISON triggers (EXPLICIT):
        - "last X posts" / "recent posts" / "pichle X posts"
        - "post ka analysis" / "posts ka analysis"
        - "how did my posts perform" / "mere posts kaisa perform kiye"
        - "compare my posts" / "posts ka comparison"
        - "post performance" / "posts ki performance"
        
        CRITICAL RULE:
        "last X post" where X is a number ALWAYS means post-comparison,
        NOT date-based analytics.
        
        Args:
            user_query: User's query string
        
        Returns:
            Tuple of (is_comparison_query, num_posts)
        """
        if not user_query:
            return (False, None)
        
        query_lower = user_query.lower().strip()
        
        import re
        
        # CRITICAL PATTERN 1: "last X post" or "last X posts" (highest priority)
        # This MUST be checked first to override date-based detection
        # Examples: "last 7 post", "last 5 posts", "pichle 10 posts"
        explicit_post_count_patterns = [
            r'last\s+(\d+)\s+posts?',        # "last 7 posts", "last 5 post"
            r'recent\s+(\d+)\s+posts?',      # "recent 5 posts"
            r'pichle\s+(\d+)\s+posts?',      # "pichle 7 posts"
            r'(\d+)\s+posts?\s+ka',          # "7 posts ka analysis"
            r'(\d+)\s+posts?\s+ki',          # "5 posts ki performance"
            r'mere\s+(\d+)\s+posts?',        # "mere 7 posts"
        ]
        
        for pattern in explicit_post_count_patterns:
            match = re.search(pattern, query_lower)
            if match:
                num_posts = int(match.group(1))
                logger.info(f"🎯 POST-COMPARISON detected via explicit pattern: '{pattern}' → num_posts={num_posts}")
                return (True, num_posts)
        
        # CRITICAL PATTERN 2: Singular vs plural without number
        # - "last post" MUST imply 1 post (requested last post)
        # - "last posts" / "recent posts" implies a small set (default 5)
        #
        # IMPORTANT: POST-COUNT BASED REQUEST > DATE BASED REQUEST
        singular_post_patterns = [
            r'\blast\s+post\b',
            r'\blatest\s+post\b',
            r'\brecent\s+post\b',
        ]
        plural_post_patterns = [
            r'\blast\s+posts\b',
            r'\brecent\s+posts\b',
            r'\blatest\s+posts\b',
            r'\bpichle\s+posts\b',
            r'\bmere\s+posts\b',
            r'\bmy\s+posts\b',
        ]

        for pattern in singular_post_patterns:
            if re.search(pattern, query_lower):
                logger.info(f"🎯 POST-COMPARISON detected via singular pattern: '{pattern}' → num_posts=1")
                return (True, 1)

        for pattern in plural_post_patterns:
            if re.search(pattern, query_lower):
                # Try to extract any number present; otherwise default to 5
                num_match = re.search(r'(\d+)', query_lower)
                num_posts = int(num_match.group(1)) if num_match else 5
                logger.info(f"🎯 POST-COMPARISON detected via plural pattern: '{pattern}' → num_posts={num_posts}")
                return (True, num_posts)
        
        # PATTERN 3: Post-wise analysis keywords
        # Examples: "posts ka analysis", "post performance", "posts ki performance"
        post_analysis_keywords = [
            "posts ka analysis",
            "post ka analysis", 
            "posts ki performance",
            "posts ka performance",
            "post performance",
            "posts performance",
            "analyze posts",
            "posts analysis",
            "compare posts",
            "posts comparison",
            "post comparison",
            "how did posts",
            "posts ne kaisa",
            "posts kaisa perform",
            "insight of my post",      # "insight of my instagram post"
            "insight on my post",      # "insight on my instagram post"
            "insight of my posts",     # "insight of my instagram posts"
            "insight on my posts",     # "insight on my instagram posts"
            "insight of post",         # "insight of instagram post"
            "insight on post",         # "insight on instagram post"
            "insight of posts",        # "insight of instagram posts"
            "insight on posts",        # "insight on instagram posts"
        ]
        
        for keyword in post_analysis_keywords:
            if keyword in query_lower:
                # Check if singular ("post") vs plural ("posts")
                is_singular = "post" in keyword and "posts" not in keyword
                
                # Try to extract number
                num_match = re.search(r'(\d+)', query_lower)
                if num_match:
                    num_posts = int(num_match.group(1))
                elif is_singular:
                    num_posts = 1  # Singular "post" = 1 post
                else:
                    num_posts = 5  # Plural "posts" = default 5
                
                logger.info(f"🎯 POST-COMPARISON detected via keyword: '{keyword}' → num_posts={num_posts}")
                return (True, num_posts)
        
        # Not a post-comparison query
        return (False, None)
    
    def _handle_post_comparison(
        self,
        state: IntentBasedChatbotState,
        analytics_dict: Dict[str, Any],
        partial_payload: Dict[str, Any]
    ) -> IntentBasedChatbotState:
        """
        PART 8: Handle post-comparison query and convert Orion output to human language.
        
        This handler:
        1. Validates platform is available
        2. Calls Orion's analyze_post_performance function
        3. Converts structured JSON output to human-friendly language
        4. Returns formatted response to user
        
        Args:
            state: Current chatbot state
            analytics_dict: Analytics payload dictionary
            partial_payload: Full partial payload
        
        Returns:
            Updated state with response
        """
        try:
            from agents.tools.Orion_Analytics_query import analyze_post_performance
            
            user_id = state.get("user_id")
            num_posts = analytics_dict.get("num_posts", 1)  # Default to 1 post
            
            # Get platform (required)
            platform_list = analytics_dict.get("platform", [])
            if not platform_list or not isinstance(platform_list, list) or len(platform_list) == 0:
                # Ask for platform
                state["response"] = "Which platform would you like to analyze?"
                state["options"] = ["instagram", "facebook", "youtube", "linkedin", "twitter", "pinterest"]
                state["needs_clarification"] = True
                state["partial_payload"] = partial_payload
                return state
            
            # Use first platform
            platform = platform_list[0]
            
            # Get metrics from analytics_dict (use requested metrics only)
            metrics = analytics_dict.get("metrics", [])
            if not isinstance(metrics, list):
                metrics = [metrics] if metrics else []
            
            logger.info(f"📊 Executing post-comparison analysis: platform={platform}, num_posts={num_posts}, metrics={metrics}")
            
            # Call Orion's post-comparison function with metrics
            result = analyze_post_performance(user_id, platform, num_posts, metrics=metrics if metrics else None)
            
            # Check for errors
            if not result or result.get("type") != "post_comparison":
                error_msg = result.get("error", "Failed to analyze posts")
                state["response"] = f"I couldn't analyze your posts: {error_msg}"
                state["needs_clarification"] = False
                return state
            
            # Convert Orion's structured output to human language
            human_response = self.format_post_level_response(result)
            
            state["response"] = human_response
            state["needs_clarification"] = False
            state["partial_payload"] = None  # Clear partial payload
            
            return state
            
        except Exception as e:
            logger.error(f"Error in _handle_post_comparison: {e}", exc_info=True)
            state["response"] = f"I encountered an error analyzing your posts: {str(e)}"
            state["needs_clarification"] = False
            return state
    
    def _format_post_comparison_response(
        self,
        result: Dict[str, Any],
        platform: str,
        num_posts: int
    ) -> str:
        """
        Converts Orion's structured post-comparison output into a
        STRICT, data-driven response with NO fabricated analytics.
        """
        try:
            posts = result.get("posts", [])
            summary = result.get("summary", {})
            num_found = summary.get("num_posts_found", len(posts))
            num_requested = summary.get("num_posts_requested", num_posts)
            
            response = []

            # ---------- HEADER ----------
            if num_found == 1:
                response.append(f"**{platform.title()} – Last Post Performance**")
            else:
                response.append(f"**{platform.title()} – Last {num_requested} Posts Performance**")

            # ---------- POST COUNT CLARITY ----------
            if num_found < num_requested:
                response.append(f"\nPosts Found: {num_found} (requested {num_requested})")

            # ---------- METRICS ANALYZED (from actual data) ----------
            if posts:
                # Extract metrics from first post
                first_post_metrics = posts[0].get("metrics", {})
                if not first_post_metrics:
                    # Check direct keys
                    excluded = ["post_id", "caption", "permalink", "timestamp", "label", "score", "ratio_vs_avg", "metadata"]
                    first_post_metrics = {k: v for k, v in posts[0].items() if k not in excluded and isinstance(v, (int, float))}
                
                metrics_list = list(first_post_metrics.keys())
                if metrics_list:
                    response.append(f"\nMetrics Analyzed: {', '.join(metrics_list)}")

            # ---------- POST-WISE BREAKDOWN (STRICT: Only real metrics) ----------
            if num_found == 1:
                response.append("\n--- Post Metrics ---")
            else:
                response.append("\n--- Post-wise Breakdown ---")

            for i, post in enumerate(posts[:num_requested], 1):
                post_metrics = post.get("metrics", {})
                if not post_metrics:
                    excluded = ["post_id", "caption", "permalink", "timestamp", "label", "score", "ratio_vs_avg", "metadata"]
                    post_metrics = {k: v for k, v in post.items() if k not in excluded and isinstance(v, (int, float))}
                
                if num_found > 1:
                    response.append(f"\nPost {i}:")
                
                # Show only actual metrics (no fabricated scores)
                for metric, value in post_metrics.items():
                    if isinstance(value, (int, float)):
                        response.append(f"  {metric.title()}: {value:,}")

            # ---------- NOTE (ONLY if relevant) ----------
            response.append("\n\nNote:")
            if num_found < num_requested:
                response.append(f"• Only {num_found} post{'s' if num_found != 1 else ''} available (requested {num_requested})")
            
            if num_found < 2:
                response.append("• This is a live snapshot of your most recent post")
                response.append("• Comparative analysis requires multiple posts")
            elif num_found < 3:
                response.append("• No ranking or averages were generated due to insufficient data")
            
            # Only show comparison if we have enough data
            comparison = result.get("comparison")
            if comparison and num_found >= 2:
                ratio = comparison.get("best_vs_worst_ratio")
                if ratio and ratio > 1:
                    response.append(f"• Top post received {ratio:.1f}x more engagement than lowest post")

            return "\n".join(response)

        except Exception as e:
            logger.error("Post comparison formatting failed", exc_info=True)
            return (
                "I analyzed your posts but encountered an issue presenting the results. "
                "Please try again later."
            )

    def _generate_recommendations(self, result: Dict[str, Any]) -> List[str]:
        """
        Generate actionable recommendations based on detected patterns.
        
        Args:
            result: Structured output from Orion
        
        Returns:
            List of recommendation strings (max 3)
        """
        recommendations = []
        reasons = result.get("reasons", [])
        posts = result.get("posts", [])
        num_posts = len(posts)
        
        # Check if this is a limited data scenario
        reasons_signals = [r.get("signal", "") for r in reasons]
        is_limited_data = "insufficient_data" in reasons_signals or "insufficient_metadata" in reasons_signals
        
        # Extract patterns from reasons
        for reason in reasons:
            signal = reason.get("signal", "")
            
            if "caption_bucket_short" in signal:
                recommendations.append("Use short captions with a clear hook")
            elif "caption_bucket_long" in signal:
                recommendations.append("Write longer, detailed captions")
            elif "content_type" in signal and "reel" in signal:
                recommendations.append("Create more Reels - they're performing better")
            elif "content_type" in signal and "post" in signal:
                recommendations.append("Focus on regular posts over other formats")
            elif "posting_time_evening" in signal:
                recommendations.append("Post in the evening for better engagement")
            elif "posting_time_morning" in signal:
                recommendations.append("Morning posts are working well for you")
            elif "has_hook_yes" in signal:
                recommendations.append("Start captions with questions or numbers")
        
        # If limited data (< 3 posts), give specific advice
        if is_limited_data or num_posts < 3:
            if num_posts >= 2:
                # We have at least 2 posts - can compare
                best_post = posts[0] if len(posts) > 0 else None
                worst_post = posts[-1] if len(posts) > 1 else None
                
                if best_post and worst_post and best_post != worst_post:
                    recommendations.append("Repeat the format used in the best post")
                    recommendations.append("Avoid the format of the low-performing post")
            
            # Always suggest creating more content for better insights
            if not any("more post" in rec.lower() for rec in recommendations):
                recommendations.insert(0, "Create more posts to get better insights and patterns")
        else:
            # Normal scenario - pattern-based recommendations
            if not recommendations and posts:
                best_post = posts[0] if len(posts) > 0 else None
                worst_post = posts[-1] if len(posts) > 1 else None
                
                if best_post and worst_post:
                    recommendations.append("Analyze what made your best post successful and replicate it")
                    recommendations.append("Avoid formats similar to your low-performing posts")
        
        # Always add a generic recommendation if we have less than 3
        if len(recommendations) < 3:
            recommendations.append("Keep experimenting and track what resonates with your audience")
        
        return recommendations[:3]  # Max 3 recommendations
    
    def _get_platform_post_metrics(self, platforms: List[str]) -> List[str]:
        """
        Get platform-specific post-level metrics.
        
        Merges metrics from all specified platforms and returns sorted unique list.
        
        Args:
            platforms: List of platform names
        
        Returns:
            Sorted list of unique metrics supported by the platforms
        """
        metrics = set()
        for platform in platforms:
            platform_normalized = platform.lower()
            if platform_normalized in self.PLATFORM_POST_METRICS:
                metrics.update(self.PLATFORM_POST_METRICS[platform_normalized])
        return sorted(list(metrics))
    
    def _validate_post_level_insight_requirements(self, analytics_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate post-level insight requirements.
        
        CRITICAL RULE:
        IF intent == "insight" AND analytics_level == "post":
            metrics MUST be provided
            metric options MUST be platform-specific
        
        Args:
            analytics_dict: Analytics payload dictionary
        
        Returns:
            None if validation passes
            Dict with clarification request if metrics missing
        """
        insight_type = analytics_dict.get("insight_type")
        analytics_level = analytics_dict.get("analytics_level")
        metrics = analytics_dict.get("metrics", [])
        platforms = analytics_dict.get("platform", [])
        
        # Only validate for post-level insights
        if insight_type != "insight":
            return None
        
        if analytics_level != "post":
            return None
        
        # If metrics already provided, validation passes
        if metrics and isinstance(metrics, list) and len(metrics) > 0:
            return None
        
        # Metrics missing - need clarification
        # Get platform-specific metrics
        if not platforms or not isinstance(platforms, list) or len(platforms) == 0:
            # No platform specified - ask for platform first
            return None  # Let normal flow handle platform question
        
        platform_metrics = self._get_platform_post_metrics(platforms)
        
        if not platform_metrics:
            # No supported metrics for this platform
            return {
                "needs_clarification": True,
                "message": f"Post-level insights are not available for the selected platform(s).",
                "options": None
            }
        
        return {
            "needs_clarification": True,
            "message": (
                "You're asking for insight on a specific post.\n"
                "Which metrics do you want to analyze?"
            ),
            "options": platform_metrics + ["all metrics"]
        }
    
    def _get_missing_fields_for_analytics(self, analytics_dict: Dict[str, Any], user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of missing REQUIRED fields for analytics payload.
        
        FIX 3: Check for empty lists, not just None.
        FIX 4: Platform implies source - skip source question if platform provided.
        FIX 6: Don't overwrite existing valid fields.
        
        Emily ONLY checks for fields that MUST be provided by the user.
        All defaults, platform inference, and business logic is handled by Orion.
        
        Required fields checked:
        - insight_type: REQUIRED (priority 1)
        - source: REQUIRED (priority 2) - SKIPPED if platform implies source
        - platform: REQUIRED if multiple platforms connected or none connected (priority 3)
        - metrics: ALWAYS REQUIRED for social_media (priority 4) - both analytics and insight
        - blog_metrics: ALWAYS REQUIRED for blog (priority 4) - both analytics and insight
        
        NOT checked here (handled by Orion):
        - date_range (optional, Orion handles defaults)
        """
        missing = []
        
        if not analytics_dict:
            return [{
                "field": "insight_type",
                "question": "I'd love to help! Would you like historical analytics (with comparisons) or live insights (current status)?",
                "options": ["analytics", "insight"],
                "priority": 1
            }]
        
        # Get insight_type (already normalized)
        insight_type = analytics_dict.get("insight_type")
        
        # FIX 4: Priority 1: insight_type (REQUIRED) - check for None OR empty string
        if not insight_type or (isinstance(insight_type, str) and not insight_type.strip()):
            missing.append({
                "field": "insight_type",
                "question": "Would you like historical analytics or live insights?",
                "options": ["analytics", "insight"],
                "priority": 1
            })
            # Return early - can't check other fields without insight_type
            return missing
        
        # FIX 4: Priority 2: source (REQUIRED) - check for None OR empty string
        # FIX 3: SKIP source question if platform implies source
        source = analytics_dict.get("source")
        platform = analytics_dict.get("platform")
        
        # FIX 3: Check if platform implies source
        platform_implies_source = False
        if platform:
            # Normalize platform to list format
            platform_list = platform if isinstance(platform, list) else [platform] if platform else []
            # Filter out None/empty values
            platform_list = [str(p).strip().lower() for p in platform_list if p]
            
            if platform_list:  # Only proceed if we have valid platforms
                social_media_platforms = ["instagram", "facebook", "twitter", "youtube", "linkedin", "tiktok", "snapchat", "pinterest"]
                blog_platforms = ["wordpress", "medium", "substack", "blogger"]
                
                # Check if any platform is a social media platform
                has_social_media = any(p in social_media_platforms for p in platform_list)
                # Check if any platform is a blog platform
                has_blog = any(p in blog_platforms for p in platform_list)
                
                # Priority: social_media platforms take precedence if mixed
                if has_social_media:
                    # Platform implies social_media source
                    if not source or source not in ["social_media", "blog"]:
                        # Auto-assign source
                        analytics_dict["source"] = "social_media"
                        source = "social_media"
                        platform_implies_source = True
                        logger.info(f"FIX 3: Platform {platform_list} implies source='social_media', auto-assigned")
                elif has_blog:
                    # Platform implies blog source
                    if not source or source not in ["social_media", "blog"]:
                        # Auto-assign source
                        analytics_dict["source"] = "blog"
                        source = "blog"
                        platform_implies_source = True
                        logger.info(f"FIX 3: Platform {platform_list} implies source='blog', auto-assigned")
        
        # Only ask for source if it's still missing after platform inference
        if not source or (isinstance(source, str) and not source.strip()):
            missing.append({
                "field": "source",
                "question": "Do you want social media analytics or blog analytics?",
                "options": ["social_media", "blog"],
                "priority": 2
            })
            # Return early - can't check mode-specific fields without source
            return missing
        
        # Priority 3: platform (REQUIRED if multiple platforms connected or none connected)
        # IMPORTANT: Check platform AFTER source is determined, but BEFORE metrics
        # This ensures we ask for platform selection when needed
        # Check if platform is missing - ask user to specify which platform
        platform = analytics_dict.get("platform")
        platform_list = platform if isinstance(platform, list) else [platform] if platform else []
        platform_list = [str(p).strip().lower() for p in platform_list if p]
        
        logger.info(f"🔍 Platform check: platform={platform}, platform_list={platform_list}, user_id={user_id}")
        
        # If no platform specified, check connected platforms
        if not platform_list and user_id:
            try:
                from agents.tools.Orion_Analytics_query import fetch_connected_platforms
                connected_platforms = fetch_connected_platforms(user_id)
                
                # FILTER: If source is known, only show platforms relevant to that source
                if source == "social_media":
                    social_media_platforms = ["instagram", "facebook", "twitter", "youtube", "linkedin", "tiktok", "snapchat", "pinterest"]
                    connected_platforms = [p for p in connected_platforms if p in social_media_platforms]
                elif source == "blog":
                    blog_platforms = ["wordpress", "medium", "substack", "blogger"]
                    connected_platforms = [p for p in connected_platforms if p in blog_platforms]
                
                if len(connected_platforms) > 1:
                    # Multiple platforms - ask user to choose
                    missing.append({
                        "field": "platform",
                        "question": "Which platform would you like to analyze?",
                        "options": connected_platforms,
                        "priority": 3
                    })
                    return missing
                elif len(connected_platforms) == 1:
                    # Only one platform - auto-assign it
                    analytics_dict["platform"] = connected_platforms
                    platform_list = connected_platforms
                    logger.info(f"Auto-assigned single connected platform: {connected_platforms}")
                else:
                    # No platforms connected - ask user to specify
                    default_options = ["instagram", "facebook", "youtube", "linkedin", "twitter", "pinterest"]
                    if source == "blog":
                         default_options = ["wordpress", "shopify", "wix", "html"]
                    
                    missing.append({
                        "field": "platform",
                        "question": "Which platform would you like to analyze?",
                        "options": default_options,
                        "priority": 3
                    })
                    return missing
            except Exception as e:
                logger.warning(f"Error checking connected platforms: {e}")
                # If we can't check, ask user to specify
                default_options = ["instagram", "facebook", "youtube", "linkedin", "twitter", "pinterest"]
                if source == "blog":
                     default_options = ["wordpress", "shopify", "wix", "html"]

                missing.append({
                    "field": "platform",
                    "question": "Which platform would you like to analyze?",
                    "options": default_options,
                    "priority": 3
                })
                return missing
        elif not platform_list:
            # No user_id available - ask user to specify platform
            default_options = ["instagram", "facebook", "youtube", "linkedin", "twitter", "pinterest"]
            if source == "blog":
                 default_options = ["wordpress", "shopify", "wix", "html"]
            
            missing.append({
                "field": "platform",
                "question": "Which platform would you like to analyze?",
                "options": default_options,
                "priority": 3
            })
            return missing
        
        # Priority 4: metrics/blog_metrics (ALWAYS REQUIRED)
        # CRITICAL: Metrics are ALWAYS required for both analytics and insight modes
        # This ensures users explicitly choose what they want to analyze
        analytics_level = analytics_dict.get("analytics_level") or "post"
        
        if source == "social_media":
            metrics = analytics_dict.get("metrics")
            
            # CRITICAL: ALWAYS require metrics (both analytics and insight)
            if not metrics or (isinstance(metrics, list) and len(metrics) == 0):
                # For post-level INSIGHT, use platform-specific metrics
                if analytics_level == "post" and insight_type == "insight":
                    platform_metrics = self._get_platform_post_metrics(platform_list)
                    if platform_metrics:
                        missing.append({
                            "field": "metrics",
                            "question": "You're asking for insight on a specific post.\nWhich metrics do you want to analyze?",
                            "options": platform_metrics + ["all metrics"],
                            "priority": 4
                        })
                    else:
                        missing.append({
                            "field": "metrics",
                            "question": "Post-level insights are not available for the selected platform(s).",
                            "options": None,
                            "priority": 4
                        })
                # For account-level or post-level analytics, show general metrics
                else:
                    # Determine appropriate metrics based on level
                    if analytics_level == "post":
                        metric_options = [
                            "reach", "impressions", "engagement", "likes", "comments", "shares",
                            "saves", "views", "profile_visits"
                        ]
                        question = "For post-level analysis, I need to know which metrics you're interested in. Which metrics should I check?"
                    else:
                        # Account-level metrics
                        metric_options = [
                            "reach", "impressions", "engagement", "likes", "comments", "shares",
                            "saves", "views", "profile_visits", "followers", "growth"
                        ]
                        question = "Which metrics would you like me to analyze?"
                    
                    missing.append({
                        "field": "metrics",
                        "question": question,
                        "options": metric_options,
                        "priority": 4
                    })
        elif source == "blog":
            blog_metrics = analytics_dict.get("blog_metrics")
            # CRITICAL: ALWAYS require blog metrics (both analytics and insight)
            if not blog_metrics or (isinstance(blog_metrics, list) and len(blog_metrics) == 0):
                missing.append({
                    "field": "blog_metrics",
                    "question": "Which blog performance metrics would you like me to analyze (e.g., SEO score, page speed)?",
                    "options": [
                        "performance_score", "lcp", "cls", "inp", 
                        "seo_score", "accessibility_score", "best_practices_score", "opportunities"
                    ],
                    "priority": 4
                })
        
        # Sort by priority
        missing.sort(key=lambda x: x.get("priority", 999))
        return missing
    
    def _generate_clarifying_question(self, missing_fields: List[Dict[str, Any]], intent_type: str) -> str:
        """Generate a clarifying question with options for missing fields"""
        if not missing_fields:
            return ""
        
        # Take the first missing field (highest priority)
        field_info = missing_fields[0]
        question = field_info["question"]
        
        # Add options if available
        if field_info.get("options"):
            options_text = ", ".join([f"**{opt}**" for opt in field_info["options"]])
            question += f"\n\nYou can pick from: {options_text} - or just tell me what you prefer!"
        
        return question
    
    def classify_intent(self, state: IntentBasedChatbotState) -> IntentBasedChatbotState:
        """Classify user query into intent and populate Pydantic payload"""
        query = state["current_query"]
        partial_payload = state.get("partial_payload")
        conversation_history = state.get("conversation_history", [])
        
        # Log the user query
        logger.info(f"Classifying intent for query: {query}")
        if partial_payload:
            logger.info(f"Merging with existing partial payload: {json.dumps(partial_payload, indent=2)}")
        
        # Build context from conversation history
        history_context = ""
        if conversation_history:
            recent_history = conversation_history[-5:]  # Last 5 messages
            history_context = "\n\nRecent conversation:\n"
            for msg in recent_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_context += f"{role}: {content}\n"
        
        # Include partial payload context if exists
        partial_context = ""
        if partial_payload:
            partial_context = f"\n\nPreviously collected information:\n{json.dumps(partial_payload, indent=2)}\n\nExtract any new information from the user's query and merge it with the existing data. Keep all previously collected non-null values."
        
        # Create the classification prompt
        classification_prompt = f"""You are an intent classifier for a business assistant chatbot.

Your job:
1. Read the user's natural language query
2. Classify it into the correct intent (one of: content_generation, analytics, leads_management, posting_manager, general_talks, faq)
3. Extract ALL entities and information from the user's query - be thorough and extract everything mentioned
4. Produce a Pydantic-validated payload according to the provided schema
5. If the user query does not contain enough information, populate whatever fields you can and leave the rest as null
6. DO NOT hallucinate missing information
7. If information is missing and required later, mark the missing fields as null - the graph nodes will ask clarifying questions
8. Always output JSON only, following the exact structure of the Pydantic models
9. If there's existing partial payload data, merge the new information with it (keep existing non-null values, only update with new information from the current query)

Your output MUST strictly follow this root structure:
{{
  "intent": "...",
  "content": {{"type": "social_media" | "blog" | "email" | "whatsapp" | "ads", "social_media": {{"platform": "...", "content_type": "...", "idea": "..."}}, ...}} | null,
  "analytics": {{...}} | null,
  "leads": {{...}} | null,
  "posting": {{...}} | null,
  "general": {{...}} | null,
  "faq": {{"query": "..."}} | null
}}

CRITICAL: ENTITY EXTRACTION FOR CONTENT GENERATION
When the user mentions content creation, you MUST extract ALL entities from their query:

1. PLATFORM EXTRACTION - Extract platform names from the query:
   - "instagram" → platform: ["instagram"]
   - "facebook" → platform: ["facebook"]
   - "youtube" → platform: ["youtube"]
   - "linkedin" → platform: ["linkedin"]
   - "twitter" → platform: ["twitter"]
   - "pinterest" → platform: ["pinterest"]
   - If multiple platforms mentioned, extract all: ["instagram", "facebook"]
   - If user says "instagram reel", extract platform: ["instagram"]

2. CONTENT_TYPE EXTRACTION - Extract content type from the query:
   - "reel" or "reels" → content_type: "reel"
   - "post" or "posts" → content_type: "post"
   - "video" or "videos" → content_type: "video"
   - "story" or "stories" → content_type: "story"
   - "carousel" or "carousels" → content_type: "carousel"
   - If user says "instagram reel", extract content_type: "reel"

3. IDEA/TOPIC EXTRACTION - Extract any topic, idea, or subject mentioned:
   - "product launch" → idea: "product launch"
   - "company update" → idea: "company update"
   - "tip about marketing" → idea: "tip about marketing"
   - Any descriptive text about what the content should be about

EXAMPLES OF CORRECT EXTRACTION:
- User: "i want to create an instagram reel"
  Output: {{
    "intent": "content_generation",
    "content": {{
      "type": "social_media",
      "social_media": {{
        "platform": ["instagram"],
        "content_type": "reel",
        "idea": null
      }}
    }},
    ...
  }}

- User: "create a facebook post about our new product"
  Output: {{
    "intent": "content_generation",
    "content": {{
      "type": "social_media",
      "social_media": {{
        "platform": ["facebook"],
        "content_type": "post",
        "idea": "our new product"
      }}
    }},
    ...
  }}

- User: "make a youtube video"
  Output: {{
    "intent": "content_generation",
    "content": {{
      "type": "social_media",
      "social_media": {{
        "platform": ["youtube"],
        "content_type": "video",
        "idea": null
      }}
    }},
    ...
  }}

4. ANALYTICS PLATFORM EXTRACTION:
   - If the user says "social media" or "social_media" but DOES NOT mention a specific app (like instagram, facebook), set source: "social_media" and platform: null.
   - If the user says "blog" or "website" but DOES NOT mention a platform (like wordpress, shopify), set source: "blog" and platform: null.
   - ONLY extract platform if a specific name is mentioned (instagram, facebook, youtube, linkedin, twitter, pinterest, wordpress, shopify, wix, html).
   - DO NOT hallucinate a default platform (like "instagram") if the user just says "social media".

EXAMPLES OF ANALYTICS EXTRACTION:
- User: "i want analytics"
  Output: {{"intent": "analytics", "analytics": {{"source": null, "platform": null}}}}
- User: "social media" (as a response to source question)
  Output: {{"intent": "analytics", "analytics": {{"source": "social_media", "platform": null}}}}
- User: "blog" (as a response to source question)
  Output: {{"intent": "analytics", "analytics": {{"source": "blog", "platform": null}}}}
- User: "instagram analytics"
  Output: {{"intent": "analytics", "analytics": {{"source": "social_media", "platform": ["instagram"]}}}}
- User: "blog speed check"
  Output: {{"intent": "analytics", "analytics": {{"source": "blog", "platform": null, "insight_type": "insight"}}}}

IMPORTANT RULES FOR CONTENT GENERATION:
- If intent is "content_generation", the "content" object MUST include a "type" field
- The "type" field MUST be one of: "social_media", "blog", "email", "whatsapp", "ads"
- If the user says "post", "reel", "video", "story", "carousel" → infer type as "social_media"
- If the user says "blog" or "article", infer type as "blog"
- If the user says "email", infer type as "email"
- If the user says "whatsapp" or "message", infer type as "whatsapp"
- If the user says "ad" or "advertisement", infer type as "ads"
- ALWAYS extract platform and content_type when mentioned in the query
- NEVER create a "content" object without a "type" field
- For social_media type, ALWAYS create the "social_media" nested object with extracted fields

EMAIL-SPECIFIC RULES:
- For email type, use these EXACT field names in the "email" nested object:
  - "email_address" (NOT "recipient", "to", "email", etc.) - the recipient's email address
  - "content" (NOT "body", "message", "text", "subject", etc.) - what the email should be about
  - "attachments" (array of strings) - file paths or URLs for email attachments (extract if user mentions "attach", "attachment", "file", "document", etc.)
  - "task" (one of: "send", "save", "schedule") - what to do with the email
- If user mentions an email address, extract it as "email_address" in the "email" object
- If user describes what the email should be about (e.g., "product launch", "meeting invitation"), extract it as "content" in the "email" object
- If user mentions attachments (e.g., "attach the PDF", "with the document"), extract file references as "attachments" array
- Example: User says "send email to john@example.com about product launch"
  Output: {{"intent": "content_generation", "content": {{"type": "email", "email": {{"email_address": "john@example.com", "content": "product launch", "task": "send"}}}}}}
- Example: User says "email to jane@example.com with the invoice attached"
  Output: {{"intent": "content_generation", "content": {{"type": "email", "email": {{"email_address": "jane@example.com", "attachments": ["invoice"], "task": "send"}}}}}}

WHATSAPP-SPECIFIC RULES:
- For whatsapp type, use these EXACT field names in the "whatsapp" nested object:
  - "phone_number" (NOT "phone", "number", etc.) - recipient's phone number with country code
  - "text" (NOT "message", "content", "body", etc.) - the message text
  - "attachment" (string) - file path or URL for WhatsApp attachment (extract if user mentions "attach", "attachment", "file", "image", "video", etc.)
  - "task" (one of: "send", "schedule", "save") - what to do with the message
- If user mentions a phone number, extract it as "phone_number" in the "whatsapp" object
- If user mentions attachments (e.g., "send image", "with a video"), extract file reference as "attachment" string
- Example: User says "send WhatsApp to +919876543210 with the image"
  Output: {{"intent": "content_generation", "content": {{"type": "whatsapp", "whatsapp": {{"phone_number": "+919876543210", "attachment": "image", "task": "send"}}}}}}

BLOG-SPECIFIC RULES:
- For blog type, use these EXACT field names in the "blog" nested object:
  - "topic" - what the blog post should be about (e.g., "marketing tips", "product review")
  - "platform" (one of: "wordpress", "shopify", "wix", "html") - where to publish the blog
  - "length" (one of: "short", "medium", "long") - how long the blog post should be
  - "media" (one of: "generate", "upload") - whether to generate new media or upload existing media
  - "media_file" (string) - file path or URL if user mentions uploading a specific file
  - "task" (one of: "draft", "schedule", "save") - what to do with the blog post
- If user mentions a blog topic, extract it as "topic" in the "blog" object
- If user mentions a platform (wordpress, shopify, wix, html), extract it as "platform" in the "blog" object
- If user mentions length (short, medium, long), extract it as "length" in the "blog" object
- If user says "upload image", "use this photo", "attach file" → set media: "upload" and extract file reference as "media_file"
- If user says "generate image", "create visual", "make graphic" → set media: "generate"
- Example: User says "create a blog post about digital marketing for wordpress"
  Output: {{"intent": "content_generation", "content": {{"type": "blog", "blog": {{"topic": "digital marketing", "platform": "wordpress", "length": null, "task": null}}}}}}
- Example: User says "blog post with this image: /path/to/image.jpg"
  Output: {{"intent": "content_generation", "content": {{"type": "blog", "blog": {{"media": "upload", "media_file": "/path/to/image.jpg"}}}}}}
- When merging with existing partial payload, preserve all non-null blog fields and only update with new information

SOCIAL MEDIA MEDIA RULES:
- For social_media type, also extract media information if mentioned:
  - "media" (one of: "upload", "generate") - whether to upload existing media or generate new media
  - "media_file" (string) - file path or URL if user mentions uploading a specific file
- If user says "upload image", "use this photo", "attach file", OR JUST "upload" → set media: "upload" and extract file reference as "media_file" if provided
- If user says "generate image", "create visual", "make graphic", OR JUST "generate" → set media: "generate"
- CRITICAL: If the user responds with ONLY "generate" or ONLY "upload" (without other context), this is a direct answer to the media question - extract it as media: "generate" or media: "upload" respectively

SOCIAL MEDIA TASK AND DATE RULES:
- For social_media type, also extract task and date information if mentioned:
  - "task" (one of: "draft", "schedule", "edit", "delete") - what to do with the post after generation
  - "date" (ISO datetime string) - when to schedule the post (only needed if task is "schedule")
- If user says "draft", "save as draft", "save it" → set task: "draft"
- If user says "schedule", "schedule it", "schedule for later" → set task: "schedule"
- If user says "edit", "modify", "change" → set task: "edit"
- If user says "delete", "remove", "remove it" → set task: "delete"
- If user mentions a date/time for scheduling (e.g., "December 25, 2024 at 2:00 PM", "tomorrow at 10am"), extract it as "date" in ISO format
- CRITICAL: If the user responds with ONLY "draft", "schedule", "edit", or "delete" (without other context), this is a direct answer to the task question - extract it accordingly
- Example: User says "create an instagram post with this image: /path/to/image.jpg"
  Output: {{"intent": "content_generation", "content": {{"type": "social_media", "social_media": {{"platform": ["instagram"], "content_type": "post", "media": "upload", "media_file": "/path/to/image.jpg"}}}}}}
- Example: User says "generate" (as a response to media question)
  Output: {{"intent": "content_generation", "content": {{"type": "social_media", "social_media": {{"media": "generate"}}}}}}
- Example: User says "schedule it for tomorrow at 10am"
  Output: {{"intent": "content_generation", "content": {{"type": "social_media", "social_media": {{"task": "schedule", "date": "2024-12-26T10:00:00Z"}}}}}}
- Example: User says "edit" (as a response to task question)
  Output: {{"intent": "content_generation", "content": {{"type": "social_media", "social_media": {{"task": "edit"}}}}}}
- Example: User says "delete" (as a response to task question)
  Output: {{"intent": "content_generation", "content": {{"type": "social_media", "social_media": {{"task": "delete"}}}}}}
- When merging with existing partial payload, preserve all non-null social_media fields and only update with new information

FAQ INTENT DETECTION:
- Classify as "faq" when the user asks informational questions about:
  • Pricing, plans, costs, subscriptions
  • How Emily works, features, capabilities
  • Onboarding, getting started, usage instructions
  • Support, help, documentation
  • Limits, restrictions, what's included
- Examples of FAQ queries:
  - "what is the basic plan price?"
  - "how does emily help my business?"
  - "what can emily do?"
  - "how do I get started?"
  - "what features are included?"
  - "what are the pricing plans?"
  - "how much does it cost?"
- If the query is informational and NOT a task (not asking to create, update, or manage something), classify as "faq"
- If the query is conversational but not informational, classify as "general_talks"
- For FAQ intent, set faq: {{"query": "<user's question>"}}

General Rules:
- EXACT intent labels must be used: content_generation, analytics, leads_management, posting_manager, general_talks, faq
- EXACT enum values must be used (e.g., "facebook", "instagram" for platforms; "post", "reel", "video", "story", "carousel" for content_type)
- Never output fields that are not in the Pydantic schema
- Never assume unknown fields
- If a query is conversational or does not match any domain, classify it under "general_talks"
- You must always return every top-level key, even if null
- If merging with existing data, preserve all non-null existing values and only add/update with new information from the current query
- BE THOROUGH: Extract every piece of information the user mentions - don't leave fields as null if they're clearly stated in the query

{partial_context}
{history_context}

User query: "{query}"

Return ONLY valid JSON matching the IntentPayload structure. No explanations, no markdown, no comments."""

        try:
            # Use structured output to get JSON
            response = self.llm.invoke([HumanMessage(content=classification_prompt)])
            
            # Log the raw LLM response
            logger.info(f"LLM raw response: {response.content}")
            
            # Parse the JSON response
            try:
                content = response.content.strip()
                
                # Remove markdown code blocks if present
                if content.startswith("```json"):
                    content = content[7:]  # Remove ```json
                elif content.startswith("```"):
                    content = content[3:]  # Remove ```
                
                if content.endswith("```"):
                    content = content[:-3]  # Remove closing ```
                
                content = content.strip()
                
                # Log the cleaned content before parsing
                logger.debug(f"LLM cleaned response: {content}")
                
                payload_dict = json.loads(content)
                
                # Merge with existing partial payload if it exists
                if partial_payload:
                    payload_dict = self._merge_payloads(partial_payload, payload_dict)
                    logger.info(f"Merged payload dict: {json.dumps(payload_dict, indent=2)}")
                
                # Log the parsed payload
                logger.info(f"Parsed payload dict: {json.dumps(payload_dict, indent=2)}")
                
                # Normalize and fix payload structure (but don't validate yet)
                payload_dict = self._normalize_payload(payload_dict)
                logger.info(f"Payload dict after normalization: {json.dumps(payload_dict, indent=2)}")
                
                # IMPORTANT: Ensure content is None if it's invalid (has type=None or missing type)
                # This prevents validation errors when creating minimal IntentPayload
                if payload_dict.get("content") and isinstance(payload_dict["content"], dict):
                    content_obj = payload_dict["content"]
                    content_type = content_obj.get("type")
                    if not content_type or content_type is None or content_type == "null" or content_type == "":
                        logger.warning(f"Content object has invalid type (type={content_type}), removing it from payload")
                        payload_dict["content"] = None
                
                # Store the merged payload as partial_payload for next iteration
                state["partial_payload"] = payload_dict
                
                # Create a minimal IntentPayload with just the intent for routing
                # We'll validate the full payload later when all required fields are collected
                # CRITICAL FIX: If there's an existing intent in partial_payload, preserve it
                # This prevents the LLM from re-classifying single-word answers like "instagram" as "general_talks"
                existing_intent = partial_payload.get("intent") if partial_payload else None
                new_intent = payload_dict.get("intent", "general_talks")
                
                # Preserve existing intent if:
                # 1. We have a partial_payload from a previous turn
                # 2. The existing intent is not "general_talks" (i.e., it's a real intent like "analytics")
                # 3. The new intent from LLM is "general_talks" (i.e., LLM couldn't classify the clarification response)
                if existing_intent and existing_intent != "general_talks" and new_intent == "general_talks":
                    intent_value = existing_intent
                    logger.info(f"🔒 PRESERVED existing intent '{existing_intent}' - user is providing clarification, not starting new conversation")
                else:
                    intent_value = new_intent
                
                # Create minimal payload for routing - only validate the intent
                # IMPORTANT: Set all payload fields to None to avoid validation
                # We only need the intent for routing
                try:
                    # Create IntentPayload with minimal data for routing
                    # Always set content to None to avoid validation
                    minimal_payload = {
                        "intent": intent_value,
                        "content": None,  # Always None - we'll validate later
                        "analytics": None,
                        "leads": None,
                        "posting": None,
                        "general": None,
                        "faq": None
                    }
                    intent_payload = IntentPayload(**minimal_payload)
                    state["intent_payload"] = intent_payload
                    logger.info(f"Intent classified as: {intent_value} (payload stored in partial_payload, validation deferred)")
                except Exception as e:
                    logger.error(f"Failed to create minimal IntentPayload: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    # Fallback to general_talks
                    state["intent_payload"] = IntentPayload(
                        intent="general_talks",
                        general=GeneralTalkPayload(message=query)
                    )
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from LLM response: {e}")
                logger.error(f"Response content: {response.content}")
                # Fallback to general_talks
                state["intent_payload"] = IntentPayload(
                    intent="general_talks",
                    general=GeneralTalkPayload(message=query)
                )
            except Exception as e:
                logger.error(f"Error processing payload: {e}")
                logger.error(f"Payload dict: {json.dumps(payload_dict, indent=2) if 'payload_dict' in locals() else 'N/A'}")
                
                # Try to fix common issues and store as partial payload
                if 'payload_dict' in locals():
                    try:
                        # Try normalization again
                        fixed_payload = self._normalize_payload(payload_dict.copy())
                        state["partial_payload"] = fixed_payload
                        
                        # Create minimal IntentPayload for routing
                        intent_value = fixed_payload.get("intent", "general_talks")
                        minimal_payload = {
                            "intent": intent_value,
                            "content": None,
                            "analytics": None,
                            "leads": None,
                            "posting": None,
                            "general": None,
                            "faq": None
                        }
                        intent_payload = IntentPayload(**minimal_payload)
                        state["intent_payload"] = intent_payload
                        logger.info(f"Fixed payload structure, intent: {intent_value} (validation deferred)")
                    except Exception as retry_error:
                        logger.error(f"Retry after normalization also failed: {retry_error}")
                        # Fallback to general_talks
                        state["intent_payload"] = IntentPayload(
                            intent="general_talks",
                            general=GeneralTalkPayload(message=query)
                        )
                else:
                    # Fallback to general_talks
                    state["intent_payload"] = IntentPayload(
                        intent="general_talks",
                        general=GeneralTalkPayload(message=query)
                    )
                
        except Exception as e:
            logger.error(f"Error in classify_intent: {e}")
            # Fallback to general_talks
            state["intent_payload"] = IntentPayload(
                intent="general_talks",
                general=GeneralTalkPayload(message=query)
            )
        
        return state
    
    def handle_content_generation(self, state: IntentBasedChatbotState) -> IntentBasedChatbotState:
        """Handle content generation intent"""
        try:
            from agents.tools.Leo_Content_Generation import execute_content_generation
            
            # Get the partial payload dictionary (not validated yet)
            partial_payload = state.get("partial_payload", {})
            content_dict = partial_payload.get("content")
            
            # Quick check: if user just said "generate" or "upload" and we're waiting for media, set it directly
            # Also check for "draft" or "schedule" for task field
            user_query = state.get("current_query", "").strip()
            user_query_lower = user_query.lower()
            if content_dict and content_dict.get("type") == "social_media":
                social_media_dict = content_dict.get("social_media", {})
                
                # Check if user sent "upload {url}" format (from file upload)
                if user_query_lower.startswith("upload ") and len(user_query) > 7:
                    # Extract URL from "upload {url}"
                    file_url = user_query[7:].strip()  # Remove "upload " prefix
                    if file_url and (file_url.startswith("http://") or file_url.startswith("https://")):
                        if "social_media" not in content_dict:
                            content_dict["social_media"] = {}
                        content_dict["social_media"]["media"] = "upload"
                        content_dict["social_media"]["media_file"] = file_url
                        partial_payload["content"] = content_dict
                        state["partial_payload"] = partial_payload
                        logger.info(f"Directly set media to 'upload' with file URL: {file_url}")
                elif not social_media_dict.get("media"):
                    if user_query_lower == "generate":
                        if "social_media" not in content_dict:
                            content_dict["social_media"] = {}
                        content_dict["social_media"]["media"] = "generate"
                        partial_payload["content"] = content_dict
                        state["partial_payload"] = partial_payload
                        logger.info("Directly set media to 'generate' from user query")
                    elif user_query_lower == "upload":
                        if "social_media" not in content_dict:
                            content_dict["social_media"] = {}
                        content_dict["social_media"]["media"] = "upload"
                        partial_payload["content"] = content_dict
                        state["partial_payload"] = partial_payload
                        logger.info("Directly set media to 'upload' from user query")
            
            # Re-get content_dict after potential update
            content_dict = partial_payload.get("content")
            
            if not content_dict:
                state["response"] = "I'd love to help you create some content! What are you thinking - are you looking to create something for social media, write a blog post, send an email, create a WhatsApp message, or maybe work on some ads?"
                state["needs_clarification"] = True
                return state
            
            # Check if type is set
            content_type = content_dict.get("type")
            if not content_type:
                state["response"] = "Sounds good! Just to make sure I create exactly what you need - are you thinking social media content, a blog post, an email, a WhatsApp message, or maybe some ads?"
                state["needs_clarification"] = True
                return state
            
            # Check for missing required fields based on content type
            # Handle social_media type
            if content_type == "social_media":
                social_media_dict = content_dict.get("social_media", {})
                
                # Check for missing fields using dictionary
                missing_fields = []
                if not social_media_dict.get("platform"):
                    missing_fields.append({
                        "field": "platform",
                        "question": "Great! Which social media platform are you thinking of? Are you looking to post on Facebook, Instagram, YouTube, LinkedIn, Twitter, or Pinterest?",
                        "options": ["facebook", "instagram", "youtube", "linkedin", "twitter", "pinterest"],
                        "priority": 1
                    })
                
                if not social_media_dict.get("content_type"):
                    missing_fields.append({
                        "field": "content_type",
                        "question": "What kind of content are you planning? Are you thinking of a regular post, a reel, a video, a story, or maybe a carousel?",
                        "options": ["post", "reel", "video", "story", "carousel"],
                        "priority": 2
                    })
                
                if not social_media_dict.get("idea"):
                    missing_fields.append({
                        "field": "idea",
                        "question": "What would you like to share in this social media post?",
                        "options": None,
                        "priority": 3
                    })
                
                # Check for media field (lower priority - ask after core fields are filled)
                if not social_media_dict.get("media"):
                    missing_fields.append({
                        "field": "media",
                        "question": "Great! For the visuals, would you like me to generate an image for this post, or do you have a file you'd like to upload?",
                        "options": ["generate", "upload"],
                        "priority": 4
                    })
                # If media is "upload" but media_file is missing, ask for the file
                elif social_media_dict.get("media") == "upload" and not social_media_dict.get("media_file"):
                    missing_fields.append({
                        "field": "media_file",
                        "question": "Perfect! You mentioned uploading a file. Could you share the file path or URL for the image/video you'd like to use?",
                        "options": None,
                        "priority": 4
                    })
                
                # Sort by priority
                missing_fields.sort(key=lambda x: x.get("priority", 999))
                
                logger.info(f"Missing fields for social_media: {missing_fields}")
                if missing_fields:
                    question = self._generate_clarifying_question(missing_fields, "social_media")
                    state["response"] = question
                    state["needs_clarification"] = True
                    # Store options for frontend rendering
                    field_info = missing_fields[0]
                    state["options"] = field_info.get("options")
                    logger.info(f"Generated clarifying question: {question}")
                    logger.info(f"Options for frontend: {state['options']}")
                    return state
            
            # Handle email type
            elif content_type == "email":
                email_dict = content_dict.get("email", {})
                
                # Check for missing fields using dictionary
                # Also check for "recipient" as an alias for "email_address"
                missing_fields = []
                email_address = email_dict.get("email_address") or email_dict.get("recipient")
                if not email_address:
                    missing_fields.append({
                        "field": "email_address",
                        "question": "Sure! Who should I send this email to? What's their email address?",
                        "options": None,
                        "priority": 1
                    })
                
                # Check for content field, also check common aliases
                email_content = email_dict.get("content") or email_dict.get("body") or email_dict.get("message") or email_dict.get("text") or email_dict.get("subject") or email_dict.get("topic") or email_dict.get("about")
                if not email_content:
                    missing_fields.append({
                        "field": "content",
                        "question": "What's this email going to be about? Are you announcing a product, inviting them to a meeting, sending a newsletter, or something else?",
                        "options": None,
                        "priority": 2
                    })
                
                if not email_dict.get("task"):
                    missing_fields.append({
                        "field": "task",
                        "question": "Got it! What would you like me to do with this email? Should I send it right away, save it as a draft, or schedule it for later?",
                        "options": ["send", "save", "schedule"],
                        "priority": 3
                    })
                
                # Sort by priority
                missing_fields.sort(key=lambda x: x.get("priority", 999))
                
                logger.info(f"Missing fields for email: {missing_fields}")
                if missing_fields:
                    question = self._generate_clarifying_question(missing_fields, "email")
                    state["response"] = question
                    state["needs_clarification"] = True
                    # Store options for frontend rendering
                    field_info = missing_fields[0]
                    state["options"] = field_info.get("options")
                    logger.info(f"Generated clarifying question: {question}")
                    logger.info(f"Options for frontend: {state['options']}")
                    return state
            
            # Handle blog type
            elif content_type == "blog":
                blog_dict = content_dict.get("blog", {})
                
                # Check for missing fields using dictionary
                missing_fields = []
                if not blog_dict.get("topic"):
                    missing_fields.append({
                        "field": "topic",
                        "question": "Awesome! What topic are you thinking of writing about? For example, are you sharing marketing tips, doing a product review, covering industry news, or something else?",
                        "options": None,
                        "priority": 1
                    })
                
                if not blog_dict.get("platform"):
                    missing_fields.append({
                        "field": "platform",
                        "question": "Perfect! Where are you planning to publish this? Are you using WordPress, Shopify, Wix, or maybe a custom HTML site?",
                        "options": ["wordpress", "shopify", "wix", "html"],
                        "priority": 2
                    })
                
                if not blog_dict.get("length"):
                    missing_fields.append({
                        "field": "length",
                        "question": "How long are you thinking? Are you going for a quick short read, a medium-length article, or a longer deep dive?",
                        "options": ["short", "medium", "long"],
                        "priority": 3
                    })
                
                if not blog_dict.get("task"):
                    missing_fields.append({
                        "field": "task",
                        "question": "Great! What would you like me to do with this blog post? Should I create it as a draft for you to review, schedule it to publish later, or just save it for now?",
                        "options": ["draft", "schedule", "save"],
                        "priority": 4
                    })
                
                # Sort by priority
                missing_fields.sort(key=lambda x: x.get("priority", 999))
                
                logger.info(f"Missing fields for blog: {missing_fields}")
                if missing_fields:
                    question = self._generate_clarifying_question(missing_fields, "blog")
                    state["response"] = question
                    state["needs_clarification"] = True
                    # Store options for frontend rendering
                    field_info = missing_fields[0]
                    state["options"] = field_info.get("options")
                    logger.info(f"Generated clarifying question: {question}")
                    logger.info(f"Options for frontend: {state['options']}")
                    return state
            
            # If all required fields are present, validate and execute
            # Now we validate the complete payload
            try:
                # Normalize one more time to ensure structure is correct
                normalized_payload = self._normalize_payload(partial_payload.copy())
                logger.info(f"Normalized payload before validation: {json.dumps(normalized_payload, indent=2, default=str)}")
                
                intent_payload = IntentPayload(**normalized_payload)
                payload = intent_payload.content
                
                if not payload:
                    logger.error("Payload is None after validation")
                    state["response"] = "I encountered an error: Content payload is missing. Please try again."
                    state["needs_clarification"] = True
                    return state
                
                logger.info("All required fields present, validating and executing payload")
                result = execute_content_generation(payload, state["user_id"])
            except Exception as validation_error:
                import traceback
                error_trace = traceback.format_exc()
                logger.error(f"Validation error when all fields should be present: {validation_error}")
                logger.error(f"Error traceback: {error_trace}")
                logger.error(f"Partial payload that failed: {json.dumps(partial_payload, indent=2, default=str)}")
                state["response"] = f"I encountered an error validating your request: {str(validation_error)}. Please try again or provide the information in a different way."
                state["needs_clarification"] = True  # Keep asking for clarification
                return state
            
            if result.get("clarifying_question"):
                state["response"] = result["clarifying_question"]
                state["needs_clarification"] = True
            elif result.get("success") and result.get("data"):
                # Store the structured content data in state for frontend
                data = result["data"]
                
                # Ensure images is always a list
                if "images" in data:
                    if not isinstance(data["images"], list):
                        data["images"] = [data["images"]] if data["images"] else []
                    # Filter out any None or empty values
                    data["images"] = [img for img in data["images"] if img and isinstance(img, str) and len(img) > 0]
                
                logger.info(f"📥 Received content generation result from Leo:")
                logger.info(f"  - Data keys: {list(data.keys())}")
                logger.info(f"  - Images: {data.get('images')}")
                logger.info(f"  - Images type: {type(data.get('images'))}")
                logger.info(f"  - Images length: {len(data.get('images', []))}")
                if data.get('images'):
                    for idx, img_url in enumerate(data['images']):
                        logger.info(f"    Image {idx + 1}: {img_url}")
                
                # Get saved_content_id and updated payload from the result
                saved_content_id = data.get("saved_content_id")
                updated_payload = result.get("payload")  # Full payload with content field set
                
                # Store in state
                state["content_data"] = data
                state["response"] = self._format_content_response(data)
                
                # Update partial payload with the full payload returned from Leo (includes content field)
                partial_payload = state.get("partial_payload", {})
                if updated_payload:
                    # Merge the updated payload from Leo into partial_payload
                    # The updated_payload should have the content field set to saved_content_id
                    if "content" not in partial_payload:
                        partial_payload["content"] = {}
                    if "social_media" not in partial_payload.get("content", {}):
                        partial_payload["content"]["social_media"] = {}
                    
                    # Merge the updated payload fields into partial_payload
                    for key, value in updated_payload.items():
                        if value is not None:  # Only update with non-null values
                            partial_payload["content"]["social_media"][key] = value
                    
                    logger.info(f"📝 Merged updated payload from Leo into partial_payload")
                    logger.info(f"   Payload content field: {partial_payload.get('content', {}).get('social_media', {}).get('content')}")
                elif saved_content_id:
                    # Fallback: if payload not returned, manually set content field
                    if "content" not in partial_payload:
                        partial_payload["content"] = {}
                    if "social_media" not in partial_payload.get("content", {}):
                        partial_payload["content"]["social_media"] = {}
                    partial_payload["content"]["social_media"]["content"] = saved_content_id
                    logger.info(f"📝 Fallback: Stored saved_content_id in payload.content.social_media.content: {saved_content_id}")
                
                # Content generation complete - task/date will be handled by posting manager
                # All fields complete, clear partial payload
                state["needs_clarification"] = False
                state["partial_payload"] = None
                
                logger.info(f"✅ Content data stored in state with {len(data.get('images', []))} image(s)")
            elif result.get("error"):
                state["response"] = f"I encountered an error: {result['error']}"
                state["needs_clarification"] = False
            else:
                state["response"] = "I've processed your content generation request."
                state["needs_clarification"] = False
                state["partial_payload"] = None
                
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error in handle_content_generation: {e}")
            logger.error(f"Error traceback: {error_trace}")
            state["response"] = f"I encountered an error while processing your content generation request: {str(e)}. Please try again."
            state["needs_clarification"] = True  # Keep asking for clarification instead of giving up
        
        return state
    
    def handle_analytics(self, state: IntentBasedChatbotState) -> IntentBasedChatbotState:
        """
        Handle analytics intent - ORCHESTRATOR ONLY.
        
        Responsibilities:
        1. Classify Detail: Detect analytics vs insight, account vs post level.
        2. Normalize: Merge user input into a canonical state.
        3. Validate: Ensure all required fields for AnalyticsState are present.
        4. Route: Construct AnalyticsState and call Orion (Engine).
        5. Present: Format Orion's structured output into a response.
        """
        try:
            from agents.tools.Orion_Analytics_query import execute_analytics_query
            
            # Get the partial payload
            partial_payload = state.get("partial_payload", {})
            user_query = state.get("current_query", "").strip()
            needs_clarification = state.get("needs_clarification", False)
            
            # Ensure analytics dict exists
            if "analytics" not in partial_payload:
                partial_payload["analytics"] = {}
            
            analytics_dict = partial_payload.get("analytics", {})
            
            # --- PHASE 1: DETECTION & NORMALIZATION ---
            
            # 1. Detect Intent (Analytics vs Insight)
            if user_query and not analytics_dict.get("insight_type"):
                insight_type = self._detect_analytics_vs_insight(user_query)
                if insight_type:
                    analytics_dict["insight_type"] = insight_type
                    logger.info(f"Auto-detected insight_type={insight_type}")

            # 2. Detect Post-Level / Comparison
            # (Overrides analytics_level if detected)
            # CRITICAL: Check BOTH current query AND previous conversation for post-level keywords
            is_post_comparison_detected = False
            num_posts_detected = None
            
            # Check current query
            if user_query:
                is_post_comparison_detected, num_posts_detected = self._detect_post_comparison_query(user_query)
                if is_post_comparison_detected:
                    analytics_dict["analytics_level"] = "post"
                    analytics_dict["top_n"] = num_posts_detected or 5
                    analytics_dict["num_posts"] = num_posts_detected or 5  # Also set num_posts for post-comparison handler
                    analytics_dict["sort_order"] = "desc" # Default to top posts
                    logger.info(f"🎯 Post-comparison detected in current query: level=post, top_n={num_posts_detected}")
            
            # CRITICAL: Also check conversation history if not detected in current query
            # This handles cases where user says "insight of my post" in first message, then "likes" in second
            if not is_post_comparison_detected:
                conversation_history = state.get("conversation_history", [])
                if conversation_history:
                    # Check last few messages for post-level keywords
                    recent_messages = conversation_history[-3:] if len(conversation_history) >= 3 else conversation_history
                    for msg in recent_messages:
                        msg_text = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                        if msg_text:
                            is_post, num_posts = self._detect_post_comparison_query(msg_text)
                            if is_post:
                                is_post_comparison_detected = True
                                num_posts_detected = num_posts
                                analytics_dict["analytics_level"] = "post"
                                analytics_dict["top_n"] = num_posts_detected or 5
                                analytics_dict["num_posts"] = num_posts_detected or 5
                                analytics_dict["sort_order"] = "desc"
                                logger.info(f"🎯 Post-comparison detected in conversation history: level=post, top_n={num_posts_detected}")
                                break
            
            # If still not detected and analytics_level not set, use regular detection
            if not is_post_comparison_detected and not analytics_dict.get("analytics_level"):
                # Regular level detection
                level, top_n, sort = self._detect_analytics_level(user_query)
                analytics_dict["analytics_level"] = level
                if top_n: analytics_dict["top_n"] = top_n
                if sort: analytics_dict["sort_order"] = sort

            # 3. Direct Answer & Entity Extraction (Platforms, Sources, Metrics)
            # CRITICAL: When needs_clarification is True, prioritize extracting answers to clarification questions
            if user_query:
                # Extract entities (platforms, metrics, etc.) from user query
                # This handles cases like: User says "likes" when asked "Which metrics?"
                self._extract_analytics_entities(user_query, analytics_dict)
                
                # If we're in clarification mode and user provided a short answer,
                # it's likely an answer to the clarification question
                if needs_clarification and len(user_query.split()) <= 3:
                    logger.info(f"🔍 Short answer detected during clarification: '{user_query}' - treating as clarification answer")
            
            # 4. Normalize & Merge
            # CRITICAL: Preserve analytics_level before normalization (detection might have set it)
            preserved_analytics_level = analytics_dict.get("analytics_level")
            preserved_num_posts = analytics_dict.get("num_posts")
            
            normalized_analytics = self._normalize_analytics_payload(analytics_dict, user_query)
            
            # Update partial payload with normalized values
            # (Logic matches original merge strategy: valid new values override old)
            for key, value in normalized_analytics.items():
                if value is not None:
                     if isinstance(value, list) and len(value) == 0: continue
                     analytics_dict[key] = value
            
            # CRITICAL: Restore preserved analytics_level if it was set by detection
            # Normalization should NOT override detection results
            if preserved_analytics_level:
                analytics_dict["analytics_level"] = preserved_analytics_level
                logger.info(f"🔒 Preserved analytics_level from detection: {preserved_analytics_level}")
            if preserved_num_posts:
                analytics_dict["num_posts"] = preserved_num_posts
            
            partial_payload["analytics"] = analytics_dict
            
            # --- PHASE 1.5: INSIGHT ONLY GUARD (BLOG) ---
            # BLOG = PERFORMANCE & SEO HEALTH INSIGHT ONLY
            # No analytics, no trends, no historical storage for blog.
            if analytics_dict.get("source") == "blog":
                logger.info("🛡️ INSIGHT_ONLY_GUARD: Forcing blog to insight mode")
                analytics_dict["insight_type"] = "insight"
                analytics_dict["date_range"] = None  # Historical ranges not supported
                analytics_dict["analytics_level"] = "account"  # Always snapshot level
                
                # Default metrics for blog insight if none provided
                if not analytics_dict.get("blog_metrics"):
                     analytics_dict["blog_metrics"] = [
                         "performance_score", "lcp", "cls", "inp", 
                         "seo_score", "opportunities"
                     ]
                
                # Auto-assign platform for blog if missing (PSI works on URL anyway)
                if not analytics_dict.get("platform"):
                    analytics_dict["platform"] = ["wordpress"]
                    logger.info("🛡️ INSIGHT_ONLY_GUARD: Auto-assigned platform='wordpress' for blog")
            
            # --- PHASE 1.6: POST-COMPARISON SHORT-CIRCUIT ---
            # CRITICAL: If post-comparison query detected, route to post-comparison handler
            # This bypasses normal analytics flow and uses post-comparison logic
            if is_post_comparison_detected and analytics_dict.get("analytics_level") == "post":
                logger.info(f"🔄 Routing to post-comparison handler (detected: {num_posts_detected} posts)")
                return self._handle_post_comparison(state, analytics_dict, partial_payload)
            
            # --- PHASE 2: MISSING FIELD CHECK ---
            
            user_id = state.get("user_id")
            missing_fields = self._get_missing_fields_for_analytics(analytics_dict, user_id)
            
            state["_previous_missing_fields"] = missing_fields
            
            if missing_fields:
                state["needs_clarification"] = True
                question = self._generate_clarifying_question(missing_fields, "analytics")
                state["response"] = question
                state["options"] = missing_fields[0].get("options")
                state["partial_payload"] = partial_payload
                return state
            
            # --- PHASE 3: EXECUTION (ORION) ---
            
            # All required fields present. Construct AnalyticsState.
            # Defaults for optional fields are handled here or passed as None.
            
            try:
                # Ensure lists are lists
                platforms = analytics_dict.get("platform", [])
                if not isinstance(platforms, list): platforms = [platforms] if platforms else []
                
                metrics = analytics_dict.get("metrics", [])
                if not isinstance(metrics, list): metrics = [metrics] if metrics else []
                
                # Merge blog metrics if source is blog
                if analytics_dict.get("source") == "blog":
                    blog_metrics = analytics_dict.get("blog_metrics", [])
                    if not isinstance(blog_metrics, list): blog_metrics = [blog_metrics] if blog_metrics else []
                    metrics = list(set(metrics + blog_metrics))
                
                # ===================================================================
                # DETERMINISTIC POST SELECTOR INFERENCE (STRICT ORDER)
                # ===================================================================
                user_query = state.get("current_query", "").lower()
                post_selector = None
                post_id = None
                recent_n = None
                
                # Post selector inference (DO NOT use LLM guessing here)
                if "last post" in user_query or "latest post" in user_query or "recent post" in user_query or "my post" in user_query:
                    post_selector = "latest"
                elif "top post" in user_query or "best post" in user_query or "highest performing" in user_query:
                    post_selector = "top"
                elif re.search(r'last\s+(\d+)\s+posts', user_query):
                    match = re.search(r'last\s+(\d+)\s+posts', user_query)
                    post_selector = "recent_n"
                    recent_n = int(match.group(1))
                elif analytics_dict.get("post_id"):
                    post_selector = "specific_id"
                    post_id = analytics_dict.get("post_id")
                
                # ===================================================================
                # ANALYTICS LEVEL LOCKING
                # ===================================================================
                analytics_level = analytics_dict.get("analytics_level", "post")
                if any(word in user_query for word in ["post", "reel", "video"]):
                    analytics_level = "post"
                else:
                    analytics_level = "account"
                
                # ===================================================================
                # INTENT LOCK (Insight vs Analytics) - Use LLM for better accuracy
                # ===================================================================
                intent = analytics_dict.get("insight_type")
                if not intent:
                    # Use LLM classification for better accuracy
                    intent = self._detect_analytics_vs_insight(user_query)
                    if not intent:
                        # Fallback: Default to insight for post-level, analytics for account-level
                        intent = "insight" if analytics_level == "post" else "analytics"
                else:
                    # Use existing intent but validate
                    if intent not in ["analytics", "insight"]:
                        # Re-classify if invalid
                        intent = self._detect_analytics_vs_insight(user_query) or "insight"
                
                # ===================================================================
                # METRICS ARE MANDATORY
                # ===================================================================
                if not metrics or len(metrics) == 0:
                    if analytics_level == "post" and platforms:
                        # Use platform-specific post metrics
                        platform = platforms[0] if isinstance(platforms, list) else platforms
                        if platform in self.PLATFORM_POST_METRICS:
                            metrics = self.PLATFORM_POST_METRICS[platform]
                        else:
                            metrics = ["likes", "comments", "engagement"]
                    else:
                        # Default account metrics
                        metrics = ["reach", "impressions", "engagement"]
                
                # Construct State Object
                analytics_state = AnalyticsState(
                    intent=intent,
                    source=analytics_dict.get("source"),
                    platforms=platforms,
                    metrics=metrics,
                    analytics_level=analytics_level,
                    user_id=user_id,
                    date_range=analytics_dict.get("date_range"),
                    top_n=analytics_dict.get("top_n"),
                    sort_order=analytics_dict.get("sort_order"),
                    post_selector=post_selector,
                    post_id=post_id,
                    recent_n=recent_n
                )
                
                logger.info(f"🚀 Routing to Orion with State: {analytics_state.model_dump_json()}")
                
                # CALL ORION (Pure Engine)
                result = execute_analytics_query(analytics_state)
                
                # --- PHASE 4: PRESENTATION (EMILY) ---
                
                logger.info(f"📊 Orion Result: success={result.get('success')}, has_data={bool(result.get('data'))}")
                
                if result.get("success"):
                    # Format the structured data into a conversational response
                    data = result.get("data", {})
                    formatted_response = self._format_analytics_result(data, analytics_state)
                    state["response"] = formatted_response
                    state["needs_clarification"] = False
                    state["partial_payload"] = None
                    logger.info(f"✅ Analytics response formatted successfully")
                else:
                    # Handle errors / warnings
                    error_msg = result.get("error", "Unknown error in analytics engine.")
                    state["response"] = f"I encountered an issue: {error_msg}"
                    state["needs_clarification"] = False
                    logger.warning(f"⚠️ Analytics execution failed: {error_msg}")
            
            except Exception as e:
                logger.error(f"Failed to execute analytics: {e}", exc_info=True)
                state["response"] = f"I'm having trouble connecting to the analytics engine right now. ({str(e)})"
                state["needs_clarification"] = False

        except Exception as e:
            logger.error(f"Error in handle_analytics: {e}", exc_info=True)
            state["response"] = "Something went wrong processing your request."
            state["needs_clarification"] = False
        
        return state

    def _extract_analytics_entities(self, query: str, analytics_dict: Dict[str, Any]):
        """
        Helper to extract entities like platform, source, metrics from query.
        
        CRITICAL: When user answers clarification questions (e.g., "likes" when asked for metrics),
        this function should extract and add the answer to the appropriate field.
        """
        query_lower = query.lower().strip()
        
        # Source / Insight Type
        if query_lower in ["analytics", "insight"]:
             analytics_dict["insight_type"] = query_lower
        if query_lower in ["social_media", "social", "blog"]:
             analytics_dict["source"] = "social_media" if "social" in query_lower else "blog"
        
        # Auto-detect: "post" or "posts" implies social_media
        if any(word in query_lower for word in [" post", "posts", "post "]):
            if not analytics_dict.get("source"):
                analytics_dict["source"] = "social_media"
                logger.info("🔍 Auto-detected source=social_media from 'post' keyword")
             
        # Platforms
        found_platforms = []
        all_platforms = ["instagram", "facebook", "twitter", "youtube", "linkedin", "pinterest", "wordpress", "shopify"]
        for p in all_platforms:
            if p in query_lower: # Simple check, can be improved with regex
                found_platforms.append(p)
        
        if found_platforms:
            current = analytics_dict.get("platform", [])
            if not isinstance(current, list): current = []
            analytics_dict["platform"] = list(set(current + found_platforms))
            
            # Infer Source
            if any(p in ["wordpress", "shopify"] for p in found_platforms):
                if not analytics_dict.get("source"): analytics_dict["source"] = "blog"
            else:
                 if not analytics_dict.get("source"): analytics_dict["source"] = "social_media"
        
        # CRITICAL: Extract metrics when user answers clarification question
        # This handles cases like: User says "likes" when asked "Which metrics?"
        import re
        
        # List of valid metrics (social media)
        social_metrics = [
            "reach", "impressions", "engagement", "likes", "comments", "shares",
            "saves", "views", "profile_visits", "followers", "growth",
            "average_watch_time", "watch_time", "avg_view_time"
        ]
        
        # List of valid blog metrics
        blog_metrics = [
            "performance_score", "lcp", "cls", "inp",
            "seo_score", "accessibility_score", "best_practices_score", "opportunities"
        ]
        
        # Check if query is a single metric (common answer to clarification)
        # Use word-boundary matching to avoid false positives
        found_metrics = []
        
        source = analytics_dict.get("source", "social_media")
        metrics_list = social_metrics if source == "social_media" else blog_metrics
        
        for metric in metrics_list:
            # Use word-boundary regex to match whole words only
            pattern = r'\b' + re.escape(metric) + r'\b'
            if re.search(pattern, query_lower):
                found_metrics.append(metric)
        
        # Also check for "all metrics" variants
        all_metrics_variants = ["all", "all metrics", "everything", "saare metrics", "saare"]
        if query_lower in all_metrics_variants:
            found_metrics.append("all")
        
        # If metrics found, add them to analytics_dict
        if found_metrics:
            current_metrics = analytics_dict.get("metrics", [])
            if not isinstance(current_metrics, list):
                current_metrics = [current_metrics] if current_metrics else []
            
            # Add new metrics (avoid duplicates)
            for metric in found_metrics:
                if metric not in current_metrics:
                    current_metrics.append(metric)
            
            analytics_dict["metrics"] = current_metrics
            logger.info(f"🔍 Extracted metrics from query: {found_metrics} → {current_metrics}")
        
        # Same for blog_metrics
        if source == "blog":
            found_blog_metrics = []
            for metric in blog_metrics:
                pattern = r'\b' + re.escape(metric) + r'\b'
                if re.search(pattern, query_lower):
                    found_blog_metrics.append(metric)
            
            if found_blog_metrics:
                current_blog_metrics = analytics_dict.get("blog_metrics", [])
                if not isinstance(current_blog_metrics, list):
                    current_blog_metrics = [current_blog_metrics] if current_blog_metrics else []
                
                for metric in found_blog_metrics:
                    if metric not in current_blog_metrics:
                        current_blog_metrics.append(metric)
                
                analytics_dict["blog_metrics"] = current_blog_metrics
                logger.info(f"🔍 Extracted blog_metrics from query: {found_blog_metrics} → {current_blog_metrics}")

    def _format_analytics_result(self, data: Dict[str, Any], state: AnalyticsState) -> str:
        """
        Format the structured data from Orion into a comprehensive analytics response.
        """
        # --- BLOG INSIGHT (Live Snapshot Only) ---
        if state.source == "blog":
             return self._format_blog_insight_response(data, state)

        # --- POST-LEVEL ANALYTICS (Detailed) ---
        if state.analytics_level == "post":
            return self.format_post_level_response(data, state)
        
        # --- ACCOUNT-LEVEL ANALYTICS ---
        else:
            return self.format_account_analytics_response(data, state)

    def _format_blog_insight_response(self, data: Dict[str, Any], state: AnalyticsState) -> str:
        """
        Emily's official blog insight formatter.
        Provides a specialized analysis focusing on reader experience and search visibility.
        """
        try:
            blog_data = data.get("blog", data)
            
            if "_warning" in blog_data:
                return f"NOTE: {blog_data['_warning']}"
            
            scores = blog_data.get("scores", {})
            cwv = blog_data.get("core_web_vitals", {})
            opportunities = blog_data.get("opportunities", [])
            
            response = ["  Blog Performance Snapshot \n"]
            response.append("This is a live snapshot of your blog's current health and performance.")
            response.append("Note: We are tracking live performance; historical trends are not yet available.\n")
            
            # 1. Search Visibility & Technical Health
            response.append("🔍 Search Visibility & SEO Health")
            response.append(f"• SEO Score: {scores.get('seo', 'N/A')}/100")
            response.append(f"• Best Practices: {scores.get('best_practices', 'N/A')}/100")
            response.append(f"• Accessibility: {scores.get('accessibility', 'N/A')}/100")
            response.append("  (High scores here help your blog rank better in search results.)\n")
            
            # 2. Reader Experience (Core Web Vitals)
            response.append("📱 Reader Experience (Speed & Stability)")
            response.append(f"• Overall Performance: {scores.get('performance', 'N/A')}/100")
            
            if cwv:
                lcp = cwv.get("lcp", {})
                cls = cwv.get("cls", {})
                inp = cwv.get("inp", {})
                
                response.append(f"  - Loading Speed (LCP): {lcp.get('displayValue', 'N/A')} ({self._get_cwv_status(lcp.get('score', 0))})")
                response.append("    (Measures how fast readers see your main content.)")
                
                response.append(f"  - Visual Stability (CLS): {cls.get('displayValue', 'N/A')} ({self._get_cwv_status(cls.get('score', 0))})")
                response.append("    (Prevents text from jumping around while reading.)")
                
                if inp:
                    response.append(f"  - Interaction (INP): {inp.get('displayValue', 'N/A')} ({self._get_cwv_status(inp.get('score', 0))})")
                    response.append("    (How quickly the page reacts when a reader clicks.)")
            else:
                response.append("  Core Web Vitals data is currently being calculated...")
            '''
            # 3. Targeted Fixes
            if opportunities:
                response.append("\n🛠️ Priority Fixes for Better Ranking")
                for i, opp in enumerate(opportunities[:3], 1):
                    response.append(f"{i}. {opp.get('title')}")
            '''
            # 4. Strategic Recommendation
            response.append("\n💡 Recommendation")
            perf_score = scores.get('performance', 0)
            seo_score = scores.get('seo', 0)
            
            if perf_score < 60:
                response.append("Your priority should be **Speed**. A slow blog loses readers before they even start reading. Focus on image optimization and reducing loading scripts.")
            elif seo_score < 90:
                response.append("Your technical foundation is good, but your **SEO** can be improved. Focus on on-page elements like meta tags, image alt text, and heading hierarchy.")
            else:
                response.append("Your blog is in excellent health! Focus on consistent content publishing—your technical performance is already optimized for growth.")

            return "\n".join(response)
        except Exception as e:
            logger.error(f"Error formatting blog insight: {e}")
            return "I've fetched your blog data, but I encountered a small hiccup while formatting the report. Rest assured, your blog is live and accessible!"

    def _get_cwv_status(self, score: int) -> str:
        """Helper to status label CWV scores."""
        if score >= 90: return "Good"
        if score >= 50: return "Needs Improvement"
        return "Poor"

    def format_post_level_response(self, data: Dict[str, Any], state: AnalyticsState = None) -> str:
        """
        Emily's official post-level formatter.
        Clean, professional analytics without emojis - focuses on clarity and actionability.
        """
        try:
            response = []
            
            # Handle both Orion return formats (direct or platform-keyed)
            if "posts" in data or "ranked_posts" in data:
                platforms_data = {"result": data}
            else:
                platforms_data = data
            
            for platform, p_data in platforms_data.items():
                if "_warning" in p_data:
                    response.append(f"NOTE: {p_data['_warning']}")
                    continue
                
                posts = p_data.get("ranked_posts") or p_data.get("posts", [])
                if not posts:
                    continue
                
                confidence = p_data.get("confidence", "low").lower()
                num_found = len(posts)
                
                # ---------- HEADER ----------
                title = platform.title() if platform != "result" else state.platforms[0].title() if (state and state.platforms) else "Post"
                response.append(f"{title} Performance Analysis \n")
                
                # Confidence indicator (clear text instead of emoji)
                if confidence == "low":
                    response.append("[Limited Data] Analysis based on very few posts - insights are preliminary.\n")
                elif confidence == "medium":
                    response.append("[Moderate Confidence] Analysis based on recent activity - patterns are emerging.\n")
                else:
                    response.append("[High Confidence] Analysis based on sufficient data - insights are reliable.\n")
                
                # ---------- HEADER WITH POST COUNT ----------
                summary = p_data.get("summary", {})
                num_requested = summary.get("num_posts_requested", num_found)
                
                if num_found < num_requested:
                    response.append(f"Posts Found: {num_found} (requested {num_requested})\n")
                else:
                    response.append(f"Posts Analyzed: {num_found}\n")
                
                # Only show rankings if multiple posts exist
                if num_found < 2:
                    response.append("--- Post Metrics ---\n")
                else:
                    response.append("--- Post-wise Breakdown ---\n")
                # Show metrics for each post (STRICT: Only show requested metrics)
                requested_metrics = state.metrics if state else []
                
                for i, post in enumerate(posts[:num_requested], 1):
                    # Get metrics from post (check both direct keys and nested metrics dict)
                    post_metrics = post.get("metrics", {})
                    if not post_metrics:
                        # If no nested metrics, check direct keys
                        excluded_keys = ["post_id", "caption", "permalink", "timestamp", "label", "score", "ratio_vs_avg", "metrics_used", "latest_date", "metadata"]
                        post_metrics = {k: v for k, v in post.items() if k not in excluded_keys and isinstance(v, (int, float))}
                    
                    # Build metric display (only show requested metrics or all if none specified)
                    metric_info = []
                    if requested_metrics:
                        for metric in requested_metrics:
                            if metric in post_metrics:
                                value = post_metrics[metric]
                                metric_info.append(f"{metric.title()}: {value:,}")
                    else:
                        # Show all available metrics
                        for metric, value in post_metrics.items():
                            if isinstance(value, (int, float)):
                                metric_info.append(f"{metric.title()}: {value:,}")
                    
                    if not metric_info:
                        metric_info = ["No metrics available"]
                    
                    # Format post display
                    if num_found > 1:
                        response.append(f"Post {i}:")
                    
                    for metric_line in metric_info:
                        response.append(f"  {metric_line}")
                    
                    response.append("")  # Empty line between posts
                
                # ---------- NOTES (ONLY if relevant) ----------
                response.append("\nNote:")
                
                if num_found < num_requested:
                    response.append(f"• Only {num_found} post{'s' if num_found != 1 else ''} available (requested {num_requested})")
                
                if num_found < 2:
                    response.append("• This is a live snapshot of your most recent post")
                    response.append("• Comparative analysis requires multiple posts")
                elif num_found < 3:
                    response.append("• Limited data available - insights are preliminary")
                    response.append("• No ranking or averages generated due to insufficient data")
                else:
                    # Only show comparison if we have enough data
                    comparison = p_data.get("comparison")
                    if comparison:
                        ratio = comparison.get("best_vs_worst_ratio")
                        if ratio and ratio > 1:
                            response.append(f"• Top post received {ratio:.1f}x more engagement than lowest post")
                
                response.append("")

            return "\n".join(response).strip() or "Unable to generate analysis - insufficient post data available."
            
        except Exception as e:
            logger.error(f"Error in format_post_level_response: {e}", exc_info=True)
            return "An error occurred while formatting the analytics report. Please try again."

    def format_account_analytics_response(self, data: Dict[str, Any], state: AnalyticsState) -> str:
        """
        Emily's Analytics & Insights Agent - Account-Level formatter.
        
        Transforms raw metrics into founder-friendly, actionable business insights.
        Structure: Snapshot → Metrics → Visibility/Engagement → Interpretation → Actions → Takeaway
        """
        try:
            response = []
            
            for platform, p_data in data.items():
                response.append(f"=== {platform.title()} Performance Analysis ===\n")
                
                if "_warning" in p_data:
                    response.append(f"NOTE: {p_data['_warning']}\n")
                    continue

                # Check for partial data quality
                if p_data.get("_data_quality") == "partial":
                    api_error = p_data.get("_api_error", "API access issue")
                    response.append(f"⚠️ PARTIAL DATA: {api_error}\n")
                    response.append("Some metrics may be estimated from recent posts rather than official analytics.\n")
                
                # CRITICAL: Handle both data structures:
                # 1. Analytics mode: {"metrics": {...}, "comparison": {...}}
                # 2. Insight mode: {"likes": 9, "comments": 5} (flat structure)
                if "metrics" in p_data:
                    # Analytics mode structure
                    metrics = p_data.get("metrics", {})
                    comparison = p_data.get("comparison", {})
                else:
                    # Insight mode structure - metrics are at top level
                    # Extract metrics (exclude internal keys)
                    metrics = {k: v for k, v in p_data.items() 
                              if not k.startswith("_") and k not in ["comparison", "type", "platform"]}
                    comparison = p_data.get("comparison", {})
                
                if not metrics:
                    response.append("No metrics available for this period.\n")
                    continue
                
                # Show post count if metrics were aggregated from posts
                post_count = p_data.get("_post_count")
                if post_count:
                    response.append(f"Based on {post_count} recent posts\n")
                
                # ================================================================
                # 1️⃣ SNAPSHOT SUMMARY (2-3 lines max)
                # ================================================================
                if comparison:
                    snapshot = self._generate_snapshot_summary(metrics, comparison)
                    response.append(f"SNAPSHOT: {snapshot}\n")
                
                # ================================================================
                # 2️⃣ METRICS WITH CONTEXT
                # ================================================================
                response.append("\n--- What The Numbers Show ---\n")
                
                # Categorize metrics by type
                visibility_metrics = {}
                engagement_metrics = {}
                growth_metrics = {}
                
                for metric, val in metrics.items():
                    metric_lower = metric.lower()
                    
                    # Categorization
                    if any(x in metric_lower for x in ['reach', 'impression', 'view']):
                        visibility_metrics[metric] = val
                    elif any(x in metric_lower for x in ['like', 'comment', 'share', 'save', 'engaged']):
                        engagement_metrics[metric] = val
                    elif any(x in metric_lower for x in ['follower', 'subscriber', 'fan']):
                        growth_metrics[metric] = val
                    else:
                        # Default to visibility
                        visibility_metrics[metric] = val
                
                # Display metrics with meaning
                for metric, val in metrics.items():
                    metric_name = metric.replace('_', ' ').title()
                    comp_info = comparison.get(metric, {}) if comparison else {}
                    
                    if comp_info:
                        current = comp_info.get("current", val)
                        previous = comp_info.get("previous", 0)
                        change = comp_info.get("percent_change", 0)
                        absolute_change = current - previous
                        
                        # Format change string
                        if absolute_change > 0:
                            change_str = f"+{absolute_change:,}, +{change:.1f}%"
                        elif absolute_change < 0:
                            change_str = f"{absolute_change:,}, {change:.1f}%"
                        else:
                            change_str = "no change"
                        
                        response.append(
                            f"{metric_name}: {current:,} (was {previous:,} → {change_str})"
                        )
                        
                        # Add meaning
                        meaning = self._explain_metric_change(metric, current, previous, change)
                        if meaning:
                            response.append(f"  Meaning: {meaning}")
                    else:
                        # No comparison available
                        response.append(f"{metric_name}: {val:,}")
                
                # ================================================================
                # 3️⃣ VISIBILITY vs ENGAGEMENT INSIGHT
                # ================================================================
                if comparison:
                    response.append("\n--- Visibility vs. Engagement Analysis ---\n")
                    
                    visibility_health = self._analyze_visibility_health(visibility_metrics, comparison)
                    engagement_health = self._analyze_engagement_health(engagement_metrics, comparison)
                    
                    response.append(f"Visibility: {visibility_health}")
                    response.append(f"Engagement Quality: {engagement_health}")
                    
                    # Diagnose issue type
                    diagnosis = self._diagnose_performance_issue(visibility_metrics, engagement_metrics, comparison)
                    if diagnosis:
                        response.append(f"\nDiagnosis: {diagnosis}")
                
                # ================================================================
                # 4️⃣ DATA-BACKED INTERPRETATION
                # ================================================================
                if comparison:
                    response.append("\n--- What This Means ---\n")
                    interpretation = self._generate_interpretation(metrics, comparison, visibility_metrics, engagement_metrics)
                    response.append(interpretation)
                
                # ================================================================
                # 5️⃣ ACTIONABLE RECOMMENDATIONS (PRIORITIZED)
                # ================================================================
                response.append("\n--- What To Do Next ---\n")
                
                if comparison:
                    recommendations = self._generate_prioritized_recommendations(
                        metrics, comparison, visibility_metrics, engagement_metrics
                    )
                    
                    if recommendations.get("high"):
                        response.append("\n[High Priority - Fix Now]")
                        for i, action in enumerate(recommendations["high"], 1):
                            response.append(f"{i}. {action}")
                    
                    if recommendations.get("medium"):
                        response.append("\n[Medium Priority - Test This Week]")
                        for i, action in enumerate(recommendations["medium"], 1):
                            response.append(f"{i}. {action}")
                    
                    if recommendations.get("continue"):
                        response.append("\n[Keep Doing]")
                        for i, action in enumerate(recommendations["continue"], 1):
                            response.append(f"{i}. {action}")
                else:
                    response.append("1. Continue posting regularly to establish performance baselines")
                    response.append("2. Track these metrics weekly to identify trends")
                
                # ================================================================
                # 6️⃣ FINAL TAKEAWAY
                # ================================================================
                if comparison:
                    response.append("\n--- Bottom Line ---\n")
                    takeaway = self._generate_final_takeaway(metrics, comparison, visibility_metrics, engagement_metrics)
                    response.append(takeaway)
                
                response.append("\n" + "=" * 60 + "\n")
            
            return "\n".join(response).strip() or "No account data available for the requested period."
            
        except Exception as e:
            logger.error(f"Error in format_account_analytics_response: {e}", exc_info=True)
            return "An error occurred while generating your analytics report. Please try again."
    
    def _generate_snapshot_summary(self, metrics: Dict, comparison: Dict) -> str:
        """Generate a 2-3 line plain-English snapshot of what changed."""
        visibility_trend = None
        engagement_trend = None
        
        for metric, comp in comparison.items():
            metric_lower = metric.lower()
            change = comp.get("percent_change", 0)
            
            if any(x in metric_lower for x in ['reach', 'impression', 'view']):
                if abs(change) > 5:
                    visibility_trend = "up" if change > 0 else "down"
            elif any(x in metric_lower for x in ['like', 'comment', 'share', 'engaged']):
                if abs(change) > 5:
                    engagement_trend = "up" if change > 0 else "down"
        
        # Generate summary
        if visibility_trend == "up" and engagement_trend == "down":
            return "Visibility is growing, but engagement has dropped. Content is reaching more people who aren't connecting with it."
        elif visibility_trend == "down" and engagement_trend == "up":
            return "Reach has declined, but engagement quality is stronger. The content resonates well with a smaller audience."
        elif visibility_trend == "up" and engagement_trend == "up":
            return "Both reach and engagement are growing. Your content strategy is working effectively."
        elif visibility_trend == "down" and engagement_trend == "down":
            return "Both visibility and engagement have declined. This signals a need for content refresh and distribution adjustment."
        elif visibility_trend == "up":
            return "Visibility is growing while engagement remains stable. You're reaching more people consistently."
        elif engagement_trend == "up":
            return "Engagement is improving while visibility holds steady. Your content quality is resonating better."
        elif visibility_trend == "down":
            return "Visibility has declined while engagement remains stable. Focus on distribution and posting times."
        elif engagement_trend == "down":
            return "Engagement has weakened while visibility holds. Your content may need stronger hooks or relevance."
        else:
            return "Performance is relatively stable across metrics. Look for incremental optimization opportunities."
    
    def _explain_metric_change(self, metric: str, current: int, previous: int, change_pct: float) -> str:
        """Provide human-readable meaning for a metric change."""
        metric_lower = metric.lower()
        
        if abs(change_pct) < 5:
            return "Stable performance, no significant change."
        
        if 'reach' in metric_lower or 'impression' in metric_lower:
            if change_pct > 20:
                return "Strong distribution growth - your posts are being shown to significantly more people."
            elif change_pct > 0:
                return "Modest visibility increase - slightly more people are seeing your content."
            elif change_pct < -20:
                return "Sharp visibility drop - fewer people are being shown your posts."
            else:
                return "Slight visibility decline - minor reduction in content distribution."
        
        if 'like' in metric_lower or 'comment' in metric_lower or 'share' in metric_lower:
            if change_pct > 20:
                return "People are actively engaging with your content much more than before."
            elif change_pct > 0:
                return "Modest engagement improvement - content is resonating slightly better."
            elif change_pct < -20:
                return "Significant engagement drop - people are seeing but not interacting."
            else:
                return "Slight engagement decline - content isn't sparking as much interaction."
        
        if 'follower' in metric_lower or 'subscriber' in metric_lower:
            if change_pct > 10:
                return "Strong audience growth - you're attracting new followers steadily."
            elif change_pct > 0:
                return "Gradual audience expansion - new followers are joining."
            elif change_pct < 0:
                return "Audience churn - you're losing more followers than you're gaining."
        
        return None
    
    def _analyze_visibility_health(self, visibility_metrics: Dict, comparison: Dict) -> str:
        """Analyze visibility metrics health."""
        if not visibility_metrics:
            return "No visibility data available"
        
        avg_change = 0
        count = 0
        
        for metric in visibility_metrics.keys():
            comp = comparison.get(metric, {})
            change = comp.get("percent_change", 0)
            avg_change += change
            count += 1
        
        if count > 0:
            avg_change = avg_change / count
        
        if avg_change > 15:
            return "Strong - content distribution is expanding significantly"
        elif avg_change > 5:
            return "Healthy - reach is growing steadily"
        elif avg_change > -5:
            return "Stable - consistent visibility levels"
        elif avg_change > -15:
            return "Declining - distribution is weakening"
        else:
            return "Critical - sharp drop in content visibility"
    
    def _analyze_engagement_health(self, engagement_metrics: Dict, comparison: Dict) -> str:
        """Analyze engagement metrics health."""
        if not engagement_metrics:
            return "No engagement data available"
        
        avg_change = 0
        count = 0
        
        for metric in engagement_metrics.keys():
            comp = comparison.get(metric, {})
            change = comp.get("percent_change", 0)
            avg_change += change
            count += 1
        
        if count > 0:
            avg_change = avg_change / count
        
        if avg_change > 15:
            return "Excellent - audience is actively engaged and responding"
        elif avg_change > 5:
            return "Good - engagement is improving"
        elif avg_change > -5:
            return "Stable - consistent interaction levels"
        elif avg_change > -15:
            return "Weakening - audience is less responsive"
        else:
            return "Poor - significant drop in audience interaction"
    
    def _diagnose_performance_issue(self, visibility_metrics: Dict, engagement_metrics: Dict, comparison: Dict) -> str:
        """Diagnose whether the issue is algorithm, content, or audience-related."""
        vis_change = 0
        vis_count = 0
        eng_change = 0
        eng_count = 0
        
        for metric in visibility_metrics.keys():
            comp = comparison.get(metric, {})
            vis_change += comp.get("percent_change", 0)
            vis_count += 1
        
        for metric in engagement_metrics.keys():
            comp = comparison.get(metric, {})
            eng_change += comp.get("percent_change", 0)
            eng_count += 1
        
        if vis_count > 0:
            vis_change /= vis_count
        if eng_count > 0:
            eng_change /= eng_count
        
        # Diagnosis logic
        if vis_change < -10 and eng_change > -5:
            return "This appears to be a distribution issue (algorithm or posting time) rather than content quality."
        elif vis_change > 5 and eng_change < -10:
            return "This indicates a content-audience mismatch - people see it but aren't connecting with it."
        elif vis_change < -10 and eng_change < -10:
            return "Both visibility and engagement are down, suggesting broader content strategy adjustment needed."
        elif vis_change > 10 and eng_change > 10:
            return "Strong performance across the board - your current strategy is effective."
        else:
            return None
    
    def _generate_interpretation(self, metrics: Dict, comparison: Dict, visibility_metrics: Dict, engagement_metrics: Dict) -> str:
        """Generate data-backed interpretation of what changed and why."""
        interpretations = []
        
        # Analyze largest changes
        largest_increase = None
        largest_decrease = None
        max_increase = 0
        max_decrease = 0
        
        for metric, comp in comparison.items():
            change = comp.get("percent_change", 0)
            if change > max_increase:
                max_increase = change
                largest_increase = (metric, comp)
            if change < max_decrease:
                max_decrease = change
                largest_decrease = (metric, comp)
        
        # Explain largest changes
        if largest_increase and max_increase > 15:
            metric_name = largest_increase[0].replace('_', ' ')
            current = largest_increase[1].get("current", 0)
            previous = largest_increase[1].get("previous", 0)
            interpretations.append(
                f"Your {metric_name} jumped from {previous:,} to {current:,}, indicating successful content or timing adjustments."
            )
        
        if largest_decrease and max_decrease < -15:
            metric_name = largest_decrease[0].replace('_', ' ')
            current = largest_decrease[1].get("current", 0)
            previous = largest_decrease[1].get("previous", 0)
            interpretations.append(
                f"Your {metric_name} dropped from {previous:,} to {current:,}, suggesting either reduced posting frequency, timing changes, or content format shifts."
            )
        
        if not interpretations:
            interpretations.append("Performance is relatively stable with no major shifts in key metrics.")
        
        return " ".join(interpretations)
    
    def _generate_prioritized_recommendations(self, metrics: Dict, comparison: Dict, visibility_metrics: Dict, engagement_metrics: Dict) -> Dict[str, List[str]]:
        """Generate prioritized, metric-backed recommendations."""
        high = []
        medium = []
        keep_doing = []
        
        # Analyze visibility
        vis_declining = any(
            comparison.get(m, {}).get("percent_change", 0) < -15 
            for m in visibility_metrics.keys()
        )
        
        # Analyze engagement
        eng_declining = any(
            comparison.get(m, {}).get("percent_change", 0) < -15 
            for m in engagement_metrics.keys()
        )
        
        # High priority actions (critical issues)
        if vis_declining and eng_declining:
            high.append("Audit recent content - identify what changed in posting frequency, times, or format")
            high.append("Review platform posting best practices - ensure you're aligned with current algorithm preferences")
        elif vis_declining:
            high.append("Test different posting times - your content may not be hitting peak audience hours")
            high.append("Increase posting frequency if it dropped recently")
        elif eng_declining:
            high.append("Refresh content hooks - first 3 seconds/lines aren't capturing attention")
            high.append("Study your best-performing posts and replicate their format")
        
        # Medium priority (optimization)
        if not vis_declining and not eng_declining:
            medium.append("Experiment with new content formats to find growth opportunities")
            medium.append("A/B test posting times to find optimal audience engagement windows")
            medium.append("Increase content variety while maintaining what works")
        else:
            medium.append("Engage with comments within first hour of posting to boost visibility")
            medium.append("Cross-promote high-performing content on other platforms")
        
        # What's working (continue doing)
        for metric, comp in comparison.items():
            change = comp.get("percent_change", 0)
            if change > 15:
                metric_name = metric.replace('_', ' ')
                keep_doing.append(f"Your {metric_name} is growing - maintain current content strategy")
                break
        
        if not keep_doing and not (vis_declining or eng_declining):
            keep_doing.append("Maintain consistent posting schedule and current content mix")
        
        return {
            "high": high,
            "medium": medium,
            "continue": keep_doing
        }
    
    def _generate_final_takeaway(self, metrics: Dict, comparison: Dict, visibility_metrics: Dict, engagement_metrics: Dict) -> str:
        """Generate final takeaway with confidence and recovery difficulty."""
        # Calculate overall trend
        total_change = sum(comp.get("percent_change", 0) for comp in comparison.values())
        avg_change = total_change / len(comparison) if comparison else 0
        
        # Determine confidence (based on data completeness)
        confidence = "High" if len(comparison) >= 3 else "Medium" if len(comparison) >= 2 else "Low"
        
        # Determine recovery difficulty
        vis_declining = any(comparison.get(m, {}).get("percent_change", 0) < -15 for m in visibility_metrics.keys())
        eng_declining = any(comparison.get(m, {}).get("percent_change", 0) < -15 for m in engagement_metrics.keys())
        
        if vis_declining and eng_declining:
            recovery = "Medium"
            conclusion = "Both visibility and engagement need attention, but focused content adjustments can turn this around within 2-3 weeks."
        elif vis_declining:
            recovery = "Low"
            conclusion = "Distribution issue is fixable with timing and frequency adjustments - expect improvement within 1 week."
        elif eng_declining:
            recovery = "Medium"
            conclusion = "Content refresh needed, but your distribution is healthy - new hooks and formats should recover engagement within 2 weeks."
        elif avg_change > 10:
            recovery = "N/A"
            conclusion = "Strong growth across metrics - maintain current momentum and look for scaling opportunities."
        else:
            recovery = "Low"
            conclusion = "Performance is stable - small optimizations can drive incremental growth."
        
        return f"{conclusion}\n\nConfidence Level: {confidence} | Recovery Difficulty: {recovery}"

    
    def _format_post_analytics(self, data: Dict[str, Any], state: AnalyticsState) -> str:
        """
        Format comprehensive post-level analytics with number-backed insights.
        Converts Orion's structured output into analytical, human-friendly explanation.
        """
        try:
            response = []
            
            for platform, p_data in data.items():
                # Handle warnings
                if "_warning" in p_data:
                    return f"*{p_data['_warning']}*"
                
                ranked_posts = p_data.get("ranked_posts", [])
                if not ranked_posts:
                    continue
                
                num_found = len(ranked_posts)
                top_n = state.top_n or 5
                
                # ---------- HEADER ----------
                response.append(f"**{platform.title()} – Recent Posts Analysis**")
                
                if num_found < top_n:
                    response.append(
                        f"Only **{num_found} post{'s' if num_found != 1 else ''}** found "
                        f"(requested {top_n}). Insights below are **directional**, not conclusive."
                    )
                
                # ---------- POST-WISE NUMBERS ----------
                engagements = []
                response.append("\n**Post-wise performance breakdown:**")
                
                for i, post in enumerate(ranked_posts[:min(top_n, 10)], 1):
                    likes = post.get("likes", 0)
                    comments = post.get("comments", 0)
                    shares = post.get("shares", 0)
                    views = post.get("views", 0) or post.get("reach", 0)
                    
                    total_engagement = likes + comments + shares
                    engagements.append(total_engagement)
                    
                    # Build metrics string
                    metrics_parts = [f"{likes:,} likes", f"{comments:,} comments"]
                    if shares > 0:
                        metrics_parts.append(f"{shares:,} shares")
                    if views > 0:
                        metrics_parts.append(f"{views:,} views")
                    
                    metrics_str = ", ".join(metrics_parts)
                    
                    response.append(
                        f"• **Post {i}** → {metrics_str} "
                        f"→ **{total_engagement:,} total interactions**"
                    )
                
                # ---------- NUMERIC COMPARISON ----------
                if len(engagements) >= 2:
                    best = max(engagements)
                    worst = min(engagements)
                    
                    response.append("\n**Performance comparison:**")
                    
                    if worst > 0:
                        ratio = round(best / worst, 1)
                        response.append(
                            f"• The best-performing post received approximately "
                            f"**{ratio}× more interactions** than the lowest-performing post."
                        )
                    else:
                        response.append(
                            "• One post attracted nearly all engagement, while another received almost none."
                        )
                    
                    # Content type analysis if available
                    reels = [p for p in ranked_posts if p.get("media_type", "").lower() in ["reel", "video"]]
                    statics = [p for p in ranked_posts if p.get("media_type", "").lower() not in ["reel", "video"]]
                    
                    if reels and statics:
                        top_2_types = [p.get("media_type", "Post") for p in ranked_posts[:2]]
                        if all("reel" in t.lower() or "video" in t.lower() for t in top_2_types):
                            response.append("• Both top posts were Reels, while lower-performing posts were static images.")
                
                # ---------- INTERPRETATION ----------
                response.append("\n**What this indicates:**")
                
                if num_found < 3:
                    response.append(
                        "• With very limited data, engagement appears uneven across posts. "
                        "This usually points to content or format differences rather than audience fatigue."
                    )
                else:
                    # Calculate variance
                    if len(engagements) >= 3:
                        avg_engagement = sum(engagements) / len(engagements)
                        high_performers = sum(1 for e in engagements if e > avg_engagement)
                        
                        if high_performers <= 2:
                            response.append("• Some posts are consistently driving more engagement than others.")
                        else:
                            response.append("• Engagement is relatively balanced across your posts.")
                    
                    # Content format insights
                    if reels and statics:
                        reel_avg = sum(p.get("likes", 0) + p.get("comments", 0) for p in reels) / len(reels)
                        static_avg = sum(p.get("likes", 0) + p.get("comments", 0) for p in statics) / len(statics)
                        
                        if static_avg > 0:
                            format_ratio = round(reel_avg / static_avg, 1)
                            if format_ratio >= 2:
                                response.append(
                                    f"• **Reels format delivers {format_ratio}× higher engagement** than static posts."
                                )
                            elif format_ratio <= 0.5:
                                response.append("• Static posts are performing better than video content for your audience.")
                
                # ---------- ACTIONS ----------
                response.append("\n**What you should do next:**")
                
                if num_found < 3:
                    response.append("• Publish 3–5 more posts to unlock stronger patterns")
                
                if len(engagements) >= 2:
                    best_idx = engagements.index(max(engagements))
                    response.append(f"• Replicate the structure or idea of Post {best_idx + 1} (your highest-performing post)")
                    response.append("• Avoid repeating formats that received little to no interaction")
                
                # Specific recommendations based on data
                if reels and statics and len(reels) > 0 and len(statics) > 0:
                    reel_avg = sum(p.get("likes", 0) + p.get("comments", 0) for p in reels) / len(reels)
                    static_avg = sum(p.get("likes", 0) + p.get("comments", 0) for p in statics) / len(statics)
                    
                    if reel_avg > static_avg * 1.5:
                        response.append("• Focus more on Reels for important or high-effort content")
                    elif static_avg > reel_avg * 1.5:
                        response.append("• Your audience responds better to static posts — lean into that")
                
                response.append("• Engage with comments quickly — early responses boost post visibility")
                
                # ---------- CONFIDENCE ----------
                if num_found >= 5:
                    confidence_msg = f"High confidence (based on {num_found} posts)"
                elif num_found >= 3:
                    confidence_msg = f"Medium confidence (based on {num_found} posts)"
                else:
                    confidence_msg = f"Low confidence (only {num_found} post{'s' if num_found != 1 else ''} available)"
                
                response.append(f"\n*{confidence_msg}*")
            
            return "\n".join(response)
        
        except Exception as e:
            logger.error("Post analytics formatting failed", exc_info=True)
            return (
                "I analyzed your posts but encountered an issue presenting the results. "
                "Please try again later."
            )
    
    def _format_account_analytics(self, data: Dict[str, Any], state: AnalyticsState) -> str:
        """Format account-level analytics with metrics and comparisons."""
        response = ""
        
        # Insight Mode (Strict Live Data)
        if state.intent == "insight":
            for platform, metrics in data.items():
                response += f"**{platform.title()} Live Insights:**\n\n"
                if isinstance(metrics, dict):
                    for k, v in metrics.items():
                        # Skip metadata
                        if k.startswith("_"): continue
                        response += f"• **{k.replace('_', ' ').title()}**: {v:,}\n"
                else:
                    response += f"{metrics}\n"
                response += "\n"
            return response.strip()
        
        # Analytics Mode (Historical + Comparison)
        else: # intent == "analytics"
            for platform, p_data in data.items():
                response += f"📊 **{platform.title()} Analytics**\n\n"
                
                # Check for warnings/errors
                if "_warning" in p_data:
                    response += f"*{p_data['_warning']}*\n"
                    continue
                
                # Current Metrics
                if "metrics" in p_data:
                    response += "**Current Period:**\n"
                    for k, v in p_data["metrics"].items():
                        response += f"• **{k.replace('_', ' ').title()}**: {v:,}\n"
                    response += "\n"
                
                # Period Comparison
                if "comparison" in p_data:
                    response += "**📈 Comparison vs Previous Period:**\n"
                    comp = p_data["comparison"]
                    for metric, info in comp.items():
                        trend_icon = "📈" if info.get("trend") == "up" else "📉" if info.get("trend") == "down" else "➡️"
                        change = info.get("percent_change", 0)
                        current = info.get("current", 0)
                        previous = info.get("previous", 0)
                        
                        if info.get("trend") == "up":
                            response += f"{trend_icon} **{metric.title()}**: {current:,} (vs {previous:,}) — **+{change:.1f}%** ⬆️\n"
                        elif info.get("trend") == "down":
                            response += f"{trend_icon} **{metric.title()}**: {current:,} (vs {previous:,}) — **{change:.1f}%** ⬇️\n"
                        else:
                            response += f"{trend_icon} **{metric.title()}**: {current:,} (vs {previous:,}) — No significant change\n"
                    response += "\n"
                
                response += "\n"
            
            return response.strip() or "No data found."
    
    def handle_leads_management(self, state: IntentBasedChatbotState) -> IntentBasedChatbotState:
        """Handle leads management intent"""
        try:
            from agents.tools.Chase_Leads_manager import execute_leads_operation
            
            payload = state["intent_payload"].leads
            if not payload:
                state["response"] = "I need more information about what you'd like to do with leads. Please specify the action."
                return state
            
            result = execute_leads_operation(payload, state["user_id"])
            
            if result.get("clarifying_question"):
                state["response"] = result["clarifying_question"]
            elif result.get("success") and result.get("data"):
                state["response"] = self._format_leads_response(result["data"])
            elif result.get("error"):
                state["response"] = f"I encountered an error: {result['error']}"
            else:
                state["response"] = "I've processed your leads management request."
                
        except Exception as e:
            logger.error(f"Error in handle_leads_management: {e}")
            state["response"] = "I encountered an error while processing your leads request. Please try again."
        
        return state
    
    def handle_posting_manager(self, state: IntentBasedChatbotState) -> IntentBasedChatbotState:
        """Handle posting manager intent"""
        try:
            from agents.tools.Emily_post_manager import execute_posting_operation
            
            payload = state["intent_payload"].posting
            if not payload:
                state["response"] = "I need more information about what you'd like to do with your posts. Please specify the action."
                return state
            
            result = execute_posting_operation(payload, state["user_id"])
            
            if result.get("clarifying_question"):
                state["response"] = result["clarifying_question"]
            elif result.get("success") and result.get("data"):
                state["response"] = self._format_posting_response(result["data"])
            elif result.get("error"):
                state["response"] = f"I encountered an error: {result['error']}"
            else:
                state["response"] = "I've processed your posting request."
                
        except Exception as e:
            logger.error(f"Error in handle_posting_manager: {e}")
            state["response"] = "I encountered an error while processing your posting request. Please try again."
        
        return state
    
    def handle_general_talks(self, state: IntentBasedChatbotState) -> IntentBasedChatbotState:
        """Handle general conversational intent"""
        try:
            from agents.tools.general_chat_tool import execute_general_chat
            
            payload = state["intent_payload"].general
            if not payload:
                payload = GeneralTalkPayload(message=state["current_query"])
            
            result = execute_general_chat(payload, state["user_id"])
            
            if result.get("success") and result.get("data"):
                state["response"] = result["data"]
            elif result.get("error"):
                state["response"] = f"I encountered an error: {result['error']}"
            else:
                state["response"] = "I'm here to help! How can I assist you today?"
                
        except Exception as e:
            logger.error(f"Error in handle_general_talks: {e}")
            state["response"] = "I'm here to help! How can I assist you today?"
        
        return state
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(dot_product / (norm1 * norm2))
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def handle_faq(self, state: IntentBasedChatbotState) -> IntentBasedChatbotState:
        """Handle FAQ intent with RAG retrieval from Supabase using semantic similarity
        
        Uses sentence-transformers embeddings for semantic search instead of keyword matching.
        """
        try:
            user_query = state.get("current_query", "").strip()
            logger.info(f"Handling FAQ query: {user_query}")
            
            # Load user profile with embedding for business context
            user_id = state.get("user_id")
            business_context = None
            try:
                logger.info(f"🔍 Loading business context for user: {user_id}")
                profile_response = supabase.table("profiles").select("*, profile_embedding").eq("id", user_id).execute()
                
                if profile_response.data and len(profile_response.data) > 0:
                    profile_data = profile_response.data[0]
                    business_context = get_profile_context_with_embedding(profile_data)
                    logger.info(f"✅ Loaded business context (has embedding: {business_context.get('use_embedding', False)})")
                else:
                    logger.warning(f"⚠️ No profile found for user {user_id}")
            except Exception as profile_error:
                logger.error(f"❌ Error loading profile: {profile_error}")
                # Continue without business context
            
            # Retrieve FAQ records from Supabase
            faq_list = []
            try:
                # Get embedding service (same pattern as profile_embedding_helper.py)
                embedding_service = get_embedding_service()
                
                # Fetch all FAQs from Supabase
                # Schema: id, faq_key, response, category
                logger.info("🔍 Fetching all FAQs from Supabase...")
                all_faqs = supabase.table("faq_responses").select("id, faq_key, response, category").execute()
                
                if not all_faqs.data or len(all_faqs.data) == 0:
                    logger.warning("⚠️ No FAQs found in database")
                    state["response"] = "I don't have an exact answer for that yet, but I can help you with features, pricing, or usage. How can I assist you?"
                    return state
                
                logger.info(f"✅ Retrieved {len(all_faqs.data)} FAQs from database")
                
                # Generate embedding for user query
                logger.info("🔍 Generating embedding for user query...")
                query_embedding = embedding_service.generate_embedding_from_text(user_query)
                logger.info(f"✅ Generated query embedding (dimension: {len(query_embedding)})")
                
                # Get profile embedding if available for business-context-aware matching
                profile_embedding = None
                if business_context and business_context.get("use_embedding"):
                    profile_embedding = business_context.get("profile_embedding")
                    if profile_embedding:
                        logger.info(f"✅ Using profile embedding for business-context-aware matching")
                
                # Generate embeddings for all FAQs and calculate similarity
                logger.info("🔍 Computing semantic similarity for all FAQs...")
                faq_similarities = []
                
                for faq in all_faqs.data:
                    faq_id = faq.get("id")
                    faq_key = faq.get("faq_key", "")
                    response = faq.get("response", "")
                    category = faq.get("category", "")
                    
                    # Combine faq_key, response, and category for better semantic matching
                    # This helps match queries like "pricing" to "pricing_basic" or "pricing_pro"
                    faq_text = f"{faq_key} {response}"
                    if category:
                        faq_text = f"{category} {faq_text}"
                    
                    # Generate embedding for this FAQ
                    faq_embedding = embedding_service.generate_embedding_from_text(faq_text)
                    
                    # Calculate cosine similarity with query
                    query_similarity = self._cosine_similarity(query_embedding, faq_embedding)
                    
                    # If profile embedding is available, also calculate business context similarity
                    business_similarity = 0.0
                    if profile_embedding:
                        business_similarity = self._cosine_similarity(profile_embedding, faq_embedding)
                        logger.debug(f"FAQ {faq_key}: query_sim={query_similarity:.4f}, business_sim={business_similarity:.4f}")
                    
                    # Combined similarity: 70% query relevance, 30% business context relevance
                    # This ensures FAQs relevant to both the query AND the business get higher scores
                    if profile_embedding:
                        combined_similarity = (0.7 * query_similarity) + (0.3 * business_similarity)
                    else:
                        combined_similarity = query_similarity
                    
                    faq_similarities.append({
                        "faq": faq,
                        "similarity": combined_similarity,
                        "query_similarity": query_similarity,
                        "business_similarity": business_similarity,
                        "faq_key": faq_key,
                        "response": response,
                        "category": category
                    })
                
                # Sort by similarity (highest first) and get top 5
                faq_similarities.sort(key=lambda x: x["similarity"], reverse=True)
                top_faqs = faq_similarities[:5]
                
                logger.info(f"✅ Top FAQ similarities:")
                for idx, item in enumerate(top_faqs, 1):
                    if profile_embedding:
                        logger.info(f"   {idx}. {item['faq_key']}: combined={item['similarity']:.4f} (query={item['query_similarity']:.4f}, business={item['business_similarity']:.4f})")
                    else:
                        logger.info(f"   {idx}. {item['faq_key']}: {item['similarity']:.4f}")
                
                # Filter by similarity threshold (only include FAQs with similarity > 0.3)
                # This prevents returning irrelevant results
                threshold = 0.3
                filtered_faqs = [item for item in top_faqs if item["similarity"] >= threshold]
                
                if not filtered_faqs:
                    logger.info(f"⚠️ No FAQs met similarity threshold ({threshold})")
                    state["response"] = "I don't have an exact answer for that yet, but I can help you with features, pricing, or usage. How can I assist you?"
                    return state
                
                faq_list = [item["faq"] for item in filtered_faqs]
                logger.info(f"✅ Selected {len(faq_list)} FAQs above similarity threshold")
                
            except Exception as db_error:
                logger.error(f"❌ Error retrieving FAQs from Supabase: {db_error}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                faq_list = []
            
            # If no FAQs found, return helpful fallback message
            if not faq_list:
                logger.info("No FAQ matches found, returning fallback message")
                state["response"] = "I don't have an exact answer for that yet, but I can help you with features, pricing, or usage. How can I assist you?"
                return state
            
            # Build context from retrieved FAQs
            # Schema: id, faq_key, response, category
            faq_context = ""
            for idx, faq in enumerate(faq_list, 1):
                faq_key = faq.get("faq_key", "")
                response = faq.get("response", "")
                category = faq.get("category", "")
                
                faq_context += f"\n\nFAQ {idx}:\n"
                faq_context += f"Topic: {faq_key}\n"
                if category:
                    faq_context += f"Category: {category}\n"
                faq_context += f"Response: {response}\n"
            
            # Generate response using LLM with FAQ context only (no business context)
            
            system_prompt = """You are Emily, an AI assistant designed to help users understand and use
the product or service you are assisting with.

You are NOT the company and must never speak as the company.

IDENTITY & VOICE
----------------
• Emily is always the doer of the response.
• Any action, offering, pricing, or plan described is done by the US.
• Use first-person plural language such as "we", "our", or "us".
• Speak as a neutral assistant explaining the business's offerings.

GROUNDING & ACCURACY
--------------------
• Use ONLY the information explicitly provided in the context.
• Do NOT rely on general knowledge or assumptions.
• Do NOT invent pricing, plans, features, or capabilities.
• If information is missing or unclear, say so clearly.


RAG USAGE
---------
• Treat retrieved context as the single source of truth.
• Rephrase or summarize the context without changing its meaning.
• Do NOT mention internal systems, databases, or retrieval mechanisms.

PRICING & PLANS
---------------
• Pricing details must come directly from retrieved context.
• If pricing is not provided, state that the exact pricing is not available.
• Never estimate, infer, or imply pricing.

TONE & STYLE
------------
• Clear, professional, and concise
• Helpful but not sales-driven
• No emojis unless explicitly requested

FALLBACK
--------
If the answer is not available in the provided context, respond honestly and
offer help with related, supported information.

."""

            user_prompt = f"""Based on the following FAQ data, answer the user's question.

FAQ Data:
{faq_context}

User Question: {user_query}

Provide a helpful and accurate answer based on the FAQ data above."""

            # Generate response
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            answer = response.content.strip()
            
            logger.info(f"Generated FAQ response: {answer[:100]}...")
            state["response"] = answer
            
        except Exception as e:
            logger.error(f"Error in handle_faq: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Fallback response
            state["response"] = "I don't have an exact answer for that yet, but I can help you with features, pricing, or usage. How can I assist you?"
        
        return state
    
    def generate_final_response(self, state: IntentBasedChatbotState) -> IntentBasedChatbotState:
        """Final response formatting node"""
        # Response is already set in handler nodes
        # This node can be used for additional formatting if needed
        return state
    
    def _format_content_response(self, data: Any) -> str:
        """Format content generation response with structured content"""
        if isinstance(data, dict):
            # Check if this is structured content (title, content, hashtags, images)
            # If it has structured content data, return a simple message (card will be displayed separately)
            if "title" in data and "content" in data:
                # Return simple message - the card will be displayed from content_data
                return "Here is the post you requested"
            elif "message" in data:
                return data["message"]
            elif "content" in data:
                return data["content"]
        return str(data)
    
    
    def _format_leads_response(self, data: Any) -> str:
        """Format leads management response"""
        if isinstance(data, dict):
            if "message" in data:
                return data["message"]
            elif "summary" in data:
                return data["summary"]
        return str(data)
    
    def _format_posting_response(self, data: Any) -> str:
        """Format posting manager response"""
        if isinstance(data, dict):
            if "message" in data:
                return data["message"]
            elif "summary" in data:
                return data["summary"]
        return str(data)
    
    def chat(self, user_id: str, query: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        """Main chat interface (deprecated - use get_intent_based_response instead)"""
        try:
            # This method is kept for backward compatibility
            # The actual implementation is now in get_intent_based_response
            initial_state: IntentBasedChatbotState = {
                "user_id": user_id,
                "current_query": query,
                "conversation_history": conversation_history or [],
                "intent_payload": None,
                "partial_payload": None,
                "response": None,
                "context": {},
                "needs_clarification": False,
                "options": None,
                "content_data": None
            }
            
            # Run the graph
            result = self.graph.invoke(initial_state)
            
            return result.get("response", "I apologize, but I couldn't process your request.")
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return "I apologize, but I encountered an error while processing your request."

# Global instance
_intent_based_chatbot = None

# In-memory cache for partial payloads (keyed by user_id)
# In production, this could be stored in Redis or database
_partial_payload_cache: Dict[str, Dict[str, Any]] = {}

def clear_partial_payload_cache(user_id: str) -> None:
    """Clear the partial payload cache for a specific user"""
    _partial_payload_cache.pop(user_id, None)
    logger.info(f"Cleared partial payload cache for user {user_id}")

def get_intent_based_chatbot() -> IntentBasedChatbot:
    """Get or create the intent-based chatbot instance"""
    global _intent_based_chatbot
    if _intent_based_chatbot is None:
        _intent_based_chatbot = IntentBasedChatbot()
    return _intent_based_chatbot

def get_intent_based_response(user_id: str, message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Get response from intent-based chatbot"""
    chatbot = get_intent_based_chatbot()
    
    # Retrieve partial payload from cache if exists
    partial_payload = _partial_payload_cache.get(user_id)
    
    # Create state with partial payload
    initial_state: IntentBasedChatbotState = {
        "user_id": user_id,
        "current_query": message,
        "conversation_history": conversation_history or [],
        "intent_payload": None,
        "partial_payload": partial_payload,
        "response": None,
        "context": {},
        "needs_clarification": False,
        "options": None,
        "content_data": None
    }
    
    # Run the graph
    result = chatbot.graph.invoke(initial_state)
    
    # Update cache with new partial payload if clarification is needed
    if result.get("needs_clarification") and result.get("partial_payload"):
        _partial_payload_cache[user_id] = result["partial_payload"]
    elif not result.get("needs_clarification"):
        # Clear cache when request is complete
        _partial_payload_cache.pop(user_id, None)
    
    return {
        "response": result.get("response", "I apologize, but I couldn't process your request."),
        "options": result.get("options"),
        "content_data": result.get("content_data")  # Include structured content data (title, content, hashtags, images)
    }

def get_intent_based_response_stream(user_id: str, message: str, conversation_history: Optional[List[Dict[str, str]]] = None):
    """Stream response from intent-based chatbot"""
    chatbot = get_intent_based_chatbot()
    
    # Retrieve partial payload from cache if exists
    partial_payload = _partial_payload_cache.get(user_id)
    
    # Create state with partial payload
    initial_state: IntentBasedChatbotState = {
        "user_id": user_id,
        "current_query": message,
        "conversation_history": conversation_history or [],
        "intent_payload": None,
        "partial_payload": partial_payload,
        "response": None,
        "context": {},
        "needs_clarification": False,
        "options": None,
        "content_data": None
    }
    
    # Run the graph
    result = chatbot.graph.invoke(initial_state)
    
    # Update cache with new partial payload if clarification is needed
    if result.get("needs_clarification") and result.get("partial_payload"):
        _partial_payload_cache[user_id] = result["partial_payload"]
    elif not result.get("needs_clarification"):
        # Clear cache when request is complete
        _partial_payload_cache.pop(user_id, None)
    
    response = result.get("response", "I apologize, but I couldn't process your request.")
    options = result.get("options")
    content_data = result.get("content_data")
    
    # Debug: Log what's in the result
    logger.info(f"🔍 Stream function - Result keys: {list(result.keys())}")
    logger.info(f"   Result has 'content_data' key: {'content_data' in result}")
    logger.info(f"   content_data value: {content_data}")
    logger.info(f"   content_data type: {type(content_data)}")
    if content_data:
        logger.info(f"   content_data keys: {list(content_data.keys()) if isinstance(content_data, dict) else 'N/A'}")
        logger.info(f"   content_data images: {content_data.get('images') if isinstance(content_data, dict) else 'N/A'}")
    
    # For now, yield the full response in chunks
    # Can be enhanced later for true streaming
    chunk_size = 10
    for i in range(0, len(response), chunk_size):
        yield response[i:i + chunk_size]
    
    # Yield options at the end if they exist
    if options:
        yield f"\n\nOPTIONS:{json.dumps(options)}"
    
    # Yield content_data at the end if it exists
    if content_data:
        logger.info(f"📤 Yielding CONTENT_DATA in stream: {json.dumps(content_data, default=str)[:200]}...")
        logger.info(f"   Images in content_data: {content_data.get('images')}")
        try:
            content_data_json = json.dumps(content_data, default=str)
            yield f"\n\nCONTENT_DATA:{content_data_json}"
            logger.info(f"✅ Successfully yielded CONTENT_DATA")
        except Exception as e:
            logger.error(f"❌ Error serializing content_data: {e}", exc_info=True)
    else:
        logger.warning(f"⚠️ content_data is None or empty - not yielding CONTENT_DATA")
        logger.warning(f"   Result keys: {list(result.keys())}")
        logger.warning(f"   Checking result directly: {result.get('content_data', 'NOT_FOUND')}")


