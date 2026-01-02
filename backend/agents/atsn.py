"""
ATSN Agent - Content & Lead Management Agent
Built with LangGraph and Pydantic
Uses Gemini 2.5 for classification and generation

Architecture:
============

User Query
    ↓
Intent Classifier (Gemini 2.5)
    ↓
    ├→ Create Content → Payload Constructor → Payload Completer → Content Generator
    ├→ Edit Content → Payload Constructor → Payload Completer → Content Editor
    ├→ Delete Content → Payload Constructor → Payload Completer → Content Deleter
    ├→ View Content → Payload Constructor → Payload Completer → Content Viewer
    ├→ Publish Content → Payload Constructor → Payload Completer → Content Publisher
    ├→ Schedule Content → Payload Constructor → Payload Completer → Content Scheduler
    ├→ Create Leads → Payload Constructor → Payload Completer → Lead Creator
    ├→ View Leads → Payload Constructor → Payload Completer → Lead Viewer
    ├→ Edit Leads → Payload Constructor → Payload Completer → Lead Editor
    ├→ Delete Leads → Payload Constructor → Payload Completer → Lead Deleter
    ├→ Follow Up Leads → Payload Constructor → Payload Completer → Lead Follow-up
    ├→ View Insights → Payload Constructor → Payload Completer → Insights Viewer
    └→ View Analytics → Payload Constructor → Payload Completer → Analytics Viewer

Key Features:
=============
- 13 task-specific payload constructors with examples
- Intelligent clarification questions with clear options
- Conversation context maintained across turns
- Gemini 2.5 for all LLM operations (lightweight & fast)
- Clean Pydantic models for type safety
- Ready for Supabase integration
"""

import os
import logging
import re
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
import google.generativeai as genai
import openai
import aiohttp
from supabase import create_client, Client
from utils.embedding_context import get_profile_context_with_embedding

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_clarifying_question(base_question: str, user_context: str, user_input: str = "") -> str:
    """
    Generate a personalized clarifying question using LLM based on user context and input.

    Args:
        base_question: The base clarifying question template
        user_context: The full conversation context to understand user tone/language
        user_input: The specific user input that triggered this clarification (optional)

    Returns:
        A personalized clarifying question in the user's tone and style
    """
    try:
        logger.info(f"Generating clarifying question for base_question: '{base_question}'")
        # Extract key information from user context to understand tone
        recent_messages = user_context.split('\n')[-10:]  # Last 10 lines for context
        user_context_sample = '\n'.join(recent_messages)
        logger.debug(f"User context sample: {user_context_sample[:200]}...")

        # Determine user's communication style
        prompt = f"""You are an AI assistant that needs to ask a clarifying question to the user.

User's recent conversation style and tone:
{user_context_sample}

Original question template: "{base_question}"

User's latest input: "{user_input}"

Your task: Rewrite the clarifying question to match the user's communication style, tone, and language patterns.
- Keep it conversational and natural
- Match their formality level (casual vs formal)
- Use similar vocabulary and sentence structure
- Make it feel like a natural continuation of the conversation
- Keep the core question the same but adapt the wording and tone

Return ONLY the rephrased question, nothing else."""

        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        response = model.generate_content(prompt)

        if response and response.text:
            personalized_question = response.text.strip()
            # Remove any quotes that might be added
            personalized_question = personalized_question.strip('"\'')
            logger.info(f"LLM generated personalized question: '{personalized_question}' (base: '{base_question}')")
            return personalized_question
        else:
            # Fallback to original question if LLM fails
            logger.warning("LLM failed to generate clarifying question, using original")
            logger.warning(f"LLM response: {response}")
            return base_question

    except Exception as e:
        logger.error(f"Error generating clarifying question with LLM: {str(e)}")
        # Fallback to original question
        return base_question


def generate_personalized_message(base_message: str, user_context: str, message_type: str = "success") -> str:
    """
    Generate a personalized success/result message using LLM based on user context.

    Args:
        base_message: The base message template
        user_context: The full conversation context to understand user tone/language
        message_type: Type of message ("success", "error", "info", etc.)

    Returns:
        A personalized message in the user's tone and style
    """
    try:
        logger.info(f"Generating personalized {message_type} message for base_message: '{base_message[:100]}...'")
        # Extract key information from user context to understand tone
        recent_messages = user_context.split('\n')[-10:]  # Last 10 lines for context
        user_context_sample = '\n'.join(recent_messages)

        # Determine user's communication style and message type
        message_type_instruction = {
            "success": "celebratory and positive",
            "error": "helpful and apologetic",
            "info": "informative and clear",
            "warning": "cautious and advisory"
        }.get(message_type, "neutral and clear")

        prompt = f"""You are an AI assistant that needs to deliver a {message_type_instruction} message to the user.

User's recent conversation style and tone:
{user_context_sample}

Original message template: "{base_message}"

Your task: Rewrite the message to match the user's communication style, tone, and language patterns.
- Keep it {message_type_instruction}
- Match their formality level (casual vs formal)
- Use similar vocabulary and sentence structure
- Make it feel like a natural, personalized response
- Preserve all factual information and key details
- Adapt the wording and tone while keeping the core message

Return ONLY the rephrased message, nothing else."""

        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        response = model.generate_content(prompt)

        if response and response.text:
            personalized_message = response.text.strip()
            # Remove any quotes that might be added
            personalized_message = personalized_message.strip('"\'')
            logger.info(f"LLM generated personalized {message_type} message: '{personalized_message[:100]}...'")
            return personalized_message
        else:
            # Fallback to original message if LLM fails
            logger.warning(f"LLM failed to generate personalized {message_type} message, using original")
            logger.warning(f"LLM response: {response}")
            return base_message

    except Exception as e:
        logger.error(f"Error generating personalized {message_type} message with LLM: {str(e)}")
        # Fallback to original message
        return base_message

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash-lite')

# Initialize OpenAI client
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

# Initialize Supabase client (following the app's pattern)
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

if not supabase:
    logger.warning("⚠️  Supabase not configured. Using mock data. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
else:
    logger.info(" Supabase client initialized successfully")


# ==================== UTILITY FUNCTIONS ====================

def detect_and_replace_pii_in_query(query: str) -> tuple[str, list, list]:
    """
    Detect email and phone numbers in user query and return sanitized query with defaults.

    Args:
        query: The user query containing potential PII

    Returns:
        tuple: (sanitized_query, original_emails, original_phones)
        - sanitized_query: Query with real PII replaced by default values
        - original_emails: List of original emails found
        - original_phones: List of original phones found
    """
    sanitized_query = query
    original_emails = []
    original_phones = []

    # Email regex pattern - matches most common email formats
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    # Phone regex pattern - matches common phone number formats (targeted)
    phone_pattern = r'\b\+?[0-9]{1,4}?[\s\-\.]?\(?[0-9]{3}\)?[\s\-\.]?[0-9]{3}[\s\-\.]?[0-9]{4}\b|\b[0-9]{10,12}\b'

    # Find and store all original emails
    email_matches = re.findall(email_pattern, query, re.IGNORECASE)
    original_emails = email_matches
    # Replace all emails with default for LLM
    if email_matches:
        sanitized_query = re.sub(email_pattern, 'atsn@gmail.com', sanitized_query, flags=re.IGNORECASE)

    # Find and store all original phones
    phone_matches = re.findall(phone_pattern, query)
    original_phones = phone_matches
    # Replace all phones with default for LLM
    if phone_matches:
        sanitized_query = re.sub(phone_pattern, '9876543210', sanitized_query)

    return sanitized_query, original_emails, original_phones


# ==================== TREND ANALYSIS FUNCTIONS ====================

async def get_trends_from_grok(topic: str, business_context: dict) -> dict:
    """Fetch social media trends from Grok API for content generation"""
    import aiohttp

    grok_api_key = os.getenv('GROK_API_KEY')
    grok_api_url = os.getenv('GROK_API_URL', 'https://api.x.ai/v1/chat/completions')
    grok_model = os.getenv('GROK_MODEL', 'grok-4-1-fast-non-reasoning')

    logger.info(f"🔍 Starting trend analysis for topic: '{topic}' using model: {grok_model}")

    if not grok_api_key:
        logger.warning("GROK_API_KEY not found, returning default trends")
        return {
            "trends": [
                {
                    "trend_name": "General Content",
                    "description": "Create engaging, valuable content for your audience",
                    "why_it_works": "Builds trust and engagement with consistent value",
                    "content_angle": "Share helpful insights and practical advice",
                    "example_hook": "Did you know...",
                    "recommended_format": "Feed Post"
                }
            ]
        }

    from datetime import datetime
    current_datetime = datetime.now()
    current_date = current_datetime.strftime("%Y-%m-%d")
    current_time = current_datetime.strftime("%H:%M:%S UTC")

    trend_prompt = f"""You are a social media trend analyst. CURRENT DATE/TIME: {current_date} at {current_time}

TASK: Identify current and emerging Instagram content trends related to the following topic. TOPIC: {topic} TARGET AUDIENCE: {business_context.get('target_audience', 'General audience')} PLATFORM: Instagram

OUTPUT REQUIREMENTS: Return ONLY valid JSON in the following structure: {{ "trends": [ {{ "trend_name": "Short name of the trend", "description": "What this trend is about in 1–2 lines", "why_it_works": "Why this trend performs well on Instagram", "content_angle": "How a brand can use this trend", "example_hook": "An example opening hook or line", "recommended_format": "Feed Post | Reel | Carousel" }} ] }}

RULES: - Provide 3 to 5 relevant trends - Trends must be practical and currently usable - No explanations outside the JSON"""

    # Log the complete trend analysis prompt
    logger.info(f"🎯 Complete trend analysis prompt being sent to Grok:")
    logger.info("=" * 80)
    logger.info(trend_prompt)
    logger.info("=" * 80)

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {grok_api_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                'model': grok_model,
                'messages': [{'role': 'user', 'content': trend_prompt}],
                'max_tokens': 1000,
                'temperature': 0.7
            }

            async with session.post(grok_api_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content'].strip()

                    # Extract JSON from response
                    import json
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    if json_start != -1 and json_end > json_start:
                        json_content = content[json_start:json_end]
                        parsed_result = json.loads(json_content)

                        # Log the trends for debugging
                        trends = parsed_result.get('trends', [])
                        logger.info(f"🎯 Grok API returned {len(trends)} trends for topic: '{topic}'")
                        for i, trend in enumerate(trends[:3]):  # Log first 3 trends
                            logger.info(f"   Trend {i+1}: {trend.get('trend_name', 'N/A')} - {trend.get('content_angle', 'N/A')[:50]}...")

                        return parsed_result
                    else:
                        logger.error(f"Could not extract JSON from image enhancer response: {content}")
                        return {
                            "image_prompt": f"Create a professional Instagram image for: {generated_post.get('title', '')}",
                            "aspect_ratio": "1:1",
                            "negative_prompt": "text, logos, watermarks"
                        }
                else:
                    logger.error(f"Grok API error: {response.status} - {await response.text()}")
                    return {"trends": []}

    except Exception as e:
        logger.error(f"❌ Error calling Grok API: {e}")
        logger.info("🔄 Falling back to default trends")
        return {"trends": []}


def parse_trends_for_content(trends_json: dict) -> dict:
    """Parse Grok trends JSON into content generation format"""

    trends = trends_json.get('trends', [])
    if not trends:
        return {
            'primary_trend': 'General Content',
            'content_angle': 'Create engaging, valuable content',
            'example_hook': 'Did you know...',
            'supporting_trends': [],
            'format': 'Feed Post'
        }

    # Use first trend as primary
    primary = trends[0]

    return {
        'primary_trend': primary.get('trend_name', 'General Content'),
        'content_angle': primary.get('content_angle', 'Create engaging content'),
        'example_hook': primary.get('example_hook', 'Here\'s something interesting...'),
        'supporting_trends': [t.get('trend_name', '') for t in trends[1:3]],  # Next 2 trends
        'format': primary.get('recommended_format', 'Feed Post')
    }


def get_instagram_prompt(payload: dict, business_context: dict, parsed_trends: dict, profile_assets: dict = None, post_design_type: str = "general", image_type: str = "general") -> str:
    """Generate Instagram-optimized content prompt"""

    from datetime import datetime
    current_datetime = datetime.now()
    current_date = current_datetime.strftime("%Y-%m-%d")
    current_time = current_datetime.strftime("%H:%M:%S UTC")

    # Build brand context using helper function
    brand_context = build_content_brand_context(profile_assets or {})

    return f"""
You are a professional Instagram content creator and copywriter. CURRENT DATE/TIME: {current_date} at {current_time}

BUSINESS CONTEXT:
Brand Name: {business_context.get('business_name', 'Business')}
Industry: {business_context.get('industry', 'General')}
Target Audience: {business_context.get('target_audience', 'General audience')}
Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}
Brand Tone: {business_context.get('brand_tone', 'Approachable')}
Post Design Type: {post_design_type}
{brand_context}

CONTENT STRATEGY INPUT (FROM TREND ANALYSIS):
Primary Trend: {parsed_trends.get('primary_trend')}
Trend-Based Content Angle: {parsed_trends.get('content_angle')}
Example Hook Inspiration: {parsed_trends.get('example_hook')}
Supporting Trends: {", ".join(parsed_trends.get('supporting_trends', []))}
Recommended Format: {parsed_trends.get('format')}

CONTENT IDEA:
{payload.get('content_idea', '')}

INSTAGRAM CONTENT REQUIREMENTS:
- Platform: Instagram
- Format: {parsed_trends.get('format')}
- Caption Style: Scroll-stopping, conversational, value-driven
- Emoji Usage: Natural and engaging
- CTA: Include exactly ONE clear CTA
- Line Breaks: Use short paragraphs for readability
- Avoid generic advice — be specific and actionable

TASK:
Create a complete Instagram post optimized for engagement and relevance to the trend.

FORMAT (Return ONLY this format, no extra text):

TITLE: [Hook-based title, max 60 characters]

CAPTION:
[Trend-aligned Instagram caption using the angle and hook]

HASHTAGS:
[7–10 relevant Instagram hashtags, space-separated]
"""


def get_platform_specific_prompt(platform: str, payload: dict, business_context: dict, parsed_trends: dict, profile_assets: dict = None) -> str:
    """Return platform-optimized prompt based on platform type"""

    platform_lower = platform.lower()

    if platform_lower == 'instagram':
        # Extract classified types from payload for Instagram
        post_design_type = payload.get('post_design_type', 'general')
        if post_design_type != 'general':
            post_design_type = classify_post_design_type(post_design_type)
        return get_instagram_prompt(payload, business_context, parsed_trends, profile_assets, post_design_type)
    else:
        # Fallback to general social media prompt for now
        from datetime import datetime
        current_datetime = datetime.now()
        current_date = current_datetime.strftime("%Y-%m-%d")
        current_time = current_datetime.strftime("%H:%M:%S UTC")

        # Build brand context for other platforms too
        brand_context = build_content_brand_context(profile_assets or {})

        return f"""You are a professional social media content creator specializing in {payload.get('platform', 'social media')} posts for businesses. CURRENT DATE/TIME: {current_date} at {current_time}

BUSINESS CONTEXT:
{business_context.get('business_name', 'Business')}
Industry: {business_context.get('industry', 'General')}
Target Audience: {business_context.get('target_audience', 'General audience')}
Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}
Brand Tone: {business_context.get('brand_tone', 'Approachable')}
{brand_context}

CONTENT REQUIREMENTS:
- Platform: {payload.get('platform', 'Social Media')}
- Channel: {payload.get('channel', 'Social Media')}
- Content Idea: {payload.get('content_idea', '')}

TASK:
Create a complete social media post with the following structure:

TITLE: [Create an engaging title for the post (max 60 characters)]

CONTENT: [Write the full post content with emojis and engaging copy]

HASHTAGS: [Provide 5-8 relevant hashtags separated by spaces]

Return ONLY in this exact format, no other text or explanations."""


def parse_instagram_response(response_text: str) -> dict:
    """Parse Instagram-specific response format"""

    lines = response_text.split('\n')
    content_data = {
        'title': '',
        'content': '',
        'hashtags': []
    }

    current_section = None

    for line in lines:
        line = line.strip()
        if line.startswith('TITLE:'):
            content_data['title'] = line.replace('TITLE:', '').strip()
            current_section = 'title'
        elif line.startswith('CAPTION:'):
            content_data['content'] = line.replace('CAPTION:', '').strip()
            current_section = 'caption'
        elif line.startswith('HASHTAGS:'):
            hashtags_text = line.replace('HASHTAGS:', '').strip()
            content_data['hashtags'] = hashtags_text.split()
            current_section = 'hashtags'
        elif current_section == 'caption' and line:
            content_data['content'] += ' ' + line
        elif current_section == 'hashtags' and line:
            # Continue collecting hashtags from subsequent lines
            content_data['hashtags'].extend(line.split())

    return content_data


async def generate_image_enhancer_prompt(generated_post: dict, payload: dict, business_context: dict, parsed_trends: dict, profile_assets: dict = None, image_type: str = "general") -> dict:
    """Generate an enhanced image prompt using AI based on the generated content"""

    from datetime import datetime
    current_datetime = datetime.now()
    current_date = current_datetime.strftime("%Y-%m-%d")
    current_time = current_datetime.strftime("%H:%M:%S UTC")

    # Build brand assets and location context using helper functions
    brand_assets_context = build_image_enhancer_brand_assets(profile_assets or {}, business_context)
    location_context = build_location_context(business_context)

    image_prompt_enhancer = f"""
You are an expert visual prompt engineer for AI image generation, specializing in Instagram content. CURRENT DATE/TIME: {current_date} at {current_time}

INPUT CONTEXT:
Platform: Instagram
Post Format: {parsed_trends.get('format', 'Feed Post')}
Industry: {business_context.get('industry', 'General')}
Target Audience: {business_context.get('target_audience', 'General audience')}
Brand Tone: {business_context.get('brand_tone', 'Approachable')}
Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}
Image Type: {image_type} (classified from user input)

{brand_assets_context}

{location_context}

INSTAGRAM POST CONTENT:
Title: {generated_post.get('title', '')}
Caption: {generated_post.get('content', '')}
Original Idea: {payload.get('content_idea', '')}

PRIMARY GOAL:
Create a visually compelling image prompt that:
- Instantly communicates the core message of the post
- Matches Instagram aesthetics and trends
- Feels natural, human, and scroll-stopping
- Aligns with the brand tone and audience

IMAGE PROMPT REQUIREMENTS:
- Describe the main subject clearly
- Specify environment/background
- Define mood, lighting, and color palette
- Include composition and camera perspective
- Ensure Instagram-friendly framing (4:5 or square)
- Avoid text-heavy visuals (no captions on image)
- Avoid logos, watermarks, or brand names
- Photorealistic unless illustration fits better

OUTPUT FORMAT (Return ONLY this JSON):

{{
  "image_prompt": "A single, detailed image generation prompt",
  "aspect_ratio": "1:1 or 4:5",
  "negative_prompt": "Things to avoid in the image"
}}
"""

    try:
        # Log the complete image enhancer prompt
        logger.info(f"🎨 Complete image enhancer prompt being sent to GPT-4o-mini:")
        logger.info("=" * 80)
        logger.info(image_prompt_enhancer)
        logger.info("=" * 80)

        logger.info(f"🎨 Generating enhanced image prompt with GPT-4o-mini at {current_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        if openai_client:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": image_prompt_enhancer}],
                max_tokens=400,
                temperature=0.7
            )

            enhancer_response = response.choices[0].message.content.strip()

            # Parse JSON response
            import json
            json_start = enhancer_response.find('{')
            json_end = enhancer_response.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                json_content = enhancer_response[json_start:json_end]
                enhanced_prompt_data = json.loads(json_content)

                logger.info(f"✅ Enhanced image prompt generated: {enhanced_prompt_data.get('visual_style', 'unknown')} style")
                return enhanced_prompt_data
            else:
                logger.error(f"Could not parse JSON from image enhancer response: {enhancer_response}")
                return {
                    "image_prompt": f"Create a professional Instagram image for: {generated_post.get('title', '')}",
                    "visual_style": "photorealistic",
                    "aspect_ratio": "1:1",
                    "negative_prompt": "text, logos, watermarks, blurry"
                }
        else:
            logger.warning("OpenAI client not available for image enhancer")
            return {
                "image_prompt": f"Create a professional Instagram image for: {generated_post.get('title', '')}",
                "visual_style": "photorealistic",
                "aspect_ratio": "1:1",
                "negative_prompt": "text, logos, watermarks, blurry"
            }

    except Exception as e:
        logger.error(f"❌ Error generating enhanced image prompt: {e}")
        return {
            "image_prompt": f"Create a professional Instagram image for: {generated_post.get('title', '')}",
            "aspect_ratio": "1:1",
            "negative_prompt": "text, logos, watermarks, blurry"
        }


# ==================== CLASSIFICATION HELPERS ====================

def classify_post_design_type(user_input: str) -> str:
    """Classify user input into post design categories for content generation"""
    if not user_input:
        return "general"

    user_input_lower = user_input.lower()

    # News category
    if any(word in user_input_lower for word in ['news', 'update', 'announcement', 'breaking', 'latest', 'current']):
        return "news"

    # Trendy category
    elif any(word in user_input_lower for word in ['trendy', 'trend', 'viral', 'popular', 'hot', 'fashion', 'style']):
        return "trendy"

    # Educational category
    elif any(word in user_input_lower for word in ['educational', 'learn', 'teach', 'tutorial', 'guide', 'how to', 'tips', 'advice']):
        return "educational"

    # Informative category
    elif any(word in user_input_lower for word in ['informative', 'info', 'facts', 'data', 'statistics', 'insights', 'analysis']):
        return "informative"

    # Announcement category
    elif any(word in user_input_lower for word in ['announcement', 'launch', 'release', 'new', 'coming soon']):
        return "announcement"

    # BTS (Behind-the-Scenes) category
    elif any(word in user_input_lower for word in ['bts', 'behind the scenes', 'behind-the-scenes', 'process', 'making of', 'how we']):
        return "bts"

    # UGC (User-Generated Content) category
    elif any(word in user_input_lower for word in ['ugc', 'user generated', 'user-generated', 'customer', 'testimonial', 'review']):
        return "ugc"

    else:
        return "general"


def get_visual_style_from_image_type(image_type: str) -> str:
    """Map classified image type to appropriate visual style for image generation"""
    if not image_type or image_type == "general":
        return "photorealistic"

    image_type_lower = image_type.lower()

    # Graphic-First Post Types → illustration/flat design
    if any(word in image_type_lower for word in ['poster', 'graphic', 'typography', 'text-only', 'quote card', 'stat', 'data card', 'announcement banner', 'offer', 'discount poster', 'countdown', 'event poster', 'reminder card', 'cta graphic', 'infographic']):
        return "flat design"

    # Photo-Based Post Types → photorealistic
    elif any(word in image_type_lower for word in ['product photo', 'lifestyle', 'flat-lay', 'close-up', 'studio', 'environmental', 'in-use', 'team photo', 'founder photo', 'office', 'workspace', 'behind-the-scenes photo']):
        return "photorealistic"

    # Illustration & Visual Art → illustration/3D
    elif any(word in image_type_lower for word in ['illustration', 'vector', 'character', 'icon', 'isometric', 'hand-drawn', 'abstract']):
        return "illustration"

    # Brand Identity Posts → flat design
    elif any(word in image_type_lower for word in ['brand color', 'mood board', 'font', 'typography', 'pattern', 'texture', 'logo placement', 'rebrand']):
        return "flat design"

    # Social Proof Visuals → photorealistic or illustration
    elif any(word in image_type_lower for word in ['testimonial', 'review', 'star-rating', 'case-study', 'client logo']):
        return "photorealistic"

    # Informational Visuals → illustration/flat design
    elif any(word in image_type_lower for word in ['chart', 'graph', 'timeline', 'process flow', 'faq']):
        return "flat design"

    # Creative / Experimental → illustration
    elif any(word in image_type_lower for word in ['collage', 'split-screen', 'brutalist', 'minimalist', 'maximalist', 'editorial', 'magazine']):
        return "illustration"

    # Default fallback
    else:
        return "photorealistic"


def classify_image_type(user_input: str) -> str:
    """Classify user input into detailed image type categories for image generation"""
    if not user_input:
        return "general"

    user_input_lower = user_input.lower()

    # Graphic-First Post Types
    if any(word in user_input_lower for word in ['poster', 'graphic', 'banner', 'typography', 'text-only', 'quote card', 'stat', 'data card', 'announcement banner', 'offer', 'discount poster', 'countdown', 'event poster', 'reminder card', 'cta graphic']):
        return "graphic"

    # Photo-Based Post Types
    elif any(word in user_input_lower for word in ['product photo', 'lifestyle', 'flat-lay', 'close-up', 'studio', 'environmental', 'in-use', 'team photo', 'founder photo', 'office', 'workspace', 'behind-the-scenes photo']):
        return "photo"

    # Photo + Graphic Hybrid
    elif any(word in user_input_lower for word in ['text overlay', 'brand frame', 'gradient overlay', 'icon overlay', 'highlighted callout', 'before-after', 'comparison']):
        return "hybrid"

    # Illustration & Visual Art
    elif any(word in user_input_lower for word in ['illustration', 'vector', 'character', 'icon', 'isometric', 'hand-drawn', '3d', 'abstract']):
        return "illustration"

    # Carousel-Style Static Sets
    elif any(word in user_input_lower for word in ['carousel', 'multi-slide', 'quote set', 'step-by-step', 'listicle', 'comparison slides', 'storytelling slides']):
        return "carousel"

    # Brand Identity Posts
    elif any(word in user_input_lower for word in ['brand color', 'mood board', 'font', 'typography', 'pattern', 'texture', 'logo placement', 'rebrand']):
        return "brand"

    # Social Proof Visuals
    elif any(word in user_input_lower for word in ['testimonial', 'review', 'star-rating', 'case-study', 'client logo']):
        return "social_proof"

    # Informational Visuals
    elif any(word in user_input_lower for word in ['infographic', 'chart', 'graph', 'timeline', 'process flow', 'faq']):
        return "informational"

    # Community & Culture
    elif any(word in user_input_lower for word in ['employee spotlight', 'culture quote', 'team celebration', 'milestone', 'thank-you']):
        return "community"

    # Seasonal & Occasion
    elif any(word in user_input_lower for word in ['festival', 'holiday', 'seasonal', 'special-day']):
        return "seasonal"

    # Interactive Static Visuals
    elif any(word in user_input_lower for word in ['question card', 'poll', 'this or that', 'guess-the-answer', 'comment-to-engage']):
        return "interactive"

    # Creative / Experimental
    elif any(word in user_input_lower for word in ['collage', 'split-screen', 'brutalist', 'minimalist', 'maximalist', 'editorial', 'magazine']):
        return "creative"

    # Utility / Filler Visuals
    elif any(word in user_input_lower for word in ['grid', 'spacer', 'filler', 'placeholder', 'schedule reminder']):
        return "utility"

    else:
        return "general"


# ==================== BUSINESS CONTEXT HELPERS ====================

def extract_text_field(profile_record: dict, field_name: str, default_value: str = '', required: bool = False) -> str:
    """Extract and validate a text field from profile record"""
    value = profile_record.get(field_name)

    if value is None or value == '':
        if required:
            logger.warning(f"⚠️ Required field '{field_name}' is empty in profile record, using default: '{default_value}'")
        else:
            logger.debug(f"📝 Optional field '{field_name}' is empty, using default: '{default_value}'")
        return default_value

    # Validate string type
    if not isinstance(value, str):
        logger.warning(f"⚠️ Field '{field_name}' is not a string (type: {type(value)}), converting to string")
        value = str(value)

    logger.debug(f"✅ Extracted field '{field_name}': '{value[:50]}{'...' if len(value) > 50 else ''}'")
    return value


def extract_array_field(profile_record: dict, field_name: str, default_value: str = '', required: bool = False) -> str:
    """Extract first item from an array field in profile record"""
    array_value = profile_record.get(field_name)

    if not array_value or not isinstance(array_value, list) or len(array_value) == 0:
        if required:
            logger.warning(f"⚠️ Required array field '{field_name}' is empty or invalid, using default: '{default_value}'")
        else:
            logger.debug(f"📝 Optional array field '{field_name}' is empty, using default: '{default_value}'")
        return default_value

    first_item = array_value[0]

    # Validate the first item
    if first_item is None or first_item == '':
        logger.warning(f"⚠️ First item in array field '{field_name}' is empty, using default: '{default_value}'")
        return default_value

    if not isinstance(first_item, str):
        logger.warning(f"⚠️ Array field '{field_name}' first item is not a string (type: {type(first_item)}), converting")
        first_item = str(first_item)

    logger.debug(f"✅ Extracted array field '{field_name}': '{first_item}' (from array of {len(array_value)} items)")
    return first_item


def extract_color_field(profile_record: dict, field_name: str) -> str:
    """Extract color field (can be None, no validation needed)"""
    color_value = profile_record.get(field_name)

    if color_value is not None:
        logger.debug(f"✅ Extracted color field '{field_name}': '{color_value}'")
    else:
        logger.debug(f"📝 Color field '{field_name}' is not set (optional)")

    return color_value


