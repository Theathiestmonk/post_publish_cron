import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from supabase import create_client
import openai
import os
from services.token_usage_service import TokenUsageService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BlogPost(BaseModel):
    id: str
    title: str
    content: str
    excerpt: str
    slug: str
    status: str = "draft"  # draft, published, scheduled
    post_type: str = "post"  # post, page
    format: str = "standard"  # standard, aside, chat, gallery, link, image, quote, status, video, audio
    categories: List[str] = []
    tags: List[str] = []
    author_id: str
    wordpress_site_id: Optional[str] = None  # Made optional for standalone blogs
    scheduled_at: str
    published_at: Optional[str] = None
    wordpress_post_id: Optional[str] = None
    meta_description: str = ""
    meta_keywords: List[str] = []
    reading_time: int = 0  # in minutes
    word_count: int = 0
    seo_score: int = 0
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = {}

class BlogCampaign(BaseModel):
    id: str
    user_id: str
    campaign_name: str
    campaign_description: str
    target_audience: str
    content_themes: List[str] = []
    posting_frequency: str = "weekly"  # daily, weekly, bi-weekly, monthly
    wordpress_sites: List[str] = []  # List of WordPress site IDs
    start_date: str
    end_date: str
    total_posts: int = 0
    published_posts: int = 0
    status: str = "active"  # active, paused, completed
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = {}

class BlogWritingState(BaseModel):
    user_id: str
    profile: Optional[Dict[str, Any]] = None
    wordpress_sites: Optional[List[str]] = None
    current_site: Optional[str] = None
    blogs: List[BlogPost] = []
    current_blog: Optional[BlogPost] = None
    campaign: Optional[BlogCampaign] = None
    error: Optional[str] = None
    progress: int = 0
    total_sites: int = 0
    completed_sites: int = 0

