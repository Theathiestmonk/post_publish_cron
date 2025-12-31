"""
Content Creation Agent using LangGraph
Generates weekly content for social media platforms one by one
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

import openai
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from supabase import create_client, Client
from services.token_usage_service import TokenUsageService, FEATURE_TYPES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PostType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    STORY = "story"
    ARTICLE = "article"


class ContentPost(BaseModel):
    platform: str
    post_type: PostType
    title: Optional[str] = None
    content: str
    hashtags: List[str] = []
    scheduled_date: str
    scheduled_time: str
    metadata: Dict[str, Any] = {}

class ContentCampaign(BaseModel):
    id: Optional[str] = None
    user_id: str
    campaign_name: str
    week_start_date: str
    week_end_date: str
    status: str = "draft"
    total_posts: int = 0
    generated_posts: int = 0


class ContentState(BaseModel):
    # User context
    user_profile: Dict[str, Any] = {}
    business_context: Dict[str, Any] = {}
    
    # Campaign data
    campaign: Optional[ContentCampaign] = None
    platforms: List[str] = []
    
    # Platform iteration control
    current_platform_index: int = 0
    current_platform: Optional[str] = None
    completed_platforms: List[str] = []
    failed_platforms: List[str] = []
    
    # Content generation per platform
    platform_content: List[ContentPost] = []
    all_content: List[ContentPost] = []
    
    # Image generation tracking
    pending_image_requests: List[str] = []
    completed_image_requests: List[str] = []
    failed_image_requests: List[str] = []
    
    # Retry logic per platform
    max_retries_per_platform: int = 1
    current_platform_retries: int = 0
    
    # Progress tracking
    current_step: str = "initializing"
    progress_percentage: int = 0
    step_details: str = ""
    
    # Results
    success: bool = False
    error_message: Optional[str] = None
    weekly_summary: Optional[str] = None

# Platform-specific content generators
PLATFORM_GENERATORS = {
    "facebook": {
        "post_types": ["text", "image", "video", "carousel"],
        "max_length": 2000,
        "optimal_length": 40,
        "hashtag_limit": 3,
        "image_requirements": {
            "sizes": ["1200x630", "1080x1080", "1200x675"],
            "preferred_styles": ["realistic", "photographic"],
            "max_images_per_post": 10
        }
    },
    "instagram": {
        "post_types": ["image", "video", "carousel", "story"],
        "max_length": 2200,
        "optimal_length": 125,
        "hashtag_limit": 30,
        "image_requirements": {
            "sizes": ["1080x1080", "1080x1350", "1080x1920"],
            "preferred_styles": ["artistic", "realistic", "minimalist"],
            "max_images_per_post": 10
        }
    },
    "linkedin": {
        "post_types": ["text", "image", "video", "article"],
        "max_length": 3000,
        "optimal_length": 150,
        "hashtag_limit": 5,
        "image_requirements": {
            "sizes": ["1200x627", "1080x1080"],
            "preferred_styles": ["realistic", "professional"],
            "max_images_per_post": 1
        }
    },
    "twitter": {
        "post_types": ["text", "image", "video"],
        "max_length": 280,
        "optimal_length": 100,
        "hashtag_limit": 2,
        "image_requirements": {
            "sizes": ["1200x675", "1080x1080"],
            "preferred_styles": ["realistic", "minimalist"],
            "max_images_per_post": 4
        }
    },
    "youtube": {
        "post_types": ["text", "video"],
        "max_length": 5000,
        "optimal_length": 200,
        "hashtag_limit": 15,
        "image_requirements": {
            "sizes": ["1280x720", "1920x1080"],
            "preferred_styles": ["realistic", "illustration"],
            "max_images_per_post": 1
        }
    },
    "twitter/x": {
        "post_types": ["text", "image", "video"],
        "max_length": 280,
        "optimal_length": 100,
        "hashtag_limit": 2,
        "image_requirements": {
            "sizes": ["1200x675", "1080x1080"],
            "preferred_styles": ["realistic", "minimalist"],
            "max_images_per_post": 4
        }
    },
    "whatsapp business": {
        "post_types": ["text", "image", "video"],
        "max_length": 1000,
        "optimal_length": 150,
        "hashtag_limit": 5,
        "image_requirements": {
            "sizes": ["1080x1080", "1200x630"],
            "preferred_styles": ["realistic", "professional"],
            "max_images_per_post": 10
        }
    }
}

class ContentCreationAgent:
    def __init__(self, supabase_url: str, supabase_key: str, openai_api_key: str, progress_callback=None):
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
        self.progress_callback = progress_callback
        self.token_tracker = TokenUsageService(supabase_url, supabase_key)
        self.graph = self._build_graph()
    
    async def update_progress(self, user_id: str, step: str, percentage: int, details: str, current_platform: str = None):
        """Update progress using callback"""
        if self.progress_callback:
            await self.progress_callback(user_id, step, percentage, details, current_platform)
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph for content creation"""
        graph = StateGraph(ContentState)
        
        # Add nodes
        graph.add_node("load_profile", self.load_user_profile)
        graph.add_node("extract_context", self.extract_business_context)
        graph.add_node("initialize_campaign", self.initialize_content_campaign)
        graph.add_node("check_platforms", self.check_more_platforms)
        graph.add_node("select_platform", self.select_next_platform)
        graph.add_node("load_platform_context", self.load_platform_specific_context)
        graph.add_node("generate_platform_content", self.generate_platform_content)
        graph.add_node("validate_platform_content", self.validate_platform_content)
        graph.add_node("should_retry_platform", self.should_retry_platform)
        graph.add_node("refine_platform_content", self.refine_platform_content)
        graph.add_node("store_platform_content", self.store_platform_content)
        graph.add_node("mark_platform_complete", self.mark_platform_complete)
        graph.add_node("generate_summary", self.generate_weekly_summary)
        graph.add_node("send_notification", self.send_notification)
        
        # Add edges
        graph.set_entry_point("load_profile")
        graph.add_edge("load_profile", "extract_context")
        graph.add_edge("extract_context", "initialize_campaign")
        graph.add_edge("initialize_campaign", "check_platforms")
        
        # Conditional edges
        graph.add_conditional_edges(
            "check_platforms",
            self.should_continue_platforms,
            {
                "continue": "select_platform",
                "complete": "generate_summary"
            }
        )
        
        graph.add_edge("select_platform", "load_platform_context")
        graph.add_edge("load_platform_context", "generate_platform_content")
        graph.add_edge("generate_platform_content", "validate_platform_content")
        
        graph.add_conditional_edges(
            "validate_platform_content",
            self.is_content_valid,
            {
                "valid": "store_platform_content",
                "invalid": "should_retry_platform"
            }
        )
        
        graph.add_conditional_edges(
            "should_retry_platform",
            self.should_retry_platform_decision,
            {
                "retry": "refine_platform_content",
                "skip": "mark_platform_complete"
            }
        )
        
        # Direct path from store to mark complete (skip retry logic)
        graph.add_edge("store_platform_content", "mark_platform_complete")
        
        graph.add_edge("refine_platform_content", "validate_platform_content")
        graph.add_edge("mark_platform_complete", "check_platforms")
        graph.add_edge("generate_summary", "send_notification")
        graph.add_edge("send_notification", END)
        
        return graph.compile()
    
    async def load_user_profile(self, state: ContentState) -> ContentState:
        """Load user profile from Supabase"""
        try:
            user_id = state.user_profile.get('user_id')
            
            # Update progress
            await self.update_progress(
                user_id, 
                "loading_profile", 
                10, 
                "Loading user profile and preferences..."
            )
            
            # Get user profile including embeddings
            profile_response = self.supabase.table("profiles").select("*, profile_embedding").eq("id", user_id).execute()
            
            if profile_response.data:
                profile_data = profile_response.data[0]
                # Keep the user_id for compatibility
                profile_data['user_id'] = profile_data['id']
                state.user_profile = profile_data
            else:
                raise Exception("User profile not found")
                
        except Exception as e:
            logger.error(f"Error loading user profile: {e}")
            state.error_message = f"Failed to load user profile: {str(e)}"
            
        return state
    
    async def extract_business_context(self, state: ContentState) -> ContentState:
        """Extract business context from user profile, using embeddings if available"""
        try:
            profile = state.user_profile
            
            # Import embedding context utility
            from utils.embedding_context import get_profile_context_with_embedding
            
            # Get context with embeddings (prefers embeddings if available)
            context = get_profile_context_with_embedding(profile)
            
            # Ensure posting_frequency is always included (critical for post count)
            if "posting_frequency" not in context or not context.get("posting_frequency"):
                context["posting_frequency"] = profile.get("posting_frequency", "daily")
            
            # Store the full context including embeddings
            state.business_context = context
            
            # Set platforms from user profile
            state.platforms = profile.get("social_media_platforms", [])
            
            # Log posting frequency for debugging
            logger.info(f"Posting frequency from profile: {profile.get('posting_frequency', 'Not set')}")
            logger.info(f"Posting frequency in business context: {context.get('posting_frequency', 'Not set')}")
            
        except Exception as e:
            logger.error(f"Error extracting business context: {e}")
            state.error_message = f"Failed to extract business context: {str(e)}"
            
        return state
    
    async def cleanup_existing_content(self, user_id: str) -> None:
        """Delete existing content for the user, but only delete draft posts. Preserve all other statuses (approved, scheduled, published, etc.)"""
        try:
            # Get all campaigns for the user
            campaigns_response = self.supabase.table("content_campaigns").select("id").eq("user_id", user_id).execute()
            
            if campaigns_response.data:
                campaign_ids = [campaign["id"] for campaign in campaigns_response.data]
                
                # Only delete posts with 'draft' status. Preserve all other statuses.
                for campaign_id in campaign_ids:
                    # Get all draft posts for this campaign
                    draft_posts_response = self.supabase.table("content_posts").select("id, status").eq("campaign_id", campaign_id).eq("status", "draft").execute()
                    
                    if draft_posts_response.data:
                        posts_to_delete = [post["id"] for post in draft_posts_response.data]
                        
                        if posts_to_delete:
                            logger.info(f"Deleting {len(posts_to_delete)} draft posts for campaign {campaign_id}")
                            
                            # Delete draft posts
                            self.supabase.table("content_posts").delete().in_("id", posts_to_delete).execute()
                            
                            # Delete associated images for deleted posts
                            self.supabase.table("content_images").delete().in_("post_id", posts_to_delete).execute()
                
                # Delete campaigns that have no posts remaining (only if all posts were drafts)
                for campaign_id in campaign_ids:
                    # Check if campaign has any posts remaining (any status)
                    remaining_posts_response = self.supabase.table("content_posts").select("id").eq("campaign_id", campaign_id).execute()
                    
                    if not remaining_posts_response.data:
                        # No posts remaining, safe to delete the campaign
                        logger.info(f"Deleting campaign {campaign_id} as it has no posts remaining")
                        self.supabase.table("content_campaigns").delete().eq("id", campaign_id).execute()
            
        except Exception as e:
            logger.error(f"Error cleaning up existing content: {e}")
            # Don't raise exception, just log the error and continue

    async def initialize_content_campaign(self, state: ContentState) -> ContentState:
        """Initialize content campaign in Supabase"""
        try:
            user_id = state.user_profile.get('user_id')
            
            # Clean up existing content first
            await self.cleanup_existing_content(user_id)
            
            # Update progress
            await self.update_progress(
                user_id, 
                "initializing", 
                5, 
                "Initializing content campaign..."
            )
            
            # Calculate campaign dates - start from today and go 30 days forward
            today = datetime.now()
            month_start = today
            month_end = today + timedelta(days=29)
            
            # Calculate total posts based on posting frequency
            posting_frequency = state.business_context.get("posting_frequency", "daily")
            posting_schedule = self.calculate_posting_schedule(posting_frequency)
            posts_per_platform = len(posting_schedule)
            
            campaign_data = {
                "user_id": user_id,
                "campaign_name": f"Monthly Content - {month_start.strftime('%Y-%m-%d')}",
                "week_start_date": month_start.strftime('%Y-%m-%d'),
                "week_end_date": month_end.strftime('%Y-%m-%d'),
                "status": "generating",
                "total_posts": len(state.platforms) * posts_per_platform,
                "generated_posts": 0
            }
            
            # Insert campaign
            campaign_response = self.supabase.table("content_campaigns").insert(campaign_data).execute()
            
            if campaign_response.data:
                campaign_data = campaign_response.data[0]
                state.campaign = ContentCampaign(**campaign_data)
                
                # Update progress with campaign ID
                await self.update_progress(
                    user_id, 
                    "campaign_created", 
                    15, 
                    f"Campaign created: {state.campaign.campaign_name}"
                )
            else:
                raise Exception("Failed to create campaign")
                
        except Exception as e:
            logger.error(f"Error initializing campaign: {e}")
            state.error_message = f"Failed to initialize campaign: {str(e)}"
            
        return state
    
    async def check_more_platforms(self, state: ContentState) -> ContentState:
        """Check if there are more platforms to process"""
        return state
    
    def should_continue_platforms(self, state: ContentState) -> str:
        """Check if there are more platforms to process"""
        if state.current_platform_index < len(state.platforms):
            return "continue"
        return "complete"
    
    async def select_next_platform(self, state: ContentState) -> ContentState:
        """Select the next platform to process"""
        if state.current_platform_index < len(state.platforms):
            state.current_platform = state.platforms[state.current_platform_index]
            state.current_platform_retries = 0
            state.platform_content = []  # Clear previous platform content
        return state
    
    async def load_platform_specific_context(self, state: ContentState) -> ContentState:
        """Load platform-specific context and preferences"""
        try:
            # Platform-specific context loading can be implemented here if needed
            pass
        except Exception as e:
            logger.error(f"Error loading platform context: {e}")
            state.error_message = f"Failed to load platform context: {str(e)}"
            
        return state
    
    async def generate_platform_content(self, state: ContentState) -> ContentState:
        """Generate content for the current platform"""
        try:
            platform = state.current_platform
            platform_lower = platform.lower()
            
            # Get platform config with fallback
            platform_config = PLATFORM_GENERATORS.get(platform_lower, {
                "post_types": ["text", "image"],
                "max_length": 1000,
                "optimal_length": 150,
                "hashtag_limit": 5,
                "image_requirements": {
                    "sizes": ["1080x1080"],
                    "preferred_styles": ["realistic"],
                    "max_images_per_post": 1
                }
            })
            
            business_context = state.business_context
            
            
            # Update progress
            user_id = state.user_profile.get('user_id')
            progress_percentage = 20 + (state.current_platform_index * 60 // len(state.platforms))
            await self.update_progress(
                user_id, 
                "generating_content", 
                progress_percentage, 
                f"Starting content generation for {platform}...",
                platform
            )
            
            # Calculate posting schedule based on user preference
            posting_frequency = business_context.get("posting_frequency", "daily")
            posting_schedule = self.calculate_posting_schedule(posting_frequency)
            
            # Generate content for each scheduled post
            content_posts = []
            
            for i, schedule_item in enumerate(posting_schedule):
                try:
                    
                    # Update progress for individual post generation - only show platform name, not post count
                    if self.progress_callback:
                        await self.progress_callback(
                            user_id,
                            "generating_content",
                            int(20 + (i / len(posting_schedule)) * 60),  # 20-80% range
                            f"Generating content for {platform}",
                            platform
                        )
                    
                        post = await self.generate_single_post(
                        platform=platform,
                        platform_config=platform_config,
                        business_context=business_context,
                        post_index=schedule_item["post_index"],
                        scheduled_date=schedule_item["scheduled_date"],
                        scheduled_time=schedule_item["scheduled_time"],
                        user_id=user_id,
                        campaign_id=state.campaign_id if hasattr(state, 'campaign_id') else None
                    )
                    
                    if post:
                        content_posts.append(post)
                        
                        # Update progress after successful post generation - only update percentage
                        if self.progress_callback:
                            await self.progress_callback(
                                user_id,
                                "generating_content",
                                int(20 + ((i + 1) / len(posting_schedule)) * 60),
                                None,  # Don't send duplicate message
                                platform
                            )
                    else:
                        logger.warning(f"Failed to generate post {i+1}")
                except Exception as e:
                    logger.error(f"Error generating post {i+1}: {e}")
                    continue
            
            state.platform_content = content_posts
            
        except Exception as e:
            logger.error(f"Error generating platform content: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            state.error_message = f"Failed to generate content for {state.current_platform}: {str(e)}"
            
        return state
    
    async def generate_single_post(self, platform: str, platform_config: dict, 
                                 business_context: dict, post_index: int, 
                                 scheduled_date: str, scheduled_time: str,
                                 user_id: str = None, campaign_id: str = None) -> ContentPost:
        """Generate a single post for a specific platform"""
        try:
            # Get content template for platform
            template_response = self.supabase.table("content_templates").select("*").eq("platform", platform).eq("is_active", True).execute()
            
            if template_response.data:
                template = template_response.data[0]
                template_prompt = template["template_prompt"]
            else:
                # Default template
                template_prompt = "Create engaging content for {business_name} on {platform}. Make it relevant to {industry} industry."
            
            # Format template with business context
            # Handle missing keys with defaults
            industry = business_context.get("industry", ["Business"])
            industry_str = ", ".join(industry) if isinstance(industry, list) else str(industry)
            
            formatted_prompt = template_prompt.format(
                business_name=business_context.get("business_name", "Your Business"),
                platform=platform,
                industry=industry_str,
                brand_voice=business_context.get("brand_voice", "professional"),
                brand_tone=business_context.get("brand_tone", "friendly"),
                topic=self.get_topic_for_day(post_index, business_context)
            )
            
            # Build prompt using embeddings if available
            from utils.embedding_context import build_embedding_prompt
            
            task_description = f"""
            {formatted_prompt}
            
            Platform Requirements:
            - Platform: {platform}
            - Max Length: {platform_config['max_length']} characters
            - Optimal Length: {platform_config['optimal_length']} characters
            - Hashtag Limit: {platform_config['hashtag_limit']}
            - Post Index: {post_index}
            - Scheduled Date: {scheduled_date}
            
            Content Theme for this post: {self.get_content_theme_for_day(post_index, business_context.get('content_themes', []), business_context)}
            
            Please generate content that:
            1. Matches the brand voice and tone
            2. Is appropriate for the platform
            3. Engages the target audience
            4. Incorporates the business description, unique value proposition, and products/services naturally
            5. Highlights what makes the business unique and valuable
            6. Focuses on the specific content theme provided above
            7. Creates unique, non-repetitive content that stands out
            8. Varies the approach, angle, and style from previous posts
            9. Includes relevant hashtags (within limit)
            10. Is optimized for the platform's character limits
            
            Return your response as a valid JSON object with this structure:
            {{
                "content": "Your generated content here",
                "hashtags": ["hashtag1", "hashtag2", "hashtag3"],
                "post_type": "text",
                "title": "Optional title if needed"
            }}
            """
            
            # Use embedding-aware prompt builder
            full_prompt = build_embedding_prompt(
                context=business_context,
                task_description=task_description,
                additional_requirements=f"Platform: {platform}, Post Index: {post_index}, Scheduled Date: {scheduled_date}"
            )
            
            # Call OpenAI API with timeout
            response = await asyncio.wait_for(
                self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=platform_config['max_length'],
                temperature=0.7
                ),
                timeout=30.0  # 30 second timeout
            )
            
            # Track token usage
            if user_id:
                await self.token_tracker.track_chat_completion_usage(
                    user_id=user_id,
                    feature_type="content_generation",
                    model_name="gpt-4o-mini",
                    response=response,
                    request_metadata={
                        "platform": platform,
                        "post_index": post_index,
                        "campaign_id": campaign_id,
                        "scheduled_date": scheduled_date,
                        "scheduled_time": scheduled_time
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
                content_data = json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed: {e}")
                # Fallback if JSON parsing fails
                content_data = {
                    "content": raw_response,
                    "hashtags": [],
                    "post_type": "text",
                    "title": None
                }
            
            return ContentPost(
                platform=platform,
                post_type=PostType(content_data.get("post_type", "text")),
                title=content_data.get("title"),
                content=content_data["content"],
                hashtags=content_data.get("hashtags", [])[:platform_config['hashtag_limit']],
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                metadata={
                    "generated_by": "emily_agent",
                    "post_index": post_index,
                    "posting_frequency": business_context.get("posting_frequency", "daily"),
                    "template_used": template.get("template_name", "default") if template_response.data else "default"
                }
            )
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout generating post for {platform} - API call took too long")
            return None
        except Exception as e:
            logger.error(f"Error generating single post for {platform}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    
    
    async def validate_platform_content(self, state: ContentState) -> ContentState:
        """Validate generated content for the current platform"""
        try:
            platform = state.current_platform
            platform_lower = platform.lower()
            
            # Get platform config with fallback
            platform_config = PLATFORM_GENERATORS.get(platform_lower, {
                "post_types": ["text", "image"],
                "max_length": 1000,
                "optimal_length": 150,
                "hashtag_limit": 5,
                "image_requirements": {
                    "sizes": ["1080x1080"],
                    "preferred_styles": ["realistic"],
                    "max_images_per_post": 1
                }
            })
            
            # Basic validation
            is_valid = True
            for post in state.platform_content:
                if len(post.content) > platform_config['max_length']:
                    is_valid = False
                    logger.warning(f"Post too long for {platform}: {len(post.content)} chars")
                    break
                    
                if len(post.hashtags) > platform_config['hashtag_limit']:
                    is_valid = False
                    logger.warning(f"Too many hashtags for {platform}: {len(post.hashtags)}")
                    break
            
            if not is_valid:
                logger.warning(f"Content validation failed for {platform}")
                
        except Exception as e:
            logger.error(f"Error validating content: {e}")
            is_valid = False
            
        return state
    
    def is_content_valid(self, state: ContentState) -> str:
        """Check if generated content is valid"""
        if state.platform_content and len(state.platform_content) > 0:
            # Calculate expected number of posts based on posting frequency
            posting_frequency = state.business_context.get("posting_frequency", "daily")
            expected_posts = len(self.calculate_posting_schedule(posting_frequency))
            actual_posts = len(state.platform_content)
            
            # Accept content if we have at least 50% of expected posts
            min_required = max(1, expected_posts // 2)
            
            if actual_posts >= min_required:
                return "valid"
            else:
                logger.warning(f"Too few posts: got {actual_posts}, need at least {min_required} for {posting_frequency} frequency")
                return "invalid"
        return "invalid"
    
    async def should_retry_platform(self, state: ContentState) -> ContentState:
        """Check if we should retry the current platform"""
        return state
    
    def should_retry_platform_decision(self, state: ContentState) -> str:
        """Decision function for retry logic"""
        if state.current_platform_retries < state.max_retries_per_platform:
            return "retry"
        return "skip"
    
    async def refine_platform_content(self, state: ContentState) -> ContentState:
        """Refine content for the current platform"""
        try:
            state.current_platform_retries += 1
            
            # Re-generate content with more specific instructions
            platform = state.current_platform
            platform_lower = platform.lower()
            
            # Get platform config with fallback
            platform_config = PLATFORM_GENERATORS.get(platform_lower, {
                "post_types": ["text", "image"],
                "max_length": 1000,
                "optimal_length": 150,
                "hashtag_limit": 5,
                "image_requirements": {
                    "sizes": ["1080x1080"],
                    "preferred_styles": ["realistic"],
                    "max_images_per_post": 1
                }
            })
            business_context = state.business_context
            
            # Calculate posting schedule based on user preference
            posting_frequency = business_context.get("posting_frequency", "daily")
            posting_schedule = self.calculate_posting_schedule(posting_frequency)
            
            # Generate refined content
            content_posts = []
            user_id = state.user_profile.get('user_id')
            for schedule_item in posting_schedule:
                post = await self.generate_single_post(
                    platform=platform,
                    platform_config=platform_config,
                    business_context=business_context,
                    post_index=schedule_item["post_index"],
                    scheduled_date=schedule_item["scheduled_date"],
                    scheduled_time=schedule_item["scheduled_time"],
                    user_id=user_id,
                    campaign_id=state.campaign_id if hasattr(state, 'campaign_id') else None
                )
                content_posts.append(post)
            
            state.platform_content = content_posts
            
        except Exception as e:
            logger.error(f"Error refining content: {e}")
            state.error_message = f"Failed to refine content for {state.current_platform}: {str(e)}"
            
        return state
    
    async def store_platform_content(self, state: ContentState) -> ContentState:
        """Store content for the current platform in Supabase"""
        try:
            platform = state.current_platform
            campaign_id = state.campaign.id
            
            # Store each post
            for post in state.platform_content:
                # Prepare post data
                post_data = {
                    "campaign_id": campaign_id,
                    "platform": post.platform,
                    "post_type": post.post_type.value,
                    "title": post.title,
                    "content": post.content,
                    "hashtags": post.hashtags,
                    "scheduled_date": post.scheduled_date,
                    "scheduled_time": post.scheduled_time,
                    "status": "draft",
                    "metadata": post.metadata
                }
                
                # Insert post
                post_response = self.supabase.table("content_posts").insert(post_data).execute()
                
                if post_response.data:
                    post_id = post_response.data[0]["id"]
                    
            
            # Update campaign progress
            self.supabase.table("content_campaigns").update({
                "generated_posts": state.campaign.generated_posts + len(state.platform_content)
            }).eq("id", campaign_id).execute()
            
            # Add to all content
            state.all_content.extend(state.platform_content)
            state.completed_platforms.append(platform)
            
        except Exception as e:
            logger.error(f"Error storing platform content: {e}")
            state.error_message = f"Failed to store content for {state.current_platform}: {str(e)}"
            
        return state
    
    async def mark_platform_complete(self, state: ContentState) -> ContentState:
        """Mark current platform as complete and move to next"""
        # Add current platform to completed list
        if state.current_platform:
            state.completed_platforms.append(state.current_platform)
        
        # Move to next platform
        state.current_platform_index += 1
        state.platform_content = []  # Clear for next platform
        state.current_platform = None  # Reset current platform
        
        return state
    
    async def generate_weekly_summary(self, state: ContentState) -> ContentState:
        """Generate monthly summary of created content"""
        try:
            total_posts = len(state.all_content)
            platforms_used = list(set([post.platform for post in state.all_content]))
            
            # Handle case where campaign is None
            campaign_name = state.campaign.campaign_name if state.campaign else "No Campaign"
            
            summary = f"""
            Monthly Content Generation Complete!
            
            Campaign: {campaign_name}
            Total Posts Generated: {total_posts}
            Platforms: {', '.join(platforms_used)}
            Completed Platforms: {', '.join(state.completed_platforms)}
            Failed Platforms: {', '.join(state.failed_platforms)}
            
            Content is ready for review and scheduling.
            """
            
            state.weekly_summary = summary
            state.success = True
            
            # Update campaign status only if campaign exists
            if state.campaign and state.campaign.id:
                self.supabase.table("content_campaigns").update({
                    "status": "completed"
                }).eq("id", state.campaign.id).execute()
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            state.error_message = f"Failed to generate summary: {str(e)}"
            
        return state
    
    async def send_notification(self, state: ContentState) -> ContentState:
        """Send notification about completed content generation"""
        try:
            # Here you would integrate with your notification system
            # For now, just log the completion
            pass
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            
        return state
    
    # Helper methods
    def get_topic_for_day(self, post_index: int, business_context: dict = None) -> str:
        """Get topic for specific post index"""
        # Use business context to get more specific topics
        if not business_context:
            business_context = getattr(self, 'current_business_context', {})
        
        business_name = business_context.get('business_name', 'Your Business')
        industry = business_context.get('industry', ['Business'])
        industry_str = ', '.join(industry) if isinstance(industry, list) else industry
        
        # Create business-specific topics
        topics = [
            f"insights about {industry_str} industry",
            f"tips for {business_name} customers",
            f"trends in {industry_str}",
            f"behind the scenes at {business_name}",
            f"success stories from {business_name}",
            f"educational content about {industry_str}",
            f"expertise in {industry_str}",
            f"innovation in {industry_str}",
            f"best practices for {industry_str}",
            f"customer success with {business_name}",
            f"industry updates and news",
            f"professional insights from {business_name}"
        ]
        return topics[post_index % len(topics)]
    
    def get_content_theme_for_day(self, post_index: int, content_themes: list, business_context: dict = None) -> str:
        """Get content theme for specific post, cycling through available themes"""
        if not content_themes:
            # Use business context to get more specific themes
            if not business_context:
                business_context = getattr(self, 'current_business_context', {})
            business_name = business_context.get('business_name', 'Your Business')
            industry = business_context.get('industry', ['Business'])
            return f"content relevant to {business_name} in the {', '.join(industry) if isinstance(industry, list) else industry} industry"
        
        # Cycle through themes based on post index
        theme_index = post_index % len(content_themes)
        selected_theme = content_themes[theme_index]
        
        # Add variation to make each post unique
        variations = [
            f"Focus on {selected_theme} with a fresh perspective",
            f"Explore {selected_theme} from a new angle",
            f"Share insights about {selected_theme}",
            f"Highlight the importance of {selected_theme}",
            f"Showcase expertise in {selected_theme}",
            f"Provide value through {selected_theme}",
            f"Connect with audience through {selected_theme}"
        ]
        
        variation_index = post_index % len(variations)
        return variations[variation_index]
    
    def calculate_posting_schedule(self, posting_frequency: str) -> List[Dict[str, Any]]:
        """Calculate posting schedule based on frequency preference"""
        from datetime import datetime, timedelta
        
        today = datetime.now()
        schedule = []
        
        # Normalize posting frequency for comparison
        freq = posting_frequency.lower().strip() if posting_frequency else "daily"
        
        if freq == "daily":
            # Generate 30 posts for the month (daily)
            for i in range(30):
                post_date = today + timedelta(days=i)
                schedule.append({
                    "post_index": i,
                    "scheduled_date": post_date.strftime('%Y-%m-%d'),
                    "scheduled_time": self.get_optimal_time("facebook"),  # Default to Facebook time
                    "day_of_month": post_date.day
                })
        
        elif freq == "3 posts a week" or freq == "3 posts per week" or freq == "3/week":
            # Generate 12 posts for the month (3 posts per week × 4 weeks)
            # Schedule on specific days: Mon/Wed/Fri or Tue/Thu/Sat or Wed/Fri/Sun pattern
            posts_per_week = 3
            weeks_in_month = 4
            total_posts = posts_per_week * weeks_in_month  # 12 posts
            
            # Determine posting pattern based on today's day of week
            # 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
            today_weekday = today.weekday()
            
            # Choose pattern: Mon/Wed/Fri (0,2,4), Tue/Thu/Sat (1,3,5), or Wed/Fri/Sun (2,4,6)
            if today_weekday in [0, 2, 4]:  # If today is Mon/Wed/Fri, use Mon/Wed/Fri pattern
                posting_days = [0, 2, 4]  # Monday, Wednesday, Friday
            elif today_weekday in [1, 3, 5]:  # If today is Tue/Thu/Sat, use Tue/Thu/Sat pattern
                posting_days = [1, 3, 5]  # Tuesday, Thursday, Saturday
            else:  # If today is Sunday, use Wed/Fri/Sun pattern
                posting_days = [2, 4, 6]  # Wednesday, Friday, Sunday
            
            post_index = 0
            
            # Generate posts for 4 weeks (12 posts total)
            for week in range(weeks_in_month):
                # Calculate the start of this week (Monday of the week)
                # Find Monday of the current week, then add weeks
                days_since_monday = today.weekday()  # 0=Monday, so this is days since Monday
                monday_of_current_week = today - timedelta(days=days_since_monday)
                week_start = monday_of_current_week + timedelta(days=week * 7)
                
                for day_offset in posting_days:
                    # Calculate the date for this posting day in the current week
                    post_date = week_start + timedelta(days=day_offset)
                    
                    # Only schedule if the date is today or in the future
                    if post_date >= today:
                        # Make sure we don't exceed 30 days from today
                        if (post_date - today).days < 30:
                            schedule.append({
                                "post_index": post_index,
                                "scheduled_date": post_date.strftime('%Y-%m-%d'),
                                "scheduled_time": self.get_optimal_time("facebook"),
                                "day_of_month": post_date.day
                            })
                            post_index += 1
                            
                            if post_index >= total_posts:
                                break
                
                if post_index >= total_posts:
                    break
        
        elif freq == "weekly" or freq == "once a week" or freq == "1/week":
            # Generate 4 posts for the month (weekly)
            for i in range(4):
                post_date = today + timedelta(days=i * 7)
                schedule.append({
                    "post_index": i,
                    "scheduled_date": post_date.strftime('%Y-%m-%d'),
                    "scheduled_time": self.get_optimal_time("facebook"),
                    "day_of_month": post_date.day
                })
        
        elif freq == "bi weekly" or freq == "bi-weekly" or freq == "twice a week" or freq == "2/week":
            # Generate 8 posts for the month (bi-weekly)
            for i in range(8):
                post_date = today + timedelta(days=i * 3.75)  # Distribute across month
                schedule.append({
                    "post_index": i,
                    "scheduled_date": post_date.strftime('%Y-%m-%d'),
                    "scheduled_time": self.get_optimal_time("facebook"),
                    "day_of_month": post_date.day
                })
        
        elif freq == "bi monthly" or freq == "bi-monthly" or freq == "twice a month" or freq == "2/month":
            # Generate 2 posts for the month (bi-monthly)
            for i in range(2):
                post_date = today + timedelta(days=i * 15)
                schedule.append({
                    "post_index": i,
                    "scheduled_date": post_date.strftime('%Y-%m-%d'),
                    "scheduled_time": self.get_optimal_time("facebook"),
                    "day_of_month": post_date.day
                })
        
        elif freq == "monthly" or freq == "once a month" or freq == "1/month":
            # Generate 1 post for the month
            schedule.append({
                "post_index": 0,
                "scheduled_date": today.strftime('%Y-%m-%d'),
                "scheduled_time": self.get_optimal_time("facebook"),
                "day_of_month": today.day
            })
        
        else:
            # Default to daily if unknown frequency
            logger.warning(f"Unknown posting frequency '{posting_frequency}', defaulting to daily")
            for i in range(30):
                post_date = today + timedelta(days=i)
                schedule.append({
                    "post_index": i,
                    "scheduled_date": post_date.strftime('%Y-%m-%d'),
                    "scheduled_time": self.get_optimal_time("facebook"),
                    "day_of_month": post_date.day
                })
        
        return schedule
    
    def get_day_name(self, day_of_week: int) -> str:
        """Get day name for day of week (0=today, 1=tomorrow, etc.)"""
        today = datetime.now()
        target_date = today + timedelta(days=day_of_week)
        return target_date.strftime('%A')
    
    def calculate_date(self, day_of_week: int) -> str:
        """Calculate scheduled date for day of week starting from today"""
        today = datetime.now()
        # day_of_week is 0-6 where 0 is today, 1 is tomorrow, etc.
        scheduled_date = today + timedelta(days=day_of_week)
        return scheduled_date.strftime('%Y-%m-%d')
    
    def get_optimal_time(self, platform: str) -> str:
        """Get optimal posting time for platform"""
        optimal_times = {
            "facebook": "09:00",
            "instagram": "11:00",
            "linkedin": "08:00",
            "twitter": "12:00",
            "youtube": "14:00",
            "twitter/x": "12:00"
        }
        return optimal_times.get(platform, "09:00")
    
    async def run_weekly_generation(self, user_id: str) -> Dict[str, Any]:
        """Run weekly content generation for a user"""
        try:
            # Initialize state
            state = ContentState(
                user_profile={"user_id": user_id},
                platforms=[],
                all_content=[],
                completed_platforms=[],
                failed_platforms=[]
            )
            
            # Run the graph with increased recursion limit
            result = await self.graph.ainvoke(state, config={"recursion_limit": 100})
            
            return {
                "success": result.get("success", True),
                "error_message": result.get("error_message"),
                "weekly_summary": result.get("weekly_summary"),
                "total_posts": len(result.get("all_content", [])),
                "completed_platforms": result.get("completed_platforms", []),
                "failed_platforms": result.get("failed_platforms", [])
            }
            
        except Exception as e:
            logger.error(f"Error running weekly generation: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error_message": str(e),
                "weekly_summary": None,
                "total_posts": 0,
                "completed_platforms": [],
                "failed_platforms": []
            }