def extract_color_array_field(profile_record: dict, field_name: str) -> list:
    """Extract color array field"""
    color_array = profile_record.get(field_name, [])

    if not isinstance(color_array, list):
        logger.warning(f"⚠️ Color array field '{field_name}' is not a list (type: {type(color_array)}), using empty array")
        return []

    logger.debug(f"✅ Extracted color array field '{field_name}': {len(color_array)} colors")
    return color_array


def get_business_context_from_profile(profile_record: dict) -> dict:
    """Extract structured business context from profile record using individual field extraction"""

    if not profile_record:
        logger.warning("❌ Profile record is None or empty, using all defaults")
        profile_record = {}

    # Count available fields for logging
    available_fields = [k for k, v in profile_record.items() if v is not None and v != '' and v != []]
    logger.info(f"📊 Profile record analysis: {len(available_fields)}/{len(profile_record)} fields populated")

    # Extract each field individually with validation
    context = {
        # Core business information
        'business_name': extract_text_field(profile_record, 'business_name', 'Business', required=True),
        'business_description': extract_text_field(profile_record, 'business_description', '', required=False),

        # Brand personality
        'brand_tone': extract_text_field(profile_record, 'brand_tone', 'Professional', required=False),
        'brand_voice': extract_text_field(profile_record, 'brand_voice', 'Professional and friendly', required=False),

        # Business categorization
        'industry': extract_array_field(profile_record, 'industry', 'General', required=False),
        'target_audience': extract_array_field(profile_record, 'target_audience', 'General audience', required=False),

        # Unique value
        'unique_value_proposition': extract_text_field(profile_record, 'unique_value_proposition', '', required=False),

        # Brand colors (optional)
        'primary_color': extract_color_field(profile_record, 'primary_color'),
        'secondary_color': extract_color_field(profile_record, 'secondary_color'),
        'brand_colors': extract_color_array_field(profile_record, 'brand_colors'),

        # Location and timezone context
        'timezone': extract_text_field(profile_record, 'timezone', '', required=False),
        'location_city': extract_text_field(profile_record, 'location_city', '', required=False),
        'location_state': extract_text_field(profile_record, 'location_state', '', required=False),
        'location_country': extract_text_field(profile_record, 'location_country', '', required=False)
    }

    # Log summary of extracted context
    color_status = f"{bool(context['primary_color'])}/{bool(context['secondary_color'])}"
    location_info = []
    if context.get('location_city'): location_info.append(context['location_city'])
    if context.get('location_country'): location_info.append(context['location_country'])
    location_str = ', '.join(location_info) if location_info else 'Not specified'

    logger.info(f"📋 Context extraction complete: Business='{context['business_name']}', Industry='{context['industry']}', Location='{location_str}', Colors={color_status}")

    return context

def get_profile_context_with_structured_data(profile_data: dict) -> dict:
    """Legacy function - now uses structured data instead of embeddings"""
    return get_business_context_from_profile(profile_data)


# ==================== BRAND ASSET HELPERS ====================

def build_brand_color_instructions(profile_assets: dict, business_context: dict) -> str:
    """Build conditional color instructions based on available brand assets"""
    primary = profile_assets.get('primary_color')
    secondary = profile_assets.get('secondary_color')
    brand_colors = profile_assets.get('brand_colors', [])

    if primary and secondary:
        color_text = f"""
BRAND COLORS:
- Primary: {primary}
- Secondary: {secondary}
- Use primary color for main elements, secondary for accents and highlights"""

        if brand_colors:
            color_text += f"\n- Additional brand colors: {', '.join(brand_colors)}"

        return color_text

    elif primary:
        color_text = f"""
BRAND COLOR:
- Primary: {primary}
- Use this color consistently throughout the design"""

        if brand_colors:
            color_text += f"\n- Additional brand colors: {', '.join(brand_colors)}"

        return color_text

    elif brand_colors:
        return f"""
BRAND COLORS:
- Available colors: {', '.join(brand_colors)}
- Use these brand colors strategically in the design"""

    else:
        return f"""
COLOR PALETTE:
- Use professional, modern colors suitable for {business_context.get('industry', 'General')} industry
- Focus on colors that appeal to {business_context.get('target_audience', 'General audience')}"""


def build_content_brand_context(profile_assets: dict) -> str:
    """Build brand context for content generation prompts"""
    if profile_assets.get('primary_color') and profile_assets.get('secondary_color'):
        return f"""
Primary Brand Color: {profile_assets['primary_color']}
Secondary Brand Color: {profile_assets['secondary_color']}
Visual Style: Use these colors strategically in any visual suggestions"""
    elif profile_assets.get('primary_color'):
        return f"""
Primary Brand Color: {profile_assets['primary_color']}
Visual Style: Use this color as the main brand color in visual suggestions"""
    else:
        return """
Visual Style: Use professional, modern colors suitable for your industry"""


def build_location_context(business_context: dict) -> str:
    """Build location-aware context for image generation"""
    location_parts = []

    if business_context.get('location_city'):
        location_parts.append(business_context['location_city'])
    if business_context.get('location_state'):
        location_parts.append(business_context['location_state'])
    if business_context.get('location_country'):
        location_parts.append(business_context['location_country'])

    if location_parts:
        location_str = ', '.join(location_parts)
        timezone = business_context.get('timezone', '')

        location_context = f"""
LOCATION CONTEXT:
Business Location: {location_str}"""

        if timezone:
            location_context += f"\nTimezone: {timezone}"

        # Add location-specific imagery suggestions
        location_context += f"""
Location-Inspired Elements: Consider incorporating subtle local landmarks, architectural styles, or cultural elements from {location_str} that would resonate with the local audience. Adapt the imagery to reflect the local environment and aesthetic preferences of {business_context.get('location_city', 'the local area')}."""

        return location_context
    else:
        return """
LOCATION CONTEXT:
No specific location information available. Use universally appealing, professional imagery that works across different regions and cultures."""


def build_image_enhancer_brand_assets(profile_assets: dict, business_context: dict) -> str:
    """Build brand assets context for image enhancer prompts"""
    primary = profile_assets.get('primary_color')
    secondary = profile_assets.get('secondary_color')
    brand_colors = profile_assets.get('brand_colors', [])

    if primary and secondary:
        color_text = f"""
BRAND ASSETS:
Primary Color: {primary}
Secondary Color: {secondary}
Color Usage: Use primary color for main elements, secondary for accents and highlights"""

        if brand_colors:
            color_text += f"\nAdditional Brand Colors: {', '.join(brand_colors)}"

        return color_text

    elif primary:
        color_text = f"""
BRAND ASSETS:
Primary Color: {primary}
Color Usage: Use this color consistently throughout the design"""

        if brand_colors:
            color_text += f"\nAdditional Brand Colors: {', '.join(brand_colors)}"

        return color_text

    elif brand_colors:
        return f"""
BRAND ASSETS:
Available Brand Colors: {', '.join(brand_colors)}
Color Usage: Use these brand colors strategically in the composition"""

    else:
        return f"""
COLOR APPROACH:
Use a professional color palette suitable for {business_context.get('industry', 'General')} industry
Focus on colors that resonate with {business_context.get('target_audience', 'General audience')}"""


# ==================== PYDANTIC MODELS ====================

class CreateContentPayload(BaseModel):
    channel: Optional[Literal["Social Media", "Blog", "Email", "messages"]] = None
    platform: Optional[Literal["Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", "Whatsapp"]] = None
    content_type: Optional[Literal["Post", "short video", "long video", "Email", "message"]] = None
    media: Optional[Literal["Generate", "Upload", "without media"]] = None
    media_file: Optional[str] = None
    content_idea: Optional[str] = Field(None, min_length=10)
    content_id: Optional[str] = None
    agent_name: Optional[str] = None
    post_design_type: Optional[str] = None
    image_type: Optional[str] = None


class EditContentPayload(BaseModel):
    channel: Optional[Literal["Social Media", "Blog", "Email", "messages"]] = None
    platform: Optional[Literal["Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", "Whatsapp"]] = None
    content_type: Optional[Literal["Image", "text"]] = None
    content_id: Optional[str] = None
    edit_instruction: Optional[str] = None


class DeleteContentPayload(BaseModel):
    channel: Optional[Literal["Social Media", "Blog", "Email", "messages"]] = None
    platform: Optional[Literal["Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", "Whatsapp"]] = None
    date_range: Optional[str] = None  # Natural language date concept: "yesterday", "today", etc.
    start_date: Optional[str] = None  # Calculated from date_range (YYYY-MM-DD)
    end_date: Optional[str] = None    # Calculated from date_range (YYYY-MM-DD)
    status: Optional[Literal["generated", "scheduled", "published"]] = None
    content_id: Optional[str] = None


class ViewContentPayload(BaseModel):
    channel: Optional[Literal["Social Media", "Blog", "Email", "messages"]] = None
    platform: Optional[Literal["Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", "Whatsapp"]] = None
    date_range: Optional[str] = None  # Natural language date concept: "yesterday", "today", "this week", etc.
    start_date: Optional[str] = None  # Format: YYYY-MM-DD (calculated from date_range)
    end_date: Optional[str] = None    # Format: YYYY-MM-DD (calculated from date_range)
    status: Optional[Literal["generated", "scheduled", "published"]] = None
    content_type: Optional[Literal["post", "short_video", "long_video", "blog", "email", "message"]] = None
    query: Optional[str] = None  # Search query for semantic search in title and content


class PublishContentPayload(BaseModel):
    channel: Optional[Literal["Social Media", "Blog", "Email", "messages"]] = None
    platform: Optional[Literal["Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", "Whatsapp"]] = None
    date_range: Optional[str] = None  # Natural language date concept: "yesterday", "today", "this week", etc.
    start_date: Optional[str] = None  # Format: YYYY-MM-DD (calculated from date_range)
    end_date: Optional[str] = None    # Format: YYYY-MM-DD (calculated from date_range)
    status: Optional[Literal["generated", "scheduled"]] = None
    content_id: Optional[str] = None  # Specific content to publish (selected by user)
    query: Optional[str] = None  # Search query for semantic search in title and content


class ScheduleContentPayload(BaseModel):
    channel: Optional[Literal["Social Media", "Blog", "Email", "messages"]] = None
    platform: Optional[Literal["Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", "Whatsapp"]] = None
    content_id: Optional[str] = None
    schedule_date: Optional[str] = None
    schedule_time: Optional[str] = None


class CreateLeadPayload(BaseModel):
    lead_id: Optional[str] = None  # UUID of the lead (for updates/operations)
    lead_name: Optional[str] = None
    lead_email: Optional[str] = None
    lead_phone: Optional[str] = None
    lead_source: Optional[Literal["Manual Entry", "Facebook", "Instagram", "Walk Ins", "Referral", "Email", "Website", "Phone Call"]] = None
    lead_status: Optional[Literal["new", "contacted", "responded", "qualified", "converted", "lost", "invalid"]] = None
    remarks: Optional[str] = None  # Now required
    follow_up: Optional[str] = None  # Now required


class ViewLeadsPayload(BaseModel):
    lead_id: Optional[str] = None  # Specific lead ID to view
    lead_source: Optional[Literal["Manual Entry", "Facebook", "Instagram", "Walk Ins", "Referral", "Email", "Website", "Phone Call"]] = None
    lead_name: Optional[str] = None
    lead_email: Optional[str] = None
    lead_status: Optional[Literal["new", "contacted", "responded", "qualified", "converted", "lost", "invalid"]] = None
    lead_phone: Optional[str] = None
    time_period: Optional[str] = None  # Time period to filter leads (e.g., "last_7_days", "last_30_days", "this_month")


class EditLeadsPayload(BaseModel):
    lead_id: Optional[str] = None  # Required: UUID of lead to edit
    lead_name: Optional[str] = None
    lead_source: Optional[str] = None
    lead_email: Optional[str] = None
    lead_phone: Optional[str] = None
    new_lead_name: Optional[str] = None
    new_lead_email: Optional[str] = None
    new_lead_phone: Optional[str] = None
    new_lead_source: Optional[Literal["Manual Entry", "Facebook", "Instagram", "Walk Ins", "Referral", "Email", "Website", "Phone Call"]] = None
    new_lead_status: Optional[Literal["new", "contacted", "responded", "qualified", "converted", "lost", "invalid"]] = None
    new_remarks: Optional[str] = None


class DeleteLeadsPayload(BaseModel):
    lead_id: Optional[str] = None  # Required: UUID of lead to delete
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    lead_email: Optional[str] = None
    lead_status: Optional[Literal["New", "Contacted", "Qualified", "Lost", "Won"]] = None


class FollowUpLeadsPayload(BaseModel):
    lead_id: Optional[str] = None  # Required: UUID of lead to follow up with
    lead_name: Optional[str] = None
    lead_email: Optional[str] = None
    lead_phone: Optional[str] = None
    follow_up_message: Optional[str] = None
    follow_up_date: Optional[str] = None  # ISO format date string for follow-up scheduling


class ViewInsightsPayload(BaseModel):
    channel: Optional[Literal["Social Media", "Blog", "Email", "messages"]] = None
    platform: Optional[Literal["Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", "Whatsapp"]] = None
    metrics: Optional[List[str]] = None
    date_range: Optional[Literal["today", "this week", "last week", "yesterday", "custom date"]] = None


class ViewAnalyticsPayload(BaseModel):
    channel: Optional[Literal["Social Media", "Blog", "Email", "messages"]] = None
    platform: Optional[Literal["Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", "Whatsapp"]] = None
    date_range: Optional[Literal["today", "this week", "last week", "yesterday", "custom date"]] = None


# ==================== STATE ====================

class AgentState(BaseModel):
    user_query: str = ""  # Contains full conversation context (all messages appended)
    conversation_history: List[str] = Field(default_factory=list)  # Deprecated: kept for compatibility, not used
    intent: Optional[str] = None
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)
    payload_complete: bool = False
    clarification_question: Optional[str] = None
    clarification_options: Optional[List[Dict[str, Any]]] = None  # Clickable options for clarification
    waiting_for_user: bool = False
    result: Optional[str] = None
    error: Optional[str] = None
    current_step: str = "intent_classification"
    user_id: Optional[str] = None  # User ID for database queries
    content_id: Optional[str] = None  # Single content ID (UUID) for operations on specific content
    content_ids: Optional[List[str]] = None  # List of content IDs available for selection
    lead_id: Optional[str] = None  # Single lead ID (UUID) for operations on specific lead
    content_items: Optional[List[Dict[str, Any]]] = None  # Structured content data for frontend card rendering
    lead_items: Optional[List[Dict[str, Any]]] = None  # Structured lead data for frontend card rendering
    needs_connection: Optional[bool] = None  # Whether user needs to connect an account
    connection_platform: Optional[str] = None  # Platform that needs to be connected

    # Temporary fields for PII privacy protection
    temp_original_email: Optional[str] = None  # Original email from user input (create operations)
    temp_original_phone: Optional[str] = None  # Original phone from user input (create operations)
    temp_original_emails: Optional[List[str]] = Field(default_factory=list)  # Original emails (edit operations)
    temp_original_phones: Optional[List[str]] = Field(default_factory=list)  # Original phones (edit operations)
    temp_filter_emails: Optional[List[str]] = Field(default_factory=list)  # Original emails for filtering
    temp_filter_phones: Optional[List[str]] = Field(default_factory=list)  # Original phones for filtering
    temp_delete_emails: Optional[List[str]] = Field(default_factory=list)  # Original emails for deletion
    temp_delete_phones: Optional[List[str]] = Field(default_factory=list)  # Original phones for deletion
    temp_followup_emails: Optional[List[str]] = Field(default_factory=list)  # Original emails for follow-up
    temp_followup_phones: Optional[List[str]] = Field(default_factory=list)  # Original phones for follow-up

    # Intent change detection
    intent_change_detected: bool = False
    intent_change_type: Optional[str] = None  # 'refinement', 'complete_shift', 'none'
    previous_intent: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


# ==================== INTENT CLASSIFICATION ====================

INTENT_MAP = {
    "greeting": None,  # No payload needed for greetings
    "general_talks": None,  # No payload needed for general conversation
    "create_content": CreateContentPayload,
    "edit_content": EditContentPayload,
    "delete_content": DeleteContentPayload,
    "view_content": ViewContentPayload,
    "publish_content": PublishContentPayload,
    "schedule_content": ScheduleContentPayload,
    "create_leads": CreateLeadPayload,
    "view_leads": ViewLeadsPayload,
    "edit_leads": EditLeadsPayload,
    "delete_leads": DeleteLeadsPayload,
    "follow_up_leads": FollowUpLeadsPayload,
    "view_insights": ViewInsightsPayload,
    "view_analytics": ViewAnalyticsPayload,
}


def classify_intent(state: AgentState) -> AgentState:
    """Classify user intent using Gemini"""
    
    # If intent is already set and we're continuing from a clarification, preserve it
    # This prevents re-classification when user responds to clarification questions
    if state.intent and state.current_step == "payload_construction":
        print(f" Intent preserved: {state.intent} (continuing from clarification)")
        return state
    
    # Check for greetings first (simple pattern matching)
    user_query_lower = state.user_query.lower().strip()
    greeting_words = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 
                      'greetings', 'howdy', 'what\'s up', 'whats up', 'sup', 'yo']
    
    if any(greeting in user_query_lower for greeting in greeting_words) and len(user_query_lower.split()) <= 5:
        state.intent = "greeting"
        state.current_step = "action_execution"
        print(f" Intent classified: greeting")
        return state
    
    prompt = f"""You are an intent classifier for a content and lead management system.
    
Available intents:
1. greeting - User is greeting (hi, hello, good morning, etc.)
2. create_content - Creating new content (posts, videos, emails, messages)
3. edit_content - Editing existing content
4. delete_content - Deleting content
5. view_content - Viewing/listing content
6. publish_content - Publishing content to platforms
7. schedule_content - Scheduling content for future publishing
8. create_leads - Creating new leads
9. view_leads - Viewing/listing leads
10. edit_leads - Editing existing leads
11. delete_leads - Deleting leads
12. follow_up_leads - Following up with leads
13. view_insights - Viewing insights and metrics
14. view_analytics - Viewing analytics data
15. general_talks - General conversation not related to the above tasks

User query: {state.user_query}

Return ONLY the intent name (e.g., "create_content", "greeting", "general_talks", etc.) without any explanation.
If the query doesn't match any specific task, return "general_talks"."""

    try:
        response = model.generate_content(prompt)
        intent = response.text.strip().lower()
        
        # Validate intent
        if intent not in INTENT_MAP:
            # Try to find closest match
            for valid_intent in INTENT_MAP.keys():
                if valid_intent in intent or intent in valid_intent:
                    intent = valid_intent
                    break
            else:
                # Default to general_talks for unmatched intents
                intent = "general_talks"
        
        state.intent = intent
        
        # For greeting, handle directly and end
        if intent == "greeting":
            state = handle_greeting(state)
            state.current_step = "end"
            # Ensure result is never None
            if not state.result:
                state.result = "Hello! How can I help you today?"
        # For general_talks, skip payload construction
        elif intent == "general_talks":
            state.current_step = "action_execution"
        else:
            state.current_step = "payload_construction"
            
        print(f" Intent classified: {intent}")
        
    except Exception as e:
        state.error = f"Intent classification failed: {str(e)}"
        state.current_step = "end"
    
    return state


# ==================== PAYLOAD CONSTRUCTORS ====================

# Common JSON-only instruction suffix for all payload constructors
JSON_ONLY_INSTRUCTION = """

CRITICAL: You MUST respond with ONLY a valid JSON object. Do NOT include any explanatory text, comments, or additional text before or after the JSON.
Your response must start with {{ and end with }}. No other text is allowed.
Return ONLY the JSON object, nothing else."""

def construct_create_content_payload(state: AgentState) -> AgentState:
    """Construct payload for create content task"""
    
    # Use user_query which contains the full conversation context
    conversation = state.user_query
    
    prompt = f"""You are extracting information to create content. Analyze the user's query and extract relevant fields.

User conversation:
{conversation}

Extract these fields if mentioned:
- channel: "Social Media", "Blog", "Email", or "messages"
- platform: "Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", or "Whatsapp"
- content_type: "Post", "short video", "long video", "Email", or "message"
- media: "Generate", "Upload", or "without media"
- content_idea: The main idea/topic for the content (minimum 10 words)
- post_design_type: The style/type of post (News, Trendy, Educational, Informative, Announcement, BTS, UGC, etc.)
- image_type: The type of image/visual (product photo, poster graphic, quote card, infographic, etc.)

IMPORTANT: Do NOT set post_design_type to null - if not mentioned, omit it entirely so clarifying question is asked.
For image_type, only include if explicitly mentioned in the context of image generation.

Examples:

Query: "Create a trendy Instagram post about sustainable fashion trends for 2025"
{{
    "channel": "Social Media",
    "platform": "Instagram",
    "content_type": "Post",
    "media": null,
    "content_idea": "sustainable fashion trends for 2025 including eco-friendly materials and circular economy practices",
    "post_design_type": "Trendy"
}}

Query: "I need an informative LinkedIn video discussing AI impact on healthcare"
{{
    "channel": "Social Media",
    "platform": "LinkedIn",
    "content_type": "short video",
    "media": null,
    "content_idea": "artificial intelligence impact on healthcare industry transformation including diagnostics and patient care",
    "post_design_type": "Informative"
}}

Query: "Write an educational blog post with infographics about productivity hacks for remote workers"
{{
    "channel": "Blog",
    "platform": null,
    "content_type": "Post",
    "media": "Generate",
    "content_idea": "productivity hacks for remote workers including time management techniques and workspace optimization strategies",
    "post_design_type": "Educational",
    "image_type": "Infographic"
}}

Query: "Create an educational Instagram post with a quote card about learning new skills"
{{
    "channel": "Social Media",
    "platform": "Instagram",
    "content_type": "Post",
    "media": "Generate",
    "content_idea": "importance of continuous learning and skill development in today's fast-paced world",
    "post_design_type": "Educational",
    "image_type": "Quote card"
}}

Extract ONLY explicitly mentioned information.

IMPORTANT RULES:
- Set basic fields (channel, platform, content_type, media, content_idea) to null if not mentioned
- For post_design_type: ONLY include if explicitly mentioned as a post style/type, otherwise omit entirely
- For image_type: ONLY include if explicitly mentioned in context of image generation, otherwise omit entirely

{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def construct_edit_content_payload(state: AgentState) -> AgentState:
    """Construct payload for edit content task"""
    
    # Use user_query which contains the full conversation context
    conversation = state.user_query
    
    prompt = f"""You are extracting information to edit existing content.

User conversation:
{conversation}

Extract these fields if mentioned:
- channel: "Social Media", "Blog", "Email", or "messages"
- platform: "Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", or "Whatsapp"
- content_type: "Image" or "text"
- content_id: Specific content identifier
- edit_instruction: What changes to make

Examples:

Query: "Edit my Instagram post from yesterday to add more emojis"
{{
    "channel": "Social Media",
    "platform": "Instagram",
    "content_type": "text",
    "content_id": null,
    "edit_instruction": "add more emojis to the post"
}}

Query: "Change the text in my LinkedIn article about AI to be more professional"
{{
    "channel": "Social Media",
    "platform": "LinkedIn",
    "content_type": "text",
    "content_id": null,
    "edit_instruction": "make the text more professional and formal"
}}

