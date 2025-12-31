"""
Ads Creation Agent using LangGraph
Generates weekly ad copy for social media platforms one by one
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
from agents.ads_media_agent import AdsMediaAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    STORY = "story"
    BANNER = "banner"

class ImageStyle(str, Enum):
    REALISTIC = "realistic"
    ARTISTIC = "artistic"
    CARTOON = "cartoon"
    MINIMALIST = "minimalist"
    PHOTOGRAPHIC = "photographic"
    ILLUSTRATION = "illustration"

class AdImage(BaseModel):
    image_url: str
    image_prompt: str
    image_style: ImageStyle
    image_size: str = "1024x1024"
    image_quality: str = "standard"
    generation_model: str = "dall-e-3"
    generation_cost: Optional[float] = None
    generation_time: Optional[int] = None
    is_approved: bool = False

class AdCopy(BaseModel):
    id: str
    title: str
    ad_copy: str
    platform: str
    ad_type: AdType
    call_to_action: str
    target_audience: str
    budget_range: str
    campaign_objective: str
    scheduled_at: datetime
    status: str = "draft"
    created_at: datetime
    media_url: Optional[str] = None
    hashtags: List[str] = []
    metadata: Dict[str, Any] = {}
    campaign_id: str
    ad_images: List[AdImage] = []

class AdCampaign(BaseModel):
    id: str
    user_id: str
    campaign_name: str
    campaign_objective: str
    target_audience: str
    budget_range: str
    platforms: List[str]
    start_date: datetime
    end_date: datetime
    status: str = "draft"
    created_at: datetime
    total_ads: int = 0
    approved_ads: int = 0
    metadata: Dict[str, Any] = {}

class AdCreationState(BaseModel):
    user_id: str
    profile: Optional[Dict[str, Any]] = None
    platforms: Optional[List[str]] = None
    current_platform: Optional[str] = None
    ads: List[AdCopy] = []
    current_ad: Optional[AdCopy] = None
    campaign: Optional[AdCampaign] = None
    error: Optional[str] = None
    progress: int = 0
    total_platforms: int = 0
    completed_platforms: int = 0

class AdsCreationAgent:
    def __init__(self, supabase_url: str, supabase_key: str, openai_api_key: str):
        self.supabase = create_client(supabase_url, supabase_key)
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.media_agent = AdsMediaAgent(supabase_url, supabase_key, openai_api_key)
        from services.token_usage_service import TokenUsageService
        self.token_tracker = TokenUsageService(supabase_url, supabase_key)
        self.graph = self._build_graph()
    
    def get_supabase_admin(self):
        """Get Supabase admin client for database operations"""
        import os
        return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for ads creation"""
        workflow = StateGraph(AdCreationState)
        
        # Add nodes
        workflow.add_node("initialize", self._initialize)
        workflow.add_node("create_campaign", self._create_campaign)
        workflow.add_node("select_platform", self._select_platform)
        workflow.add_node("generate_ad_copy", self._generate_ad_copy)
        workflow.add_node("generate_ad_image", self._generate_ad_image)
        workflow.add_node("save_ad", self._save_ad)
        workflow.add_node("check_platforms", self._check_platforms)
        workflow.add_node("finalize_campaign", self._finalize_campaign)
        workflow.add_node("error_handler", self._error_handler)
        
        # Add edges
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "create_campaign")
        workflow.add_edge("create_campaign", "select_platform")
        workflow.add_edge("select_platform", "generate_ad_copy")
        workflow.add_edge("generate_ad_copy", "generate_ad_image")
        workflow.add_edge("generate_ad_image", "save_ad")
        workflow.add_edge("save_ad", "check_platforms")
        workflow.add_conditional_edges(
            "check_platforms",
            self._should_continue,
            {
                "continue": "select_platform",
                "finish": "finalize_campaign",
                "error": "error_handler"
            }
        )
        workflow.add_edge("finalize_campaign", END)
        workflow.add_edge("error_handler", END)
        
        return workflow.compile()
    
    async def _initialize(self, state: AdCreationState) -> AdCreationState:
        """Initialize the ads creation process"""
        try:
            logger.info(f"Initializing ads creation for user: {state.user_id}")
            
            # Get user profile
            supabase_admin = self.get_supabase_admin()
            profile_response = supabase_admin.table("profiles").select("*").eq("id", state.user_id).execute()
            if not profile_response.data:
                state.error = "User profile not found"
                return state
            
            state.profile = profile_response.data[0]
            state.platforms = state.profile.get("social_media_platforms", [])
            state.total_platforms = len(state.platforms)
            state.completed_platforms = 0
            state.progress = 5
            
            logger.info(f"Found {len(state.platforms)} platforms: {state.platforms}")
            return state
            
        except Exception as e:
            logger.error(f"Error in initialize: {e}")
            state.error = str(e)
            return state
    
    async def _create_campaign(self, state: AdCreationState) -> AdCreationState:
        """Create a new ad campaign"""
        try:
            logger.info("Creating ad campaign")
            
            # Generate campaign name
            campaign_name = f"Weekly Ads Campaign - {datetime.now().strftime('%B %Y')}"
            
            # Create campaign with proper UUID
            import uuid
            campaign_id = str(uuid.uuid4())
            campaign_data = {
                "id": campaign_id,
                "user_id": state.user_id,
                "campaign_name": campaign_name,
                "campaign_objective": state.profile.get("primary_goals", ["brand_awareness"])[0],
                "target_audience": ", ".join(state.profile.get("target_audience", ["general"])),
                "budget_range": state.profile.get("monthly_budget_range", "medium"),
                "platforms": state.platforms,
                "start_date": datetime.now().isoformat(),
                "end_date": (datetime.now() + timedelta(days=7)).isoformat(),
                "status": "draft",
                "created_at": datetime.now().isoformat(),
                "total_ads": 0,
                "approved_ads": 0,
                "metadata": {
                    "generated_by": "ads_creation_agent",
                    "generation_date": datetime.now().isoformat(),
                    "user_profile": state.profile
                }
            }
            
            # Save to database
            supabase_admin = self.get_supabase_admin()
            campaign_response = supabase_admin.table("ad_campaigns").insert(campaign_data).execute()
            if campaign_response.data:
                state.campaign = AdCampaign(**campaign_response.data[0])
                logger.info(f"Created campaign: {state.campaign.id}")
            else:
                state.error = "Failed to create campaign"
                return state
            
            state.progress = 10
            return state
            
        except Exception as e:
            logger.error(f"Error in create_campaign: {e}")
            state.error = str(e)
            return state
    
    async def _select_platform(self, state: AdCreationState) -> AdCreationState:
        """Select the next platform to generate ads for"""
        try:
            if state.completed_platforms >= len(state.platforms):
                return state
            
            state.current_platform = state.platforms[state.completed_platforms]
            logger.info(f"Selected platform: {state.current_platform}")
            
            state.progress = 15 + (state.completed_platforms * 15)
            return state
            
        except Exception as e:
            logger.error(f"Error in select_platform: {e}")
            state.error = str(e)
            return state
    
    async def _generate_ad_copy(self, state: AdCreationState) -> AdCreationState:
        """Generate ad copy for the current platform"""
        try:
            logger.info(f"Generating ad copy for {state.current_platform}")
            
            # Create platform-specific prompt
            platform_prompts = {
                "facebook": "Create engaging Facebook ad copy that drives engagement and conversions",
                "instagram": "Create visually appealing Instagram ad copy with relevant hashtags",
                "linkedin": "Create professional LinkedIn ad copy for B2B audience",
                "twitter": "Create concise Twitter ad copy that captures attention",
                "youtube": "Create compelling YouTube ad copy for video content",
                "tiktok": "Create trendy TikTok ad copy that resonates with younger audience"
            }
            
            platform_prompt = platform_prompts.get(state.current_platform, "Create effective ad copy")
            
            # Build the main prompt
            prompt = f"""
You are an expert digital marketing copywriter specializing in {state.current_platform} advertising.

Business Information:
- Business Name: {state.profile.get('business_name', 'Our Business')}
- Business Type: {', '.join(state.profile.get('business_type', []))}
- Industry: {', '.join(state.profile.get('industry', []))}
- Business Description: {state.profile.get('business_description', '')}
- Target Audience: {', '.join(state.profile.get('target_audience', []))}
- Brand Voice: {state.profile.get('brand_voice', 'professional')}
- Brand Tone: {state.profile.get('brand_tone', 'friendly')}
- Unique Value Proposition: {state.profile.get('unique_value_proposition', '')}
- Primary Goals: {', '.join(state.profile.get('primary_goals', []))}
- Budget Range: {state.profile.get('monthly_budget_range', 'medium')}

Platform: {state.current_platform}
Objective: {platform_prompt}

Create 3 different ad copy variations for {state.current_platform} that:
1. Align with the brand voice and tone
2. Target the specified audience
3. Include compelling call-to-action
4. Are optimized for the platform's format
5. Drive the primary business goals
6. Include relevant hashtags (if applicable)
7. Are within character limits for the platform

For each ad copy, provide:
- Title (catchy headline)
- Ad Copy (main content)
- Call to Action (specific action)
- Target Audience (refined audience)
- Budget Range (suggested spend)
- Campaign Objective (specific goal)
- Hashtags (platform-appropriate)
- Ad Type (text, image, video, carousel, story, banner)

Return the response as a JSON array with 3 ad copy objects.
"""

            # Generate ad copy using OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert digital marketing copywriter. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Track token usage
            user_id = state.profile.get("user_id") if state.profile else None
            if user_id and self.token_tracker:
                await self.token_tracker.track_chat_completion_usage(
                    user_id=user_id,
                    feature_type="ads_creation",
                    model_name="gpt-4o-mini",
                    response=response,
                    request_metadata={
                        "platform": state.current_platform,
                        "campaign_id": state.campaign_id if hasattr(state, 'campaign_id') else None
                    }
                )
            
            # Parse the response
            try:
                response_content = response.choices[0].message.content
                logger.info(f"OpenAI response: {response_content[:200]}...")
                
                ad_copy_data = json.loads(response_content)
                if not isinstance(ad_copy_data, list) or len(ad_copy_data) == 0:
                    raise ValueError("Invalid response format from OpenAI")
                    
                logger.info(f"Parsed {len(ad_copy_data)} ad copies")
            except (json.JSONDecodeError, ValueError, IndexError) as e:
                logger.error(f"Error parsing OpenAI response: {e}")
                logger.error(f"Response content: {response_content if 'response_content' in locals() else 'No content'}")
                # Create fallback ad copy
                ad_copy_data = [{
                    "title": f"Ad for {state.current_platform}",
                    "ad_copy": f"Engaging content for {state.current_platform}",
                    "call_to_action": "Learn More",
                    "target_audience": state.profile.get("target_audience", ["general"])[0],
                    "budget_range": state.profile.get("monthly_budget_range", "medium"),
                    "campaign_objective": state.profile.get("primary_goals", ["brand_awareness"])[0],
                    "hashtags": [],
                    "ad_type": "text"
                }]
            
            # Create AdCopy objects for this platform
            platform_ads = []
            for i, ad_data in enumerate(ad_copy_data):
                try:
                    import uuid
                    
                    logger.info(f"Processing ad {i+1} for {state.current_platform}: {ad_data}")
                    
                    # Map different field names from OpenAI response
                    title = ad_data.get("title") or ad_data.get("Title", f"Ad {i+1}")
                    ad_copy_text = ad_data.get("ad_copy") or ad_data.get("Ad Copy", "")
                    call_to_action = ad_data.get("call_to_action") or ad_data.get("Call to Action", "Learn More")
                    
                    # Safe access to profile fields with fallbacks
                    profile_target_audience = state.profile.get("target_audience", [])
                    if not profile_target_audience or len(profile_target_audience) == 0:
                        profile_target_audience = ["general"]
                    
                    profile_goals = state.profile.get("primary_goals", [])
                    if not profile_goals or len(profile_goals) == 0:
                        profile_goals = ["brand_awareness"]
                    
                    target_audience = ad_data.get("target_audience") or ad_data.get("Target Audience", profile_target_audience[0])
                    budget_range = ad_data.get("budget_range") or ad_data.get("Budget Range", state.profile.get("monthly_budget_range", "medium"))
                    campaign_objective = ad_data.get("campaign_objective") or ad_data.get("Campaign Objective", profile_goals[0])
                    hashtags_raw = ad_data.get("hashtags") or ad_data.get("Hashtags", [])
                    # Ensure hashtags is a list
                    if isinstance(hashtags_raw, str):
                        hashtags = [tag.strip() for tag in hashtags_raw.split() if tag.strip()]
                    elif isinstance(hashtags_raw, list):
                        hashtags = hashtags_raw
                    else:
                        hashtags = []
                    ad_type_raw = ad_data.get("ad_type") or ad_data.get("Ad Type", "text")
                    # Normalize ad type to lowercase and map common variations
                    ad_type_mapping = {
                        "image": "image",
                        "video": "video", 
                        "carousel": "carousel",
                        "banner": "image",
                        "story": "image",
                        "text": "text"
                    }
                    ad_type = ad_type_mapping.get(ad_type_raw.lower(), "text")
                    
                    logger.info(f"Processed fields for ad {i+1}: title={title}, ad_copy={ad_copy_text[:50]}...")
                    
                    ad_copy = AdCopy(
                        id=str(uuid.uuid4()),
                        title=title,
                        ad_copy=ad_copy_text,
                        platform=state.current_platform,
                        ad_type=AdType(ad_type),
                        call_to_action=call_to_action,
                        target_audience=target_audience,
                        budget_range=budget_range,
                        campaign_objective=campaign_objective,
                        scheduled_at=datetime.now() + timedelta(days=i),
                        status="draft",
                        created_at=datetime.now(),
                        hashtags=hashtags,
                        metadata={
                            "generated_by": "ads_creation_agent",
                            "platform": state.current_platform,
                            "generation_date": datetime.now().isoformat(),
                            "ad_variation": i + 1
                        },
                        campaign_id=state.campaign.id
                    )
                    platform_ads.append(ad_copy)
                    logger.info(f"Successfully created ad {i+1} for {state.current_platform}")
                    
                except Exception as e:
                    logger.error(f"Error processing ad {i+1}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Add platform ads to state
            state.ads.extend(platform_ads)
            
            state.progress = 20 + (state.completed_platforms * 15)
            return state
            
        except Exception as e:
            logger.error(f"Error in generate_ad_copy: {e}")
            state.error = str(e)
            return state
    
    async def _generate_ad_image(self, state: AdCreationState) -> AdCreationState:
        """Generate images for the current ad using media agent"""
        try:
            logger.info(f"Generating ad image for {state.current_platform}")
            
            if not state.ads:
                return state
            
            current_ad = state.ads[-1]  # Get the last created ad
            
            # Use media agent to generate and upload image
            media_result = await self.media_agent.generate_media_for_ad(
                user_id=state.user_id,
                ad_id=current_ad.id
            )
            
            if media_result["success"]:
                # Update ad with media URL
                current_ad.media_url = media_result["media_url"]
                
                # Create AdImage object for tracking
                ad_image = AdImage(
                    image_url=media_result["media_url"],
                    image_prompt=media_result["metadata"].get("image_prompt", ""),
                    image_style=ImageStyle.PHOTOGRAPHIC,
                    image_size="1024x1024",
                    image_quality="standard",
                    generation_model="dall-e-3",
                    is_approved=False
                )
                
                current_ad.ad_images.append(ad_image)
                logger.info(f"Image generated and uploaded: {media_result['media_url']}")
            else:
                logger.warning(f"Image generation failed: {media_result.get('error')}")
            
            state.progress = 25 + (state.completed_platforms * 15)
            return state
            
        except Exception as e:
            logger.error(f"Error in generate_ad_image: {e}")
            # Don't fail the entire process if image generation fails
            logger.warning("Image generation failed, continuing without image")
            return state
    
    async def _save_ad(self, state: AdCreationState) -> AdCreationState:
        """Save the current ad to the database"""
        try:
            logger.info(f"Saving ad for {state.current_platform}")
            
            if not state.ads:
                return state
            
            # Get ads for current platform
            platform_ads = [ad for ad in state.ads if ad.platform == state.current_platform]
            logger.info(f"Saving {len(platform_ads)} ads for {state.current_platform}")
            
            for current_ad in platform_ads:
                # Prepare ad data for database
                ad_data = {
                    "id": current_ad.id,
                    "title": current_ad.title,
                    "ad_copy": current_ad.ad_copy,
                    "platform": current_ad.platform,
                    "ad_type": current_ad.ad_type.value,
                    "call_to_action": current_ad.call_to_action,
                    "target_audience": current_ad.target_audience,
                    "budget_range": current_ad.budget_range,
                    "campaign_objective": current_ad.campaign_objective,
                    "scheduled_at": current_ad.scheduled_at.isoformat(),
                    "status": current_ad.status,
                    "created_at": current_ad.created_at.isoformat(),
                    "media_url": current_ad.media_url,
                    "hashtags": current_ad.hashtags,
                    "metadata": current_ad.metadata,
                    "campaign_id": current_ad.campaign_id
                }
                
                # Save ad to database
                supabase_admin = self.get_supabase_admin()
                ad_response = supabase_admin.table("ad_copies").insert(ad_data).execute()
                
                if ad_response.data:
                    logger.info(f"Saved ad: {current_ad.id}")
                    
                    # Save ad images if any
                    for i, ad_image in enumerate(current_ad.ad_images):
                        import uuid
                        image_data = {
                            "id": str(uuid.uuid4()),
                            "ad_id": current_ad.id,
                            "image_url": ad_image.image_url,
                            "image_prompt": ad_image.image_prompt,
                            "image_style": ad_image.image_style.value,
                            "image_size": ad_image.image_size,
                            "image_quality": ad_image.image_quality,
                            "generation_model": ad_image.generation_model,
                            "generation_service": "openai_dalle",  # Ads use DALL-E
                            "generation_cost": ad_image.generation_cost,
                            "generation_time": ad_image.generation_time,
                            "is_approved": ad_image.is_approved,
                            "created_at": datetime.now().isoformat()
                        }
                        
                        supabase_admin.table("ad_images").insert(image_data).execute()
                else:
                    logger.error(f"Failed to save ad: {current_ad.id}")
            
            state.progress = 30 + (state.completed_platforms * 15)
            return state
            
        except Exception as e:
            logger.error(f"Error in save_ad: {e}")
            state.error = str(e)
            return state
    
    async def _check_platforms(self, state: AdCreationState) -> AdCreationState:
        """Check if we need to continue with more platforms"""
        try:
            state.completed_platforms += 1
            logger.info(f"Completed platform {state.completed_platforms}/{state.total_platforms}")
            
            if state.completed_platforms >= state.total_platforms:
                state.progress = 90
                return state
            else:
                state.progress = 35 + (state.completed_platforms * 15)
                return state
                
        except Exception as e:
            logger.error(f"Error in check_platforms: {e}")
            state.error = str(e)
            return state
    
    async def _finalize_campaign(self, state: AdCreationState) -> AdCreationState:
        """Finalize the campaign and update statistics"""
        try:
            logger.info("Finalizing campaign")
            
            # Update campaign statistics
            total_ads = len(state.ads)
            approved_ads = len([ad for ad in state.ads if ad.status == "approved"])
            
            campaign_update = {
                "total_ads": total_ads,
                "approved_ads": approved_ads,
                "status": "completed",
                "metadata": {
                    **state.campaign.metadata,
                    "total_ads_generated": total_ads,
                    "platforms_processed": state.platforms,
                    "completion_date": datetime.now().isoformat()
                }
            }
            
            # Update campaign in database
            supabase_admin = self.get_supabase_admin()
            supabase_admin.table("ad_campaigns").update(campaign_update).eq("id", state.campaign.id).execute()
            
            state.progress = 100
            logger.info(f"Campaign finalized with {total_ads} ads")
            return state
            
        except Exception as e:
            logger.error(f"Error in finalize_campaign: {e}")
            state.error = str(e)
            return state
    
    async def _error_handler(self, state: AdCreationState) -> AdCreationState:
        """Handle errors in the workflow"""
        logger.error(f"Error in ads creation workflow: {state.error}")
        return state
    
    def _should_continue(self, state: AdCreationState) -> str:
        """Determine if we should continue with more platforms"""
        if state.error:
            return "error"
        elif state.completed_platforms >= state.total_platforms:
            return "finish"
        else:
            return "continue"
    
    async def generate_ads_for_user(self, user_id: str) -> Dict[str, Any]:
        """Generate ads for a specific user"""
        try:
            logger.info(f"Starting ads generation for user: {user_id}")
            
            # Initialize state
            state = AdCreationState(user_id=user_id)
            
            # Run the workflow
            result = await self.graph.ainvoke(state)
            
            if hasattr(result, 'error') and result.error:
                return {
                    "success": False,
                    "error": result.error,
                    "ads_generated": len(result.ads) if hasattr(result, 'ads') else 0,
                    "campaign_id": result.campaign.id if hasattr(result, 'campaign') and result.campaign else None
                }
            
            return {
                "success": True,
                "ads_generated": len(result.ads) if hasattr(result, 'ads') else 0,
                "campaign_id": result.campaign.id if hasattr(result, 'campaign') and result.campaign else None,
                "platforms_processed": result.platforms if hasattr(result, 'platforms') else [],
                "ads": [ad.dict() for ad in result.ads] if hasattr(result, 'ads') else []
            }
            
        except Exception as e:
            logger.error(f"Error in generate_ads_for_user: {e}")
            return {
                "success": False,
                "error": str(e),
                "ads_generated": 0,
                "campaign_id": None
            }