class BlogWritingAgent:
    def __init__(self, supabase_url: str, supabase_key: str, openai_api_key: str):
        self.supabase = create_client(supabase_url, supabase_key)
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.token_tracker = TokenUsageService(supabase_url, supabase_key)
        self.graph = self._build_graph()

    def get_supabase_admin(self):
        """Get Supabase admin client for database operations"""
        return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for blog writing"""
        workflow = StateGraph(BlogWritingState)
        
        # Add nodes - removed campaign dependency
        workflow.add_node("fetch_profile", self._fetch_profile)
        workflow.add_node("fetch_wordpress_sites", self._fetch_wordpress_sites)
        workflow.add_node("generate_blog", self._generate_blog)
        workflow.add_node("save_blog", self._save_blog)
        workflow.add_node("update_progress", self._update_progress)
        
        # Add edges - direct flow without campaign
        workflow.set_entry_point("fetch_profile")
        workflow.add_edge("fetch_profile", "fetch_wordpress_sites")
        workflow.add_edge("fetch_wordpress_sites", "generate_blog")
        workflow.add_edge("generate_blog", "save_blog")
        workflow.add_edge("save_blog", "update_progress")
        workflow.add_edge("update_progress", END)
        
        return workflow.compile()

    async def _fetch_profile(self, state: BlogWritingState) -> BlogWritingState:
        """Fetch user profile information"""
        try:
            logger.info(f"Fetching profile for user: {state.user_id}")
            
            supabase_admin = self.get_supabase_admin()
            # Include embeddings in the query
            response = supabase_admin.table("profiles").select("*, profile_embedding").eq("id", state.user_id).execute()
            
            if response.data:
                state.profile = response.data[0]
                print("=" * 80)
                print("PROFILE DATA LOADED FROM DATABASE:")
                print("=" * 80)
                print(f"User ID: {state.user_id}")
                print(f"Name: {state.profile.get('name', 'Unknown')}")
                print(f"Business Name: {state.profile.get('business_name', 'Not specified')}")
                print(f"Industry: {state.profile.get('industry', 'Not specified')}")
                print(f"Target Audience: {state.profile.get('target_audience', 'Not specified')}")
                print(f"Content Themes: {state.profile.get('content_themes', 'Not specified')}")
                print(f"Business Description: {state.profile.get('business_description', 'Not specified')}")
                print(f"Unique Value Proposition: {state.profile.get('unique_value_proposition', 'Not specified')}")
                print(f"Products/Services: {state.profile.get('products_or_services', 'Not specified')}")
                print(f"Brand Voice: {state.profile.get('brand_voice', 'Not specified')}")
                print(f"Brand Tone: {state.profile.get('brand_tone', 'Not specified')}")
                print("=" * 80)
                
                logger.info(f"Profile fetched successfully for user {state.user_id}:")
                logger.info(f"  - Name: {state.profile.get('name', 'Unknown')}")
                logger.info(f"  - Business Name: {state.profile.get('business_name', 'Not specified')}")
                logger.info(f"  - Industry: {state.profile.get('industry', 'Not specified')}")
                logger.info(f"  - Target Audience: {state.profile.get('target_audience', 'Not specified')}")
                logger.info(f"  - Content Themes: {state.profile.get('content_themes', 'Not specified')}")
                logger.info(f"  - Business Description: {state.profile.get('business_description', 'Not specified')[:100]}...")
                logger.info(f"  - Unique Value Proposition: {state.profile.get('unique_value_proposition', 'Not specified')[:100]}...")
                logger.info(f"  - Products/Services: {state.profile.get('products_or_services', 'Not specified')[:100]}...")
                
                # Validate critical fields
                if not state.profile.get('business_name'):
                    print("CRITICAL: No business_name in profile data!")
                    logger.error("CRITICAL: No business_name in profile data!")
                if not state.profile.get('industry'):
                    print("CRITICAL: No industry in profile data!")
                    logger.error("CRITICAL: No industry in profile data!")
                if not state.profile.get('target_audience'):
                    print("CRITICAL: No target_audience in profile data!")
                    logger.error("CRITICAL: No target_audience in profile data!")
            else:
                print("CRITICAL: No profile found for user:", state.user_id)
                logger.error(f"CRITICAL: No profile found for user: {state.user_id}")
                state.profile = {"name": "Unknown User", "bio": ""}
            
            return state
        except Exception as e:
            logger.error(f"Error fetching profile: {e}")
            state.error = str(e)
            return state

    async def _fetch_wordpress_sites(self, state: BlogWritingState) -> BlogWritingState:
        """Fetch user's WordPress sites or create standalone mode"""
        try:
            logger.info(f"Fetching WordPress sites for user: {state.user_id}")
            
            supabase_admin = self.get_supabase_admin()
            response = supabase_admin.table("platform_connections").select("*").eq("user_id", state.user_id).eq("platform", "wordpress").eq("is_active", True).execute()
            
            if response.data:
                state.wordpress_sites = [site["id"] for site in response.data]
                state.total_sites = len(state.wordpress_sites)
                print("=" * 80)
                print("WORDPRESS SITES LOADED:")
                print("=" * 80)
                for i, site in enumerate(response.data):
                    print(f"Site {i+1}: {site.get('wordpress_site_name', site.get('page_name', 'Unknown'))} (ID: {site['id']})")
                    print(f"  - URL: {site.get('wordpress_url', 'Not specified')}")
                    print(f"  - Active: {site.get('is_active', False)}")
                print(f"Total sites: {len(state.wordpress_sites)}")
                print("=" * 80)
                logger.info(f"Found {len(state.wordpress_sites)} WordPress sites")
            else:
                print("No WordPress sites found - enabling standalone mode")
                logger.info("No WordPress sites found - enabling standalone mode")
                # Create a virtual site for standalone blog generation
                state.wordpress_sites = ["standalone"]
                state.total_sites = 1
                print("=" * 80)
                print("STANDALONE MODE ENABLED:")
                print("=" * 80)
                print("Site: Standalone Blog (No WordPress connection required)")
                print("  - Mode: Content generation only")
                print("  - Storage: Local database")
                print("  - Publishing: Manual or future integration")
                print("=" * 80)
            
            return state
        except Exception as e:
            logger.error(f"Error fetching WordPress sites: {e}")
            state.error = str(e)
            return state

    async def _create_campaign(self, state: BlogWritingState) -> BlogWritingState:
        """Create a blog campaign"""
        try:
            logger.info("Creating blog campaign")
            
            campaign_id = str(uuid.uuid4())
            now = datetime.now()
            
            # Generate campaign name based on date
            campaign_name = f"Blog Campaign - {now.strftime('%B %Y')}"
            
            # Calculate end date (30 days from now)
            end_date = now + timedelta(days=30)
            
            # Get profile data with proper fallbacks
            profile_name = state.profile.get('name', 'User')
            target_audience = state.profile.get('target_audience', [])
            content_themes = state.profile.get('content_themes', [])
            
            # Convert lists to strings if needed for campaign
            target_audience_str = ', '.join(target_audience) if isinstance(target_audience, list) else str(target_audience)
            content_themes_list = content_themes if isinstance(content_themes, list) else [str(content_themes)] if content_themes else []
            
            # Log profile data for debugging
            logger.info(f"Profile data for campaign creation:")
            logger.info(f"  - Name: {profile_name}")
            logger.info(f"  - Target Audience: {target_audience_str}")
            logger.info(f"  - Content Themes: {content_themes_list}")
            logger.info(f"  - Business Name: {state.profile.get('business_name', 'Not specified')}")
            logger.info(f"  - Industry: {state.profile.get('industry', 'Not specified')}")
            
            campaign = BlogCampaign(
                id=campaign_id,
                user_id=state.user_id,
                campaign_name=campaign_name,
                campaign_description=f"Automated blog campaign for {profile_name}",
                target_audience=target_audience_str,
                content_themes=content_themes_list,
                posting_frequency="weekly",
                wordpress_sites=state.wordpress_sites or [],
                start_date=now.isoformat(),
                end_date=end_date.isoformat(),
                total_posts=len(state.wordpress_sites or []) * 4,  # 4 posts per site
                published_posts=0,
                status="active",
                created_at=now.isoformat(),
                updated_at=now.isoformat(),
                metadata={
                    "generated_by": "blog_writing_agent",
                    "profile_name": profile_name,
                    "sites_count": len(state.wordpress_sites or []),
                    "business_name": state.profile.get('business_name', 'Unknown'),
                    "industry": state.profile.get('industry', 'Unknown')
                }
            )
            
            state.campaign = campaign
            
            # Save campaign to database
            supabase_admin = self.get_supabase_admin()
            campaign_data = {
                "id": campaign.id,
                "user_id": campaign.user_id,
                "campaign_name": campaign.campaign_name,
                "campaign_description": campaign.campaign_description,
                "target_audience": campaign.target_audience,
                "content_themes": campaign.content_themes,
                "posting_frequency": campaign.posting_frequency,
                "wordpress_sites": campaign.wordpress_sites,
                "start_date": campaign.start_date,
                "end_date": campaign.end_date,
                "total_posts": campaign.total_posts,
                "published_posts": campaign.published_posts,
                "status": campaign.status,
                "created_at": campaign.created_at,
                "updated_at": campaign.updated_at,
                "metadata": campaign.metadata
            }
            
            supabase_admin.table("blog_campaigns").insert(campaign_data).execute()
            logger.info(f"Campaign created: {campaign.id}")
            
            return state
        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            state.error = str(e)
            return state

    async def _generate_blog(self, state: BlogWritingState) -> BlogWritingState:
        """Generate blog content for each WordPress site or standalone mode"""
        try:
            logger.info("Generating blog content")
            
            if not state.wordpress_sites:
                logger.warning("No sites available for blog generation")
                return state
            
            # Generate blogs for each site
            successful_blogs = 0
            for site_id in state.wordpress_sites:
                try:
                    logger.info(f"Generating blog for site: {site_id}")
                    
                    # Handle standalone mode
                    if site_id == "standalone":
                        site_name = "Standalone Blog"
                        logger.info("Generating standalone blog content")
                    else:
                        # Get site information for WordPress sites
                        supabase_admin = self.get_supabase_admin()
                        site_response = supabase_admin.table("platform_connections").select("*").eq("id", site_id).eq("platform", "wordpress").execute()
                        
                        if not site_response.data:
                            logger.warning(f"Site not found: {site_id}")
                            continue
                        
                        site_info = site_response.data[0]
                        site_name = site_info.get("wordpress_site_name", site_info.get("page_name", "Unknown Site"))
                    
                    # Generate blog content
                    blog = await self._generate_blog_content(state, site_id, site_name)
                    print(f"Blog generation result: {blog}")
                    if blog == "API_QUOTA_ERROR":
                        # API quota error detected
                        state.error = "OpenAI API quota exceeded. Please check your billing details."
                        logger.error("API quota exceeded - stopping blog generation")
                        print("API QUOTA EXCEEDED - Please check your billing details")
                        break  # Stop trying to generate more blogs
                    elif blog:
                        state.blogs.append(blog)
                        successful_blogs += 1
                        logger.info(f"Blog generated: {blog.title}")
                    else:
                        logger.warning(f"Failed to generate blog for site {site_id}")
                    
                except Exception as e:
                    logger.error(f"Error generating blog for site {site_id}: {e}")
                    continue
            
            # Check if no blogs were generated and set error if needed
            if successful_blogs == 0 and len(state.wordpress_sites) > 0:
                if not state.error:  # Only set error if not already set
                    state.error = "Failed to generate any blogs. Please check your OpenAI API quota and billing details."
                    print("NO BLOGS GENERATED - Check OpenAI API quota")
            
            return state
        except Exception as e:
            logger.error(f"Error in generate_blog: {e}")
            state.error = str(e)
            return state

    async def _generate_blog_content(self, state: BlogWritingState, site_id: str, site_name: str) -> Optional[BlogPost]:
        """Generate individual blog content"""
        try:
            # Prepare context for blog generation using actual user profile
            profile_name = state.profile.get('name', 'Unknown User')
            business_name = state.profile.get('business_name', '')
            business_description = state.profile.get('business_description', '')
            industry = state.profile.get('industry', [])
            target_audience = state.profile.get('target_audience', [])
            content_themes = state.profile.get('content_themes', [])
            unique_value_proposition = state.profile.get('unique_value_proposition', '')
            brand_voice = state.profile.get('brand_voice', 'Professional')
            brand_tone = state.profile.get('brand_tone', 'Formal')
            products_or_services = state.profile.get('products_or_services', '')
            
            # Use ONLY profile data - no campaign dependency
            # Convert lists to proper format if needed
            if isinstance(target_audience, list):
                target_audience = ', '.join(target_audience) if target_audience else 'General audience'
            if isinstance(content_themes, list):
                content_themes = content_themes if content_themes else ['General business topics']
            if isinstance(industry, list):
                industry = ', '.join(industry) if industry else 'Business'
            
            # Log the final values being used for blog generation
            print("=" * 80)
            print("BLOG GENERATION CONTEXT - PROFILE DATA BEING USED:")
            print("=" * 80)
            print(f"Author: {profile_name}")
            print(f"Business Name: {business_name}")
            print(f"Industry: {industry}")
            print(f"Target Audience: {target_audience}")
            print(f"Content Themes: {content_themes}")
            print(f"Business Description: {business_description}")
            print(f"Products/Services: {products_or_services}")
            print(f"Unique Value Proposition: {unique_value_proposition}")
            print(f"Brand Voice: {brand_voice}")
            print(f"Brand Tone: {brand_tone}")
            print(f"WordPress Site: {site_name}")
            print("=" * 80)
            
            logger.info(f"Final blog generation context (using PROFILE DATA ONLY):")
            logger.info(f"  - Business Name: {business_name}")
            logger.info(f"  - Industry: {industry}")
            logger.info(f"  - Target Audience: {target_audience}")
            logger.info(f"  - Content Themes: {content_themes}")
            logger.info(f"  - Business Description: {business_description[:100]}...")
            logger.info(f"  - Products/Services: {products_or_services[:100]}...")
            logger.info(f"  - Unique Value Proposition: {unique_value_proposition[:100]}...")
            
            # Validate that we have essential business data - use fallback if missing
            if not business_name or business_name.strip() == '':
                logger.warning("No business name found in profile data, using fallback")
                business_name = "Your Business"
            
            if not industry or (isinstance(industry, list) and len(industry) == 0):
                logger.warning("No industry information found in profile data, using fallback")
                industry = "Business"
            
            # Build business context with embeddings if available
            from utils.embedding_context import get_profile_context_with_embedding, build_embedding_prompt
            
            # Get context with embeddings
            business_context = get_profile_context_with_embedding(state.profile)
            
            # Build task description
            task_description = f"""
            You are an expert blog writer creating content for WordPress. Generate a comprehensive blog post.
            
            Site: {site_name}
            
            REQUIREMENTS:
            1. Create an engaging, SEO-optimized blog title that reflects the business and industry
            2. Write comprehensive blog content (1000-2000 words) that is SPECIFICALLY relevant to the business and their industry
            3. Create a compelling excerpt (150-160 characters) that highlights the business value
            4. Generate a URL-friendly slug
            5. Suggest relevant categories (2-3) that match the business industry and content themes
            6. Suggest relevant tags (5-8) that are specific to the business and industry
            7. Create meta description (150-160 characters) that includes business-relevant keywords
            8. Suggest meta keywords (5-10) that are specific to the business, industry, and target audience
            9. Calculate reading time and word count
            10. Provide SEO score (1-100)
            
            IMPORTANT: The content must be highly relevant to the business, industry, and target audience. Avoid generic topics and focus on content that would genuinely interest and provide value to their specific customers and prospects.
            
            OUTPUT FORMAT (JSON):
            {{
                "title": "Blog Title Here",
                "content": "Full blog content with proper HTML formatting...",
                "excerpt": "Brief description of the blog post...",
                "slug": "blog-title-here",
                "categories": ["Category1", "Category2"],
                "tags": ["tag1", "tag2", "tag3"],
                "meta_description": "SEO meta description...",
                "meta_keywords": ["keyword1", "keyword2", "keyword3"],
                "reading_time": 8,
                "word_count": 1200,
                "seo_score": 85
            }}
            
            Make the content engaging, informative, and valuable for the target audience. Use proper HTML formatting for the content.
            """
            
            # Build the prompt using embedding context (like custom blog agent does)
            prompt = build_embedding_prompt(
                context=business_context,
                task_description=task_description,
                additional_requirements=f"WordPress Site: {site_name}, Business: {business_name}, Industry: {industry}"
            )
            
            # Generate content using OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert blog writer and SEO specialist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            # Track token usage
            user_id = state.user_id
            if user_id:
                await self.token_tracker.track_chat_completion_usage(
                    user_id=user_id,
                    feature_type="blog_generation",
                    model_name="gpt-4o-mini",
                    response=response,
                    request_metadata={
                        "wordpress_site_id": state.current_site,
                        "campaign_id": state.campaign.id if state.campaign else None
                    }
                )
            
            # Parse response
            content = response.choices[0].message.content.strip()
            
            # Try to extract JSON from response
            try:
                import json
                # Find JSON in the response
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_content = content[start_idx:end_idx]
                    blog_data = json.loads(json_content)
                else:
                    raise ValueError("No JSON found in response")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                # Fallback: create basic blog structure
                blog_data = {
                    "title": f"Blog Post for {site_name}",
                    "content": content,
                    "excerpt": content[:150] + "..." if len(content) > 150 else content,
                    "slug": f"blog-post-{datetime.now().strftime('%Y-%m-%d')}",
                    "categories": ["General"],
                    "tags": ["blog", "content"],
                    "meta_description": content[:150] + "..." if len(content) > 150 else content,
                    "meta_keywords": ["blog", "content", "wordpress"],
                    "reading_time": max(1, len(content.split()) // 200),
                    "word_count": len(content.split()),
                    "seo_score": 70
                }
            
            # Log the generated blog content
            print("=" * 80)
            print("GENERATED BLOG CONTENT:")
            print("=" * 80)
            print(f"Title: {blog_data.get('title', 'No title')}")
            print(f"Excerpt: {blog_data.get('excerpt', 'No excerpt')}")
            print(f"Slug: {blog_data.get('slug', 'No slug')}")
            print(f"Categories: {blog_data.get('categories', [])}")
            print(f"Tags: {blog_data.get('tags', [])}")
            print(f"Meta Description: {blog_data.get('meta_description', 'No meta description')}")
            print(f"Meta Keywords: {blog_data.get('meta_keywords', [])}")
            print(f"Reading Time: {blog_data.get('reading_time', 0)} minutes")
            print(f"Word Count: {blog_data.get('word_count', 0)} words")
            print(f"SEO Score: {blog_data.get('seo_score', 0)}/100")
            print(f"Content Preview: {blog_data.get('content', 'No content')[:200]}...")
            print("=" * 80)
            
            # Create blog post
            blog_id = str(uuid.uuid4())
            now = datetime.now()
            scheduled_time = now + timedelta(hours=1)  # Schedule 1 hour from now
            
            # Handle WordPress site ID for standalone mode
            wordpress_site_id = None if site_id == "standalone" else site_id
            
            blog = BlogPost(
                id=blog_id,
                title=blog_data.get("title", f"Blog Post for {site_name}"),
                content=blog_data.get("content", content),
                excerpt=blog_data.get("excerpt", ""),
                slug=blog_data.get("slug", f"blog-{blog_id[:8]}"),
                status="draft",
                post_type="post",
                format="standard",
                categories=blog_data.get("categories", ["General"]),
                tags=blog_data.get("tags", ["blog"]),
                author_id=state.user_id,
                wordpress_site_id=wordpress_site_id,
                scheduled_at=scheduled_time.isoformat(),
                meta_description=blog_data.get("meta_description", ""),
                meta_keywords=blog_data.get("meta_keywords", []),
                reading_time=blog_data.get("reading_time", 5),
                word_count=blog_data.get("word_count", 0),
                seo_score=blog_data.get("seo_score", 70),
                created_at=now.isoformat(),
                updated_at=now.isoformat(),
                metadata={
                    "generated_by": "blog_writing_agent",
                    "site_name": site_name,
                    "site_type": "standalone" if site_id == "standalone" else "wordpress",
                    "campaign_id": state.campaign.id if state.campaign else None,
                    "ai_model": "gpt-4o-mini",
                    "generation_time": datetime.now().isoformat()
                }
            )
            
            return blog
            
        except Exception as e:
            logger.error(f"Error generating blog content: {e}")
            print(f"ERROR generating blog content: {e}")
            print(f"ERROR type: {type(e).__name__}")
            
            # Check if it's an API quota error - be more specific
            error_str = str(e).lower()
            error_type = type(e).__name__
            
            # Check for OpenAI API errors specifically
            is_quota_error = False
            
            # Check OpenAI error structure
            if hasattr(e, 'status_code'):
                if e.status_code == 429:
                    is_quota_error = True
                    print(f"OpenAI API returned 429 status code")
            
            # Check error message for quota-related terms (but be specific)
            if not is_quota_error:
                if ("insufficient_quota" in error_str or 
                    "quota exceeded" in error_str or 
                    "exceeded your current quota" in error_str or
                    (error_str.count("quota") > 0 and "check your plan" in error_str)):
                    is_quota_error = True
            
            # Check for rate limit errors (different from quota)
            is_rate_limit = "rate limit" in error_str or "too many requests" in error_str
            
            if is_quota_error:
                print("OPENAI API QUOTA EXCEEDED - Please check your billing details")
                return "API_QUOTA_ERROR"
            elif is_rate_limit:
                print("OPENAI API RATE LIMIT - Please try again in a moment")
                # Don't treat rate limit as quota error - it's temporary
                return None
            else:
                # Other errors - log and return None
                print(f"Other error (not quota): {e}")
                return None

    async def _save_blog(self, state: BlogWritingState) -> BlogWritingState:
        """Save blog posts to database"""
        try:
            logger.info(f"Saving {len(state.blogs)} blog posts")
            
            if not state.blogs:
                return state
            
            supabase_admin = self.get_supabase_admin()
            
            for blog in state.blogs:
                try:
                    # Get site name from platform_connections or use metadata
                    site_name = "Unknown Site"
                    if blog.wordpress_site_id and blog.wordpress_site_id != "standalone":
                        site_response = supabase_admin.table("platform_connections").select("wordpress_site_name").eq("id", blog.wordpress_site_id).eq("platform", "wordpress").execute()
                        if site_response.data:
                            site_name = site_response.data[0].get("wordpress_site_name", "Unknown Site")
                    elif blog.metadata and blog.metadata.get("site_name"):
                        site_name = blog.metadata.get("site_name")
                    
                    # Prepare blog data for database
                    blog_data = {
                        "id": blog.id,
                        "title": blog.title,
                        "content": blog.content,
                        "excerpt": blog.excerpt,
                        "slug": blog.slug,
                        "status": blog.status,
                        "post_type": blog.post_type,
                        "format": blog.format,
                        "categories": blog.categories,
                        "tags": blog.tags,
                        "author_id": blog.author_id,
                        "wordpress_site_id": blog.wordpress_site_id,
                        "site_name": site_name,  # Add site name for frontend display
                        "scheduled_at": blog.scheduled_at,
                        "published_at": blog.published_at,
                        "wordpress_post_id": blog.wordpress_post_id,
                        "meta_description": blog.meta_description,
                        "meta_keywords": blog.meta_keywords,
                        "reading_time": blog.reading_time,
                        "word_count": blog.word_count,
                        "seo_score": blog.seo_score,
                        "created_at": blog.created_at,
                        "updated_at": blog.updated_at,
                        "metadata": blog.metadata
                    }
                    
                    # Save blog to database
                    supabase_admin.table("blog_posts").insert(blog_data).execute()
                    logger.info(f"Blog saved: {blog.title}")
                    
                except Exception as e:
                    logger.error(f"Error saving blog {blog.id}: {e}")
                    continue
            
            return state
        except Exception as e:
            logger.error(f"Error in save_blog: {e}")
            state.error = str(e)
            return state

    async def _update_progress(self, state: BlogWritingState) -> BlogWritingState:
        """Update progress and complete the workflow"""
        try:
            logger.info("Updating progress")
            
            state.completed_sites = len(state.blogs)
            state.progress = 100
            
            # Update campaign with published posts count
            if state.campaign:
                supabase_admin = self.get_supabase_admin()
                supabase_admin.table("blog_campaigns").update({
                    "published_posts": len(state.blogs),
                    "updated_at": datetime.now().isoformat()
                }).eq("id", state.campaign.id).execute()
            
            logger.info(f"Blog generation completed: {len(state.blogs)} blogs created")
            return state
            
        except Exception as e:
            logger.error(f"Error updating progress: {e}")
            state.error = str(e)
            return state

    async def generate_blogs_for_user(self, user_id: str) -> Dict[str, Any]:
        """Main entry point for generating blogs for a user"""
        try:
            logger.info(f"Starting blog generation for user: {user_id}")
            
            # Initialize state
            state = BlogWritingState(
                user_id=user_id,
                blogs=[],
                progress=0,
                total_sites=0,
                completed_sites=0
            )
            
            # Run the workflow
            result = await self.graph.ainvoke(state)
            
            # Debug: Log the result structure
            logger.info(f"Blog generation workflow completed")
            logger.info(f"Result type: {type(result)}")
            if hasattr(result, 'blogs'):
                logger.info(f"Blogs in result: {len(result.blogs) if result.blogs else 0}")
            if hasattr(result, 'wordpress_sites'):
                logger.info(f"WordPress sites in result: {result.wordpress_sites}")
            if hasattr(result, 'error'):
                logger.info(f"Error in result: {result.error}")
            if hasattr(result, 'profile'):
                logger.info(f"Profile in result: {result.profile is not None}")
            
            # Check if result is a dict or BlogWritingState object
            if isinstance(result, dict):
                # Result is a dict
                if result.get('error'):
                    logger.error(f"Blog generation failed: {result['error']}")
                    return {
                        "success": False,
                        "error": result['error'],
                        "blogs": [],
                        "campaign": None
                    }
                blogs_list = result.get('blogs', [])
                campaign_obj = result.get('campaign')
            else:
                # Result is a BlogWritingState object
                if hasattr(result, 'error') and result.error:
                    logger.error(f"Blog generation failed: {result.error}")
                    return {
                        "success": False,
                        "error": result.error,
                        "blogs": [],
                        "campaign": None
                    }
                blogs_list = result.blogs if hasattr(result, 'blogs') else []
                campaign_obj = result.campaign if hasattr(result, 'campaign') else None
            
            # Ensure blogs_list is a list and handle conversion
            try:
                if blogs_list and len(blogs_list) > 0:
                    # Convert to dict if needed
                    if hasattr(blogs_list[0], 'dict'):
                        blogs_dict = [blog.dict() for blog in blogs_list]
                    else:
                        blogs_dict = blogs_list
                else:
                    blogs_dict = []
                
                # Handle campaign conversion
                campaign_dict = None
                if campaign_obj:
                    if hasattr(campaign_obj, 'dict'):
                        campaign_dict = campaign_obj.dict()
                    else:
                        campaign_dict = campaign_obj
                
                # Check if no blogs were generated and there was an error
                if len(blogs_dict) == 0 and hasattr(result, 'error') and result.error:
                    logger.error(f"No blogs generated due to error: {result.error}")
                    print(f"BLOG GENERATION FAILED: {result.error}")
                    return {
                        "success": False,
                        "error": result.error,
                        "blogs": [],
                        "campaign": campaign_dict,
                        "total_blogs": 0,
                        "message": f"Blog generation failed: {result.error}"
                    }
                
                # Check if no blogs were generated but only if there was no specific error
                if len(blogs_dict) == 0 and not (hasattr(result, 'error') and result.error):
                    # Check if we have sites to generate for
                    if hasattr(result, 'wordpress_sites') and result.wordpress_sites and len(result.wordpress_sites) > 0:
                        # Try to generate a fallback blog in standalone mode
                        if "standalone" in result.wordpress_sites:
                            logger.info("Attempting to generate fallback standalone blog...")
                            try:
                                fallback_blog = await self._generate_fallback_blog(result, user_id)
                                if fallback_blog:
                                    blogs_dict = [fallback_blog.dict() if hasattr(fallback_blog, 'dict') else fallback_blog]
                                    logger.info("Fallback blog generated successfully")
                                else:
                                    error_msg = "No blogs were generated despite having sites available. This could be due to OpenAI API quota exceeded or other issues."
                                    logger.warning(f"{error_msg}")
                                    print(f"{error_msg}")
                                    return {
                                        "success": False,
                                        "error": error_msg,
                                        "blogs": [],
                                        "campaign": campaign_dict,
                                        "total_blogs": 0,
                                        "message": error_msg
                                    }
                            except Exception as e:
                                logger.error(f"Fallback blog generation failed: {e}")
                                error_msg = "No blogs were generated despite having sites available. This could be due to OpenAI API quota exceeded or other issues."
                                logger.warning(f"{error_msg}")
                                print(f"{error_msg}")
                                return {
                                    "success": False,
                                    "error": error_msg,
                                    "blogs": [],
                                    "campaign": campaign_dict,
                                    "total_blogs": 0,
                                    "message": error_msg
                                }
                        else:
                            error_msg = "No blogs were generated despite having sites available. This could be due to OpenAI API quota exceeded or other issues."
                            logger.warning(f"{error_msg}")
                            print(f"{error_msg}")
                            return {
                                "success": False,
                                "error": error_msg,
                                "blogs": [],
                                "campaign": campaign_dict,
                                "total_blogs": 0,
                                "message": error_msg
                            }
                    else:
                        # No sites available - this might be expected in some cases
                        logger.info("No blogs generated - no sites available for generation")
                        return {
                            "success": True,
                            "blogs": [],
                            "campaign": campaign_dict,
                            "total_blogs": 0,
                            "message": "No sites available for blog generation"
                        }
                
                logger.info(f"Blog generation successful: {len(blogs_dict)} blogs created")
                
                return {
                    "success": True,
                    "blogs": blogs_dict,
                    "campaign": campaign_dict,
                    "total_blogs": len(blogs_dict),
                    "message": f"Successfully generated {len(blogs_dict)} blog posts"
                }
            except Exception as e:
                logger.error(f"Error processing blog results: {e}")
                return {
                    "success": False,
                    "error": f"Error processing results: {str(e)}",
                    "blogs": [],
                    "campaign": None
                }
            
        except Exception as e:
            logger.error(f"Error in generate_blogs_for_user: {e}")
            return {
                "success": False,
                "error": str(e),
                "blogs": [],
                "campaign": None
            }

    async def _generate_fallback_blog(self, result, user_id: str) -> Optional[BlogPost]:
        """Generate a simple fallback blog when normal generation fails"""
        try:
            logger.info("Generating fallback blog...")
            
            # Get profile data
            profile = result.profile if hasattr(result, 'profile') else {}
            business_name = profile.get('business_name', 'Your Business')
            industry = profile.get('industry', 'Business')
            
            # Create a simple blog post
            blog_id = str(uuid.uuid4())
            now = datetime.now()
            scheduled_time = now + timedelta(hours=1)
            
            # Simple blog content
            title = f"Welcome to {business_name} - Your {industry} Journey Begins"
            content = f"""
            <h2>Welcome to {business_name}</h2>
            <p>We're excited to share our journey in the {industry} industry with you. This is just the beginning of our story, and we can't wait to show you what we have in store.</p>
            
            <h3>What You Can Expect</h3>
            <p>In the coming weeks and months, we'll be sharing:</p>
            <ul>
                <li>Industry insights and trends</li>
                <li>Behind-the-scenes content</li>
                <li>Expert tips and advice</li>
                <li>Success stories and case studies</li>
            </ul>
            
            <h3>Stay Connected</h3>
            <p>Make sure to follow us for regular updates and don't hesitate to reach out if you have any questions or suggestions.</p>
            
            <p>Thank you for being part of our community!</p>
            <p><strong>The {business_name} Team</strong></p>
            """
            
            blog = BlogPost(
                id=blog_id,
                title=title,
                content=content,
                excerpt="Welcome to our blog! We're excited to share our journey and insights with you.",
                slug=f"welcome-to-{business_name.lower().replace(' ', '-')}",
                status="draft",
                post_type="post",
                format="standard",
                categories=["Welcome", "Introduction"],
                tags=["welcome", "introduction", "business"],
                author_id=user_id,
                wordpress_site_id=None,  # Standalone blog
                scheduled_at=scheduled_time.isoformat(),
                meta_description=f"Welcome to {business_name}'s blog. Discover insights, tips, and stories from our {industry} journey.",
                meta_keywords=["welcome", "business", industry.lower(), "blog"],
                reading_time=3,
                word_count=len(content.split()),
                seo_score=75,
                created_at=now.isoformat(),
                updated_at=now.isoformat(),
                metadata={
                    "generated_by": "blog_writing_agent_fallback",
                    "site_name": "Standalone Blog",
                    "site_type": "standalone",
                    "ai_model": "fallback",
                    "generation_time": datetime.now().isoformat(),
                    "is_fallback": True
                }
            )
            
            logger.info(f"Fallback blog generated: {blog.title}")
            return blog
            
        except Exception as e:
            logger.error(f"Error generating fallback blog: {e}")
            return None