Extract ONLY explicitly mentioned information. Set fields to null if not mentioned.
{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def construct_delete_content_payload(state: AgentState) -> AgentState:
    """Construct payload for delete content task"""

    # Use user_query which contains the full conversation context
    conversation = state.user_query

    # Get current date and user timezone for date parsing context
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Get user timezone from profile
    user_timezone = "UTC"  # default
    if state.user_id and supabase:
        try:
            profile_response = supabase.table("profiles").select("timezone").eq("id", state.user_id).execute()
            if profile_response.data and len(profile_response.data) > 0:
                user_timezone = profile_response.data[0].get("timezone", "UTC")
        except Exception as e:
            logger.warning(f"Could not fetch user timezone: {e}")

    prompt = f"""You are extracting information to delete content.

Current date reference: Today is {current_date}
User timezone: {user_timezone}

User conversation:
{conversation}

Extract these fields ONLY if explicitly mentioned:
- channel: "Social Media", "Blog", "Email", or "messages"
- platform: "Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", or "Whatsapp"
- date_range: PARSE dates into YYYY-MM-DD format (e.g., "2025-12-27") or date ranges like "2025-12-20 to 2025-12-27"
- status: "generated", "scheduled", or "published"
- content_id: Specific content identifier
- query: Any search terms or phrases the user wants to search for in content (e.g., "posts for new year", "christmas content", "product launch")

CRITICAL DATE PARSING RULES:
- Parse ALL date mentions into YYYY-MM-DD format without errors
- "today" → current date ({current_date}) in YYYY-MM-DD format
- "yesterday" → yesterday's date relative to {current_date}
- "tomorrow" → tomorrow's date relative to {current_date}
- "this week" → current week range (Monday to current day) relative to {current_date}
- "last week" → previous week range (Monday to Sunday) relative to {current_date}
- "this month" → current month range (1st to current day) relative to {current_date}
- "last month" → previous month range (1st to last day) relative to {current_date}
- "last_7_days" → date range for last 7 days from {current_date}
- "last_30_days" → date range for last 30 days from {current_date}
- Specific dates like "27 december" → "YYYY-12-27" (use current year if not specified)
- Month names: "january"/"jan" → "01", "february"/"feb" → "02", etc.
- For date ranges, use format "YYYY-MM-DD to YYYY-MM-DD"
- If no date mentioned, set date_range to null
- NEVER leave date parsing incomplete - always convert to proper format
- Use the user's timezone ({user_timezone}) for all date calculations

CRITICAL QUERY EXTRACTION:
- Extract search queries that indicate what content the user is looking for
- Examples: "posts for new year", "christmas content", "summer sale posts", "product launch videos"
- Set query field to the search phrase if user wants to find content by topic/theme
- If no specific search query mentioned, set query to null

CRITICAL RULES:
1. Set fields to null if NOT explicitly mentioned in the conversation
2. DO NOT infer or assume values - only extract what the user explicitly stated
3. If user says "delete content" without mentioning status, set status to null
4. If user says "remove posts" without mentioning status, set status to null
5. Only set status to "published" if user explicitly says "published", "posted", "live", etc.
6. Only set status to "scheduled" if user explicitly says "scheduled", "scheduled posts", etc.
7. Only set status to "generated" if user explicitly says "generated", "draft", "created", etc.
8. IMPORTANT: When user responds to clarification questions with single words, parse dates correctly:
   - "yesterday" → date_range: yesterday's date ({(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')})
   - "today" → date_range: today's date ({current_date})
   - "tomorrow" → date_range: tomorrow's date ({(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')})
   - "this week" → date_range: current week range
   - "last week" → date_range: previous week range
   - "this month" → date_range: current month range
   - "last month" → date_range: previous month range
   - "last_7_days" → date_range: last 7 days from {current_date}
   - "last_30_days" → date_range: last 30 days from {current_date}
   - "generated" → status: "generated"
   - "scheduled" → status: "scheduled"
   - "published" → status: "published"
   - "Instagram" → platform: "Instagram"
   - "Facebook" → platform: "Facebook"
   - "LinkedIn" → platform: "LinkedIn"
   - "YouTube" → platform: "Youtube"
   - "Gmail" → platform: "Gmail"
   - "WhatsApp" → platform: "Whatsapp"
   - "Social Media" → channel: "Social Media"
   - "Blog" → channel: "Blog"
   - "Email" → channel: "Email"
9. Preserve existing payload values - only update fields that are explicitly mentioned in the current response


{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def construct_view_content_payload(state: AgentState) -> AgentState:
    """Construct payload for view content task"""
    
    # Use user_query which contains the full conversation context
    conversation = state.user_query

    # Get current date and user timezone for date parsing context
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Get user timezone from profile
    user_timezone = "UTC"  # default
    if state.user_id and supabase:
        try:
            profile_response = supabase.table("profiles").select("timezone").eq("id", state.user_id).execute()
            if profile_response.data and len(profile_response.data) > 0:
                user_timezone = profile_response.data[0].get("timezone", "UTC")
        except Exception as e:
            logger.warning(f"Could not fetch user timezone: {e}")

    prompt = f"""You are extracting information to view/list content from the database.

Current date reference: Today is {current_date}
User timezone: {user_timezone}

User conversation:
{conversation}

Extract these fields ONLY if explicitly mentioned:
- channel: "Social Media", "Blog", "Email", or "messages"
- platform: "Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", or "Whatsapp"
- date_range: PARSE dates into YYYY-MM-DD format (e.g., "2025-12-27") or date ranges like "2025-12-20 to 2025-12-27"
- status: "generated", "scheduled", or "published"
- content_type: "post", "short_video", "long_video", "blog", "email", or "message"
- query: Any search terms or phrases the user wants to search for in content (e.g., "posts for new year", "christmas content", "product launch")

CRITICAL DATE PARSING RULES:
- Parse ALL date mentions into YYYY-MM-DD format without errors
- "today" → current date in YYYY-MM-DD format
- "yesterday" → yesterday's date in YYYY-MM-DD format
- "tomorrow" → tomorrow's date in YYYY-MM-DD format
- "this week" → current week range (Monday to current day)
- "last week" → previous week range (Monday to Sunday)
- "this month" → current month range (1st to current day)
- "last month" → previous month range (1st to last day)
- "last_7_days" → date range for last 7 days
- "last_30_days" → date range for last 30 days
- Specific dates like "27 december" → "YYYY-12-27" (use current year)
- For date ranges, use format "YYYY-MM-DD to YYYY-MM-DD"
- If no date mentioned, set date_range to null
- NEVER leave date parsing incomplete - always convert to proper format

CRITICAL QUERY EXTRACTION:
- Extract search queries that indicate what content the user is looking for
- Examples: "posts for new year", "christmas content", "summer sale posts", "product launch videos"
- Set query field to the search phrase if user wants to find content by topic/theme
- If no specific search query mentioned, set query to null

CRITICAL RULES:
1. Set fields to null if NOT explicitly mentioned in the conversation
2. DO NOT infer or assume values - only extract what the user explicitly stated
3. If user says "view content" without mentioning status, set status to null
4. If user says "show posts" without mentioning status, set status to null
5. Only set status to "published" if user explicitly says "published", "posted", "live", etc.
6. Only set status to "scheduled" if user explicitly says "scheduled", "scheduled posts", etc.
7. Only set status to "generated" if user explicitly says "generated", "draft", "created", etc.
8. Extract search queries like "posts about new year", "christmas content", "summer campaigns"
9. IMPORTANT: When user responds to clarification questions with single words, parse dates correctly:
   - "yesterday" → date_range: yesterday's date
   - "today" → date_range: today's date
   - "tomorrow" → date_range: tomorrow's date
   - "this week" → date_range: current week range
   - "last week" → date_range: previous week range
   - "this month" → date_range: current month range
   - "last month" → date_range: previous month range
   - Specific dates like "december 12" → parse to appropriate date
   - "Instagram" → platform: "Instagram"
   - "Facebook" → platform: "Facebook"
   - "Social Media" → channel: "Social Media"
   - "post" → content_type: "post"
   - "generated" → status: "generated"
   - "published" → status: "published"
10. Preserve existing payload values - only update fields that are explicitly mentioned in the current response


Extract ONLY explicitly mentioned information. Set fields to null if not mentioned.
DO NOT infer status - only set it if user explicitly mentions "published", "scheduled", "generated", "draft", etc.
When user responds with single words like "yesterday", "today", "Instagram", extract them into the correct field.

CRITICAL: You MUST respond with ONLY a valid JSON object. Do NOT include any explanatory text, comments, or additional text before or after the JSON.
Your response must start with {{ and end with }}. No other text is allowed.

Return ONLY this format:
{{
    "channel": null or "Social Media" or "Blog" or "Email" or "messages",
    "platform": null or "Instagram" or "Facebook" or "LinkedIn" or "Youtube" or "Gmail" or "Whatsapp",
    "date_range": null or "YYYY-MM-DD" or "YYYY-MM-DD to YYYY-MM-DD",
    "status": null or "generated" or "scheduled" or "published",
    "content_type": null or "post" or "short_video" or "long_video" or "blog" or "email" or "message"
}}"""

    return _extract_payload(state, prompt)


def construct_publish_content_payload(state: AgentState) -> AgentState:
    """Construct payload for publish content task"""

    # Use user_query which contains the full conversation context
    conversation = state.user_query

    # Get current date and user timezone for date parsing context
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Get user timezone from profile
    user_timezone = "UTC"  # default
    if state.user_id and supabase:
        try:
            profile_response = supabase.table("profiles").select("timezone").eq("id", state.user_id).execute()
            if profile_response.data and len(profile_response.data) > 0:
                user_timezone = profile_response.data[0].get("timezone", "UTC")
        except Exception as e:
            logger.warning(f"Could not fetch user timezone: {e}")

    prompt = f"""You are extracting information to publish content.

Current date reference: Today is {current_date}
User timezone: {user_timezone}

User conversation:
{conversation}

Extract these fields ONLY if explicitly mentioned:
- channel: "Social Media", "Blog", "Email", or "messages"
- platform: "Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", or "Whatsapp"
- date_range: PARSE dates into YYYY-MM-DD format (e.g., "2025-12-27") or date ranges like "2025-12-20 to 2025-12-27"
- status: "generated", "scheduled"
- content_id: Specific content identifier (e.g., "abc123", "content_001")
- query: Any search terms or phrases the user wants to search for in content (e.g., "posts for new year", "christmas content", "product launch")

CRITICAL CONTENT SELECTION:
- If user says "Publish content: [ID]" or similar, extract the content_id
- Examples: "Publish content: abc123", "Select content abc123", "Publish this content"

CRITICAL DATE PARSING RULES:
- Parse ALL date mentions into YYYY-MM-DD format without errors
- "today" → current date in YYYY-MM-DD format
- "yesterday" → yesterday's date in YYYY-MM-DD format
- "tomorrow" → tomorrow's date in YYYY-MM-DD format
- "this week" → current week range (Monday to current day)
- "last week" → previous week range (Monday to Sunday)
- "this month" → current month range (1st to current day)
- "last month" → previous month range (1st to last day)
- "last_7_days" → date range for last 7 days
- "last_30_days" → date range for last 30 days
- Specific dates like "27 december" → "YYYY-12-27" (use current year)
- For date ranges, use format "YYYY-MM-DD to YYYY-MM-DD"
- If no date mentioned, set date_range to null
- NEVER leave date parsing incomplete - always convert to proper format

CRITICAL QUERY EXTRACTION:
- Extract search queries that indicate what content the user is looking for
- Examples: "posts for new year", "christmas content", "summer sale posts", "product launch videos"
- Set query field to the search phrase if user wants to find content by topic/theme
- If no specific search query mentioned, set query to null

Examples:

Query: "Publish my christmas content to Instagram this week"
{{
    "channel": "Social Media",
    "platform": "Instagram",
    "date_range": "current week range",
    "status": null,
    "content_id": null,
    "query": "christmas"
}}

Query: "Post the Facebook content I created yesterday"
{{
    "channel": "Social Media",
    "platform": "Facebook",
    "date_range": "yesterday's date",
    "status": null,
    "content_id": null,
    "query": null
}}

Query: "Publish content: abc123"
{{
    "channel": null,
    "platform": null,
    "date_range": null,
    "status": null,
    "content_id": "abc123",
    "query": null
}}

Extract ONLY explicitly mentioned information. Set fields to null if not mentioned.

Return ONLY this format:
{{
    "channel": null or "Social Media" or "Blog" or "Email" or "messages",
    "platform": null or "Instagram" or "Facebook" or "LinkedIn" or "Youtube" or "Gmail" or "Whatsapp",
    "date_range": null or "YYYY-MM-DD" or "YYYY-MM-DD to YYYY-MM-DD",
    "status": null or "generated" or "scheduled",
    "content_id": null or string,
    "query": null or string
}}

{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def construct_schedule_content_payload(state: AgentState) -> AgentState:
    """Construct payload for schedule content task"""
    
    # Use user_query which contains the full conversation context
    conversation = state.user_query
    
    prompt = f"""You are extracting information to schedule content for future publishing.

User conversation:
{conversation}

Extract these fields if mentioned:
- channel: "Social Media", "Blog", "Email", or "messages"
- platform: "Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", or "Whatsapp"
- content_id: Specific content identifier
- schedule_date: Date to publish (format: YYYY-MM-DD or relative like "tomorrow", "next Monday")
- schedule_time: Time to publish (format: HH:MM or "morning", "afternoon", "evening")

Examples:

Query: "Schedule my Instagram post for tomorrow at 9 AM"
{{
    "channel": "Social Media",
    "platform": "Instagram",
    "content_id": null,
    "schedule_date": "tomorrow",
    "schedule_time": "09:00"
}}

Query: "Post to LinkedIn next Monday at 2 PM"
{{
    "channel": "Social Media",
    "platform": "LinkedIn",
    "content_id": null,
    "schedule_date": "next Monday",
    "schedule_time": "14:00"
}}

Extract ONLY explicitly mentioned information. Set fields to null if not mentioned.
{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def construct_create_leads_payload(state: AgentState) -> AgentState:
    """Construct payload for create leads task"""

    # Detect and replace PII with default values, store originals
    sanitized_conversation, original_emails, original_phones = detect_and_replace_pii_in_query(state.user_query)
    # Store first email/phone found (for create operations, typically only one set)
    state.temp_original_email = original_emails[0] if original_emails else None
    state.temp_original_phone = original_phones[0] if original_phones else None

    # Get current date and user timezone for date parsing context
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Get user timezone from profile
    user_timezone = "UTC"  # default
    if state.user_id and supabase:
        try:
            profile_response = supabase.table("profiles").select("timezone").eq("id", state.user_id).execute()
            if profile_response.data and len(profile_response.data) > 0:
                user_timezone = profile_response.data[0].get("timezone", "UTC")
        except Exception as e:
            logger.warning(f"Could not fetch user timezone: {e}")

    prompt = f"""You are extracting information to create a new lead in the system.

Current date reference: Today is {current_date}
User timezone: {user_timezone}

User conversation:
{sanitized_conversation}

Extract these fields if mentioned:
- lead_name: Full name of the lead
- lead_email: Email address
- lead_phone: Phone number
- lead_source: Where the lead came from (website, referral, event, social media, etc.)
- lead_status: "New", "Contacted", "Qualified", "Lost", or "Won"
- follow_up: PARSE dates into YYYY-MM-DD format or ISO format (YYYY-MM-DDTHH:MM:SS)
- remarks: Additional notes

CRITICAL DATE PARSING RULES FOR follow_up:
- Parse ALL date mentions into YYYY-MM-DD format
- "today" → current date ({current_date}) in YYYY-MM-DD format
- "yesterday" → DO NOT USE PAST DATES, convert to tomorrow
- "tomorrow" → tomorrow's date in YYYY-MM-DD format
- "next week" → date 7 days from {current_date}
- Weekday names ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday") → calculate the NEXT occurrence of that weekday from {current_date}
  * If today is Tuesday (Dec 31, 2025) and user says "Sunday", return 2026-01-04 (next Sunday)
  * If today is Tuesday and user says "Friday", return 2026-01-03 (this Friday)
  * If today is Tuesday and user says "Tuesday", return 2026-01-07 (next Tuesday, not today)
  * ALWAYS find the NEXT upcoming occurrence, never use today or past dates
- "next monday", "next tuesday", etc → same as above, calculate next occurrence of that weekday
- Specific dates like "Jan 15" → "YYYY-01-15" (use current/next year appropriately)
- NEVER use past dates - always convert to future dates
- If no date mentioned, set follow_up to null
- Use {current_date} as the reference point for all calculations

Examples:

Query: "Add a new lead John Doe from the website, email atsn@gmail.com, follow up tomorrow"
{{
    "lead_name": "John Doe",
    "lead_email": "atsn@gmail.com",
    "lead_phone": null,
    "lead_source": "website",
    "lead_status": null,
    "follow_up": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}",
    "remarks": null
}}

Query: "Create lead Sarah Johnson, phone 9876543210, came from LinkedIn, status is qualified, follow up next Monday"
{{
    "lead_name": "Sarah Johnson",
    "lead_email": null,
    "lead_phone": "9876543210",
    "lead_source": "LinkedIn",
    "lead_status": "Qualified",
    "follow_up": "2025-01-06",
    "remarks": null
}}

Query: "New lead: Mike Chen, atsn@gmail.com, referred by existing client, very interested in our services"
{{
    "lead_name": "Mike Chen",
    "lead_email": "atsn@gmail.com",
    "lead_phone": null,
    "lead_source": "referral",
    "lead_status": null,
    "follow_up": null,
    "remarks": "very interested in our services, referred by existing client"
}}

Extract ONLY explicitly mentioned information. Set fields to null if not mentioned.
{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def construct_view_leads_payload(state: AgentState) -> AgentState:
    """Construct payload for view leads task"""

    # Detect and replace PII with default values for privacy
    sanitized_conversation, original_emails, original_phones = detect_and_replace_pii_in_query(state.user_query)
    # Store originals for potential filtering
    state.temp_filter_emails = original_emails
    state.temp_filter_phones = original_phones

    # Get current date and user timezone for date parsing context
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Get user timezone from profile
    user_timezone = "UTC"  # default
    if state.user_id and supabase:
        try:
            profile_response = supabase.table("profiles").select("timezone").eq("id", state.user_id).execute()
            if profile_response.data and len(profile_response.data) > 0:
                user_timezone = profile_response.data[0].get("timezone", "UTC")
        except Exception as e:
            logger.warning(f"Could not fetch user timezone: {e}")

    prompt = f"""You are extracting information to view/filter leads.

Current date reference: Today is {current_date}
User timezone: {user_timezone}

User conversation:
{sanitized_conversation}

Extract these fields if mentioned:
- lead_source: One of "Manual Entry", "Facebook", "Instagram", "Walk Ins", "Referral", "Email", "Website", "Phone Call"
- lead_name: Filter by name
- lead_email: Filter by email
- lead_status: One of "new", "contacted", "responded", "qualified", "converted", "lost", "invalid"
- lead_phone: Filter by phone
- date_range: PARSE dates into YYYY-MM-DD format or date ranges

CRITICAL DATE PARSING RULES:
- Parse ALL date mentions into YYYY-MM-DD format without errors
- "today" → current date in YYYY-MM-DD format
- "yesterday" → yesterday's date in YYYY-MM-DD format
- "tomorrow" → tomorrow's date in YYYY-MM-DD format
- "this week" → current week range (Monday to current day)
- "last week" → previous week range (Monday to Sunday)
- "this month" → current month range (1st to current day)
- "last month" → previous month range (1st to last day)
- "last_7_days" → date range for last 7 days
- "last_30_days" → date range for last 30 days
- Specific dates like "27 december" → "YYYY-12-27" (use current year)
- For date ranges, use format "YYYY-MM-DD to YYYY-MM-DD"
- If no date mentioned, set date_range to null
- NEVER leave date parsing incomplete - always convert to proper format

Examples:

Query: "Show me all leads from Facebook"
{{
    "lead_source": "Facebook",
    "lead_name": null,
    "lead_email": null,
    "lead_status": null,
    "lead_phone": null,
    "date_range": null
}}

Query: "List all qualified leads from last month"
{{
    "lead_source": null,
    "lead_name": null,
    "lead_email": null,
    "lead_status": "qualified",
    "lead_phone": null,
    "date_range": "last month range"
}}

Query: "Find lead John Doe"
{{
    "lead_source": null,
    "lead_name": "John Doe",
    "lead_email": null,
    "lead_status": null,
    "lead_phone": null,
    "date_range": null
}}

Query: "Show me converted leads from Instagram in the last 30 days"
{{
    "lead_source": "Instagram",
    "lead_name": null,
    "lead_email": null,
    "lead_status": "converted",
    "lead_phone": null,
    "date_range": "last 30 days range"
}}

Query: "Show me leads from yesterday"
{{
    "lead_source": null,
    "lead_name": null,
    "lead_email": null,
    "lead_status": null,
    "lead_phone": null,
    "date_range": "yesterday's date"
}}

Extract ONLY explicitly mentioned information. Set fields to null if not mentioned.

Return ONLY this format:
{{
    "lead_source": null or "Manual Entry" or "Facebook" or "Instagram" or "Walk Ins" or "Referral" or "Email" or "Website" or "Phone Call",
    "lead_name": null or string,
    "lead_email": null or string,
    "lead_status": null or "new" or "contacted" or "responded" or "qualified" or "converted" or "lost" or "invalid",
    "lead_phone": null or string,
    "date_range": null or "YYYY-MM-DD" or "YYYY-MM-DD to YYYY-MM-DD"
}}

{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def construct_edit_leads_payload(state: AgentState) -> AgentState:
    """Construct payload for edit leads task"""

    # Detect and replace PII with default values, store originals for both current and new values
    sanitized_conversation, original_emails, original_phones = detect_and_replace_pii_in_query(state.user_query)
    # For edit operations, store multiple emails/phones (current and new)
    state.temp_original_emails = original_emails
    state.temp_original_phones = original_phones

    prompt = f"""You are extracting information to edit an existing lead.

User conversation:
{sanitized_conversation}

Extract these fields if mentioned:
Identification (current values):
- lead_name: Current name to find the lead
- lead_email: Current email to find the lead (use atsn@gmail.com if mentioned)
- lead_phone: Current phone to find the lead (use 9876543210 if mentioned)

Updates (new values, prefix with "new_"):
- new_lead_name: New name
- new_lead_email: New email (use atsn@gmail.com if mentioned)
- new_lead_phone: New phone (use 9876543210 if mentioned)
- new_lead_source: New source
- new_lead_status: "New", "Contacted", "Qualified", "Lost", or "Won"
- new_remarks: New remarks

Examples:

Query: "Update John Doe's status to Contacted"
{{
    "lead_name": "John Doe",
    "lead_email": null,
    "lead_phone": null,
    "new_lead_status": "Contacted"
}}

Query: "Change the email for Sarah Johnson to atsn@gmail.com"
{{
    "lead_name": "Sarah Johnson",
    "lead_email": null,
    "lead_phone": null,
    "new_lead_email": "atsn@gmail.com"
}}

Query: "Mark lead atsn@gmail.com as won and add note: closed deal worth $10k"
{{
    "lead_name": null,
    "lead_email": "atsn@gmail.com",
    "lead_phone": null,
    "new_lead_status": "Won",
    "new_remarks": "closed deal worth $10k"
}}

Extract ONLY explicitly mentioned information. Set fields to null if not mentioned.
{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def construct_delete_leads_payload(state: AgentState) -> AgentState:
    """Construct payload for delete leads task"""

    # Detect and replace PII with default values for privacy
    sanitized_conversation, original_emails, original_phones = detect_and_replace_pii_in_query(state.user_query)
    # Store originals for deletion identification
    state.temp_delete_emails = original_emails
    state.temp_delete_phones = original_phones

    prompt = f"""You are extracting information to delete a lead.

User conversation:
{sanitized_conversation}

Extract these fields if mentioned:
- lead_name: Name of lead to delete
- lead_phone: Phone of lead to delete
- lead_email: Email of lead to delete
- lead_status: Filter by status before deleting

Examples:

Query: "Delete the lead John Doe"
{{
    "lead_name": "John Doe",
    "lead_phone": null,
    "lead_email": null,
    "lead_status": null
}}

Query: "Remove lead with email atsn@gmail.com"
{{
    "lead_name": null,
    "lead_phone": null,
    "lead_email": "spam@example.com",
    "lead_status": null
}}

Query: "Delete all lost leads"
{{
    "lead_name": null,
    "lead_phone": null,
    "lead_email": null,
    "lead_status": "Lost"
}}

Extract ONLY explicitly mentioned information. Set fields to null if not mentioned.
{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def construct_follow_up_leads_payload(state: AgentState) -> AgentState:
    """Construct payload for follow up leads task"""

    # Detect and replace PII with default values for privacy
    sanitized_conversation, original_emails, original_phones = detect_and_replace_pii_in_query(state.user_query)
    # Store originals for follow-up identification
    state.temp_followup_emails = original_emails
    state.temp_followup_phones = original_phones

    # Get current date for date parsing context
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""You are extracting information to follow up with a lead.

Current date reference: Today is {current_date}

User conversation:
{sanitized_conversation}

Extract these fields if mentioned:
- lead_name: Name of lead to follow up
- lead_email: Email of lead to follow up
- lead_phone: Phone of lead to follow up
- follow_up_message: Specific message to send (optional)
- follow_up_date: PARSE dates into YYYY-MM-DD format

DATE PARSING RULES FOR follow_up_date:
- "today" → current date ({current_date}) in YYYY-MM-DD format
- "tomorrow" → tomorrow's date in YYYY-MM-DD format
- "next week" → date 7 days from {current_date}
- Weekday names ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday") → calculate the NEXT occurrence of that weekday from {current_date}
  * If today is Tuesday (Dec 31, 2025) and user says "Sunday", return 2026-01-04 (next Sunday)
  * If today is Tuesday and user says "Friday", return 2026-01-03 (this Friday)
  * If today is Tuesday and user says "Tuesday", return 2026-01-07 (next Tuesday, not today)
  * ALWAYS find the NEXT upcoming occurrence, never use today or past dates
- "next monday", "next tuesday", etc → same as above, calculate next occurrence of that weekday
- Specific dates like "Jan 15" → "YYYY-01-15" (use current/next year appropriately)
- NEVER use past dates - always convert to future dates
- If no date mentioned, set to null
- Use {current_date} as the reference point for all calculations

Examples:

Query: "Follow up with John Doe about the proposal next Monday"
{{
    "lead_name": "John Doe",
    "lead_email": null,
    "lead_phone": null,
    "follow_up_message": "following up about the proposal",
    "follow_up_date": "2025-01-06"
}}

Query: "Send follow-up email to atsn@gmail.com asking about the meeting tomorrow"
{{
    "lead_name": null,
    "lead_email": "sarah@company.com",
    "lead_phone": null,
    "follow_up_message": "asking about the meeting",
    "follow_up_date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}"
}}

Query: "Call lead Mike Chen to check if he's ready to proceed"
{{
    "lead_name": "Mike Chen",
    "lead_email": null,
    "lead_phone": null,
    "follow_up_message": "check if ready to proceed with next steps",
    "follow_up_date": null
}}

Extract ONLY explicitly mentioned information. Set fields to null if not mentioned.
{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def construct_view_insights_payload(state: AgentState) -> AgentState:
    """Construct payload for view insights task"""
    
    # Use user_query which contains the full conversation context
    conversation = state.user_query
    
    prompt = f"""You are extracting information to view insights and metrics.

User conversation:
{conversation}

Extract these fields if mentioned:
- channel: "Social Media", "Blog", "Email", or "messages"
- platform: "Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", or "Whatsapp"
- metrics: List of metrics (engagement, reach, clicks, conversions, etc.)
- date_range: "today", "this week", "last week", "yesterday", or "custom date"

Examples:

Query: "Show me Instagram engagement metrics for this week"
{{
    "channel": "Social Media",
    "platform": "Instagram",
    "metrics": ["engagement"],
    "date_range": "this week"
}}

Query: "What's the reach and clicks on LinkedIn posts from last week?"
{{
    "channel": "Social Media",
    "platform": "LinkedIn",
    "metrics": ["reach", "clicks"],
    "date_range": "last week"
}}

Query: "Display all social media insights"
{{
    "channel": "Social Media",
    "platform": null,
    "metrics": null,
    "date_range": null
}}

Extract ONLY explicitly mentioned information. Set fields to null if not mentioned.
{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def construct_view_analytics_payload(state: AgentState) -> AgentState:
    """Construct payload for view analytics task"""
    
    # Use user_query which contains the full conversation context
    conversation = state.user_query
    
    prompt = f"""You are extracting information to view analytics data.

User conversation:
{conversation}

Extract these fields if mentioned:
- channel: "Social Media", "Blog", "Email", or "messages"
- platform: "Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", or "Whatsapp"
- date_range: "today", "this week", "last week", "yesterday", or "custom date"

Examples:

Query: "Show me Facebook analytics for this week"
{{
    "channel": "Social Media",
    "platform": "Facebook",
    "date_range": "this week"
}}

Query: "Display email analytics from last week"
{{
    "channel": "Email",
    "platform": "Gmail",
    "date_range": "last week"
}}

Query: "Show all LinkedIn analytics"
{{
    "channel": "Social Media",
    "platform": "LinkedIn",
    "date_range": null
}}

Extract ONLY explicitly mentioned information. Set fields to null if not mentioned.
{JSON_ONLY_INSTRUCTION}"""

    return _extract_payload(state, prompt)


def _extract_payload(state: AgentState, prompt: str) -> AgentState:
    """Helper function to extract payload using Gemini with retry mechanism"""
    import json
    import re
    
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            # Add stricter instruction on retry
            current_prompt = prompt
            if attempt > 0:
                current_prompt = prompt + "\n\nREMINDER: Respond with ONLY JSON. No explanations, no text before or after. Just the JSON object starting with { and ending with }."
            
            response = model.generate_content(current_prompt)
            raw_result = response.text.strip()
            
            # Log raw response for debugging
            logger.info(f"Raw LLM response (attempt {attempt + 1}): {raw_result[:300]}...")
            
            if not raw_result:
                if attempt < max_retries - 1:
                    continue  # Retry
                raise ValueError("Empty response from LLM")
            
            result = raw_result
            
            # Clean JSON response - try multiple extraction methods
            # Method 1: Extract from code blocks
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                # Try to extract JSON from any code block
                code_blocks = re.findall(r'```(?:json)?\s*\n?(.*?)```', result, re.DOTALL)
                if code_blocks:
                    result = code_blocks[0].strip()
            
            # Method 2: Try to find JSON object in text using improved regex
            if not result or result == raw_result or not result.startswith('{'):
                # Look for JSON object pattern - improved regex to handle nested objects
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_result, re.DOTALL)
                if json_match:
                    result = json_match.group(0).strip()
            
            # Method 3: If still no JSON found, try the whole response
            if not result or result == raw_result:
                result = raw_result.strip()
            
            # Remove any leading/trailing non-JSON text
            # Find the first { and last }
            first_brace = result.find('{')
            last_brace = result.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                result = result[first_brace:last_brace + 1]
            
            # Check if result looks like JSON (starts with { and ends with })
            if not result or not result.startswith('{') or not result.endswith('}'):
                if attempt < max_retries - 1:
                    logger.warning(f"No valid JSON found in attempt {attempt + 1}, retrying...")
                    continue  # Retry
                raise ValueError(f"No JSON found in response. Raw response: {raw_result[:200]}")
            
            # Try to parse JSON
            try:
                extracted_payload = json.loads(result)
            except json.JSONDecodeError as json_err:
                # Log the problematic JSON for debugging
                logger.error(f"JSON parse error (attempt {attempt + 1}): {json_err}")
                logger.error(f"Attempted to parse: {result[:500]}")
                if attempt < max_retries - 1:
                    logger.warning(f"Retrying with stricter prompt...")
                    continue  # Retry with stricter prompt
                raise ValueError(f"Invalid JSON format: {str(json_err)}. Response: {result[:200]}")
            
            # Validate extracted payload is a dict
            if not isinstance(extracted_payload, dict):
                if attempt < max_retries - 1:
                    continue  # Retry
                raise ValueError(f"Extracted payload is not a dictionary: {type(extracted_payload)}")
            
            # Merge with existing payload - only update non-null values to preserve existing data
            if state.payload:
                # Only update fields that are not null in the extracted payload
                for key, value in extracted_payload.items():
                    # For required clarifying question fields, treat null as "not present"
                    if key in ['post_design_type', 'image_type'] and value is None:
                        continue  # Skip null values for clarifying question fields
                    elif value is not None:
                        state.payload[key] = value
            else:
                # Filter out null values for clarifying question fields
                filtered_payload = {k: v for k, v in extracted_payload.items()
                                  if not (k in ['post_design_type', 'image_type'] and v is None)}
                state.payload = filtered_payload
            
            state.current_step = "payload_completion"
            print(f" Payload constructed: {state.payload}")
            logger.info(f"Successfully extracted payload on attempt {attempt + 1}: {state.payload}")
            return state  # Success!
            
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}, retrying...")
                continue  # Retry
            else:
                # Final attempt failed
                error_msg = f"Payload construction failed after {max_retries} attempts: {str(e)}"
                logger.error(error_msg, exc_info=True)
                logger.error(f"Final raw response: {raw_result[:500] if 'raw_result' in locals() else 'N/A'}")
                state.error = error_msg
                state.current_step = "end"
                # Don't clear existing payload on error - preserve what we have
                return state
    
    # Should not reach here, but just in case
    state.error = "Payload construction failed: Unknown error"
    state.current_step = "end"
    return state


# ==================== PAYLOAD COMPLETERS ====================

FIELD_CLARIFICATIONS = {
    "create_content": {
        "channel": {
            "question": "Hello! Let's create some content together.\n\nWhich channel would you like to focus on?",
            "options": [
                {"label": "Social Media", "value": "Social Media"},
                {"label": "Blog", "value": "Blog"},
                {"label": "Email", "value": "Email"},
                {"label": "Messages", "value": "Messages"}
            ]
        },
        "platform": {
            "question": "Great choice! Now, where would you like to share this content?",
            "options": [
                {"label": "Instagram", "value": "Instagram"},
                {"label": "Facebook", "value": "Facebook"},
                {"label": "LinkedIn", "value": "LinkedIn"},
                {"label": "YouTube", "value": "YouTube"},
                {"label": "Gmail", "value": "Gmail"},
                {"label": "WhatsApp", "value": "WhatsApp"}
            ]
        },
        "content_type": {
            "question": "Perfect! What kind of content are you thinking?",
            "options": [
                {"label": "Post", "value": "Post"},
                {"label": "Short video", "value": "Short video"},
                {"label": "Long video", "value": "Long video"},
                {"label": "Email", "value": "Email"},
                {"label": "Message", "value": "Message"}
            ]
        },
        "media": {
            "question": "Awesome! Should we include some visual elements?",
            "options": [
                {"label": "Yes, Generate", "value": "Generate"},
                {"label": "I will Upload", "value": "Upload"},
                {"label": "Generate Without media", "value": "Without media"}
            ]
        },
        "content_idea": {
            "question": "Love it! Tell me more about what you have in mind. What's the main idea or topic you want to cover? (Aim for at least 10 words to give me a good sense of what you're looking for)",
            "options": []
        },
        "post_design_type": {
            "question": "What kind of post design are you looking for? (News, Trendy, Educational, Informative, Announcement, BTS, UGC, etc.)",
            "options": []
        },
        "image_type": {
            "question": "What type of image would you like? (e.g., product photo, poster graphic, quote card, infographic, etc.)",
            "options": []
        },
    },
    "edit_content": {
        "channel": {
            "question": "Let's edit some content! Which channel is your content currently on?",
            "options": [
                {"label": "Social Media", "value": "Social Media", "description": "Posts and updates"},
                {"label": "Blog", "value": "Blog", "description": "Articles and long-form content"},
                {"label": "Email", "value": "Email", "description": "Newsletters and campaigns"},
                {"label": "Messages", "value": "Messages", "description": "Direct messaging content"}
            ]
        },
        "platform": {
            "question": "Got it! Which platform are we working with?",
            "options": [
                {"label": "Instagram", "value": "Instagram", "description": "Visual content"},
                {"label": "Facebook", "value": "Facebook", "description": "Community posts"},
                {"label": "LinkedIn", "value": "LinkedIn", "description": "Professional content"},
                {"label": "YouTube", "value": "YouTube", "description": "Video content"},
                {"label": "Gmail", "value": "Gmail", "description": "Email content"},
                {"label": "WhatsApp", "value": "WhatsApp", "description": "Messages"}
            ]
        },
        "content_type": {
            "question": "Perfect! What would you like to edit?",
            "options": [
                {"label": "Image", "value": "image", "description": "Update photos or graphics"},
                {"label": "Text", "value": "text", "description": "Modify the written content"}
            ]
        },
        "edit_instruction": {
            "question": "Sounds good! What changes would you like to make? Feel free to describe exactly what you want to update, change, or improve!",
            "options": []
        },
    },
    "delete_content": {
        "channel": {
            "question": "Let's clean up some content! Which channel should we look in?",
            "options": [
                {"label": "Social Media", "value": "Social Media"},
                {"label": "Blog", "value": "Blog"},
                {"label": "Email", "value": "Email"},
                {"label": "Messages", "value": "Messages"}
            ]
        },
        "platform": {
            "question": "Alright! which platform do you want to delete content from? I can show you your content for Instagram, Facebook, LinkedIn, YouTube, Gmail, or WhatsApp.",
            "options": [
                {"label": "Instagram", "value": "Instagram"},
                {"label": "Facebook", "value": "Facebook"},
                {"label": "LinkedIn", "value": "LinkedIn"},
                {"label": "YouTube", "value": "YouTube"},
                {"label": "Gmail", "value": "Gmail"},
                {"label": "WhatsApp", "value": "WhatsApp"}
            ]
        },
        "date_range": {
            "question": "Please select a time period to delete content from",
            "options": [
                {"label": "Today", "value": "today"},
                {"label": "This week", "value": "this week"},
                {"label": "Last week", "value": "last week"},
                {"label": "Yesterday", "value": "yesterday"},
                {"label": "Custom date", "value": "show_date_picker"}
            ]
        },
        "status": {
            "question": "which content do you want to delete, your drafts or scheduled posts or published posts ?",
            "options": [
                {"label": "Generated", "value": "generated"},
                {"label": "Scheduled", "value": "scheduled"},
                {"label": "Published", "value": "published"}
            ]
        },
    },
    "view_content": {
        "channel": {
            "question": "Which channel would you like to explore? I can show you your content in Social Media, Blog, Email, or Messages.",
            "options": [
                {"label": "Social Media", "value": "Social Media"},
                {"label": "Blog", "value": "Blog"},
                {"label": "Email", "value": "Email"},
                {"label": "Messages", "value": "Messages"}
            ]
        },
        "platform": {
            "question": "Which platform would you like to explore? I can show you your content on Instagram, Facebook, LinkedIn, YouTube, Gmail, or WhatsApp.",
            "options": [
                {"label": "Instagram", "value": "Instagram"},
                {"label": "Facebook", "value": "Facebook"},
                {"label": "LinkedIn", "value": "LinkedIn"},
                {"label": "YouTube", "value": "YouTube"},
                {"label": "Gmail", "value": "Gmail"},
                {"label": "WhatsApp", "value": "WhatsApp"}
            ]
        },
        "date_range": {
            "question": "Which time period would you like to explore? I can show you content from Today, This week, Last week, Yesterday, or you can specify a custom date.",
            "options": [
                {"label": "Today", "value": "today"},
                {"label": "This week", "value": "this week"},
                {"label": "Last week", "value": "last week"},
                {"label": "Yesterday", "value": "yesterday"},
                {"label": "Custom date", "value": "show_date_picker"}
            ]
        },
        "status": {
            "question": "Which content status would you like to see? I can filter by Generated (drafts), Scheduled (waiting to publish), or Published (already posted).",
            "options": [
                {"label": "Generated", "value": "generated"},
                {"label": "Scheduled", "value": "scheduled"},
                {"label": "Published", "value": "published"}
            ]
        },
        "content_type": {
            "question": "Which content type would you like to explore? I can show you Posts, Short videos, Long videos, Blogs, Emails, or Messages.",
            "options": [
                {"label": "Post", "value": "post"},
                {"label": "Short video", "value": "short video"},
                {"label": "Long video", "value": "long video"},
                {"label": "Blog", "value": "blog"},
                {"label": "Email", "value": "email"},
                {"label": "Message", "value": "message"}
            ]
        },
    },
    "publish_content": {
        "channel": {
            "question": "Which content do you want to publish? I can show you your content for Social Media, Blog, Email, or Messages.",
            "options": [
                {"label": "Social Media", "value": "Social Media"},
                {"label": "Blog", "value": "Blog"},
                {"label": "Email", "value": "Email"},
                {"label": "Messages", "value": "Messages"}
            ]
        },
        "platform": {
            "question": "Which platform do you want to publish on? I can show you your content for Instagram, Facebook, LinkedIn, YouTube, Gmail, or WhatsApp.",
            "options": [
                {"label": "Instagram", "value": "Instagram"},
                {"label": "Facebook", "value": "Facebook"},
                {"label": "LinkedIn", "value": "LinkedIn"},
                {"label": "YouTube", "value": "YouTube"},
                {"label": "Gmail", "value": "Gmail"},
                {"label": "WhatsApp", "value": "WhatsApp"}
            ]
        },
        "date_range": {
            "question": "Please select a time period to search your drafted posts or scheduled posts to publish",
            "options": [
                {"label": "Today", "value": "today"},
                {"label": "This week", "value": "this week"},
                {"label": "Last week", "value": "last week"},
                {"label": "Yesterday", "value": "yesterday"},
                {"label": "Custom date", "value": "show_date_picker"}
            ]
        },
        "status": {
            "question": "Do you want to publish from your generated or drafts posts? or publish a scheduled post early",
            "options": [
                {"label": "Generated/Drafts", "value": "generated"},
                {"label": "Scheduled", "value": "scheduled"}
            ]
        },
    },
    "schedule_content": {
        "channel": {
            "question": "Let's schedule some content! Which channel are we working with?",
            "options": [
                {"label": "Social Media", "value": "Social Media", "description": "Posts and updates"},
                {"label": "Blog", "value": "Blog", "description": "Articles and long-form content"},
                {"label": "Email", "value": "Email", "description": "Newsletters and campaigns"},
                {"label": "Messages", "value": "Messages", "description": "Direct messaging content"}
            ]
        },
        "platform": {
            "question": "Great! Which platform should we schedule for?",
            "options": [
                {"label": "Instagram", "value": "Instagram", "description": "Visual posts"},
                {"label": "Facebook", "value": "Facebook", "description": "Community content"},
                {"label": "LinkedIn", "value": "LinkedIn", "description": "Professional posts"},
                {"label": "YouTube", "value": "YouTube", "description": "Video content"},
                {"label": "Gmail", "value": "Gmail", "description": "Email campaigns"},
                {"label": "WhatsApp", "value": "WhatsApp", "description": "Messages"}
            ]
        },
        "content_id": {
            "question": "Almost there! Which specific content would you like to schedule?",
            "options": []
        },
        "schedule_date": {
            "question": "Perfect! When would you like this to go live? You can say things like 'Tomorrow at 3pm', 'December 25, 2025', or 'Next Monday morning'. What's your preferred date and time?",
            "options": []
        },
        "schedule_time": {
            "question": "Awesome! What time should it be posted? (e.g., '9:00 AM', '2:30 PM', etc.)",
            "options": []
        },
    },
    "create_leads": {
        "lead_name": {
            "question": "Let's add a new lead! What's the person's name? (This helps us identify them easily)",
            "options": []
        },
        "lead_email": {
            "question": "Got it! What's their email address? We'll use this to stay in touch.",
            "options": []
        },
        "lead_phone": {
            "question": "Perfect! What's their phone number? (Optional, but helpful for follow-ups)",
            "options": []
        },
        "lead_source": {
            "question": "Thanks! How did you connect with this lead? This helps us understand where our best leads come from!",
            "options": [
                {"label": "Website", "value": "Website", "description": "Through your site"},
                {"label": "Social Media", "value": "Social Media", "description": "From social platforms"},
                {"label": "Referral", "value": "Referral", "description": "Someone recommended them"},
                {"label": "Event", "value": "Event", "description": "Met at an event"},
                {"label": "Other", "value": "Other", "description": "Tell me more"}
            ]
        },
        "lead_status": {
            "question": "Great! What's their current status in our process?",
            "options": [
                {"label": "New", "value": "new", "description": "Just discovered"},
                {"label": "Contacted", "value": "contacted", "description": "We've reached out"},
                {"label": "Qualified", "value": "qualified", "description": "Good fit for us"},
                {"label": "Proposal", "value": "proposal", "description": "Sent a proposal"},
                {"label": "Negotiation", "value": "negotiation", "description": "Discussing terms"},
                {"label": "Closed Won", "value": "closed_won", "description": "They chose us!"},
                {"label": "Closed Lost", "value": "closed_lost", "description": "Didn't work out"}
            ]
        },
        "follow_up": {
            "question": "When should we follow up with this lead? Choose from common options or pick a custom date.",
            "options": [
                {"label": "Today", "value": "today"},
                {"label": "Tomorrow", "value": "tomorrow"},
                {"label": "Next week", "value": "next week"},
                {"label": "Next month", "value": "next month"},
                {"label": "Custom date", "value": "show_date_picker"}
            ]
        },
        "remarks": {
            "question": "Awesome! Any additional notes or details about this lead that would be helpful to remember?",
            "options": []
        },
    },
    "view_leads": {
        "lead_source": {
            "question": "Let's find some leads! Which source would you like to check?",
            "options": [
                {"label": "Website", "value": "Website"},
                {"label": "Social Media", "value": "Social Media"},
                {"label": "Referral", "value": "Referral"},
                {"label": "Event", "value": "Event"},
                {"label": "Other", "value": "Other"}
            ]
        },
        "lead_name": {
            "question": "Perfect! Which lead would you like to look up? Just give me their name.",
            "options": []
        },
        "lead_email": {
            "question": "Got it! What's their email address? I'll find them for you.",
            "options": []
        },
        "lead_status": {
            "question": "Great! Which status group are you interested in?",
            "options": [
                {"label": "New", "value": "new"},
                {"label": "Contacted", "value": "contacted"},
                {"label": "Qualified", "value": "qualified"},
                {"label": "Proposal", "value": "proposal"},
                {"label": "Negotiation", "value": "negotiation"},
                {"label": "Closed Won", "value": "closed_won"},
                {"label": "Closed Lost", "value": "closed_lost"}
            ]
        },
        "lead_phone": {
            "question": "Alright! What's their phone number? I'll search for the matching contact.",
            "options": []
        },
        "date_range": {
            "question": "Please select a date range to view these leads.",
            "options": [
                {"label": "Today", "value": "today"},
                {"label": "Yesterday", "value": "yesterday"},
                {"label": "This week", "value": "this week"},
                {"label": "Last week", "value": "last week"},
                {"label": "This month", "value": "this month"},
                {"label": "Last month", "value": "last month"},
                {"label": "Custom date", "value": "show_date_picker"}
            ]
        },
    },
    "edit_leads": {
        "lead_name": {
            "question": "Let's update a lead! Which lead would you like to edit? Just tell me their name.",
            "options": []
        },
        "lead_source": {
            "question": "Thanks! What's their new source?",
            "options": [
                {"label": "Website", "value": "Website", "description": "Website visitor"},
                {"label": "Social Media", "value": "Social Media", "description": "Social contact"},
                {"label": "Referral", "value": "Referral", "description": "Recommended"},
                {"label": "Event", "value": "Event", "description": "Event attendee"},
                {"label": "Other", "value": "Other", "description": "Tell me more"}
            ]
        },
        "lead_email": {
            "question": "Got it! What's their new email address?",
            "options": []
        },
        "lead_phone": {
            "question": "Perfect! What's their updated phone number?",
            "options": []
        },
    },
    "delete_leads": {
        "lead_name": {
            "question": "Let's clean up the leads list! Which lead would you like to remove? Just give me their name.",
            "options": []
        },
        "lead_phone": {
            "question": "Alright! What's their phone number? This helps me find the right person.",
            "options": []
        },
        "lead_email": {
            "question": "Got it! What's their email address? I'll locate them for you.",
            "options": []
        },
        "lead_status": {
            "question": "Thanks! What's their current status?",
            "options": [
                {"label": "New", "value": "new", "description": "Fresh leads"},
                {"label": "Contacted", "value": "contacted", "description": "We've reached out"},
                {"label": "Qualified", "value": "qualified", "description": "Good prospects"},
                {"label": "Proposal", "value": "proposal", "description": "Sent proposals"},
                {"label": "Negotiation", "value": "negotiation", "description": "Active discussions"},
                {"label": "Closed Won", "value": "closed_won", "description": "Our clients!"},
                {"label": "Closed Lost", "value": "closed_lost", "description": "Didn't convert"}
            ]
        },
    },
    "follow_up_leads": {
        "lead_name": {
            "question": "Time for a follow-up! Which lead would you like to reach out to?",
            "options": []
        },
        "lead_email": {
            "question": "Perfect! What's their email address? I'll help you craft the perfect follow-up.",
            "options": []
        },
        "lead_phone": {
            "question": "Got it! What's their phone number? We can prepare a call or message.",
            "options": []
        },
    },
    "view_insights": {
        "channel": {
            "question": "Let's check your performance! Which channel would you like insights for?",
            "options": [
                {"label": "Social Media", "value": "Social Media", "description": "Social performance"},
                {"label": "Blog", "value": "Blog", "description": "Article engagement"},
                {"label": "Email", "value": "Email", "description": "Campaign results"},
                {"label": "Messages", "value": "Messages", "description": "Direct message stats"}
            ]
        },
        "platform": {
            "question": "Awesome! Which platform should we analyze?",
            "options": [
                {"label": "Instagram", "value": "Instagram", "description": "Visual analytics"},
                {"label": "Facebook", "value": "Facebook", "description": "Community metrics"},
                {"label": "LinkedIn", "value": "LinkedIn", "description": "Professional insights"},
                {"label": "YouTube", "value": "YouTube", "description": "Video performance"},
                {"label": "Gmail", "value": "Gmail", "description": "Email analytics"},
                {"label": "WhatsApp", "value": "WhatsApp", "description": "Message engagement"}
            ]
        },
        "date_range": {
            "question": "Perfect! What time period interests you?",
            "options": [
                {"label": "Today", "value": "today", "description": "Today's performance"},
                {"label": "This week", "value": "this week", "description": "Weekly overview"},
                {"label": "Last week", "value": "last week", "description": "Previous week"},
                {"label": "This month", "value": "this month", "description": "Monthly summary"},
                {"label": "Last month", "value": "last month", "description": "Last month's data"}
            ]
        },
        "metrics": {
            "question": "Great! What would you like to focus on?",
            "options": [
                {"label": "Engagement", "value": "engagement", "description": "Likes, comments, shares"},
                {"label": "Reach", "value": "reach", "description": "How many people saw it"},
                {"label": "Followers", "value": "followers", "description": "Growth metrics"},
                {"label": "Performance", "value": "performance", "description": "Overall success"},
                {"label": "All metrics", "value": "all", "description": "Complete overview"}
            ]
        },
    },
    "view_analytics": {
        "channel": {
            "question": "Let's dive into the numbers! Which channel would you like to analyze?",
            "options": [
                {"label": "Social Media", "value": "Social Media", "description": "Social performance"},
                {"label": "Blog", "value": "Blog", "description": "Article analytics"},
                {"label": "Email", "value": "Email", "description": "Campaign metrics"},
                {"label": "Messages", "value": "Messages", "description": "Direct message stats"}
            ]
        },
        "platform": {
            "question": "Exciting! Which platform should we examine?",
            "options": [
                {"label": "Instagram", "value": "Instagram", "description": "Visual analytics"},
                {"label": "Facebook", "value": "Facebook", "description": "Community insights"},
                {"label": "LinkedIn", "value": "LinkedIn", "description": "Professional metrics"},
                {"label": "YouTube", "value": "YouTube", "description": "Video performance"},
                {"label": "Gmail", "value": "Gmail", "description": "Email analytics"},
                {"label": "WhatsApp", "value": "WhatsApp", "description": "Message statistics"}
            ]
        },
        "date_range": {
            "question": "Perfect! What time period should we look at?",
            "options": [
                {"label": "Today", "value": "today", "description": "Today's data"},
                {"label": "This week", "value": "this week", "description": "Weekly trends"},
                {"label": "Last week", "value": "last week", "description": "Previous week"},
                {"label": "This month", "value": "this month", "description": "Monthly overview"},
                {"label": "Last month", "value": "last month", "description": "Last month's performance"}
            ]
        },
    },
}


# ==================== INDIVIDUAL PAYLOAD COMPLETERS ====================

def complete_view_content_payload(state: AgentState) -> AgentState:
    """Complete view_content payload - ALL fields required before proceeding, except when search query is provided"""
    # If payload is already complete, don't check again
    if state.payload_complete:
        logger.info("Payload already complete, skipping completion check")
        state.current_step = "action_execution"
        return state

    # Give priority to search queries - if query is present, skip clarifying questions
    if state.payload.get('query') and state.payload['query'].strip():
        logger.info("Search query detected, skipping clarifying questions and proceeding with search")
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" View content payload complete - search query provided, proceeding without clarifications")
        print(f"  Final payload: {state.payload}")
        return state

    required_fields = ["channel", "platform", "date_range", "status", "content_type"]
    clarifications = FIELD_CLARIFICATIONS.get("view_content", {})

    # Convert date_range to start_date and end_date if present
    if state.payload.get("date_range") and state.payload["date_range"]:
        date_range = str(state.payload["date_range"]).strip()
        date_filter = _parse_date_range_format(date_range)

        if date_filter:
            # Successfully converted date_range to actual dates
            state.payload["start_date"] = date_filter.get("start") if date_filter.get("start") else None
            state.payload["end_date"] = date_filter.get("end") if date_filter.get("end") else None
            print(f" Converted '{date_range}' to start_date: {state.payload['start_date']}, end_date: {state.payload['end_date']}")
        else:
            # Could not parse date_range
            print(f"⚠️ Could not parse date_range '{date_range}', treating as missing")
            state.payload["date_range"] = None
            state.payload["start_date"] = None
            state.payload["end_date"] = None
    
    # Normalize platform if present (handle case)
    if state.payload.get("platform"):
        platform_val = str(state.payload["platform"]).strip()
        valid_platforms = ["Instagram", "Facebook", "LinkedIn", "Youtube", "Gmail", "Whatsapp"]
        # Keep original case for platform (it's used as-is in queries)
        if platform_val.title() in [p.title() for p in valid_platforms]:
            state.payload["platform"] = platform_val
        else:
            # Try to match common variations
            platform_lower = platform_val.lower()
            if platform_lower in ["instagram", "ig"]:
                state.payload["platform"] = "Instagram"
            elif platform_lower in ["facebook", "fb"]:
                state.payload["platform"] = "Facebook"
            elif platform_lower in ["linkedin", "li"]:
                state.payload["platform"] = "LinkedIn"
            elif platform_lower in ["youtube", "yt"]:
                state.payload["platform"] = "Youtube"
            elif platform_lower == "gmail":
                state.payload["platform"] = "Gmail"
            elif platform_lower in ["whatsapp", "wa"]:
                state.payload["platform"] = "Whatsapp"
    
    # Normalize channel if present
    if state.payload.get("channel"):
        channel_val = str(state.payload["channel"]).strip()
        valid_channels = ["Social Media", "Blog", "Email", "messages"]
        if channel_val in valid_channels:
            state.payload["channel"] = channel_val
        else:
            # Try to match variations
            channel_lower = channel_val.lower()
            if "social" in channel_lower or "media" in channel_lower:
                state.payload["channel"] = "Social Media"
            elif channel_lower == "blog":
                state.payload["channel"] = "Blog"
            elif channel_lower == "email":
                state.payload["channel"] = "Email"
            elif channel_lower in ["message", "messages"]:
                state.payload["channel"] = "messages"
    
    # Normalize status if present
    if state.payload.get("status"):
        status_val = str(state.payload["status"]).lower().strip()
        valid_statuses = ["generated", "scheduled", "published"]
        if status_val in valid_statuses:
            state.payload["status"] = status_val
        else:
            # Try to match variations
            if status_val in ["draft", "create", "new"]:
                state.payload["status"] = "generated"
            elif status_val in ["schedule", "pending"]:
                state.payload["status"] = "scheduled"
            elif status_val in ["publish", "posted", "live"]:
                state.payload["status"] = "published"
            else:
                state.payload["status"] = None
    
    # Normalize content_type if present
    if state.payload.get("content_type"):
        content_type_val = str(state.payload["content_type"]).lower().strip()
        valid_types = ["post", "short_video", "long_video", "blog", "email", "message"]
        if content_type_val in valid_types:
            state.payload["content_type"] = content_type_val
        else:
            # Try to match variations
            if content_type_val in ["posts", "post"]:
                state.payload["content_type"] = "post"
            elif "short" in content_type_val and "video" in content_type_val:
                state.payload["content_type"] = "short_video"
            elif "long" in content_type_val and "video" in content_type_val:
                state.payload["content_type"] = "long_video"
            elif content_type_val == "blog":
                state.payload["content_type"] = "blog"
            elif content_type_val == "email":
                state.payload["content_type"] = "email"
            elif content_type_val in ["message", "messages"]:
                state.payload["content_type"] = "message"
            else:
                state.payload["content_type"] = None
    
    missing_fields = [
        f for f in required_fields 
        if f not in state.payload or state.payload.get(f) is None or not state.payload.get(f)
    ]
    
    if not missing_fields:
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" View content payload complete - all fields provided")
        print(f"  Final payload: {state.payload}")
        return state
    
    next_field = missing_fields[0]
    clarification_data = clarifications.get(next_field, {})

    if isinstance(clarification_data, dict):
        base_question = clarification_data.get("question", f"Please provide: {next_field.replace('_', ' ')}")

        # Generate personalized question using LLM
        logger.info(f"Calling LLM for clarification question. Base: '{base_question}', User context length: {len(state.user_query or '')}")
        personalized_question = generate_clarifying_question(
            base_question=base_question,
            user_context=state.user_query,
            user_input=state.user_query.split('\n')[-1] if state.user_query else ""
        )
        logger.info(f"LLM returned: '{personalized_question}'")

        state.clarification_question = personalized_question
        state.clarification_options = clarification_data.get("options", [])
    else:
        # Backward compatibility for string clarifications
        state.clarification_question = clarification_data or f"Please provide: {next_field.replace('_', ' ')}"
        state.clarification_options = []

    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for view_content: {state.clarification_question}")

    return state


def complete_create_content_payload(state: AgentState) -> AgentState:
    """Complete create_content payload"""
    required_fields = ["channel", "platform", "content_type", "media", "content_idea", "post_design_type"]
    clarifications = FIELD_CLARIFICATIONS.get("create_content", {})

    # Add image_type as required if media is "Generate"
    if state.payload.get("media") == "Generate":
        required_fields.append("image_type")

    missing_fields = [
        f for f in required_fields
        if f not in state.payload or state.payload.get(f) is None or not state.payload.get(f)
    ]

    if not missing_fields:
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" Create content payload complete")
        return state

    next_field = missing_fields[0]
    clarification_data = clarifications.get(next_field, {})

    if isinstance(clarification_data, dict):
        base_question = clarification_data.get("question", f"Please provide: {next_field.replace('_', ' ')}")

        # Generate personalized question using LLM
        logger.info(f"Calling LLM for clarification question. Base: '{base_question}', User context length: {len(state.user_query or '')}")
        personalized_question = generate_clarifying_question(
            base_question=base_question,
            user_context=state.user_query,
            user_input=state.user_query.split('\n')[-1] if state.user_query else ""
        )
        logger.info(f"LLM returned: '{personalized_question}'")

        state.clarification_question = personalized_question
        state.clarification_options = clarification_data.get("options", [])
    else:
        # Backward compatibility for string clarifications
        state.clarification_question = clarification_data or f"Please provide: {next_field.replace('_', ' ')}"
        state.clarification_options = []

    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for create_content: {state.clarification_question}")

    return state


def complete_edit_content_payload(state: AgentState) -> AgentState:
    """Complete edit_content payload"""
    required_fields = ["channel", "platform", "edit_instruction"]
    clarifications = FIELD_CLARIFICATIONS.get("edit_content", {})

    missing_fields = [
        f for f in required_fields
        if f not in state.payload or state.payload.get(f) is None or not state.payload.get(f)
    ]

    if not missing_fields:
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" Edit content payload complete")
        return state

    next_field = missing_fields[0]
    clarification_data = clarifications.get(next_field, {})

    if isinstance(clarification_data, dict):
        base_question = clarification_data.get("question", f"Please provide: {next_field.replace('_', ' ')}")

        # Generate personalized question using LLM
        logger.info(f"Calling LLM for clarification question. Base: '{base_question}', User context length: {len(state.user_query or '')}")
        personalized_question = generate_clarifying_question(
            base_question=base_question,
            user_context=state.user_query,
            user_input=state.user_query.split('\n')[-1] if state.user_query else ""
        )
        logger.info(f"LLM returned: '{personalized_question}'")

        state.clarification_question = personalized_question
        state.clarification_options = clarification_data.get("options", [])
    else:
        # Backward compatibility for string clarifications
        state.clarification_question = clarification_data or f"Please provide: {next_field.replace('_', ' ')}"
        state.clarification_options = []

    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for edit_content: {state.clarification_question}")

    return state


def complete_delete_content_payload(state: AgentState) -> AgentState:
    """Complete delete_content payload - ALL fields required for safety, except when search query is provided"""
    # If payload is already complete, don't check again
    if state.payload_complete:
        logger.info("Payload already complete, skipping completion check")
        state.current_step = "action_execution"
        return state

    # Give priority to search queries - if query is present, skip clarifying questions
    if state.payload.get('query') and state.payload['query'].strip():
        logger.info("Search query detected, skipping clarifying questions and proceeding with search")
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" Delete content payload complete - search query provided, proceeding without clarifications")
        print(f"  Final payload: {state.payload}")
        return state

    required_fields = ["channel", "platform", "date_range", "status"]
    clarifications = FIELD_CLARIFICATIONS.get("delete_content", {})

    # Convert date_range to start_date and end_date if present (same as view_content)
    if state.payload.get("date_range") and state.payload["date_range"]:
        date_range = str(state.payload["date_range"]).strip()
        date_filter = _parse_date_range_format(date_range)

        if date_filter:
            # Successfully converted date_range to actual dates
            state.payload["start_date"] = date_filter.get("start") if date_filter.get("start") else None
            state.payload["end_date"] = date_filter.get("end") if date_filter.get("end") else None
            print(f" Converted '{date_range}' to start_date: {state.payload['start_date']}, end_date: {state.payload['end_date']}")
        else:
            # Could not parse date_range
            print(f"⚠️ Could not parse date_range '{date_range}', treating as missing")
            state.payload["date_range"] = None
            state.payload["start_date"] = None
            state.payload["end_date"] = None

    # Check if we have all required fields including converted dates
    missing_fields = [
        f for f in required_fields
        if f not in state.payload or state.payload.get(f) is None or not state.payload.get(f)
    ]

    # Also check that date conversion was successful
    if not state.payload.get("start_date") or not state.payload.get("end_date"):
        if "date_range" not in missing_fields:
            missing_fields.append("date_range")

    # Normalize status if present
    if state.payload.get("status"):
        status_val = str(state.payload["status"]).lower().strip()
        valid_statuses = ["generated", "scheduled", "published"]
        if status_val in valid_statuses:
            state.payload["status"] = status_val
        else:
            # Try to match variations
            if status_val in ["draft", "create", "new"]:
                state.payload["status"] = "generated"
            elif status_val in ["schedule", "pending"]:
                state.payload["status"] = "scheduled"
            elif status_val in ["publish", "posted", "live"]:
                state.payload["status"] = "published"
            else:
                state.payload["status"] = None

    if not missing_fields:
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" Delete content payload complete - all fields and date conversion successful")
        return state

    next_field = missing_fields[0]
    clarification_data = clarifications.get(next_field, {})

    if isinstance(clarification_data, dict):
        base_question = clarification_data.get("question", f"Please provide: {next_field.replace('_', ' ')}")

        # Generate personalized question using LLM
        logger.info(f"Calling LLM for clarification question. Base: '{base_question}', User context length: {len(state.user_query or '')}")
        personalized_question = generate_clarifying_question(
            base_question=base_question,
            user_context=state.user_query,
            user_input=state.user_query.split('\n')[-1] if state.user_query else ""
        )
        logger.info(f"LLM returned: '{personalized_question}'")

        state.clarification_question = personalized_question
        state.clarification_options = clarification_data.get("options", [])
    else:
        # Backward compatibility for string clarifications
        state.clarification_question = clarification_data or f"Please provide: {next_field.replace('_', ' ')}"
        state.clarification_options = []

    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for delete_content: {state.clarification_question}")

    return state


def check_channel_connection(user_id: str, channel_or_platform: str) -> bool:
    """Check if user has an active connection for the specified channel/platform"""
    if not supabase or not user_id or not channel_or_platform:
        return False

    try:
        # First check if it's a direct platform name
        platform_names = ["instagram", "facebook", "linkedin", "youtube", "gmail", "whatsapp", "wordpress", "google"]
        if channel_or_platform.lower() in platform_names:
            platform = channel_or_platform.lower()
            # Handle platform name variations
            if platform == "gmail":
                platform = "google"
        else:
            # Map channel to platform for connection checking
            platform_mapping = {
                "Social Media": None,  # Social Media is a channel, not a specific platform
                "Blog": "wordpress",
                "Email": "google",  # Gmail uses Google OAuth
                "messages": "whatsapp"
            }

            platform = platform_mapping.get(channel_or_platform)
            if not platform:
                # For Social Media channel or unknown channel, allow to proceed
                # They will need to specify a platform
                return True

        # Check if user has active connection for this platform (case-insensitive)
        response = supabase.table("platform_connections").select("*").eq(
            "user_id", user_id
        ).ilike("platform", platform).eq("is_active", True).execute()

        return bool(response.data and len(response.data) > 0)

    except Exception as e:
        logger.error(f"Error checking channel connection: {e}")
        return False


def complete_publish_content_payload(state: AgentState) -> AgentState:
    """Complete publish_content payload - fields required before proceeding, except when search query is provided"""

    # Handle direct content selection (highest priority)
    if state.payload.get('content_id') and state.payload['content_id'].strip():
        logger.info(f"Direct content selection detected: {state.payload['content_id']}")
        state.payload_complete = True
        state.current_step = "action_execution"
        print(f" Publish content payload complete - direct content selection: {state.payload['content_id']}")
        print(f"  Final payload: {state.payload}")
        return state

    # Give priority to search queries - if query is present, skip clarifying questions
    if state.payload.get('query') and state.payload['query'].strip():
        logger.info("Search query detected, skipping clarifying questions and proceeding with search")
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" Publish content payload complete - search query provided, proceeding without clarifications")
        print(f"  Final payload: {state.payload}")
        return state

    required_fields = ["channel", "platform", "date_range", "status"]
    clarifications = FIELD_CLARIFICATIONS.get("publish_content", {})

    # Convert date_range to start_date and end_date if present
    if state.payload.get("date_range") and state.payload["date_range"]:
        date_range = str(state.payload["date_range"]).strip()
        date_filter = _parse_date_range_format(date_range)

        if date_filter:
            # Successfully converted date_range to actual dates
            state.payload["start_date"] = date_filter.get("start") if date_filter.get("start") else None
            state.payload["end_date"] = date_filter.get("end") if date_filter.get("end") else None
            print(f" Converted '{date_range}' to start_date: {state.payload['start_date']}, end_date: {state.payload['end_date']}")
        else:
            # Could not parse date_range
            print(f"⚠️ Could not parse date_range '{date_range}', treating as missing")
            state.payload["date_range"] = None
            state.payload["start_date"] = None
            state.payload["end_date"] = None

    # Handle special connection-related responses
    user_query_lower = state.user_query.lower().strip() if state.user_query else ""
    if user_query_lower in ["connect_account", "change_channel", "change_platform", "cancel"]:
        if user_query_lower == "connect_account":
            # Determine which platform needs to be connected based on current payload
            platform_to_connect = state.payload.get('platform')
            print(f"DEBUG: connect_account selected, current payload: {state.payload}")
            print(f"DEBUG: platform from payload: {platform_to_connect}")

            if not platform_to_connect:
                # Try to map channel to platform
                channel = state.payload.get('channel')
                print(f"DEBUG: channel from payload: {channel}")

                if channel == "Social Media":
                    # For Social Media, ask user to specify which platform
                    state.result = "Please specify which social media platform you want to connect to first. Choose from: Instagram, Facebook, LinkedIn, or YouTube."
                    state.clarification_question = "Which social media platform would you like to connect?"
                    state.clarification_options = [
                        {"label": "Instagram", "value": "instagram"},
                        {"label": "Facebook", "value": "facebook"},
                        {"label": "LinkedIn", "value": "linkedin"},
                        {"label": "YouTube", "value": "youtube"}
                    ]
                    state.waiting_for_user = True
                    state.current_step = "waiting_for_clarification"
                    return state
                elif channel == "Blog":
                    platform_to_connect = "wordpress"
                elif channel == "Email":
                    platform_to_connect = "google"
                elif channel == "messages":
                    platform_to_connect = "whatsapp"

            # Normalize platform name to lowercase for OAuth compatibility
            if platform_to_connect:
                platform_to_connect = platform_to_connect.lower()
                # Handle special cases
                if platform_to_connect == "gmail":
                    platform_to_connect = "google"

            print(f"DEBUG: normalized platform_to_connect: {platform_to_connect}")

            # Return connection information for frontend to handle OAuth
            state.result = f"To publish to this platform, you need to connect your account first."
            state.needs_connection = True
            state.connection_platform = platform_to_connect
            state.payload_complete = True
            state.current_step = "connection_required"
            return state
        elif user_query_lower in ["change_channel", "change_platform"]:
            # Reset the relevant field to allow user to choose again
            if "channel" in state.payload:
                state.payload["channel"] = None
            if "platform" in state.payload:
                state.payload["platform"] = None
            state.payload_complete = False
            state.waiting_for_user = False
            state.current_step = "payload_construction"
            return state
        elif user_query_lower == "cancel":
            # Cancel the operation
            state.result = "Publish operation cancelled."
            state.payload_complete = True
            state.current_step = "end"
            return state
    
    missing_fields = [
        f for f in required_fields 
        if f not in state.payload or state.payload.get(f) is None or not state.payload.get(f)
    ]
    
    if not missing_fields:
        # Check if user has connection for the selected channel/platform before allowing publish
        channel = state.payload.get('channel')
        platform = state.payload.get('platform')

        # Check platform connection first (more specific)
        if platform and not check_channel_connection(state.user_id, platform):
            # User doesn't have connection for this platform
            state.payload_complete = False
            state.clarification_question = f"You don't have a connection set up for {platform}. Would you like to connect your {platform} account first?"
            state.clarification_options = [
                {"label": "Connect Account", "value": "connect_account"},
                {"label": "Choose Different Platform", "value": "change_platform"},
                {"label": "Cancel", "value": "cancel"}
            ]
            state.waiting_for_user = True
            state.current_step = "waiting_for_clarification"
            print(f"? Connection needed for {platform}")
            return state

        # Check channel connection (for channels that don't have specific platforms)
        elif channel and not check_channel_connection(state.user_id, channel):
            # User doesn't have connection for this channel
            state.payload_complete = False
            state.clarification_question = f"You don't have a connection set up for {channel}. Would you like to connect your {channel.lower()} account first?"
            state.clarification_options = [
                {"label": "Connect Account", "value": "connect_account"},
                {"label": "Choose Different Channel", "value": "change_channel"},
                {"label": "Cancel", "value": "cancel"}
            ]
            state.waiting_for_user = True
            state.current_step = "waiting_for_clarification"
            print(f"? Connection needed for {channel}")
            return state

        state.payload_complete = True
        state.current_step = "action_execution"
        print(" Publish content payload complete")
        return state
    
    next_field = missing_fields[0]
    clarification_data = clarifications.get(next_field, {})

    if isinstance(clarification_data, dict):
        base_question = clarification_data.get("question", f"Please provide: {next_field.replace('_', ' ')}")

        # Generate personalized question using LLM
        logger.info(f"Calling LLM for clarification question. Base: '{base_question}', User context length: {len(state.user_query or '')}")
        personalized_question = generate_clarifying_question(
            base_question=base_question,
            user_context=state.user_query,
            user_input=state.user_query.split('\n')[-1] if state.user_query else ""
        )
        logger.info(f"LLM returned: '{personalized_question}'")

        state.clarification_question = personalized_question
        state.clarification_options = clarification_data.get("options", [])
    else:
        # Backward compatibility for string clarifications
        state.clarification_question = clarification_data or f"Please provide: {next_field.replace('_', ' ')}"
        state.clarification_options = []

    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for publish_content: {state.clarification_question}")

    return state


def complete_schedule_content_payload(state: AgentState) -> AgentState:
    """Complete schedule_content payload"""
    required_fields = ["channel", "platform", "schedule_date", "schedule_time"]
    clarifications = FIELD_CLARIFICATIONS.get("schedule_content", {})
    
    missing_fields = [
        f for f in required_fields 
        if f not in state.payload or state.payload.get(f) is None or not state.payload.get(f)
    ]
    
    if not missing_fields:
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" Schedule content payload complete")
        return state
    
    next_field = missing_fields[0]
    clarification_data = clarifications.get(next_field, {})

    if isinstance(clarification_data, dict):
        base_question = clarification_data.get("question", f"Please provide: {next_field.replace('_', ' ')}")

        # Generate personalized question using LLM
        logger.info(f"Calling LLM for clarification question. Base: '{base_question}', User context length: {len(state.user_query or '')}")
        personalized_question = generate_clarifying_question(
            base_question=base_question,
            user_context=state.user_query,
            user_input=state.user_query.split('\n')[-1] if state.user_query else ""
        )
        logger.info(f"LLM returned: '{personalized_question}'")

        state.clarification_question = personalized_question
        state.clarification_options = clarification_data.get("options", [])
    else:
        # Backward compatibility for string clarifications
        state.clarification_question = clarification_data or f"Please provide: {next_field.replace('_', ' ')}"
        state.clarification_options = []

    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for schedule_content: {state.clarification_question}")

    return state


def complete_create_leads_payload(state: AgentState) -> AgentState:
    """Complete create_leads payload - ALL fields are compulsory"""
    clarifications = FIELD_CLARIFICATIONS.get("create_leads", {})

    # Check ALL required fields
    has_name = state.payload.get("lead_name") and state.payload.get("lead_name").strip()
    has_email = state.payload.get("lead_email") and state.payload.get("lead_email").strip()
    has_phone = state.payload.get("lead_phone") and state.payload.get("lead_phone").strip()
    has_source = state.payload.get("lead_source") and state.payload.get("lead_source").strip()
    has_status = state.payload.get("lead_status") and state.payload.get("lead_status").strip()
    has_follow_up = state.payload.get("follow_up") and state.payload.get("follow_up").strip()
    has_remarks = state.payload.get("remarks") and state.payload.get("remarks").strip()

    # Must have ALL required fields: name, contact method, source, status, follow_up, remarks
    if has_name and (has_email or has_phone) and has_source and has_status and has_follow_up and has_remarks:
        # All required fields are present, proceed
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" Create leads payload complete")
        return state

    # Ask for what's missing - check in priority order
    if not has_name:
        clarification_data = clarifications.get("lead_name", {})
        if isinstance(clarification_data, dict):
            base_question = clarification_data.get("question", "What's the lead's name?")
            personalized_question = generate_clarifying_question(
                base_question=base_question,
                user_context=state.user_query,
                user_input=state.user_query.split('\n')[-1] if state.user_query else ""
            )
            state.clarification_question = personalized_question
            state.clarification_options = clarification_data.get("options", [])
        else:
            state.clarification_question = clarification_data or "What's the lead's name?"
            state.clarification_options = []
    elif not has_email and not has_phone:
        clarification_data = clarifications.get("lead_email", {})
        if isinstance(clarification_data, dict):
            base_question = clarification_data.get("question", "What's their email address?")
            personalized_question = generate_clarifying_question(
                base_question=base_question,
                user_context=state.user_query,
                user_input=state.user_query.split('\n')[-1] if state.user_query else ""
            )
            state.clarification_question = personalized_question
            state.clarification_options = clarification_data.get("options", [])
        else:
            state.clarification_question = clarification_data or "What's their email address?"
            state.clarification_options = []
    elif not has_email:
        clarification_data = clarifications.get("lead_email", {})
        if isinstance(clarification_data, dict):
            base_question = clarification_data.get("question", "What's their email address?")
            personalized_question = generate_clarifying_question(
                base_question=base_question,
                user_context=state.user_query,
                user_input=state.user_query.split('\n')[-1] if state.user_query else ""
            )
            state.clarification_question = personalized_question
            state.clarification_options = clarification_data.get("options", [])
        else:
            state.clarification_question = clarification_data or "What's their email address?"
            state.clarification_options = []
    elif not has_phone:
        clarification_data = clarifications.get("lead_phone", {})
        if isinstance(clarification_data, dict):
            base_question = clarification_data.get("question", "What's their phone number?")
            personalized_question = generate_clarifying_question(
                base_question=base_question,
                user_context=state.user_query,
                user_input=state.user_query.split('\n')[-1] if state.user_query else ""
            )
            state.clarification_question = personalized_question
            state.clarification_options = clarification_data.get("options", [])
        else:
            state.clarification_question = clarification_data or "What's their phone number?"
            state.clarification_options = []
    elif not has_source:
        clarification_data = clarifications.get("lead_source", {})
        if isinstance(clarification_data, dict):
            base_question = clarification_data.get("question", "How did you connect with this lead?")
            personalized_question = generate_clarifying_question(
                base_question=base_question,
                user_context=state.user_query,
                user_input=state.user_query.split('\n')[-1] if state.user_query else ""
            )
            state.clarification_question = personalized_question
            state.clarification_options = clarification_data.get("options", [])
        else:
            state.clarification_question = clarification_data or "How did you connect with this lead?"
            state.clarification_options = []
    elif not has_status:
        clarification_data = clarifications.get("lead_status", {})
        if isinstance(clarification_data, dict):
            base_question = clarification_data.get("question", "What's their current status?")
            personalized_question = generate_clarifying_question(
                base_question=base_question,
                user_context=state.user_query,
                user_input=state.user_query.split('\n')[-1] if state.user_query else ""
            )
            state.clarification_question = personalized_question
            state.clarification_options = clarification_data.get("options", [])
        else:
            state.clarification_question = clarification_data or "What's their current status?"
            state.clarification_options = []
    elif not has_follow_up:
        clarification_data = clarifications.get("follow_up", {})
        if isinstance(clarification_data, dict):
            base_question = clarification_data.get("question", "When should we follow up with this lead?")
            personalized_question = generate_clarifying_question(
                base_question=base_question,
                user_context=state.user_query,
                user_input=state.user_query.split('\n')[-1] if state.user_query else ""
            )
            state.clarification_question = personalized_question
            state.clarification_options = clarification_data.get("options", [])
        else:
            state.clarification_question = clarification_data or "When should we follow up with this lead?"
            state.clarification_options = []
    elif not has_remarks:
        clarification_data = clarifications.get("remarks", {})
        if isinstance(clarification_data, dict):
            base_question = clarification_data.get("question", "Any additional notes or remarks about this lead?")
            personalized_question = generate_clarifying_question(
                base_question=base_question,
                user_context=state.user_query,
                user_input=state.user_query.split('\n')[-1] if state.user_query else ""
            )
            state.clarification_question = personalized_question
            state.clarification_options = clarification_data.get("options", [])
        else:
            state.clarification_question = clarification_data or "Any additional notes or remarks about this lead?"
            state.clarification_options = []

    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for create_leads: {state.clarification_question}")

    return state


def complete_view_leads_payload(state: AgentState) -> AgentState:
    """Complete view_leads payload - all fields optional except date_range when lead_status is provided"""
    payload = state.payload

    # If lead_status is provided, date_range becomes mandatory
    if payload.get('lead_status') and not payload.get('date_range'):
        state.payload_complete = False

        # Use FIELD_CLARIFICATIONS for consistent questioning
        clarifications = FIELD_CLARIFICATIONS.get("view_leads", {})
        clarification_data = clarifications.get("date_range", {})

        if isinstance(clarification_data, dict):
            base_question = clarification_data.get("question", "Please select a date range to view these leads.")
            # Generate personalized question using LLM
            logger.info(f"Calling LLM for clarification question. Base: '{base_question}', User context length: {len(state.user_query or '')}")
            personalized_question = generate_clarifying_question(
                base_question=base_question,
                user_context=state.user_query,
                user_input=state.user_query.split('\n')[-1] if state.user_query else ""
            )
            logger.info(f"LLM returned: '{personalized_question}'")

            state.clarification_question = personalized_question
            state.clarification_options = clarification_data.get("options", [])
        else:
            # Backward compatibility for string clarifications
            state.clarification_question = clarification_data or "When would you like to see these leads? Please tell me the time period (e.g., 'yesterday', 'this week', 'last month')."
            state.clarification_options = []

        state.waiting_for_user = True
        state.current_step = "waiting_for_clarification"
        print(f"? Clarification needed for view_leads: {state.clarification_question}")
        return state

    # Convert date_range to start_date and end_date if present
    if payload.get("date_range") and payload["date_range"]:
        date_range = str(payload["date_range"]).strip()
        date_filter = _parse_date_range_format(date_range)

        if date_filter:
            # Successfully converted date_range to actual dates
            payload["start_date"] = date_filter.get("start") if date_filter.get("start") else None
            payload["end_date"] = date_filter.get("end") if date_filter.get("end") else None
            print(f" Converted '{date_range}' to start_date: {payload['start_date']}, end_date: {payload['end_date']}")
        else:
            # Could not parse date_range
            print(f"⚠️ Could not parse date_range '{date_range}', treating as missing")
            payload["date_range"] = None
            payload["start_date"] = None
            payload["end_date"] = None

    # All fields are optional otherwise
    state.payload_complete = True
    state.current_step = "action_execution"
    print(" View leads payload complete")
    return state


def complete_edit_leads_payload(state: AgentState) -> AgentState:
    """Complete edit_leads payload"""
    required_fields = ["lead_name"]
    clarifications = FIELD_CLARIFICATIONS.get("edit_leads", {})
    
    missing_fields = [
        f for f in required_fields 
        if f not in state.payload or state.payload.get(f) is None or not state.payload.get(f)
    ]
    
    if not missing_fields:
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" Edit leads payload complete")
        return state
    
    next_field = missing_fields[0]
    clarification_data = clarifications.get(next_field, {})

    if isinstance(clarification_data, dict):
        base_question = clarification_data.get("question", f"Please provide: {next_field.replace('_', ' ')}")

        # Generate personalized question using LLM
        logger.info(f"Calling LLM for clarification question. Base: '{base_question}', User context length: {len(state.user_query or '')}")
        personalized_question = generate_clarifying_question(
            base_question=base_question,
            user_context=state.user_query,
            user_input=state.user_query.split('\n')[-1] if state.user_query else ""
        )
        logger.info(f"LLM returned: '{personalized_question}'")

        state.clarification_question = personalized_question
        state.clarification_options = clarification_data.get("options", [])
    else:
        # Backward compatibility for string clarifications
        state.clarification_question = clarification_data or f"Please provide: {next_field.replace('_', ' ')}"
        state.clarification_options = []

    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for edit_leads: {state.clarification_question}")

    return state


def complete_delete_leads_payload(state: AgentState) -> AgentState:
    """Complete delete_leads payload"""
    required_fields = ["lead_name"]
    clarifications = FIELD_CLARIFICATIONS.get("delete_leads", {})
    
    missing_fields = [
        f for f in required_fields 
        if f not in state.payload or state.payload.get(f) is None or not state.payload.get(f)
    ]
    
    if not missing_fields:
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" Delete leads payload complete")
        return state
    
    next_field = missing_fields[0]
    clarification_data = clarifications.get(next_field, {})

    if isinstance(clarification_data, dict):
        base_question = clarification_data.get("question", f"Please provide: {next_field.replace('_', ' ')}")

        # Generate personalized question using LLM
        logger.info(f"Calling LLM for clarification question. Base: '{base_question}', User context length: {len(state.user_query or '')}")
        personalized_question = generate_clarifying_question(
            base_question=base_question,
            user_context=state.user_query,
            user_input=state.user_query.split('\n')[-1] if state.user_query else ""
        )
        logger.info(f"LLM returned: '{personalized_question}'")

        state.clarification_question = personalized_question
        state.clarification_options = clarification_data.get("options", [])
    else:
        # Backward compatibility for string clarifications
        state.clarification_question = clarification_data or f"Please provide: {next_field.replace('_', ' ')}"
        state.clarification_options = []

    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for delete_leads: {state.clarification_question}")

    return state


def complete_follow_up_leads_payload(state: AgentState) -> AgentState:
    """Complete follow_up_leads payload"""
    required_fields = ["lead_name", "follow_up_date"]
    clarifications = FIELD_CLARIFICATIONS.get("follow_up_leads", {})
    
    missing_fields = [
        f for f in required_fields 
        if f not in state.payload or state.payload.get(f) is None or not state.payload.get(f)
    ]
    
    if not missing_fields:
        state.payload_complete = True
        state.current_step = "action_execution"
        print("✓ Follow up leads payload complete")
        return state
    
    next_field = missing_fields[0]
    
    # Special handling for follow_up_date
    if next_field == "follow_up_date":
        state.clarification_question = "When should we follow up with this lead? (e.g., 'tomorrow', 'next week', 'Jan 15')"
        state.clarification_options = []
    else:
        clarification_data = clarifications.get(next_field, {})

        if isinstance(clarification_data, dict):
            base_question = clarification_data.get("question", f"Please provide: {next_field.replace('_', ' ')}")
            personalized_question = generate_clarifying_question(
                base_question=base_question,
                user_context=state.user_query,
                user_input=state.user_query.split('\n')[-1] if state.user_query else ""
            )
            state.clarification_question = personalized_question
            state.clarification_options = clarification_data.get("options", [])
        else:
            state.clarification_question = clarification_data or f"Please provide: {next_field.replace('_', ' ')}"
            state.clarification_options = []

    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for follow_up_leads: {state.clarification_question}")

    return state


def complete_view_insights_payload(state: AgentState) -> AgentState:
    """Complete view_insights payload"""
    required_fields = ["channel"]
    clarifications = FIELD_CLARIFICATIONS.get("view_insights", {})
    
    missing_fields = [
        f for f in required_fields 
        if f not in state.payload or state.payload.get(f) is None or not state.payload.get(f)
    ]
    
    if not missing_fields:
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" View insights payload complete")
        return state
    
    next_field = missing_fields[0]
    state.clarification_question = clarifications.get(
        next_field,
        f"Please provide: {next_field.replace('_', ' ')}"
    )
    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for view_insights: {state.clarification_question}")
    
    return state


def complete_view_analytics_payload(state: AgentState) -> AgentState:
    """Complete view_analytics payload"""
    required_fields = ["channel"]
    clarifications = FIELD_CLARIFICATIONS.get("view_analytics", {})
    
    missing_fields = [
        f for f in required_fields 
        if f not in state.payload or state.payload.get(f) is None or not state.payload.get(f)
    ]
    
    if not missing_fields:
        state.payload_complete = True
        state.current_step = "action_execution"
        print(" View analytics payload complete")
        return state
    
    next_field = missing_fields[0]
    state.clarification_question = clarifications.get(
        next_field,
        f"Please provide: {next_field.replace('_', ' ')}"
    )
    state.waiting_for_user = True
    state.current_step = "waiting_for_clarification"
    print(f"? Clarification needed for view_analytics: {state.clarification_question}")
    
    return state


def complete_payload(state: AgentState) -> AgentState:
    """Route to specific payload completer based on intent"""
    if state.intent not in INTENT_MAP:
        state.current_step = "end"
        return state
    
    # Route to specific completer
    completers = {
        "view_content": complete_view_content_payload,
        "create_content": complete_create_content_payload,
        "edit_content": complete_edit_content_payload,
        "delete_content": complete_delete_content_payload,
        "publish_content": complete_publish_content_payload,
        "schedule_content": complete_schedule_content_payload,
        "create_leads": complete_create_leads_payload,
        "view_leads": complete_view_leads_payload,
        "edit_leads": complete_edit_leads_payload,
        "delete_leads": complete_delete_leads_payload,
        "follow_up_leads": complete_follow_up_leads_payload,
        "view_insights": complete_view_insights_payload,
        "view_analytics": complete_view_analytics_payload,
    }
    
    completer = completers.get(state.intent)
    if completer:
        return completer(state)
    else:
        state.error = f"No completer found for intent: {state.intent}"
        state.current_step = "end"
        return state


# ==================== CONVERSATION HANDLERS ====================

def handle_greeting(state: AgentState) -> AgentState:
    """Handle greeting messages with personalized tip"""
    
    # Get user profile for personalization
    user_name = "there"
    business_type = "your business"
    
    if state.user_id and supabase:
        try:
            response = supabase.table("profiles").select("name, business_type, business_name").eq("id", state.user_id).execute()
            if response.data and len(response.data) > 0:
                profile_data = response.data[0]
                user_name = profile_data.get("name") or profile_data.get("business_name") or "there"
                business_type = profile_data.get("business_type") or "your business"
        except Exception as e:
            logger.warning(f"Could not fetch profile for greeting: {e}")
    
    # Generate personalized greeting with LLM
    prompt = f"""Generate a warm, brief greeting (under 40 words) for {user_name} who runs {business_type}.

Include:
1. A friendly greeting
2. ONE quick social media tip/trending topic for their business type
3. Ask what they'd like to work on

Keep it conversational, helpful, and under 40 words total.
DO NOT use any emojis.

Greeting:"""

    try:
        response = model.generate_content(prompt)
        greeting = response.text.strip()
        
        # Ensure it's not too long
        words = greeting.split()
        if len(words) > 45:
            greeting = ' '.join(words[:45]) + '...'
        
        state.result = greeting
        
    except Exception as e:
        logger.error(f"Greeting LLM failed: {str(e)}")
        # Fallback greeting
        state.result = f"""Hello {user_name}! Ready to boost {business_type}?

Tip: Video content drives 3x more engagement right now!"""
    
    # Final safeguard - ensure result is never None or empty
    if not state.result or not state.result.strip():
        state.result = "Hello! I'm your ATSN Agent. How can I help you with content or leads today?"
    
    return state


def handle_general_talks(state: AgentState) -> AgentState:
    """Handle general conversation using LLM"""
    
    prompt = f"""You are ATSN Agent, a professional business assistant for content and lead management.

User said: {state.user_query}

Respond in a friendly but professional way. Keep your response under 20 words.
Gently guide them to discuss their business needs - content creation, lead management, or analytics.
Be helpful and encouraging.
DO NOT use any emojis.

Response:"""

    try:
        response = model.generate_content(prompt)
        llm_response = response.text.strip()
        
        # Add a helpful nudge
        state.result = f"{llm_response}\n\nI'm here to help with your content and leads. What would you like to work on?"
        
    except Exception as e:
        logger.error(f"General talks LLM failed: {str(e)}")
        state.result = """I'm here to help with your business! 

I specialize in:
- Content Management (create, view, schedule, publish)
- Lead Management (add, track, follow-up)
- Analytics & Insights

What can I help you with today?"""
    
    return state


# ==================== ACTION EXECUTION ====================

async def execute_action(state: AgentState) -> AgentState:
    """Execute the action based on intent and complete payload"""
    
    intent = state.intent
    payload = state.payload
    
    print(f" Executing action: {intent}")
    print(f"  Payload: {payload}")
    
    # Route to specific handler
    if intent == "greeting":
        state = handle_greeting(state)
    elif intent == "general_talks":
        state = handle_general_talks(state)
    elif intent == "create_content":
        state = await handle_create_content(state)
    elif intent == "edit_content":
        state = handle_edit_content(state)
    elif intent == "delete_content":
        state = handle_delete_content(state)
    elif intent == "view_content":
        state = handle_view_content(state)
        # Log the result for debugging
        if state.result:
            logger.info(f"View content result length: {len(state.result)} characters")
            logger.info(f"View content payload content_ids: {state.payload.get('content_ids', [])}")
    elif intent == "publish_content":
        state = handle_publish_content(state)
    elif intent == "schedule_content":
        state = handle_schedule_content(state)
    elif intent == "create_leads":
        state = handle_create_leads(state)
    elif intent == "view_leads":
        state = handle_view_leads(state)
    elif intent == "edit_leads":
        state = handle_edit_leads(state)
    elif intent == "delete_leads":
        state = handle_delete_leads(state)
    elif intent == "follow_up_leads":
        state = handle_follow_up_leads(state)
    elif intent == "view_insights":
        state = handle_view_insights(state)
    elif intent == "view_analytics":
        state = handle_view_analytics(state)
    else:
        state.error = f"No handler for intent: {intent}"
    
    # Clear clarification state when action executes successfully
    # This ensures the frontend shows the result instead of the clarification question
    state.clarification_question = None
    state.waiting_for_user = False

    # Ensure payload_complete remains True after action execution
    # This prevents re-asking for clarification after showing results
    if state.payload_complete:
        logger.info(f"Action executed for {intent}, payload_complete remains True")

    state.current_step = "end"
    return state


# ==================== CONTENT HANDLERS ====================

async def handle_create_content(state: AgentState) -> AgentState:
    """Generate and create content"""
    payload = state.payload
    
    # Set agent name for content creation
    payload['agent_name'] = 'chase'

    if not state.payload_complete:
        state.error = "Payload is not complete"
        return state

    try:
        generated_content = ""
        generated_image_url = None
        content_data = {}  # Store data to save to database

        # Load business context and profile assets from profiles table
        business_context = {}
        profile_assets = {}
        if state.user_id:
            logger.info(f"🔍 Loading profile data for user_id: {state.user_id}")
            try:
                # Fetch comprehensive profile data including all context fields
                profile_fields = [
                    "business_name", "business_description", "brand_tone", "industry", "target_audience",
                    "brand_voice", "unique_value_proposition", "primary_color", "secondary_color",
                    "brand_colors", "logo_url", "timezone", "location_city", "location_state", "location_country"
                ]
                logger.info(f"🔍 Fetching profile fields: {', '.join(profile_fields)}")
                profile_response = supabase.table("profiles").select(", ".join(profile_fields)).eq("id", state.user_id).execute()

                logger.info(f"🔍 Profile query response: {len(profile_response.data) if profile_response.data else 0} records found")

                if profile_response.data and len(profile_response.data) > 0:
                    profile_data = profile_response.data[0]
                    logger.info(f"🔍 Raw profile data: {profile_data}")

                    business_context = get_business_context_from_profile(profile_data)

                    # Extract brand assets for content and image generation
                    profile_assets = {
                        'primary_color': profile_data.get('primary_color'),
                        'secondary_color': profile_data.get('secondary_color'),
                        'brand_colors': profile_data.get('brand_colors') or [],  # Ensure it's always a list
                        'logo': profile_data.get('logo_url')  # Use correct column name
                    }

                    logger.info(f"✅ Loaded structured business context for: {business_context.get('business_name', 'Business')}")
                    logger.info(f"   Brand colors: {bool(profile_assets['primary_color'])}/{bool(profile_assets['secondary_color'])}")
                    brand_colors_len = len(profile_assets.get('brand_colors') or [])
                    logger.info(f"   Brand colors array: {brand_colors_len} colors")
                    logger.info(f"   Logo: {bool(profile_assets.get('logo'))}")
                    logger.info(f"   Industry: {business_context.get('industry', 'N/A')}")
                    logger.info(f"   Target audience: {business_context.get('target_audience', 'N/A')}")
                else:
                    logger.warning(f"❌ No profile data found for user_id: {state.user_id}, using defaults")
                    logger.warning("   This usually means the user hasn't completed their profile onboarding")
                    business_context = get_business_context_from_profile({})
                    profile_assets = {'primary_color': None, 'secondary_color': None, 'brand_colors': [], 'logo': None}
            except Exception as e:
                logger.error(f"❌ Failed to load business context for user_id {state.user_id}: {e}")
                logger.error(f"   Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
                business_context = get_business_context_from_profile({})
                profile_assets = {'primary_color': None, 'secondary_color': None, 'brand_colors': [], 'logo': None}
        else:
            logger.warning("❌ No user_id provided in state, using defaults")
            business_context = get_business_context_from_profile({})
            profile_assets = {'primary_color': None, 'secondary_color': None, 'brand_colors': [], 'logo': None}

        # Handle different content types
        content_type = payload.get('content_type', '')

        if content_type == 'Post':
            # Step 1: Get trends from Grok API for trend-aware content
            topic = payload.get('content_idea', '')
            trends_data = await get_trends_from_grok(topic, business_context)
            parsed_trends = parse_trends_for_content(trends_data)

            # Step 2: Classify post design type and image type for better content generation
            post_design_type = payload.get('post_design_type')
            if post_design_type:
                classified_post_design = classify_post_design_type(post_design_type)
                logger.info(f"🎨 Classified post design type: '{post_design_type}' → '{classified_post_design}'")
            else:
                classified_post_design = "general"

            image_type = payload.get('image_type')
            if image_type:
                classified_image_type = classify_image_type(image_type)
                logger.info(f"🖼️ Image type input: '{image_type}' → Classified as: '{classified_image_type}'")
            else:
                classified_image_type = "general"
                logger.info(f"🖼️ No image type specified, using default: '{classified_image_type}'")

            # Step 3: Get platform-specific prompt
            platform = payload.get('platform', 'Instagram')
            prompt = get_platform_specific_prompt(platform, payload, business_context, parsed_trends, profile_assets)

            # Log the complete prompt being sent to LLM
            logger.info(f"📝 Complete prompt being sent to GPT-4o-mini for {platform}:")
            logger.info("=" * 80)
            logger.info(prompt)
            logger.info("=" * 80)

            # Generate structured content with GPT-4o-mini
            from datetime import datetime
            content_gen_datetime = datetime.now()
            logger.info(f"📝 Generating content with GPT-4o-mini for platform: {platform} at {content_gen_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            if openai_client:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=600,
                    temperature=0.7
                )
                generated_response = response.choices[0].message.content.strip()

                # Parse platform-specific response
                if platform.lower() == 'instagram':
                    parsed_content = parse_instagram_response(generated_response)
                    title = parsed_content['title']
                    content = parsed_content['content']
                    hashtags = parsed_content['hashtags']
                else:
                    # Fallback parsing for other platforms
                    title = ""
                    content = ""
                    hashtags = []

                    lines = generated_response.split('\n')
                    current_section = None

                    for line in lines:
                        line = line.strip()
                        if line.startswith('TITLE:'):
                            title = line.replace('TITLE:', '').strip()
                            current_section = 'title'
                        elif line.startswith('CONTENT:'):
                            content = line.replace('CONTENT:', '').strip()
                            current_section = 'content'
                        elif line.startswith('HASHTAGS:'):
                            hashtags_text = line.replace('HASHTAGS:', '').strip()
                            hashtags = hashtags_text.split() if hashtags_text else []
                            current_section = 'hashtags'
                        elif current_section == 'content' and line:
                            content += ' ' + line
                        elif current_section == 'hashtags' and line:
                            hashtags.extend(line.split())

                # Save structured data
                content_data['title'] = title
                content_data['content'] = content
                content_data['hashtags'] = hashtags

                generated_content = f"{title}\n\n{content}\n\n{' '.join(hashtags)}"
            else:
                generated_content = "OpenAI client not configured"
                content_data['title'] = "Content Generation Failed"
                content_data['content'] = generated_content
                content_data['hashtags'] = []

        elif content_type == 'short video':
            # Generate short video script using GPT-4o-mini
            prompt = f"""You are a professional video script writer specializing in short-form video content for {payload.get('platform', 'social media')}.

BUSINESS CONTEXT:
{business_context.get('business_name', 'Business')}
Industry: {business_context.get('industry', 'General')}
Target Audience: {business_context.get('target_audience', 'General audience')}
Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}

CONTENT REQUIREMENTS:
- Platform: {payload.get('platform', 'TikTok/Instagram Reels/YouTube Shorts')}
- Content Idea: {payload.get('content_idea', '')}
- Duration: 15-60 seconds (keep script concise)

TASK:
Create a complete short video script that includes:
1. Hook (first 3-5 seconds - grab attention)
2. Main content (deliver value based on the content idea)
3. Call-to-action (what you want viewers to do)
4. Visual cues and transitions

SCRIPT FORMAT:
[0-3s] HOOK: [Compelling opening line]
[3-45s] MAIN CONTENT: [Core message and value]
[45-60s] CTA: [Call to action with clear next steps]

Keep total script length suitable for 15-60 second video.
Use engaging, conversational language.
Include timing cues for editing."""

            if openai_client:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=800,
                    temperature=0.7
                )
                generated_script = response.choices[0].message.content.strip()
                content_data['short_video_script'] = generated_script  # Save to short_video_script column
                generated_content = f"Short Video Script Generated:\n\n{generated_script}"
            else:
                generated_content = "OpenAI client not configured"
                content_data['short_video_script'] = "Script generation failed - OpenAI client not configured"

        elif content_type == 'long video':
            # Generate long video script using GPT-4o-mini
            prompt = f"""You are a professional video script writer specializing in long-form video content.

BUSINESS CONTEXT:
{business_context.get('business_name', 'Business')}
Industry: {business_context.get('industry', 'General')}
Target Audience: {business_context.get('target_audience', 'General audience')}
Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}

CONTENT REQUIREMENTS:
- Platform: {payload.get('platform', 'YouTube/Vimeo')}
- Content Idea: {payload.get('content_idea', '')}
- Duration: 5-15 minutes

TASK:
Create a complete long-form video script that includes:
1. Introduction/Hook (30-60 seconds)
2. Main content sections with clear structure
3. Key points and value delivery
4. Conclusion with call-to-action
5. Visual and editing cues

SCRIPT FORMAT:
[0:00-0:30] INTRODUCTION: [Hook and overview]
[0:30-8:00] MAIN CONTENT: [Detailed explanation with sections]
[8:00-10:00] CONCLUSION: [Summary and CTA]

Use professional, engaging language.
Include timing estimates for each section."""

            if openai_client:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2000,
                    temperature=0.7
                )
                generated_script = response.choices[0].message.content.strip()
                content_data['long_video_script'] = generated_script  # Save to long_video_script column
                generated_content = f"Long Video Script Generated:\n\n{generated_script}"
            else:
                generated_content = "OpenAI client not configured"
                content_data['long_video_script'] = "Script generation failed - OpenAI client not configured"

        elif content_type == 'Email':
            # Generate email content using GPT-4o-mini
            prompt = f"""You are a professional email marketer creating compelling email content.

BUSINESS CONTEXT:
{business_context.get('business_name', 'Business')}
Industry: {business_context.get('industry', 'General')}
Target Audience: {business_context.get('target_audience', 'General audience')}
Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}

CONTENT REQUIREMENTS:
- Content Idea: {payload.get('content_idea', '')}
- Platform: Email

TASK:
Create email content with:
1. Compelling subject line (50 characters max)
2. Engaging email body with clear structure
3. Strong call-to-action

SUBJECT LINE: [Create an attention-grabbing subject]

EMAIL BODY:
[Greeting]
[Hook/Introduction]
[Main Content - deliver value]
[Call-to-Action]
[Sign-off]

Keep email professional and conversion-focused."""

            if openai_client:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                    temperature=0.7
                )
                email_content = response.choices[0].message.content.strip()

                # Parse subject and body (simple parsing - could be improved)
                lines = email_content.split('\n')
                subject_line = ""
                body_content = email_content

                for i, line in enumerate(lines):
                    if line.upper().startswith('SUBJECT:') or line.upper().startswith('SUBJECT LINE:'):
                        subject_line = line.split(':', 1)[1].strip()
                        body_content = '\n'.join(lines[i+1:]).strip()
                        break

                content_data['email_subject'] = subject_line  # Save to email_subject column
                content_data['email_body'] = body_content      # Save to email_body column
                generated_content = f"Email Subject: {subject_line}\n\nEmail Body:\n{body_content}"
            else:
                generated_content = "OpenAI client not configured"
                content_data['email_subject'] = "Email generation failed"
                content_data['email_body'] = "OpenAI client not configured"

        elif content_type == 'message':
            # Generate message content using GPT-4o-mini
            prompt = f"""You are a professional communicator creating engaging messages for {payload.get('platform', 'messaging platforms')}.

BUSINESS CONTEXT:
{business_context.get('business_name', 'Business')}
Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}

CONTENT REQUIREMENTS:
- Platform: {payload.get('platform', 'WhatsApp/SMS')}
- Content Idea: {payload.get('content_idea', '')}

TASK:
Create a concise, engaging message that:
1. Delivers the key message from the content idea
2. Maintains brand voice
3. Includes appropriate emojis
4. Ends with a clear call-to-action
5. Is optimized for mobile reading

Keep message under 160 characters for SMS, or conversational for WhatsApp."""

            if openai_client:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=0.7
                )
                message_content = response.choices[0].message.content.strip()
                content_data['message'] = message_content  # Save to message column
                generated_content = f"Message Content:\n{message_content}"
            else:
                generated_content = "OpenAI client not configured"
                content_data['message'] = "Message generation failed - OpenAI client not configured"
        else:
            # For other content types, use original logic
            generated_content = f"Generated {content_type} for {payload.get('platform', 'platform')}"
            content_data['content'] = generated_content

        # Handle media generation based on payload.media
        logger.info(f"Media type: {payload.get('media')}")
        if payload.get('media') == 'Generate':
            # Generate image using Gemini with the generated content and business context
            try:
                # First, generate enhanced image prompt using AI
                generated_post = {
                    'title': title,
                    'content': content
                }

                enhanced_prompt_data = await generate_image_enhancer_prompt(
                    generated_post, payload, business_context, parsed_trends, profile_assets, classified_image_type
                )

                # Build final image generation prompt using the enhanced prompt
                from datetime import datetime
                current_datetime = datetime.now()
                current_date = current_datetime.strftime("%Y-%m-%d")
                current_time = current_datetime.strftime("%H:%M:%S UTC")

                # Use the enhanced prompt as the base
                base_prompt = enhanced_prompt_data.get('image_prompt', f"Create a professional image for: {title}")
                # Determine visual style from classified image type instead of LLM
                visual_style = get_visual_style_from_image_type(classified_image_type)
                aspect_ratio = enhanced_prompt_data.get('aspect_ratio', '1:1')
                negative_prompt = enhanced_prompt_data.get('negative_prompt', 'text, logos, watermarks')

                # Build color instructions and location context using helper functions
                color_instructions = build_brand_color_instructions(profile_assets, business_context)
                location_context = build_location_context(business_context)

                image_prompt = f"""{base_prompt}

VISUAL REQUIREMENTS:
- Style: {visual_style}
- Aspect Ratio: {aspect_ratio}
- Business: {business_context.get('business_name', 'Business')}
- Industry: {business_context.get('industry', 'General')}
- Target Audience: {business_context.get('target_audience', 'General audience')}
{color_instructions}

{location_context}

AVOID: {negative_prompt}

Create a high-quality, professional image optimized for Instagram that reflects current design trends for {current_date}."""

                # Log the complete image generation prompt
                logger.info(f"🎨 Complete image generation prompt being sent to Gemini:")
                logger.info("=" * 80)
                logger.info(image_prompt)
                logger.info("=" * 80)

                # Generate image with Gemini
                logger.info(f"🎨 Generating image with Gemini for platform: {payload.get('platform')} at {current_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                logger.info(f"   Image type '{classified_image_type}' → Visual style: {visual_style}, Aspect ratio: {aspect_ratio}")
                gemini_image_model = 'gemini-2.5-flash-image-preview'
                image_response = genai.GenerativeModel(gemini_image_model).generate_content(
                    contents=[image_prompt]
                )
                logger.info(f"Gemini response received, has candidates: {bool(image_response.candidates)}")

                # Extract image data
                if image_response.candidates and len(image_response.candidates) > 0:
                    candidate = image_response.candidates[0]
                    if candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.inline_data is not None and part.inline_data.data:
                                try:
                                    # Get image data as bytes
                                    image_data = part.inline_data.data
                                    if not isinstance(image_data, bytes):
                                        import base64
                                        image_data = base64.b64decode(image_data)

                                    # Generate unique filename
                                    import uuid
                                    filename = f"generated/{uuid.uuid4()}.png"
                                    file_path = filename

                                    logger.info(f"📤 Uploading generated image to content-images bucket: {file_path}")

                                    # Upload to ai-generated-images bucket in generated folder
                                    storage_response = supabase.storage.from_("ai-generated-images").upload(
                                        file_path,
                                        image_data,
                                        file_options={"content-type": "image/png", "upsert": "false"}
                                    )

                                    if hasattr(storage_response, 'error') and storage_response.error:
                                        logger.error(f"Storage upload error: {storage_response.error}")
                                        generated_image_url = None
                                    else:
                                        # Get public URL
                                        generated_image_url = supabase.storage.from_("ai-generated-images").get_public_url(file_path)
                                        logger.info(f"✅ Image uploaded successfully: {generated_image_url}")

                                        if generated_image_url and isinstance(generated_image_url, str):
                                            content_data['images'] = [generated_image_url]

                                            # ✅ Increment image count after successful generation and storage
                                            try:
                                                # Read current image count and increment
                                                current_images = supabase.table('profiles').select('images_generated_this_month').eq('id', state.user_id).execute()
                                                if current_images.data and len(current_images.data) > 0:
                                                    current_image_count = current_images.data[0]['images_generated_this_month'] or 0
                                                    supabase.table('profiles').update({
                                                        'images_generated_this_month': current_image_count + 1
                                                    }).eq('id', state.user_id).execute()
                                                    logger.info(f"Incremented image count for user {state.user_id} after successful generation (from {current_image_count} to {current_image_count + 1})")
                                            except Exception as counter_error:
                                                logger.error(f"Error incrementing image count after generation: {counter_error}")
                                        else:
                                            logger.error(f"Invalid public URL returned: {generated_image_url}")
                                            generated_image_url = None

                                except Exception as upload_error:
                                    logger.error(f"Error uploading image to storage: {upload_error}")
                                    generated_image_url = None

                                break

            except Exception as e:
                logger.error(f"Image generation failed: {e}")
                generated_image_url = None

        elif payload.get('media') == 'Upload':
            # Use uploaded image (managed by frontend, media_file should contain the URL/path)
            generated_image_url = payload.get('media_file')
            if generated_image_url:
                content_data['images'] = [generated_image_url]
        # For "without media", no images added

        # Save to Supabase created_content table
        logger.info(f"💾 Preparing to save content_data keys: {list(content_data.keys())}")
        if state.user_id and content_data:
            try:
                # Prepare data for created_content table
                db_data = {
                    'user_id': state.user_id,
                    'platform': payload.get('platform', '').lower(),
                    'content_type': content_type.lower(),
                    'title': content_data.get('title', f"{content_type} for {payload.get('platform', 'Platform').lower()}"),
                    'status': 'generated',
                    'metadata': {
                        'channel': payload.get('channel'),
                        'content_idea': payload.get('content_idea'),
                        'generated_at': datetime.now().isoformat()
                    },
                    **content_data  # This spreads the content-specific data into the correct columns
                }

                # Insert into created_content table
                result = supabase.table('created_content').insert(db_data).execute()
                if result.data and len(result.data) > 0:
                    content_id = result.data[0]['id']
                    state.content_id = str(content_id)
                    logger.info(f"✅ Successfully saved {content_type} content to created_content table with ID: {content_id}")

                    # Log which columns were saved
                    saved_columns = list(content_data.keys())
                    logger.info(f"📝 Saved content to columns: {', '.join(saved_columns)}")
                    logger.info(f"📸 Images in content_data: {'images' in content_data and len(content_data.get('images', []))} image(s)")
                    if 'images' in content_data:
                        logger.info(f"📸 Image URLs saved: {len(content_data['images'])} URL(s) in database")
                else:
                    logger.warning("Failed to save content to created_content table - no data returned")

            except Exception as e:
                logger.error(f"Error saving content to created_content table: {e}")
                state.error = f"Failed to save content to database: {str(e)}"

        # Generate display content ID
        display_content_id = f"CONTENT_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Create content item for frontend display
        if state.user_id and state.content_id:
            try:
                # Fetch the newly created content from database to get complete data
                content_response = supabase.table('created_content').select('*').eq('id', state.content_id).execute()
                if content_response.data and len(content_response.data) > 0:
                    item = content_response.data[0]

                    # Extract image URL from images array (first image if available)
                    images = item.get('images', [])
                    media_url = None
                    if images and len(images) > 0:
                        first_image = images[0]
                        if isinstance(first_image, str):
                            media_url = first_image

                    # Format hashtags
                    hashtags = item.get('hashtags', [])
                    hashtag_text = ''
                    if hashtags:
                        if isinstance(hashtags, list):
                            hashtag_text = ' '.join([f"#{tag}" if not tag.startswith('#') else tag for tag in hashtags[:10]])

                    # Format date
                    created_at = item.get('created_at', '')
                    date_display = ''
                    if created_at:
                        try:
                            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            date_display = dt.strftime('%B %d, %Y at %I:%M %p')
                        except:
                            date_display = created_at[:10] if len(created_at) >= 10 else created_at

                    # Get content text based on content type
                    content_type = item.get('content_type', 'post')
                    content_text = ''
                    if content_type == 'email':
                        if item.get('email_subject') and item.get('email_body'):
                            content_text = f"Subject: {item['email_subject']}\n\n{item['email_body']}"
                        else:
                            content_text = item.get('content', '')
                    elif content_type == 'short video':
                        content_text = item.get('short_video_script', '')
                    elif content_type == 'long video':
                        content_text = item.get('long_video_script', '')
                    elif content_type == 'message':
                        content_text = item.get('message', '')
                    else:
                        content_text = item.get('content', '')

                    # Get title
                    title = item.get('title', f"{content_type.title()} for {item.get('platform', 'Platform')}")

                    # Create structured content item for frontend
                    content_item = {
                        'id': 1,  # Single item
                        'content_id': state.content_id,
                        'platform': item.get('platform', 'Unknown').title(),
                        'content_type': content_type.replace('_', ' ').title(),
                        'status': item.get('status', 'generated').title(),
                        'created_at': date_display,
                        'created_at_raw': created_at,
                        'title': title,
                        'title_display': title,
                        'content_text': content_text,
                        'content_preview': content_text[:150] + '...' if len(content_text) > 150 else content_text,
                        'hashtags': hashtag_text,
                        'hashtags_display': hashtag_text,
                        'media_url': media_url,
                        'has_media': bool(media_url),
                        'images': item.get('images', []),
                        # Additional fields for different content types
                        'email_subject': item.get('email_subject'),
                        'email_body': item.get('email_body'),
                        'short_video_script': item.get('short_video_script'),
                        'long_video_script': item.get('long_video_script'),
                        'message': item.get('message'),
                        # Platform emoji
                        'platform_emoji': {
                            'Instagram': '📸',
                            'Facebook': '👥',
                            'Linkedin': '💼',
                            'Youtube': '🎥',
                            'Gmail': '✉️',
                            'Whatsapp': '💬'
                        }.get(item.get('platform', 'Unknown').title(), '🌐'),
                        # Status emoji and color
                        'status_emoji': {
                            'Generated': '📝',
                            'Scheduled': '⏰',
                            'Published': '✅'
                        }.get(item.get('status', 'generated').title(), '📄'),
                        'status_color': {
                            'Generated': 'blue',
                            'Scheduled': 'orange',
                            'Published': 'green'
                        }.get(item.get('status', 'generated').title(), 'gray'),
                        'metadata': item.get('metadata', {}),
                        'raw_data': item
                    }

                    # Set content_items for frontend display
                    state.content_items = [content_item]

            except Exception as e:
                logger.error(f"Error creating content item for display: {e}")

        # Set intent for frontend to enable action buttons
        state.intent = "created_content"

        # Minimal success response - cards will be displayed by frontend
        base_message = "Content created successfully! Use the action buttons below to manage your content."
        state.result = generate_personalized_message(
            base_message=base_message,
            user_context=state.user_query,
            message_type="success"
        )
        
    except Exception as e:
        state.error = f"Content generation failed: {str(e)}"
        logger.error(f"Content creation error: {e}")
    
    return state


def handle_edit_content(state: AgentState) -> AgentState:
    """Edit existing content"""
    payload = state.payload
    
    state.result = f"""Content edit prepared

Content ID: {payload.get('content_id', 'Will be selected')}
Edit instruction: {payload.get('edit_instruction')}

Next steps:
1. Search for content matching criteria
2. User selects specific content
3. Apply edits
4. Confirm save or discard"""
    
    return state


def handle_delete_content(state: AgentState) -> AgentState:
    """Display content for deletion selection"""
    payload = state.payload

    if not supabase:
        state.error = "Database connection not configured. Please contact support."
        state.result = "Unable to fetch content for deletion: Database not available."
        logger.error("Supabase not configured - cannot fetch content for deletion")
        return state

    # Ensure user_id is present for security
    if not state.user_id:
        state.error = "User ID is required to view content for deletion"
        state.result = "Unable to fetch content: User authentication required."
        logger.error("User ID missing in handle_delete_content")
        return state

    try:
        # Build query for created_content table - select all fields including uuid (id)
        query = supabase.table('created_content').select('*')

        # Security: Always filter by user_id (required)
        query = query.eq('user_id', state.user_id)

        # Apply filters from payload
        if payload.get('channel'):
            # Channel filter (Social Media, Blog, Email, Messages)
            query = query.eq('channel', payload['channel'])

        # Apply filters from payload - convert to lowercase for platform and status
        if payload.get('platform'):
            # Convert platform to lowercase to match schema (instagram, facebook, etc.)
            platform_filter = payload['platform'].lower().strip()
            query = query.eq('platform', platform_filter)

        if payload.get('status'):
            # Convert status to lowercase to match schema (generated, scheduled, published)
            status_filter = payload['status'].lower().strip()
            query = query.eq('status', status_filter)

        if payload.get('content_type'):
            query = query.eq('content_type', payload['content_type'])

        # Check if we have a semantic search query
        has_semantic_search = payload.get('query') and payload['query'].strip()

        if has_semantic_search:
            # Use semantic search instead of traditional filters
            search_query = payload['query'].strip()
            logger.info(f"Performing semantic search for deletion: '{search_query}'")

            # Perform text search on title and content columns
            # Use ilike for case-insensitive partial matching
            query = query.or_(f"title.ilike.%{search_query}%,content.ilike.%{search_query}%")

            # Apply any additional filters if present
            if payload.get('channel'):
                query = query.eq('channel', payload['channel'])
            if payload.get('platform'):
                platform_filter = payload['platform'].lower().strip()
                query = query.eq('platform', platform_filter)
            if payload.get('status'):
                status_filter = payload['status'].lower().strip()
                query = query.eq('status', status_filter)
            if payload.get('content_type'):
                query = query.eq('content_type', payload['content_type'])

        # Apply date range filter - use start_date and end_date directly
        if payload.get('start_date'):
            # Convert YYYY-MM-DD to PostgreSQL timestamp format (start of day)
            start_datetime = f"{payload['start_date']}T00:00:00.000Z"
            query = query.gte('created_at', start_datetime)

        if payload.get('end_date'):
            # Convert YYYY-MM-DD to PostgreSQL timestamp format (end of day)
            end_datetime = f"{payload['end_date']}T23:59:59.999Z"
            query = query.lte('created_at', end_datetime)

        # Order by most recent first
        query = query.order('created_at', desc=True)

        # For semantic search, limit results to avoid too many matches
        # For traditional filters, show more results
        if has_semantic_search:
            response = query.limit(50).execute()  # Limit semantic search results
        else:
            response = query.limit(100).execute()  # Allow more results for filtered searches

        logger.info(f"Delete content query executed: Found {len(response.data) if response.data else 0} items (semantic_search: {has_semantic_search})")

        if not response.data or len(response.data) == 0:
            # Generate personalized "no results" message
            if has_semantic_search:
                base_message = f"No content found matching your search for '{payload['query']}'. Try different keywords or check your filters."
            else:
                filters_desc = []
                if payload.get('channel'): filters_desc.append(f"channel: {payload['channel']}")
                if payload.get('platform'): filters_desc.append(f"platform: {payload['platform']}")
                if payload.get('status'): filters_desc.append(f"status: {payload['status']}")
                if payload.get('content_type'): filters_desc.append(f"type: {payload['content_type']}")
                if payload.get('start_date'): filters_desc.append(f"date from: {payload['start_date']}")
                if payload.get('end_date'): filters_desc.append(f"date to: {payload['end_date']}")

                if filters_desc:
                    base_message = f"No content found with the specified filters: {', '.join(filters_desc)}. Please adjust your criteria and try again."
                else:
                    base_message = "No content found. Please specify some search criteria and try again."

            state.result = base_message
            return state

        # Collect content_ids and structured content items for frontend selection
        content_items = []
        content_ids = []  # Store all content IDs for payload

        for idx, item in enumerate(response.data[:50], 1):  # Show up to 50 items for deletion
            # Get content_id (uuid) - store for payload
            content_id = item.get('id') or item.get('uuid')
            if content_id:
                content_ids.append(content_id)

            # Extract image URL from images array (first image if available)
            images = item.get('images', [])
            media_url = None
            if images and len(images) > 0:
                # Handle both string URLs and object formats
                first_image = images[0]
                if isinstance(first_image, str):
                    media_url = first_image
                elif isinstance(first_image, dict):
                    media_url = first_image.get('url') or first_image.get('image_url')

            # Format hashtags
            hashtags = item.get('hashtags', [])
            hashtag_text = ''
            if hashtags:
                if isinstance(hashtags, list):
                    hashtag_text = ' '.join([f"#{tag}" if not tag.startswith('#') else tag for tag in hashtags[:10]])
                else:
                    hashtag_text = str(hashtags)

            # Format date
            created_at = item.get('created_at', '')
            date_display = ''
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_display = dt.strftime('%B %d, %Y at %I:%M %p')
                except:
                    date_display = created_at[:10] if len(created_at) >= 10 else created_at

            # Get content text (try multiple field names)
            content_text = item.get('content') or item.get('content_text') or item.get('text', '')

            # Get title
            title = item.get('title', '')

            # Create structured content item for frontend deletion selection
            content_item = {
                'id': idx,
                'content_id': content_id,
                'platform': item.get('platform', 'Unknown').title(),
                'content_type': item.get('content_type', 'post').replace('_', ' ').title(),
                'status': item.get('status', 'unknown').title(),
                'created_at': date_display,
                'created_at_raw': created_at,  # Raw timestamp for sorting/filtering
                'title': title,
                'title_display': title,  # Full title for deletion
                'content_text': content_text,
                'content_preview': content_text[:150] + '...' if len(content_text) > 150 else content_text,
                'hashtags': hashtag_text,
                'hashtags_display': hashtag_text,  # Clean hashtags
                'media_url': media_url,
                'has_media': bool(media_url),
                'images': item.get('images', []),
                # Additional metadata for frontend
                'platform_emoji': {
                    'Instagram': '📸',
                    'Facebook': '👥',
                    'Linkedin': '💼',
                    'Youtube': '🎥',
                    'Gmail': '✉️',
                    'Whatsapp': '💬'
                }.get(item.get('platform', 'Unknown').title(), '🌐'),
                'status_emoji': {
                    'Generated': '📝',
                    'Scheduled': '⏰',
                    'Published': '✅'
                }.get(item.get('status', 'unknown').title(), '📄'),
                'status_color': {
                    'Generated': 'blue',
                    'Scheduled': 'orange',
                    'Published': 'green'
                }.get(item.get('status', 'unknown').title(), 'gray'),
                # Raw data for advanced frontend features
                'metadata': item.get('metadata', {}),
                'raw_data': item  # Full original item for debugging
            }

            content_items.append(content_item)

        total_count = len(response.data)
        showing = len(content_items)

        # Set structured content data for frontend
        state.content_items = content_items

        # Append content_ids to payload for frontend
        if content_ids:
            state.payload['content_ids'] = content_ids
            state.payload['content_count'] = total_count

        # Format date range display
        date_display = payload.get('start_date', 'All')
        if payload.get('start_date') and payload.get('end_date'):
            start_date = payload.get('start_date')
            end_date = payload.get('end_date')
            if start_date == end_date:
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                    date_display = date_obj.strftime('%B %d, %Y')
                except:
                    date_display = start_date
            else:
                date_display = f"{start_date} to {end_date}"

        # Format status display
        status = payload.get('status')
        status_display = status.title() if status else 'Any Status'

        # Build beautiful, concise result message
        channel = payload.get('channel', 'content')
        platform = payload.get('platform', '')
        content_type = payload.get('content_type', '')
        date_info = date_display

        # Format the message components
        if platform:
            platform_str = f"{platform} "
        else:
            platform_str = ""

        if content_type:
            content_type_str = f"{content_type} "
        else:
            content_type_str = ""

        result = f"""These are your {channel} {platform_str}{content_type_str}from {date_info}.

Select the items you want to delete from the list below."""

        if total_count > showing:
            result += f"\n\nShowing {showing} of {total_count} items."

        # Generate personalized success message
        state.result = generate_personalized_message(
            base_message=result,
            user_context=state.user_query,
            message_type="success"
        )

        # Log final state for debugging
        logger.info(f"Delete content: Found {total_count} items for deletion selection")
        logger.info(f"Delete content payload content_ids: {content_ids[:5]}...")  # Log first 5 IDs

    except Exception as e:
        error_msg = f"Failed to fetch content for deletion: {str(e)}"
        state.error = error_msg
        state.result = f"Error: {error_msg}\n\nPlease try again or contact support if the issue persists."
        logger.error(f"Database query failed in handle_delete_content: {str(e)}", exc_info=True)

    return state


def _format_view_content_summary(payload: Dict[str, Any], count: int) -> str:
    """Format a human-readable summary message for view content results"""
    from datetime import datetime, timedelta

    # Format status
    status = payload.get('status', '').lower() if payload.get('status') else ''
    status_display = ''
    if status == 'generated':
        status_display = 'generated'
    elif status == 'scheduled':
        status_display = 'scheduled'
    elif status == 'published':
        status_display = 'published'
    else:
        status_display = 'content'

    # Format channel
    channel = payload.get('channel', '').lower() if payload.get('channel') else ''
    channel_display = ''
    if channel == 'social media':
        channel_display = 'social media'
    elif channel == 'blog':
        channel_display = 'blog'
    elif channel == 'email':
        channel_display = 'email'
    elif channel == 'messages':
        channel_display = 'messages'
    else:
        channel_display = 'content'

    # Format content type with proper pluralization
    content_type = payload.get('content_type', '').lower() if payload.get('content_type') else ''
    content_type_display = ''
    if content_type == 'post':
        content_type_display = 'post' if count == 1 else 'posts'
    elif content_type == 'short_video':
        content_type_display = 'short video' if count == 1 else 'short videos'
    elif content_type == 'long_video':
        content_type_display = 'long video' if count == 1 else 'long videos'
    elif content_type == 'blog':
        content_type_display = 'blog post' if count == 1 else 'blog posts'
    elif content_type == 'email':
        content_type_display = 'email' if count == 1 else 'emails'
    elif content_type == 'message':
        content_type_display = 'message' if count == 1 else 'messages'
    else:
        content_type_display = 'item' if count == 1 else 'items'

    # Format platform
    platform = payload.get('platform', '')
    platform_display = platform if platform else ''

    # Format date range using the original date_range concept
    date_range = payload.get('date_range', '').lower() if payload.get('date_range') else ''
    date_display = ''

    # Show the natural language date concept, not calculated dates
    if date_range:
        if date_range == 'today':
            date_display = "for today"
        elif date_range == 'yesterday':
            date_display = "for yesterday"
        elif date_range == 'this week':
            date_display = "for this week"
        elif date_range == 'last week':
            date_display = "for last week"
        elif date_range == 'custom date':
            # For custom dates, we might have start_date/end_date
            start_date = payload.get('start_date')
            end_date = payload.get('end_date')
            if start_date and end_date and start_date == end_date:
                try:
                    date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                    date_display = f"for {date_obj.strftime('%m/%d/%y')}"
                except:
                    date_display = f"for {start_date}"
            else:
                date_display = f"for {date_range}"
        else:
            # For other custom date formats like "december 12", show as-is
            date_display = f"for {date_range}"
    else:
        date_display = ""

    # Build the summary message with proper grammar
    parts = []

    # Check if this is a semantic search result
    has_query = payload.get('query') and payload['query'].strip()

    if has_query:
        # For semantic search, use different formatting
        parts.append(f"You have {count}")
        parts.append("item" if count == 1 else "items")
        parts.append(f"matching '{payload['query']}'")

        # Add any additional filters
        filter_parts = []
        if status_display != 'content':
            filter_parts.append(f"status: {status_display}")
        if channel_display != 'content':
            filter_parts.append(f"channel: {channel_display}")
        if content_type_display != 'items':
            filter_parts.append(f"type: {content_type_display}")
        if platform_display:
            filter_parts.append(f"platform: {platform_display}")
        if date_display:
            filter_parts.append(date_display.strip())

        if filter_parts:
            parts.append(f"(filtered by {', '.join(filter_parts)})")
    else:
        # Traditional filter-based summary
        # Start with "You have {count}"
        parts.append(f"You have {count}")

        # Add status if specified
        if status_display != 'content':
            parts.append(status_display)

        # Add channel if specified
        if channel_display != 'content':
            parts.append(channel_display)

        # Add content type if specified
        if content_type_display != 'items':
            parts.append(content_type_display)
        else:
            parts.append("item" if count == 1 else "items")

        # Add platform if specified
        if platform_display:
            parts.append(f"on {platform_display}")

        # Add date range if specified
        if date_display:
            parts.append(date_display)

    # Join parts with spaces
    summary = ' '.join(parts)

    # Capitalize first letter
    summary = summary[0].upper() + summary[1:] if summary else f"You have {count} content items"

    # Add period at the end
    if not summary.endswith('.'):
        summary += '.'

    # Add action instructions
    summary += "\n\nIf you want to edit, delete, publish or schedule any post, just click on the post and select options."

    return summary


def handle_view_content(state: AgentState) -> AgentState:
    """View content from created_content table with rich formatting similar to dashboard"""
    payload = state.payload
    
    if not supabase:
        state.error = "Database connection not configured. Please contact support."
        state.result = "Unable to fetch content: Database not available."
        logger.error("Supabase not configured - cannot fetch content")
        return state
    
    # Ensure user_id is present for security
    if not state.user_id:
        state.error = "User ID is required to view content"
        state.result = "Unable to fetch content: User authentication required."
        logger.error("User ID missing in handle_view_content")
        return state
    
    try:
        # Build query for created_content table - select all fields including uuid (id)
        query = supabase.table('created_content').select('*')

        # Security: Always filter by user_id (required)
        query = query.eq('user_id', state.user_id)

        # Check if we have a semantic search query
        has_semantic_search = payload.get('query') and payload['query'].strip()

        if has_semantic_search:
            # Use semantic search instead of traditional filters
            search_query = payload['query'].strip()
            logger.info(f"Performing semantic search for query: '{search_query}'")

            # Perform text search on title and content columns
            # Use ilike for case-insensitive partial matching
            query = query.or_(f"title.ilike.%{search_query}%,content.ilike.%{search_query}%")

            # Apply any additional filters if present
            if payload.get('channel'):
                query = query.eq('channel', payload['channel'])
            if payload.get('platform'):
                platform_filter = payload['platform'].lower().strip()
                query = query.eq('platform', platform_filter)
            if payload.get('status'):
                status_filter = payload['status'].lower().strip()
                query = query.eq('status', status_filter)
            if payload.get('content_type'):
                query = query.eq('content_type', payload['content_type'])

        else:
            # Use traditional filters
            # Apply filters from payload
            if payload.get('channel'):
                # Channel filter (Social Media, Blog, Email, Messages)
                query = query.eq('channel', payload['channel'])

            # Apply filters from payload - convert to lowercase for platform and status
            if payload.get('platform'):
                # Convert platform to lowercase to match schema (instagram, facebook, etc.)
                platform_filter = payload['platform'].lower().strip()
                query = query.eq('platform', platform_filter)

            if payload.get('status'):
                # Convert status to lowercase to match schema (generated, scheduled, published)
                status_filter = payload['status'].lower().strip()
                query = query.eq('status', status_filter)

            if payload.get('content_type'):
                query = query.eq('content_type', payload['content_type'])
        
        # Apply date range filter using start_date and end_date directly
        if payload.get('start_date'):
            # Convert YYYY-MM-DD to PostgreSQL timestamp format (start of day)
            start_datetime = f"{payload['start_date']}T00:00:00.000Z"
            query = query.gte('created_at', start_datetime)

        if payload.get('end_date'):
            # Convert YYYY-MM-DD to PostgreSQL timestamp format (end of day)
            end_datetime = f"{payload['end_date']}T23:59:59.999Z"
            query = query.lte('created_at', end_datetime)
        
        # Order by creation date (newest first) and limit results
        query = query.order('created_at', desc=True)

        # For semantic search, limit results to avoid too many matches
        # For traditional filters, show more results
        if has_semantic_search:
            result = query.limit(50).execute()  # Limit semantic search results
        else:
            result = query.limit(100).execute()  # Allow more results for filtered searches

        logger.info(f"View content query executed: Found {len(result.data) if result.data else 0} items (semantic_search: {has_semantic_search})")
        
        if not result.data or len(result.data) == 0:
            # Generate personalized "no results" message
            if has_semantic_search:
                base_message = f"No content found matching your search for '{payload['query']}'. Try different keywords or check your filters."
            else:
                filters_desc = []
                if payload.get('channel'): filters_desc.append(f"channel: {payload['channel']}")
                if payload.get('platform'): filters_desc.append(f"platform: {payload['platform']}")
                if payload.get('status'): filters_desc.append(f"status: {payload['status']}")
                if payload.get('content_type'): filters_desc.append(f"type: {payload['content_type']}")
                if payload.get('start_date') or payload.get('end_date'):
                    date_desc = ""
                    if payload.get('start_date'): date_desc += f"from {payload['start_date']}"
                    if payload.get('end_date'): date_desc += f" to {payload['end_date']}"
                    filters_desc.append(f"date: {date_desc.strip()}")

                filters_text = ", ".join(filters_desc) if filters_desc else "no filters applied"
                base_message = f"No content found with the specified filters ({filters_text}). Try adjusting your search criteria."

            state.result = generate_personalized_message(
                base_message=base_message,
                user_context=state.user_query,
                message_type="info"
            )
            return state
        
        # Process content items for display
        content_items = []
        content_ids = []  # Store all content IDs for payload
        total_count = len(result.data)

        # Show fewer items for semantic search to avoid overwhelming results
        showing = min(total_count, 20 if has_semantic_search else 50)

        for idx, item in enumerate(result.data[:showing], 1):
            # Debug logging for images field
            logger.info(f"Content item {idx}: has images field: {'images' in item}, images value: {item.get('images', 'NOT_FOUND')}")

            # Get content_id (uuid) - store for payload
            content_id = item.get('id') or item.get('uuid')
            if content_id:
                content_ids.append(content_id)

            # Extract image URL from images array (first image if available)
            images = item.get('images', [])
            media_url = None
            if images and len(images) > 0:
                # Handle both string URLs and object formats
                first_image = images[0]
                if isinstance(first_image, str):
                    media_url = first_image
                elif isinstance(first_image, dict):
                    media_url = first_image.get('url') or first_image.get('image_url')
            
            # Format hashtags
            hashtags = item.get('hashtags', [])
            hashtag_text = ''
            if hashtags:
                if isinstance(hashtags, list):
                    hashtag_text = ' '.join([f"#{tag}" if not tag.startswith('#') else tag for tag in hashtags[:10]])
                else:
                    hashtag_text = str(hashtags)
            
            # Format date
            created_at = item.get('created_at', '')
            date_display = ''
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_display = dt.strftime('%B %d, %Y at %I:%M %p')
                except:
                    date_display = created_at[:10] if len(created_at) >= 10 else created_at
            
            # Get content text (try multiple field names)
            content_text = item.get('content') or item.get('content_text') or item.get('text', '')
            
            # Get title
            title = item.get('title', '')

            # Process content for display
            processed_title = title
            if title and len(title) > 60:
                processed_title = title[:60] + '...'

            processed_content = content_text
            if content_text:
                # Clean up line breaks and extra spaces
                processed_content = ' '.join(content_text.split())
                if len(processed_content) > 150:
                    processed_content = processed_content[:150] + '...'

            processed_hashtags = hashtag_text
            if hashtag_text:
                processed_hashtags = hashtag_text.replace(' #', ' #')

            # Create structured content item for frontend card rendering
            content_item = {
                'id': idx,
                'content_id': content_id,
                'platform': item.get('platform', 'Unknown').title(),
                'content_type': item.get('content_type', 'post').replace('_', ' ').title(),
                'status': item.get('status', 'unknown').title(),
                'created_at': date_display,
                'created_at_raw': created_at,  # Raw timestamp for sorting/filtering
                'title': title,
                'title_display': processed_title,  # Truncated for display
                'content_text': content_text,
                'content_preview': processed_content,  # Processed preview
                'hashtags': hashtag_text,
                'hashtags_display': processed_hashtags,  # Clean hashtags
                'media_url': media_url,
                'has_media': bool(media_url),
                'images': item.get('images', []),
                # Additional metadata for frontend
                'platform_emoji': {
                    'Instagram': '📸',
                    'Facebook': '👥',
                    'Linkedin': '💼',
                    'Youtube': '🎥',
                    'Gmail': '✉️',
                    'Whatsapp': '💬'
                }.get(item.get('platform', 'Unknown').title(), '🌐'),
                'status_emoji': {
                    'Generated': '📝',
                    'Scheduled': '⏰',
                    'Published': '✅'
                }.get(item.get('status', 'unknown').title(), '📄'),
                'status_color': {
                    'Generated': 'blue',
                    'Scheduled': 'orange',
                    'Published': 'green'
                }.get(item.get('status', 'unknown').title(), 'gray'),
                # Raw data for advanced frontend features
                'metadata': item.get('metadata', {}),
                'raw_data': item  # Full original item for debugging
            }

            # Debug logging for content_item
            logger.info(f"Content item {idx} created with images: {content_item.get('images', 'MISSING')}")

            content_items.append(content_item)

        total_count = len(result.data)
        showing = len(content_items)
        
        # Append content_ids to payload for chatbot
        if content_ids:
            state.payload['content_ids'] = content_ids
            state.payload['content_count'] = total_count
            # Set content_id in AgentState (first content ID if multiple results)
            state.content_id = content_ids[0] if len(content_ids) > 0 else None
            # Also add to payload for backward compatibility
            state.payload['content_id'] = content_ids[0] if len(content_ids) > 0 else None
        
        # Set structured content data for frontend
        state.content_items = content_items

        # Format summary message with proper grammar and action instructions
        summary_message = _format_view_content_summary(payload, total_count)

        # Build result with summary only (frontend will render cards)
        result = summary_message
        if total_count > showing:
            result += f"\n\nShowing {showing} of {total_count} items."

        # Generate personalized success message
        personalized_result = generate_personalized_message(
            base_message=result,
            user_context=state.user_query,
            message_type="success"
        )

        state.result = personalized_result
        
        # Log final state for debugging
        logger.info(f"View content: Found {total_count} items, added {len(content_ids)} content_ids to payload")
        logger.info(f"View content result set: {len(state.result) if state.result else 0} characters")
        logger.info(f"View content payload keys: {list(state.payload.keys())}")
        logger.info(f"View content payload content_ids: {state.payload.get('content_ids', [])}")
        
    except Exception as e:
        error_msg = f"Failed to fetch content: {str(e)}"
        state.error = error_msg
        state.result = f"Error: {error_msg}\n\nPlease try again or contact support if the issue persists."
        logger.error(f"Database query failed in handle_view_content: {str(e)}", exc_info=True)
    
    return state


def _get_date_range_filter(date_range: str) -> Optional[Dict[str, str]]:
    """Convert date range string to start/end dates for PostgreSQL timestamp filtering"""
    from datetime import datetime, timedelta
    
    now = datetime.now()
    date_range_lower = date_range.lower().strip()
    
    if date_range_lower == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return {"start": start.isoformat(), "end": end.isoformat()}
    
    elif date_range_lower == "yesterday":
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        return {"start": start.isoformat(), "end": end.isoformat()}
    
    elif date_range_lower == "tomorrow":
        tomorrow = now + timedelta(days=1)
        start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
        return {"start": start.isoformat(), "end": end.isoformat()}
    
    elif date_range_lower == "this week":
        # Start of current week (Monday)
        days_since_monday = now.weekday()
        start = now - timedelta(days=days_since_monday)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return {"start": start.isoformat(), "end": end.isoformat()}
    
    elif date_range_lower == "last week":
        # Previous week (Monday to Sunday)
        days_since_monday = now.weekday()
        last_monday = now - timedelta(days=days_since_monday + 7)
        start = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        last_sunday = last_monday + timedelta(days=6)
        end = last_sunday.replace(hour=23, minute=59, second=59, microsecond=999999)
        return {"start": start.isoformat(), "end": end.isoformat()}
    
    elif date_range_lower == "custom date":
        # For custom dates, return None - will need to be handled separately
        return None
    
    return None


def _parse_date_range_format(date_range: str) -> Optional[Dict[str, str]]:
    """Parse YYYY-MM-DD format dates and ranges into start/end dates for filtering"""
    from datetime import datetime

    date_range = date_range.strip()

    # Handle single date: "2025-12-27"
    if len(date_range) == 10 and date_range.count('-') == 2:
        try:
            # Validate the date format
            datetime.strptime(date_range, '%Y-%m-%d')
            return {"start": date_range, "end": date_range}
        except ValueError:
            return None

    # Handle date range: "2025-12-23 to 2025-12-27"
    if ' to ' in date_range:
        try:
            start_str, end_str = date_range.split(' to ')
            start_str = start_str.strip()
            end_str = end_str.strip()

            # Validate both dates
            datetime.strptime(start_str, '%Y-%m-%d')
            datetime.strptime(end_str, '%Y-%m-%d')

            return {"start": start_str, "end": end_str}
        except (ValueError, AttributeError):
            return None

    return None


def _generate_mock_view_content(payload: Dict[str, Any]) -> str:
    """Generate mock content list for testing without database"""
    
    # Mock data
    mock_content = [
        {
            "id": "CONTENT_001",
            "platform": payload.get('platform', 'Instagram'),
            "content_type": payload.get('content_type', 'post'),
            "status": payload.get('status', 'generated'),
            "created_at": "2025-12-24",
            "content_text": "Exciting AI trends for 2025! Discover how artificial intelligence is transforming..."
        },
        {
            "id": "CONTENT_002",
            "platform": payload.get('platform', 'LinkedIn'),
            "content_type": payload.get('content_type', 'post'),
            "status": payload.get('status', 'published'),
            "created_at": "2025-12-23",
            "content_text": "Top 10 productivity hacks for remote workers. Boost your efficiency with these..."
        },
        {
            "id": "CONTENT_003",
            "platform": payload.get('platform', 'Facebook'),
            "content_type": payload.get('content_type', 'short_video'),
            "status": payload.get('status', 'scheduled'),
            "created_at": "2025-12-22",
            "content_text": "Video: Sustainable fashion trends you need to know about in 2025..."
        },
    ]
    
    content_list = []
    for idx, item in enumerate(mock_content, 1):
        content_list.append(f"""
{idx}. {item['content_type'].title().replace('_', ' ')} - {item['platform']}
   Status: {item['status'].upper()}
   Created: {item['created_at']}
   ID: {item['id']}
   Preview: {item['content_text'][:100]}...
""")
    
    return f"""Viewing Content (Mock Data)

Filters:
- Channel: {payload.get('channel', 'All')}
- Platform: {payload.get('platform', 'All')}
- Status: {payload.get('status', 'All')}
- Content Type: {payload.get('content_type', 'All')}
- Date range: {payload.get('date_range', 'All time')}

Found 3 content item(s):
{''.join(content_list)}

Note: This is mock data. Connect to Supabase to see real content.
   Set SUPABASE_URL and SUPABASE_KEY environment variables."""


def handle_publish_content(state: AgentState) -> AgentState:
    """Handle content publishing - either direct publish or search and select"""
    payload = state.payload

    # Set agent name for content publishing
    payload['agent_name'] = 'emily'

    # If content_id is provided directly, publish that specific content
    if payload.get('content_id') and payload['content_id'].strip():
        return handle_publish_specific_content(state)

    # Otherwise, search for content and present for selection
    return handle_publish_content_search(state)


def handle_publish_specific_content(state: AgentState) -> AgentState:
    """Publish a specific piece of content by ID"""
    payload = state.payload

    # Set agent name for content publishing
    payload['agent_name'] = 'emily'

    content_id = payload['content_id'].strip()

    if not supabase:
        state.error = "Database connection not configured. Please contact support."
        state.result = generate_personalized_message(
            base_message="Unable to publish content: Database not available.",
            user_context=state.user_query,
            message_type="error"
        )
        logger.error("Supabase not configured - cannot publish content")
        return state

    # Ensure user_id is present for security
    if not state.user_id:
        state.error = "User ID is required to publish content"
        state.result = generate_personalized_message(
            base_message="Unable to publish content: User authentication required.",
            user_context=state.user_query,
            message_type="error"
        )
        logger.error("User ID missing in handle_publish_specific_content")
        return state

    try:
        # Fetch the specific content
        response = supabase.table('created_content').select('*').eq('id', content_id).eq('user_id', state.user_id).execute()

        if not response.data or len(response.data) == 0:
            state.error = f"Content with ID '{content_id}' not found"
            state.result = generate_personalized_message(
                base_message=f"❌ Content with ID '{content_id}' not found. Please check the content ID and try again.",
                user_context=state.user_query,
                message_type="error"
            )
            return state

        content = response.data[0]

        # Check if content is already published
        if content.get('status') == 'published':
            state.result = generate_personalized_message(
                base_message=f"⚠️ Content '{content_id}' is already published. Cannot publish again.",
                user_context=state.user_query,
                message_type="warning"
            )
            return state

        # Here you would implement the actual publishing logic
        # For now, just mark as published in the database
        publish_response = supabase.table('created_content').update({
            'status': 'published',
            'published_at': 'now()'
        }).eq('id', content_id).eq('user_id', state.user_id).execute()

        if publish_response.data:
            base_success_message = f"""✅ Content published successfully!

📝 **Content Details:**
• ID: {content_id}
• Platform: {content.get('platform', 'Unknown')}
• Type: {content.get('content_type', 'Unknown')}
• Status: Published

The content has been published to your connected {content.get('platform', 'platform')} account."""
            state.result = generate_personalized_message(
                base_message=base_success_message,
                user_context=state.user_query,
                message_type="success"
            )
        else:
            state.error = "Failed to update content status"
            state.result = generate_personalized_message(
                base_message="❌ Failed to publish content. Please try again.",
                user_context=state.user_query,
                message_type="error"
            )

    except Exception as e:
        logger.error(f"Error publishing specific content: {e}")
        state.error = f"Failed to publish content: {str(e)}"
        state.result = generate_personalized_message(
            base_message=f"❌ Error publishing content: {str(e)}",
            user_context=state.user_query,
            message_type="error"
        )

    return state


def handle_publish_content_search(state: AgentState) -> AgentState:
    """Search for content to publish and present for user selection"""
    payload = state.payload

    if not supabase:
        state.error = "Database connection not configured. Please contact support."
        state.result = "Unable to fetch content for publishing: Database not available."
        logger.error("Supabase not configured - cannot fetch content for publishing")
        return state

    # Ensure user_id is present for security
    if not state.user_id:
        state.error = "User ID is required to view content for publishing"
        state.result = "Unable to fetch content: User authentication required."
        logger.error("User ID missing in handle_publish_content_search")
        return state

    try:
        # Build query for created_content table - select all fields including uuid (id)
        query = supabase.table('created_content').select('*')

        # Security: Always filter by user_id (required)
        query = query.eq('user_id', state.user_id)

        # Check if we have a semantic search query
        has_semantic_search = payload.get('query') and payload['query'].strip()

        if has_semantic_search:
            # Use semantic search instead of traditional filters
            search_query = payload['query'].strip()
            logger.info(f"Performing semantic search for publishing: '{search_query}'")

            # Perform text search on title and content columns
            # Use ilike for case-insensitive partial matching
            query = query.or_(f"title.ilike.%{search_query}%,content.ilike.%{search_query}%")

            # Apply any additional filters if present
            if payload.get('channel'):
                query = query.eq('channel', payload['channel'])
            if payload.get('platform'):
                platform_filter = payload['platform'].lower().strip()
                query = query.eq('platform', platform_filter)
            if payload.get('status'):
                status_filter = payload['status'].lower().strip()
                query = query.eq('status', status_filter)

        else:
            # Use traditional filters
            # Apply filters from payload
            if payload.get('channel'):
                # Channel filter (Social Media, Blog, Email, Messages)
                query = query.eq('channel', payload['channel'])

            # Apply filters from payload - convert to lowercase for platform and status
            if payload.get('platform'):
                # Convert platform to lowercase to match schema (instagram, facebook, etc.)
                platform_filter = payload['platform'].lower().strip()
                query = query.eq('platform', platform_filter)

            if payload.get('status'):
                # Convert status to lowercase to match schema (generated, scheduled, published)
                status_filter = payload['status'].lower().strip()
                query = query.eq('status', status_filter)

        # Apply date range filter - use start_date and end_date directly
        if payload.get('start_date'):
            # Convert YYYY-MM-DD to PostgreSQL timestamp format (start of day)
            start_datetime = f"{payload['start_date']}T00:00:00.000Z"
            query = query.gte('created_at', start_datetime)

        if payload.get('end_date'):
            # Convert YYYY-MM-DD to PostgreSQL timestamp format (end of day)
            end_datetime = f"{payload['end_date']}T23:59:59.999Z"
            query = query.lte('created_at', end_datetime)

        # Order by most recent first
        query = query.order('created_at', desc=True)

        # For semantic search, limit results to avoid too many matches
        # For traditional filters, show more results
        if has_semantic_search:
            response = query.limit(50).execute()  # Limit semantic search results
        else:
            response = query.limit(100).execute()  # Allow more results for filtered searches

        logger.info(f"Publish content query executed: Found {len(response.data) if response.data else 0} items (semantic_search: {has_semantic_search})")

        if not response.data or len(response.data) == 0:
            # Generate personalized "no results" message
            if has_semantic_search:
                base_message = f"No content found matching your search for '{payload['query']}'. Try different keywords or check your filters."
            else:
                filters_desc = []
                if payload.get('channel'): filters_desc.append(f"channel: {payload['channel']}")
                if payload.get('platform'): filters_desc.append(f"platform: {payload['platform']}")
                if payload.get('status'): filters_desc.append(f"status: {payload['status']}")
                if payload.get('start_date'): filters_desc.append(f"date from: {payload['start_date']}")
                if payload.get('end_date'): filters_desc.append(f"date to: {payload['end_date']}")

                if filters_desc:
                    base_message = f"No content found with the specified filters: {', '.join(filters_desc)}. Please adjust your criteria and try again."
                else:
                    base_message = "No content found. Please specify some search criteria and try again."

            state.result = base_message
            return state

        # Collect content_ids and structured content items for frontend selection
        content_items = []
        content_ids = []  # Store all content IDs for payload

        for idx, item in enumerate(response.data[:50], 1):  # Show up to 50 items for publishing
            # Get content_id (uuid) - store for payload
            content_id = item.get('id') or item.get('uuid')
            if content_id:
                content_ids.append(content_id)

                # Extract image URL from images array (first image if available)
                images = item.get('images', [])
                media_url = None
                if images and len(images) > 0:
                    # Handle both string URLs and object formats
                    first_image = images[0]
                    if isinstance(first_image, str):
                        media_url = first_image
                    elif isinstance(first_image, dict):
                        media_url = first_image.get('url') or first_image.get('image_url')

                # Create content item for frontend display
                content_item = {
                    "content_id": content_id,
                    "platform": item.get('platform', 'Unknown'),
                    "content_type": item.get('content_type', 'Unknown'),
                    "status": item.get('status', 'Unknown'),
                    "created_at": item.get('created_at', 'Unknown'),
                    "title": item.get('title', ''),
                    "content": item.get('content', '')[:200] + ('...' if len(item.get('content', '')) > 200 else ''),
                    "channel": item.get('channel', 'Unknown'),
                    "media_url": media_url,
                    "has_media": bool(media_url),
                    "images": item.get('images', [])
                }
                content_items.append(content_item)

        # Check if this is a semantic search result
        has_query = payload.get('query') and payload['query'].strip()

        if has_query:
            # For semantic search, use different formatting
            result_parts = [f"You have {len(content_items)} content item{'s' if len(content_items) != 1 else ''} matching '{payload['query']}' that can be published."]
        else:
            result_parts = [f"Found {len(content_items)} content item{'s' if len(content_items) != 1 else ''} ready for publishing."]

        result_parts.append("\nSelect which content you'd like to publish:")

        # Add filters info
        filters = []
        if payload.get('channel'): filters.append(f"Channel: {payload['channel']}")
        if payload.get('platform'): filters.append(f"Platform: {payload['platform']}")
        if payload.get('status'): filters.append(f"Status: {payload['status']}")
        if payload.get('start_date'): filters.append(f"Date: {payload['start_date']} to {payload.get('end_date', 'now')}")

        if filters:
            result_parts.append(f"Filters: {', '.join(filters)}")

        # Generate personalized success message
        state.result = generate_personalized_message(
            base_message='\n'.join(result_parts),
            user_context=state.user_query,
            message_type="success"
        )
        state.content_ids = content_ids  # Store available content IDs
        state.content_items = content_items  # Store structured content for frontend

        # Don't set payload_complete - wait for user to select content
        state.waiting_for_user = True
        state.current_step = "content_selection"

    except Exception as e:
        logger.error(f"Error in handle_publish_content: {e}")
        state.error = f"Failed to search content for publishing: {str(e)}"
        state.result = generate_personalized_message(
            base_message=f"❌ Error searching content: {str(e)}",
            user_context=state.user_query,
            message_type="error"
        )

    return state


def handle_schedule_content(state: AgentState) -> AgentState:
    """Schedule content"""
    payload = state.payload
    
    state.result = f"""📅 Content scheduled

Platform: {payload.get('platform')}
Content ID: {payload.get('content_id')}
Scheduled for: {payload.get('schedule_date')} at {payload.get('schedule_time')}

Status: Scheduled successfully"""
    
    return state


# ==================== LEAD HANDLERS ====================

def handle_create_leads(state: AgentState) -> AgentState:
    """Create new lead with database insertion and card display"""
    payload = state.payload

    # Check if payload is complete before proceeding
    if not state.payload_complete:
        state.result = "Lead creation payload is not complete. Please provide all required information first."
        return state

    # Set agent name to Chase
    payload['agent_name'] = 'chase'

    # Basic safety validation (payload should be complete, but double-check)
    lead_name = payload.get('lead_name', '').strip()
    if not lead_name:
        state.result = "Lead name is required."
        return state

    # Ensure we have user_id
    if not state.user_id:
        state.result = "User authentication required."
        return state

    # Get contact info - use original values if available, otherwise use payload values
    lead_email = getattr(state, 'temp_original_email', None) or payload.get('lead_email')
    lead_phone = getattr(state, 'temp_original_phone', None) or payload.get('lead_phone')

    # Final validation for contact info
    if not lead_email and not lead_phone:
        state.result = "Either email or phone number is required."
        return state

    lead_data = {
        "user_id": state.user_id,
        "name": lead_name.strip(),  # Keep name as-is (not lowercase)
        "email": lead_email.lower() if lead_email else None,  # Lowercase email
        "phone_number": lead_phone,  # Keep phone as-is
        "source_platform": payload.get('lead_source').strip().lower(),  # Lowercase source
        "status": payload.get('lead_status').strip().lower(),  # Lowercase status
        "form_data": {},
        "metadata": {
            "remarks": (payload.get('remarks') or '').lower(),  # Lowercase remarks
            "created_by_agent": True,
            "agent_name": "chase",
            "created_at": datetime.now().isoformat()
        }
    }

    # Handle follow_up_at if provided
    follow_up = payload.get('follow_up')
    if follow_up:
        try:
            from dateutil import parser
            follow_up_dt = parser.parse(str(follow_up))
            # Ensure it's timezone aware
            if follow_up_dt.tzinfo is None:
                follow_up_dt = follow_up_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
            lead_data["follow_up_at"] = follow_up_dt.isoformat()
        except Exception as e:
            logger.warning(f"Failed to parse follow_up_at: {follow_up}, continuing without it")

    try:
        # Insert into Supabase leads table
        if supabase:
            result = supabase.table("leads").insert(lead_data).execute()

            if result.data:
                created_lead = result.data[0]
                lead_id = created_lead["id"]

                # Set lead_id for frontend to fetch and display
                state.lead_id = lead_id

                # Set success intent for frontend
                state.intent = "lead_created"

                # Simple success message - lead card will be displayed separately
                base_message = "Added a new lead successfully!"

                state.result = generate_personalized_message(
                    base_message=base_message,
                    user_context=state.user_query,
                    message_type="success"
                )

                return state
            else:
                state.result = "Failed to create lead in database."
                return state
        else:
            state.result = "Database connection not available."
            return state

    except Exception as e:
        logger.error(f"Error creating lead: {e}")
        state.result = f"Error creating lead: {str(e)}"
        return state


def handle_view_leads(state: AgentState) -> AgentState:
    """View leads with database query and fuzzy matching"""
    payload = state.payload

    # Set agent name to Chase
    payload['agent_name'] = 'chase'

    # Ensure user_id is present for security
    if not state.user_id:
        state.result = "User authentication required."
        return state

    try:
        if not supabase:
            state.result = "Database connection not available."
            return state

        # Build query - always filter by user_id for security
        query = supabase.table("leads").select("*").eq("user_id", state.user_id)

        # Add filters
        filters = []

        if payload.get('lead_source'):
            query = query.eq("source_platform", payload['lead_source'])
            filters.append(f"Source: {payload['lead_source']}")

        if payload.get('lead_status'):
            query = query.eq("status", payload['lead_status'])
            filters.append(f"Status: {payload['lead_status']}")

        # Add date range filter if provided
        if payload.get('start_date') and payload.get('end_date'):
            filters.append(f"Date range: {payload['start_date']} to {payload['end_date']}")
            # Use the parsed start_date and end_date from complete_view_leads_payload
            start_datetime = f"{payload['start_date']}T00:00:00.000Z"
            end_datetime = f"{payload['end_date']}T23:59:59.999Z"
            query = query.gte("created_at", start_datetime).lte("created_at", end_datetime)
        elif payload.get('start_date'):
            filters.append(f"Date from: {payload['start_date']}")
            # Single date filter
            start_datetime = f"{payload['start_date']}T00:00:00.000Z"
            end_datetime = f"{payload['start_date']}T23:59:59.999Z"
            query = query.gte("created_at", start_datetime).lte("created_at", end_datetime)

        # Add fuzzy matching for name/email if provided
        if payload.get('lead_name'):
            # Use ilike for case-insensitive partial matching
            query = query.ilike("name", f"%{payload['lead_name']}%")
            filters.append(f"Name contains: {payload['lead_name']}")

        if payload.get('lead_email'):
            # Use original email for filtering
            filter_email = getattr(state, 'temp_filter_emails', [payload['lead_email']])[0]
            query = query.ilike("email", f"%{filter_email}%")
            filters.append(f"Email contains: {filter_email}")

        if payload.get('lead_phone'):
            # Use original phone for filtering
            filter_phone = getattr(state, 'temp_filter_phones', [payload['lead_phone']])[0]
            query = query.ilike("phone", f"%{filter_phone}%")
            filters.append(f"Phone contains: {filter_phone}")

        # Order by creation date (newest first) and limit results
        query = query.order("created_at", desc=True).limit(50)

        result = query.execute()
        leads = result.data if result.data else []

        # Get last remarks for all leads (similar to leads.py router)
        last_remarks = {}
        if leads:
            lead_ids = [lead["id"] for lead in leads]
            status_history_result = supabase.table("lead_status_history").select("lead_id, reason, created_at").in_("lead_id", lead_ids).order("created_at", desc=True).execute()

            seen_leads = set()
            if status_history_result.data:
                for history in status_history_result.data:
                    lead_id = history["lead_id"]
                    if lead_id not in seen_leads and history.get("reason"):
                        last_remarks[lead_id] = history["reason"]
                        seen_leads.add(lead_id)

        # Create secure lead items for frontend display (not sent to LLM)
        if not leads:
            state.result = generate_personalized_message(
                base_message="No leads found matching your criteria.",
                user_context=state.user_query,
                message_type="info"
            )
        else:
            # Store lead_ids and structured data for frontend only
            lead_ids = [lead["id"] for lead in leads]
            state.payload['lead_ids'] = lead_ids

            # Create lead_items for frontend display (not sent to LLM)
            lead_items = []
            for lead in leads:
                last_remark = last_remarks.get(lead["id"], "No remarks")
                created_date = lead.get("created_at", "Unknown")[:10] if lead.get("created_at") else "Unknown"

                lead_item = {
                    'id': lead["id"],
                    'lead_id': lead["id"],
                    'name': lead.get('name', 'Unknown'),
                    'email': lead.get('email', 'No email'),
                    'phone': lead.get('phone_number', 'No phone'),
                    'status': lead.get('status', 'Unknown'),
                    'source_platform': lead.get('source_platform', 'Unknown'),
                    'created_at': created_date,
                    'last_remark': last_remark,
                    # Add any other fields needed for frontend display
                    'metadata': lead.get('metadata', {}),
                    'raw_data': lead  # Full data for advanced frontend features
                }
                lead_items.append(lead_item)

            state.lead_items = lead_items

            # Send only summary to LLM (no PII)
            base_message = f"Found {len(leads)} lead{'s' if len(leads) != 1 else ''} matching your criteria. Select any lead to view details or take actions."

            if filters:
                base_message += f"\n\nFilters applied: {', '.join(filters)}"

            state.result = generate_personalized_message(
                base_message=base_message,
                user_context=state.user_query,
                message_type="success"
            )

    except Exception as e:
        logger.error(f"Error viewing leads: {e}")
        state.result = f"Error retrieving leads: {str(e)}"

    return state


def handle_edit_leads(state: AgentState) -> AgentState:
    """Edit lead"""
    payload = state.payload

    # Set agent name to Chase
    payload['agent_name'] = 'chase'
    
    updates = []
    if payload.get('new_lead_name'):
        updates.append(f"Name → {payload['new_lead_name']}")
    if payload.get('new_lead_email'):
        updates.append(f"Email → {payload['new_lead_email']}")
    if payload.get('new_lead_status'):
        updates.append(f"Status → {payload['new_lead_status']}")
    
    state.result = f"""Lead updated

Identifying lead:
- Name: {payload.get('lead_name')}
- Email: {payload.get('lead_email')}
- Phone: {payload.get('lead_phone')}

Updates applied:
{chr(10).join(f'  • {u}' for u in updates)}"""
    
    return state


def handle_delete_leads(state: AgentState) -> AgentState:
    """Delete lead"""
    payload = state.payload

    # Set agent name to Chase
    payload['agent_name'] = 'chase'
    
    # Get original contact info for display
    display_email = getattr(state, 'temp_delete_emails', [None])[0] or payload.get('lead_email')
    display_phone = getattr(state, 'temp_delete_phones', [None])[0] or payload.get('lead_phone')

    state.result = f"""⚠️ Lead deletion prepared

Lead to delete:
- Name: {payload.get('lead_name')}
- Email: {display_email}
- Phone: {display_phone}

Status: Awaiting confirmation"""
    
    return state


def handle_follow_up_leads(state: AgentState) -> AgentState:
    """Follow up with lead"""
    payload = state.payload

    # Set agent name to Chase
    payload['agent_name'] = 'chase'
    
    # Generate follow-up message if not provided
    if not payload.get('follow_up_message'):
        prompt = f"""Generate a professional follow-up message for a lead.

Lead name: {payload.get('lead_name')}

Make it friendly, brief, and action-oriented."""
        
        try:
            response = model.generate_content(prompt)
            follow_up_message = response.text.strip()
        except:
            follow_up_message = f"Hi {payload.get('lead_name', 'there')}, following up on our previous conversation..."
    else:
        follow_up_message = payload['follow_up_message']
    
    # Get original contact info for display
    display_email = getattr(state, 'temp_followup_emails', [None])[0] or payload.get('lead_email')
    display_phone = getattr(state, 'temp_followup_phones', [None])[0] or payload.get('lead_phone')
    
    # Format the follow-up date for display
    follow_up_date = payload.get('follow_up_date')
    formatted_date = f"\n📅 Scheduled: {follow_up_date}" if follow_up_date else ""

    state.result = f"""📧 Follow-up prepared

Lead: {payload.get('lead_name')}
Contact: {display_email or display_phone}{formatted_date}

Message:
{follow_up_message}

Status: Ready to send"""
    
    return state


# ==================== ANALYTICS HANDLERS ====================

def handle_view_insights(state: AgentState) -> AgentState:
    """View insights"""
    payload = state.payload
    
    state.result = f"""📊 Insights Dashboard

Channel: {payload.get('channel', 'All')}
Platform: {payload.get('platform', 'All')}
Metrics: {', '.join(payload.get('metrics', ['All']))}
Period: {payload.get('date_range', 'All time')}

[Insights data would be displayed here]"""
    
    return state


def handle_view_analytics(state: AgentState) -> AgentState:
    """View analytics"""
    payload = state.payload
    
    state.result = f"""📈 Analytics Dashboard

Channel: {payload.get('channel', 'All')}
Platform: {payload.get('platform', 'All')}
Period: {payload.get('date_range', 'All time')}

[Analytics data would be displayed here]"""
    
    return state


# ==================== GRAPH CONSTRUCTION ====================

def route_to_constructor(state: AgentState) -> str:
    """Route to specific payload constructor based on intent"""
    if state.error:
        return "end"
    
    # Greeting goes directly to end
    if state.intent == "greeting":
        return "end"
    
    # General_talks skips payload construction
    if state.intent == "general_talks":
        return "execute_action"
    
    intent_to_constructor = {
        "create_content": "construct_create_content",
        "edit_content": "construct_edit_content",
        "delete_content": "construct_delete_content",
        "view_content": "construct_view_content",
        "publish_content": "construct_publish_content",
        "schedule_content": "construct_schedule_content",
        "create_leads": "construct_create_leads",
        "view_leads": "construct_view_leads",
        "edit_leads": "construct_edit_leads",
        "delete_leads": "construct_delete_leads",
        "follow_up_leads": "construct_follow_up_leads",
        "view_insights": "construct_view_insights",
        "view_analytics": "construct_view_analytics",
    }
    
    return intent_to_constructor.get(state.intent, "end")


def should_continue_to_completion(state: AgentState) -> str:
    """Route after payload construction"""
    if state.error:
        return "end"
    return "complete_payload"


def should_continue_to_action(state: AgentState) -> str:
    """Route after payload completion check"""
    if state.error:
        return "end"
    if state.payload_complete:
        return "execute_action"
    # When waiting for user clarification, stop graph execution
    # The graph will pause and return control. When user responds,
    # process_query will update state and invoke graph again from entry point
    if state.waiting_for_user:
        return "end"  # Stop execution - graph pauses naturally
    return "end"


def build_graph():
    """Build the LangGraph workflow"""
    
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("classify_intent", classify_intent)
    
    # Add specific payload constructor nodes for each intent
    workflow.add_node("construct_create_content", construct_create_content_payload)
    workflow.add_node("construct_edit_content", construct_edit_content_payload)
    workflow.add_node("construct_delete_content", construct_delete_content_payload)
    workflow.add_node("construct_view_content", construct_view_content_payload)
    workflow.add_node("construct_publish_content", construct_publish_content_payload)
    workflow.add_node("construct_schedule_content", construct_schedule_content_payload)
    workflow.add_node("construct_create_leads", construct_create_leads_payload)
    workflow.add_node("construct_view_leads", construct_view_leads_payload)
    workflow.add_node("construct_edit_leads", construct_edit_leads_payload)
    workflow.add_node("construct_delete_leads", construct_delete_leads_payload)
    workflow.add_node("construct_follow_up_leads", construct_follow_up_leads_payload)
    workflow.add_node("construct_view_insights", construct_view_insights_payload)
    workflow.add_node("construct_view_analytics", construct_view_analytics_payload)
    
    # Add payload completer and action executor
    workflow.add_node("complete_payload", complete_payload)
    workflow.add_node("execute_action", execute_action)
    
    # Add edges
    workflow.set_entry_point("classify_intent")
    
    # Route from intent classifier to specific constructor or direct to action
    workflow.add_conditional_edges(
        "classify_intent",
        route_to_constructor,
        {
            "execute_action": "execute_action",  # For greeting and general_talks
            "construct_create_content": "construct_create_content",
            "construct_edit_content": "construct_edit_content",
            "construct_delete_content": "construct_delete_content",
            "construct_view_content": "construct_view_content",
            "construct_publish_content": "construct_publish_content",
            "construct_schedule_content": "construct_schedule_content",
            "construct_create_leads": "construct_create_leads",
            "construct_view_leads": "construct_view_leads",
            "construct_edit_leads": "construct_edit_leads",
            "construct_delete_leads": "construct_delete_leads",
            "construct_follow_up_leads": "construct_follow_up_leads",
            "construct_view_insights": "construct_view_insights",
            "construct_view_analytics": "construct_view_analytics",
            "end": END
        }
    )
    
    # All constructors go to payload completer
    for constructor_name in [
        "construct_create_content", "construct_edit_content", "construct_delete_content",
        "construct_view_content", "construct_publish_content", "construct_schedule_content",
        "construct_create_leads", "construct_view_leads", "construct_edit_leads",
        "construct_delete_leads", "construct_follow_up_leads", "construct_view_insights",
        "construct_view_analytics"
    ]:
        workflow.add_conditional_edges(
            constructor_name,
            should_continue_to_completion,
            {
                "complete_payload": "complete_payload",
                "end": END
            }
        )
    
    # Payload completer routes to action or ends (when waiting for user)
    workflow.add_conditional_edges(
        "complete_payload",
        should_continue_to_action,
        {
            "execute_action": "execute_action",
            "end": END  # Ends when waiting for user clarification or on error
        }
    )
    
    workflow.add_edge("execute_action", END)
    
    return workflow.compile()


# ==================== MAIN AGENT CLASS ====================

class ATSNAgent:
    """Main agent class for content and lead management"""
    
    def __init__(self, user_id: Optional[str] = None):
        self.graph = build_graph()
        self.state = None
        self.user_id = user_id
    
    async def process_query(self, user_query: str, conversation_history: List[str] = None, user_id: Optional[str] = None, media_file: Optional[str] = None) -> Dict[str, Any]:
        """Process a user query
        
        Maintains conversation context by appending new messages to user_query.
        This ensures the LLM always has full context for intent classification and payload construction.
        """
        
        # Use provided user_id or fall back to instance user_id
        active_user_id = user_id or self.user_id
        
        # Clean and normalize user query
        user_query = user_query.strip()
        if not user_query:
            return {
                "error": "Empty query provided",
                "current_step": "end"
            }
        
        # Initialize or update state
        # Check if previous query was completed (has result and payload_complete)
        previous_completed = (
            self.state is not None 
            and self.state.payload_complete 
            and (self.state.result or self.state.current_step == "end")
            and not self.state.waiting_for_user
        )
        
        if self.state is None or previous_completed or not self.state.waiting_for_user:
            # New conversation or new query after completion
            # Reset state if previous query was completed
            if previous_completed:
                logger.info("Previous query completed, starting new conversation")
            self.state = AgentState(
                user_query=user_query,
                conversation_history=[],  # Deprecated but kept for compatibility
                user_id=active_user_id
            )
        else:
            # User is responding to clarification - append to maintain context
            # This ensures the LLM sees the full conversation flow
            if self.state.user_query:
                # Append with space separator, ensuring no double spaces
                existing_query = self.state.user_query.rstrip()
                self.state.user_query = f"{existing_query} {user_query}"
            else:
                self.state.user_query = user_query
            
            self.state.waiting_for_user = False
            self.state.current_step = "payload_construction"
            
            # Preserve user_id if provided
            if active_user_id:
                self.state.user_id = active_user_id

        # Handle media_file if provided (for upload functionality)
        if media_file:
            self.state.payload['media_file'] = media_file
            logger.info(f"Media file set in payload: {media_file}")

        # Run the graph
        result = await self.graph.ainvoke(self.state)
        
        # Update state with result
        self.state = AgentState(**result)
        
        # Prepare response - only include clarification_options when actually waiting for user
        clarification_options = []
        if self.state.waiting_for_user and hasattr(self.state, 'clarification_options'):
            clarification_options = getattr(self.state, 'clarification_options', [])

        response = {
            "intent": self.state.intent,
            "payload": self.state.payload,
            "payload_complete": self.state.payload_complete,
            "waiting_for_user": self.state.waiting_for_user,
            "clarification_question": self.state.clarification_question,
            "clarification_options": clarification_options,  # Only include when waiting
            "result": self.state.result,
            "error": self.state.error,
            "current_step": self.state.current_step,
            "content_id": self.state.content_id,  # Single content ID (UUID)
            "content_ids": getattr(self.state, 'content_ids', None),  # List of content IDs for selection
            "lead_id": self.state.lead_id,  # Single lead ID (UUID)
            "content_items": self.state.content_items,  # Structured content data for frontend cards
            "lead_items": self.state.lead_items,  # Structured lead data for frontend cards
            "needs_connection": getattr(self.state, 'needs_connection', None),  # Whether user needs to connect account
            "connection_platform": getattr(self.state, 'connection_platform', None)  # Platform to connect
        }
        
        return response
    
    def reset(self):
        """Reset the agent state"""
        self.state = None


# ==================== USAGE EXAMPLE ====================

def main():
    """Example usage"""
    
    print("=" * 80)
    print("ATSN Agent - Content & Lead Management")
    print("Built with LangGraph | Powered by Gemini 2.5")
    print("=" * 80)
    print()
    
    agent = ATSNAgent()
    
    # Example 1: Create content with clarifications
    print("📝 Example 1: Create Instagram post")
    print("-" * 80)
    print("User: Create an Instagram post about sustainable fashion trends for 2025")
    response = agent.process_query(
        "Create an Instagram post about sustainable fashion trends for 2025"
    )
    
    # Handle clarifications
    clarification_count = 0
    while response['waiting_for_user'] and clarification_count < 5:
        clarification_count += 1
        print(f"\n🤖 Agent: {response['clarification_question']}")
        
        # Simulate user responses
        if "media" in response['clarification_question'].lower():
            user_response = "Generate an image"
            print(f"👤 User: {user_response}")
            response = agent.process_query(user_response)
        else:
            user_response = input("👤 User: ")
            response = agent.process_query(user_response)
    
    if response['result']:
        print(f"\n{response['result']}")
    elif response['error']:
        print(f"\nError: {response['error']}")
    
    print("\n")
    
    # Example 2: Create lead with partial information
    print("👤 Example 2: Create a new lead")
    print("-" * 80)
    print("User: Add a new lead John Doe from website")
    agent.reset()
    response = agent.process_query(
        "Add a new lead John Doe from website"
    )
    
    clarification_count = 0
    while response['waiting_for_user'] and clarification_count < 5:
        clarification_count += 1
        print(f"\n🤖 Agent: {response['clarification_question']}")
        
        # Simulate responses
        if "email" in response['clarification_question'].lower():
            user_response = "john.doe@example.com"
        elif "phone" in response['clarification_question'].lower():
            user_response = "+1234567890"
        else:
            user_response = input("👤 User: ")
        
        print(f"👤 User: {user_response}")
        response = agent.process_query(user_response)
    
    if response['result']:
        print(f"\n{response['result']}")
    elif response['error']:
        print(f"\nError: {response['error']}")
    
    print("\n")
    
    # Example 3: Schedule content
    print("📅 Example 3: Schedule LinkedIn content")
    print("-" * 80)
    print("User: Schedule my LinkedIn post for tomorrow at 2 PM")
    agent.reset()
    response = agent.process_query(
        "Schedule my LinkedIn post for tomorrow at 2 PM"
    )
    
    clarification_count = 0
    while response['waiting_for_user'] and clarification_count < 5:
        clarification_count += 1
        print(f"\n🤖 Agent: {response['clarification_question']}")
        user_response = input("👤 User: ")
        response = agent.process_query(user_response)
    
    if response['result']:
        print(f"\n{response['result']}")
    elif response['error']:
        print(f"\nError: {response['error']}")
    
    print("\n")
    
    # Example 4: View leads with filters
    print("Example 4: View qualified leads")
    print("-" * 80)
    print("User: Show me all qualified leads from LinkedIn")
    agent.reset()
    response = agent.process_query(
        "Show me all qualified leads from LinkedIn"
    )
    
    clarification_count = 0
    while response['waiting_for_user'] and clarification_count < 5:
        clarification_count += 1
        print(f"\n🤖 Agent: {response['clarification_question']}")
        user_response = input("👤 User: ")
        response = agent.process_query(user_response)
    
    if response['result']:
        print(f"\n{response['result']}")
    elif response['error']:
        print(f"\nError: {response['error']}")
    
    print("\n")
    
    # Example 5: View content with filters (NEW - Database integration)
    print("Example 5: View content with filters")
    print("-" * 80)
    print("User: Show me all scheduled Instagram posts")
    agent.reset()
    response = agent.process_query(
        "Show me all scheduled Instagram posts"
    )
    
    clarification_count = 0
    while response['waiting_for_user'] and clarification_count < 5:
        clarification_count += 1
        print(f"\n🤖 Agent: {response['clarification_question']}")
        user_response = input("👤 User: ")
        response = agent.process_query(user_response)
    
    if response['result']:
        print(f"\n{response['result']}")
    elif response['error']:
        print(f"\nError: {response['error']}")
    
    print("\n")
    print("=" * 80)
    print("All examples completed!")
    print("=" * 80)
    print("\nTip: Set SUPABASE_URL and SUPABASE_KEY to use real database")
    print("   Otherwise, mock data will be displayed.")


if __name__ == "__main__":
    main()

