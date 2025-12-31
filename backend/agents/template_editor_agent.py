"""
Template Editor Designer Agent using LangGraph
This agent transforms content and images into beautiful graphic templates.
"""

import os
import base64
import json
from typing import Dict, List, Any, Optional, TypedDict
from datetime import datetime
import asyncio
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import openai
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from PIL import Image, ImageDraw, ImageFont
import requests
from supabase import create_client, Client

# Import template manager
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from utils.template_manager import template_manager
    from utils.prompt_manager import prompt_manager
except ImportError:
    # Fallback for when running from different directory
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from utils.template_manager import template_manager
    from utils.prompt_manager import prompt_manager

# OpenAI client will be initialized per request

# Initialize Supabase client (optional for static templates)
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")
supabase: Optional[Client] = None

if supabase_url and supabase_key:
    try:
        supabase = create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"Warning: Could not initialize Supabase client: {e}")
        supabase = None

class TemplateEditorState(TypedDict):
    """State for the template editor workflow"""
    # Input data
    current_content: str
    current_image_url: str
    user_id: str
    content_id: str
    
    # Template data
    template_image: Optional[str]  # Base64 encoded template image
    template_type: str  # 'user_upload' or 'premade'
    template_id: Optional[str]  # For premade templates
    
    # Logo data
    user_logo: Optional[Dict[str, Any]]  # User's logo information
    
    # Analysis results
    template_analysis: Optional[Dict[str, Any]]
    content_pieces: Optional[Dict[str, str]]
    image_modifications: Optional[Dict[str, Any]]
    
    # Generated content
    modified_content: Optional[str]
    modified_image: Optional[str]  # Base64 encoded
    final_template: Optional[str]  # Base64 encoded final image
    
    # User interaction
    user_satisfied: bool
    custom_instructions: Optional[str]
    needs_restart: bool
    
    # Custom prompt system
    has_custom_prompt: bool
    custom_prompt: Optional[str]
    custom_prompt_data: Optional[Dict[str, Any]]
    
    # Workflow control
    current_node: str
    error_message: Optional[str]

class TemplateEditorAgent:
    """Template Editor Designer Agent using LangGraph"""
    
    def __init__(self):
        from services.token_usage_service import TokenUsageService
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        self.token_tracker = TokenUsageService(supabase_url, supabase_key) if supabase_url and supabase_key else None
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(TemplateEditorState)
        
        # Add nodes
        workflow.add_node("template_uploader", self.template_uploader)
        workflow.add_node("custom_prompt_processor", self.custom_prompt_processor)
        workflow.add_node("template_analyzer", self.template_analyzer)
        workflow.add_node("logo_fetcher", self.logo_fetcher)
        workflow.add_node("content_modifier", self.content_modifier)
        workflow.add_node("image_modifier", self.image_modifier)
        workflow.add_node("content_output_generator", self.content_output_generator)
        workflow.add_node("flow_router", self.flow_router)
        workflow.add_node("custom_edit_node", self.custom_edit_node)
        workflow.add_node("save_image", self.save_image)
        
        # Set entry point
        workflow.set_entry_point("template_uploader")
        
        # Add edges
        workflow.add_edge("template_uploader", "custom_prompt_processor")
        
        # Always go to template_analyzer from custom_prompt_processor
        workflow.add_edge("custom_prompt_processor", "template_analyzer")
        
        workflow.add_edge("template_analyzer", "logo_fetcher")
        workflow.add_edge("logo_fetcher", "content_modifier")
        workflow.add_edge("content_modifier", "image_modifier")
        workflow.add_edge("image_modifier", "content_output_generator")
        workflow.add_edge("content_output_generator", "flow_router")
        
        # Conditional edges from flow_router
        workflow.add_conditional_edges(
            "flow_router",
            self._route_decision,
            {
                "custom_edit": "custom_edit_node",
                "save": "save_image",
                "restart": "template_uploader",
                "error": END
            }
        )
        
        # Edges from custom_edit_node
        workflow.add_conditional_edges(
            "custom_edit_node",
            self._custom_edit_decision,
            {
                "continue_edit": "custom_edit_node",
                "save": "save_image",
                "restart": "template_uploader",
                "error": END
            }
        )
        
        # End after save_image
        workflow.add_edge("save_image", END)
        
        return workflow.compile()
    
    async def template_uploader(self, state: TemplateEditorState) -> TemplateEditorState:
        """Node 1: Template uploader - handles template selection/upload"""
        print("🚀 TEMPLATE UPLOADER NODE CALLED!")
        try:
            print("🎨 Template Uploader: Processing template selection...")
            print(f"🔍 Template Uploader - Template ID: {state.get('template_id')}")
            print(f"🔍 Template Uploader - Template image present: {bool(state.get('template_image'))}")
            
            # If template_id is provided, load static template
            if state.get("template_id"):
                # Template image is already loaded in the router
                # Just set the template type and create basic analysis
                state["template_type"] = "premade"
                
                # Create enhanced template analysis for static templates based on template_id
                template_id = state['template_id']
                
                # Analyze template based on its ID and category
                if 'social-media' in template_id:
                    if 'Did_you_know' in template_id:
                        state["template_analysis"] = {
                            "content_areas": [
                                {
                                    "type": "text",
                                    "label": "title",
                                    "purpose": "main headline",
                                    "position": {"x": 50, "y": 50, "width": 400, "height": 80},
                                    "style": {
                                        "font_size": 28,
                                        "color": "#FFFFFF",
                                        "font_family": "Arial",
                                        "font_weight": "bold",
                                        "text_align": "center"
                                    },
                                    "content_guidelines": "Should be an attention-grabbing question or statement",
                                    "max_length": 60,
                                    "required": True
                                },
                                {
                                    "type": "text",
                                    "label": "subtitle",
                                    "purpose": "supporting information",
                                    "position": {"x": 50, "y": 150, "width": 400, "height": 60},
                                    "style": {
                                        "font_size": 18,
                                        "color": "#FFFFFF",
                                        "font_family": "Arial",
                                        "font_weight": "normal",
                                        "text_align": "center"
                                    },
                                    "content_guidelines": "Provide additional context or explanation",
                                    "max_length": 100,
                                    "required": False
                                },
                                {
                                    "type": "text",
                                    "label": "hashtags",
                                    "purpose": "social media tags",
                                    "position": {"x": 50, "y": 400, "width": 400, "height": 30},
                                    "style": {
                                        "font_size": 14,
                                        "color": "#CCCCCC",
                                        "font_family": "Arial",
                                        "font_weight": "normal",
                                        "text_align": "center"
                                    },
                                    "content_guidelines": "Relevant hashtags for social media engagement",
                                    "max_length": 50,
                                    "required": False
                                }
                            ],
                            "image_areas": [
                                {
                                    "label": "background_image",
                                    "purpose": "visual backdrop",
                                    "position": {"x": 0, "y": 0, "width": 500, "height": 500},
                                    "aspect_ratio": "1:1",
                                    "content_guidelines": "Should complement the educational/informational content"
                                }
                            ],
                            "logo_areas": [
                                {
                                    "label": "company_logo",
                                    "purpose": "brand identification",
                                    "position": {"x": 400, "y": 20, "width": 80, "height": 80},
                                    "aspect_ratio": "1:1",
                                    "content_guidelines": "User's company/brand logo for brand recognition",
                                    "required": True
                                }
                            ],
                            "design_info": {
                                "primary_colors": ["#4A90E2", "#FFFFFF"],
                                "secondary_colors": ["#CCCCCC", "#333333"],
                                "font_families": ["Arial", "Helvetica"],
                                "overall_style": "modern",
                                "layout_type": "centered",
                                "visual_hierarchy": ["title", "subtitle"],
                                "template_purpose": "educational social media post",
                                "target_audience": "general",
                                "tone": "informative"
                            },
                            "content_strategy": {
                                "main_goal": "educate and inform",
                                "key_message": "share interesting facts or knowledge",
                                "call_to_action": "encourage learning and sharing",
                                "content_flow": "title -> subtitle"
                            }
                        }
                    else:
                        # Generic social media template
                        state["template_analysis"] = {
                            "content_areas": [
                                {
                                    "type": "text",
                                    "label": "title",
                                    "purpose": "main headline",
                                    "position": {"x": 50, "y": 50, "width": 400, "height": 80},
                                    "style": {
                                        "font_size": 24,
                                        "color": "#000000",
                                        "font_family": "Arial",
                                        "font_weight": "bold",
                                        "text_align": "center"
                                    },
                                    "content_guidelines": "Should be engaging and relevant to the content",
                                    "max_length": 80,
                                    "required": True
                                },
                                {
                                    "type": "text",
                                    "label": "body",
                                    "purpose": "main content",
                                    "position": {"x": 50, "y": 150, "width": 400, "height": 120},
                                    "style": {
                                        "font_size": 16,
                                        "color": "#333333",
                                        "font_family": "Arial",
                                        "font_weight": "normal",
                                        "text_align": "center"
                                    },
                                    "content_guidelines": "Expand on the main message with relevant details",
                                    "max_length": 200,
                                    "required": True
                                }
                            ],
                            "image_areas": [
                                {
                                    "label": "main_image",
                                    "purpose": "primary visual content",
                                    "position": {"x": 50, "y": 300, "width": 400, "height": 200},
                                    "aspect_ratio": "2:1",
                                    "content_guidelines": "Should be high-quality and relevant to the main message"
                                }
                            ],
                            "logo_areas": [
                                {
                                    "label": "company_logo",
                                    "purpose": "brand identification",
                                    "position": {"x": 400, "y": 20, "width": 60, "height": 60},
                                    "aspect_ratio": "1:1",
                                    "content_guidelines": "User's company/brand logo for brand recognition",
                                    "required": True
                                }
                            ],
                            "design_info": {
                                "primary_colors": ["#000000", "#FFFFFF"],
                                "secondary_colors": ["#333333", "#CCCCCC"],
                                "font_families": ["Arial", "Helvetica"],
                                "overall_style": "modern",
                                "layout_type": "centered",
                                "visual_hierarchy": ["title", "body"],
                                "template_purpose": "social media post",
                                "target_audience": "general",
                                "tone": "professional"
                            },
                            "content_strategy": {
                                "main_goal": "inform and engage",
                                "key_message": "highlight important information",
                                "call_to_action": "encourage engagement",
                                "content_flow": "title -> body"
                            }
                        }
                else:
                    # Default template analysis for other categories
                    state["template_analysis"] = {
                        "content_areas": [
                            {
                                "type": "text",
                                "label": "title",
                                "purpose": "main headline",
                                "position": {"x": 100, "y": 50, "width": 300, "height": 60},
                                "style": {
                                    "font_size": 24,
                                    "color": "#000000",
                                    "font_family": "Arial",
                                    "font_weight": "bold",
                                    "text_align": "center"
                                },
                                "content_guidelines": "Should be attention-grabbing and concise",
                                "max_length": 50,
                                "required": True
                            }
                        ],
                        "image_areas": [],
                        "design_info": {
                            "primary_colors": ["#000000"],
                            "secondary_colors": ["#FFFFFF"],
                            "font_families": ["Arial"],
                            "overall_style": "modern",
                            "layout_type": "centered",
                            "visual_hierarchy": ["title"],
                            "template_purpose": "general content",
                            "target_audience": "general",
                            "tone": "professional"
                        },
                        "content_strategy": {
                            "main_goal": "inform and engage",
                            "key_message": "highlight important information",
                            "call_to_action": "encourage engagement",
                            "content_flow": "title"
                        }
                    }
                
                print(f"✅ Loaded static template: {state['template_id']}")
            else:
                # Handle user uploaded template
                # This would typically come from a file upload
                # For now, we'll assume it's already base64 encoded
                state["template_type"] = "user_upload"
                print("✅ Using user uploaded template")
            
            state["current_node"] = "template_uploader"
            print("✅ Template uploaded successfully")
            
            # Log data being sent to next node
            print("📤 SENDING TO CUSTOM PROMPT PROCESSOR:")
            print(f"   - template_id: {state.get('template_id', 'None')}")
            print(f"   - template_type: {state.get('template_type', 'None')}")
            print(f"   - current_content: {state.get('current_content', 'None')[:100]}..." if state.get('current_content') else "   - current_content: None")
            print(f"   - template_image: {'Present' if state.get('template_image') else 'None'}")
            print(f"   - user_id: {state.get('user_id', 'None')}")
            print(f"   - content_id: {state.get('content_id', 'None')}")
            
        except Exception as e:
            state["error_message"] = f"Template upload failed: {str(e)}"
            print(f"❌ Template upload error: {e}")
        
        return state
    
    async def custom_prompt_processor(self, state: TemplateEditorState) -> TemplateEditorState:
        """Node 1.5: Custom prompt processor - checks for custom prompts and processes them"""
        print("🚀 CUSTOM PROMPT PROCESSOR NODE CALLED!")
        try:
            print("🎯 Custom Prompt Processor: Checking for custom prompts...")
            print(f"🔍 Custom Prompt Processor - Template ID: {state.get('template_id')}")
            
            # Extract template name from template_id
            template_id = state.get('template_id', '')
            template_name = self._extract_template_name(template_id)
            
            print(f"🔍 Template ID: {template_id}")
            print(f"🔍 Extracted template name: {template_name}")
            
            if template_name:
                # Check if custom prompt exists for this template
                custom_prompt_data = prompt_manager.get_template_prompt(template_name)
                
                if custom_prompt_data:
                    print(f"✅ Found custom prompt for template: {template_name}")
                    print(f"🔍 Custom prompt data keys: {list(custom_prompt_data.keys())}")
                    
                    # Get the formatted prompt with content substitution
                    post_content = state.get('current_content', '')
                    custom_prompt = prompt_manager.get_prompt_text(template_name, post_content)
                    
                    print(f"🔍 Post content: {post_content}")
                    print(f"🔍 Formatted custom prompt: {custom_prompt[:200]}...")
                    
                    if custom_prompt:
                        # Store custom prompt in state for content modifier to use
                        state["custom_prompt"] = custom_prompt
                        state["custom_prompt_data"] = custom_prompt_data
                        state["has_custom_prompt"] = True
                        print("✅ Custom prompt stored for content modifier to use")
                    else:
                        print("⚠️ Custom prompt found but failed to format")
                        state["has_custom_prompt"] = False
                        state["skip_template_analyzer"] = False
                else:
                    print(f"ℹ️ No custom prompt found for template: {template_name}")
                    state["has_custom_prompt"] = False
                    state["skip_template_analyzer"] = False
            else:
                print(f"ℹ️ No template name extracted from template_id: '{template_id}', proceeding with normal flow")
                state["has_custom_prompt"] = False
                state["skip_template_analyzer"] = False
            
            state["current_node"] = "custom_prompt_processor"
            print("✅ Custom prompt processing completed")
            
            # Log data being sent to next node
            print("📤 SENDING TO TEMPLATE ANALYZER:")
            print(f"   - has_custom_prompt: {state.get('has_custom_prompt', False)}")
            print(f"   - custom_prompt: {'Present' if state.get('custom_prompt') else 'None'}")
            print(f"   - custom_prompt_data: {'Present' if state.get('custom_prompt_data') else 'None'}")
            print(f"   - template_id: {state.get('template_id', 'None')}")
            print(f"   - current_content: {state.get('current_content', 'None')[:100]}..." if state.get('current_content') else "   - current_content: None")
            
        except Exception as e:
            print(f"❌ Custom prompt processor error: {e}")
            state["error_message"] = f"Custom prompt processing failed: {str(e)}"
            state["has_custom_prompt"] = False
            state["skip_template_analyzer"] = False
        
        return state
    
    def _extract_template_name(self, template_id: str) -> str:
        """Extract template name from template_id"""
        try:
            if not template_id:
                return ""
            
            # Convert template_id to lowercase for matching
            template_id_lower = template_id.lower()
            print(f"🔍 Template ID: {template_id}")
            print(f"🔍 Template ID Lower: {template_id_lower}")
            
            # Check for known template patterns
            if 'did_you_know' in template_id_lower:
                return 'did_you_know'
            elif 'motivational_quote' in template_id_lower:
                return 'motivational_quote'
            elif 'tips_and_tricks' in template_id_lower:
                return 'tips_and_tricks'
            elif 'behind_the_scenes' in template_id_lower:
                return 'behind_the_scenes'
            elif 'new_product' in template_id_lower:
                return 'new_product'
            elif 'success_story' in template_id_lower:
                return 'success_story'
            elif 'school_1' in template_id_lower:
                return 'school_1'
            elif 'insights' in template_id_lower:
                return 'insights'
            else:
                # Try to extract from the template_id pattern
                # Assuming format like "social-media-Did_you_know-1" or "social-media-New Product"
                parts = template_id.split('-')
                if len(parts) >= 2:
                    # Convert to lowercase, replace spaces with underscores, and handle underscores
                    template_name = parts[-1].lower().replace(' ', '_').replace('_', '_')
                    print(f"🔍 Extracted template name: {template_name}")
                    return template_name
                
                return ""
                
        except Exception as e:
            print(f"Error extracting template name from {template_id}: {e}")
            return ""
    
    async def _create_content_from_custom_prompt(self, custom_prompt: str, prompt_data: Dict[str, Any], state: TemplateEditorState) -> Dict[str, Any]:
        """Create content pieces directly from custom prompt using OpenAI"""
        try:
            print("🎨 Creating content from custom prompt...")
            
            # Use OpenAI to generate content based on custom prompt
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": custom_prompt
                    },
                    {
                        "role": "user", 
                        "content": f"Please transform this content: {state.get('current_content', '')}"
                    }
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            generated_content = response.choices[0].message.content.strip()
            print(f"🔍 Generated content from custom prompt: {generated_content}")
            
            # Track token usage
            user_id = state.get('user_id')
            if user_id and self.token_tracker:
                await self.token_tracker.track_chat_completion_usage(
                    user_id=user_id,
                    feature_type="template_editing",
                    model_name="gpt-4o-mini",
                    response=response,
                    request_metadata={"template_name": state.get('template_name')}
                )
            
            # Create content pieces structure based on template type
            template_name = prompt_data.get("name", "").lower()
            
            if "did you know" in template_name:
                # For "Did you know" template, the generated content should already be in the right format
                content_pieces = {
                    "title": "Did you know?",
                    "subtitle": generated_content.replace("Did you know?", "").strip(),
                    "main_text": generated_content,
                    "generated_by": "custom_prompt",
                    "template_name": prompt_data.get("name", "Custom Template"),
                    "prompt_version": prompt_data.get("updated_at", "1.0.0")
                }
            else:
                # For other templates, use the general structure
                content_pieces = {
                    "main_text": generated_content,
                    "title": self._extract_title_from_content(generated_content),
                    "subtitle": self._extract_subtitle_from_content(generated_content),
                    "generated_by": "custom_prompt",
                    "template_name": prompt_data.get("name", "Custom Template"),
                    "prompt_version": prompt_data.get("updated_at", "1.0.0")
                }
            
            print(f"✅ Content generated from custom prompt: {generated_content[:100]}...")
            return content_pieces
            
        except Exception as e:
            print(f"❌ Error creating content from custom prompt: {e}")
            # Fallback to basic content structure
            return {
                "main_text": state.get('current_content', ''),
                "title": "Generated Content",
                "subtitle": "",
                "generated_by": "custom_prompt_fallback",
                "template_name": "Custom Template",
                "prompt_version": "1.0.0"
            }
    
    def _extract_title_from_content(self, content: str) -> str:
        """Extract title from generated content"""
        try:
            # Look for patterns like "Did you know?" or quoted text
            if "Did you know?" in content:
                return "Did you know?"
            elif content.startswith('"') and '"' in content[1:]:
                # Extract quoted text
                end_quote = content.find('"', 1)
                if end_quote > 0:
                    return content[1:end_quote]
            
            # Take first line or first 50 characters
            first_line = content.split('\n')[0]
            return first_line[:50] + "..." if len(first_line) > 50 else first_line
            
        except Exception as e:
            print(f"Error extracting title: {e}")
            return "Generated Content"
    
    def _extract_subtitle_from_content(self, content: str) -> str:
        """Extract subtitle from generated content"""
        try:
            # Look for content after "Did you know?" or after quoted text
            if "Did you know?" in content:
                parts = content.split("Did you know?", 1)
                if len(parts) > 1:
                    subtitle = parts[1].strip()
                    return subtitle[:100] + "..." if len(subtitle) > 100 else subtitle
            
            # Take second line if available
            lines = content.split('\n')
            if len(lines) > 1:
                return lines[1][:100] + "..." if len(lines[1]) > 100 else lines[1]
            
            return ""
            
        except Exception as e:
            print(f"Error extracting subtitle: {e}")
            return ""
    
    
    async def template_analyzer(self, state: TemplateEditorState) -> TemplateEditorState:
        """Node 2: Template analyzer - uses OpenAI vision to analyze template"""
        print("🚀 TEMPLATE ANALYZER NODE CALLED!")
        try:
            print("🔍 Template Analyzer: Analyzing template structure...")
            print(f"🔍 Template Analyzer - Template image present: {bool(state.get('template_image'))}")
            
            # If we already have template analysis from static template, use it
            if state.get("template_analysis"):
                print("✅ Using pre-loaded template analysis")
                print(f"🔍 Template Analyzer - Preserving custom prompt data: {state.get('has_custom_prompt', False)}")
                state["current_node"] = "template_analyzer"
                return state
            
            # For static templates without pre-loaded analysis, generate it
            print("🔍 Generating analysis for static template...")
            
            if not state.get("template_image"):
                raise ValueError("No template image provided")
            
            # For user-uploaded templates, use OpenAI vision analysis
            print("🔍 Analyzing user-uploaded template with OpenAI vision...")
            
            # Prepare the image for OpenAI vision
            image_data = state["template_image"]
            if image_data.startswith('data:image'):
                # Remove data URL prefix
                image_data = image_data.split(',')[1]
            
            # Decode base64 image
            image_bytes = base64.b64decode(image_data)
            
            # Analyze template using OpenAI vision with enhanced prompting
            analysis_prompt = """
            Analyze this template image comprehensively to understand its structure and content requirements.
            
            DETAILED ANALYSIS REQUIRED:
            
            1. CONTENT AREAS - Identify ALL text areas that need content:
               - Primary headline/title (usually largest text)
               - Subtitle or tagline (secondary text)
               - Body text or description
               - Call-to-action (CTA) text
               - Date/time information
               - Location/venue details
               - Author/creator attribution
               - Hashtags or social media tags
               - Any other text elements
            
            2. VISUAL ELEMENTS - Identify image areas and design elements:
               - Main image placeholder
               - Background images
               - Logo placement areas (CRITICAL: Look for company/brand logo spots)
               - Decorative elements
               - Icons or graphics
               - Watermark areas
               - Brand/attribution areas
            
            3. DESIGN ANALYSIS - Analyze the visual design:
               - Primary color scheme (hex codes)
               - Secondary/accent colors
               - Typography styles and font families
               - Overall design aesthetic (modern, vintage, minimalist, etc.)
               - Layout style (centered, left-aligned, grid-based, etc.)
               - Visual hierarchy and emphasis areas
            
            4. CONTENT STRATEGY - Understand the template's purpose:
               - What type of content is this designed for? (social media post, announcement, event, product, etc.)
               - What's the intended tone? (professional, casual, playful, serious, etc.)
               - What's the target audience?
               - What's the main message or goal?
            
            Return a comprehensive JSON structure:
            {
                "content_areas": [
                    {
                        "type": "text",
                        "label": "title",
                        "purpose": "main headline",
                        "position": {"x": 100, "y": 50, "width": 300, "height": 60},
                        "style": {
                            "font_size": 24,
                            "color": "#000000",
                            "font_family": "Arial",
                            "font_weight": "bold",
                            "text_align": "center"
                        },
                        "content_guidelines": "Should be attention-grabbing and concise",
                        "max_length": 50,
                        "required": true
                    }
                ],
                "image_areas": [
                    {
                        "label": "main_image",
                        "purpose": "primary visual content",
                        "position": {"x": 50, "y": 100, "width": 400, "height": 300},
                        "aspect_ratio": "4:3",
                        "content_guidelines": "Should be high-quality and relevant to the main message"
                    }
                ],
                "logo_areas": [
                    {
                        "label": "company_logo",
                        "purpose": "brand identification",
                        "position": {"x": 400, "y": 20, "width": 80, "height": 80},
                        "aspect_ratio": "1:1",
                        "content_guidelines": "User's company/brand logo",
                        "required": true
                    }
                ],
                "design_info": {
                    "primary_colors": ["#FF0000", "#00FF00"],
                    "secondary_colors": ["#FFFFFF", "#CCCCCC"],
                    "font_families": ["Arial", "Helvetica"],
                    "overall_style": "modern",
                    "layout_type": "centered",
                    "visual_hierarchy": ["title", "subtitle", "body", "cta"],
                    "template_purpose": "social media post",
                    "target_audience": "general",
                    "tone": "professional"
                },
                "content_strategy": {
                    "main_goal": "inform and engage",
                    "key_message": "highlight important information",
                    "call_to_action": "encourage engagement",
                    "content_flow": "title -> subtitle -> body -> cta"
                }
            }
            """
            
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": analysis_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000
            )
            
            # Track token usage
            user_id = state.get('user_id')
            if user_id and self.token_tracker:
                await self.token_tracker.track_chat_completion_usage(
                    user_id=user_id,
                    feature_type="template_editing",
                    model_name="gpt-4o-mini",
                    response=response,
                    request_metadata={"action": "analyze_template"}
                )
            
            # Parse the analysis result
            analysis_text = response.choices[0].message.content
            try:
                analysis_data = json.loads(analysis_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, create a basic structure
                analysis_data = {
                    "content_areas": [
                        {
                            "type": "text",
                            "label": "title",
                            "position": {"x": 100, "y": 50, "width": 300, "height": 60},
                            "style": {"font_size": 24, "color": "#000000", "font_family": "Arial"},
                            "required": True
                        }
                    ],
                    "image_areas": [],
                    "design_info": {
                        "primary_colors": ["#000000"],
                        "font_families": ["Arial"],
                        "overall_style": "modern"
                    }
                }
            
            state["template_analysis"] = analysis_data
            state["current_node"] = "template_analyzer"
            print("✅ Template analysis completed")
            
            # Log data being sent to next node
            print("📤 SENDING TO LOGO FETCHER:")
            print(f"   - template_analysis: {'Present' if state.get('template_analysis') else 'None'}")
            print(f"   - has_custom_prompt: {state.get('has_custom_prompt', False)}")
            print(f"   - custom_prompt: {'Present' if state.get('custom_prompt') else 'None'}")
            print(f"   - template_id: {state.get('template_id', 'None')}")
            print(f"   - current_content: {state.get('current_content', 'None')[:100]}..." if state.get('current_content') else "   - current_content: None")
            
        except Exception as e:
            state["error_message"] = f"Template analysis failed: {str(e)}"
            print(f"❌ Template analysis error: {e}")
        
        return state
    
    async def logo_fetcher(self, state: TemplateEditorState) -> TemplateEditorState:
        """Node 2.5: Logo fetcher - fetches user's logo from profile if template needs it"""
        print("🚀 LOGO FETCHER NODE CALLED!")
        try:
            print("🏢 Logo Fetcher: Checking for logo requirements...")
            print(f"🔍 Logo Fetcher - Received state keys: {list(state.keys())}")
            print(f"🔍 Logo Fetcher - has_custom_prompt: {state.get('has_custom_prompt', 'NOT_FOUND')}")
            print(f"🔍 Logo Fetcher - custom_prompt: {'Present' if state.get('custom_prompt') else 'None'}")
            
            template_analysis = state.get("template_analysis", {})
            logo_areas = template_analysis.get("logo_areas", [])
            
            if not logo_areas:
                print("ℹ️ No logo areas detected in template, skipping logo fetch")
                state["user_logo"] = None
                state["current_node"] = "logo_fetcher"
                return state
            
            print(f"🔍 Found {len(logo_areas)} logo areas in template")
            
            # Fetch user's logo from Supabase profiles table
            user_id = state.get("user_id")
            if not user_id:
                print("⚠️ No user_id provided, skipping logo fetch")
                state["user_logo"] = None
                state["current_node"] = "logo_fetcher"
                return state
            
            # Import supabase here to avoid circular imports
            try:
                from supabase import create_client, Client
                supabase_admin = create_client(
                    os.getenv("SUPABASE_URL"),
                    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                )
                
                # Fetch user profile with logo information
                profile_response = supabase_admin.table("profiles").select("logo_url, business_name").eq("id", user_id).execute()
                
                if profile_response.data and len(profile_response.data) > 0:
                    profile = profile_response.data[0]
                    logo_url = profile.get("logo_url")
                    business_name = profile.get("business_name", "Company")
                    
                    if logo_url:
                        print(f"✅ Found user logo: {logo_url}")
                        state["user_logo"] = {
                            "url": logo_url,
                            "business_name": business_name,
                            "areas": logo_areas
                        }
                    else:
                        print("⚠️ User has no logo_url in profile")
                        state["user_logo"] = None
                else:
                    print("⚠️ User profile not found")
                    state["user_logo"] = None
                    
            except Exception as e:
                print(f"⚠️ Error fetching user logo: {e}")
                state["user_logo"] = None
            
            state["current_node"] = "logo_fetcher"
            print("✅ Logo fetching completed")
            
            # Ensure custom prompt data is preserved
            if not state.get("has_custom_prompt"):
                print("⚠️ WARNING: Custom prompt data lost in Logo Fetcher!")
            
            # Log data being sent to next node
            print("📤 SENDING TO CONTENT MODIFIER:")
            print(f"   - user_logo: {'Present' if state.get('user_logo') else 'None'}")
            print(f"   - template_analysis: {'Present' if state.get('template_analysis') else 'None'}")
            print(f"   - has_custom_prompt: {state.get('has_custom_prompt', False)}")
            print(f"   - custom_prompt: {'Present' if state.get('custom_prompt') else 'None'}")
            print(f"   - current_content: {state.get('current_content', 'None')[:100]}..." if state.get('current_content') else "   - current_content: None")
            
        except Exception as e:
            state["error_message"] = f"Logo fetching failed: {str(e)}"
            print(f"❌ Logo fetching error: {e}")
        
        return state
    
    async def content_modifier(self, state: TemplateEditorState) -> TemplateEditorState:
        """Node 3: Content modifier - adapts content for template structure"""
        print("🚀 CONTENT MODIFIER NODE CALLED!")
        try:
            print("✏️ Content Modifier: Adapting content for template...")
            print(f"🔍 Content Modifier - Template analysis present: {bool(state.get('template_analysis'))}")
            print(f"🔍 Content Modifier - Content pieces present: {bool(state.get('content_pieces'))}")
            
            # Check if we have a custom prompt to use
            if state.get("has_custom_prompt", False) and state.get("custom_prompt"):
                print("✅ Using custom prompt for content modification")
                # Use custom prompt to generate content
                content_pieces = await self._create_content_from_custom_prompt(
                    state["custom_prompt"], 
                    state["custom_prompt_data"], 
                    state
                )
                state["content_pieces"] = content_pieces
                state["current_node"] = "content_modifier"
                print("✅ Content pieces created from custom prompt")
                
                # Log data being sent to next node
                print("📤 SENDING TO IMAGE MODIFIER (CUSTOM PROMPT PATH):")
                print(f"   - content_pieces: {'Present' if state.get('content_pieces') else 'None'}")
                print(f"   - has_custom_prompt: {state.get('has_custom_prompt', False)}")
                print(f"   - template_analysis: {'Present' if state.get('template_analysis') else 'None'}")
                print(f"   - user_logo: {'Present' if state.get('user_logo') else 'None'}")
                if state.get('content_pieces'):
                    print(f"   - content_pieces keys: {list(state.get('content_pieces', {}).keys())}")
                    print(f"   - title: {state.get('content_pieces', {}).get('title', 'None')}")
                    print(f"   - subtitle: {state.get('content_pieces', {}).get('subtitle', 'None')[:50]}..." if state.get('content_pieces', {}).get('subtitle') else "   - subtitle: None")
                
                return state
            
            if not state.get("template_analysis"):
                raise ValueError("No template analysis available")
            
            current_content = state["current_content"]
            template_analysis = state["template_analysis"]
            
            # Create content pieces based on enhanced template analysis
            content_pieces = {}
            design_info = template_analysis.get("design_info", {})
            content_strategy = template_analysis.get("content_strategy", {})
            
            # Get template context for better content generation
            template_purpose = design_info.get("template_purpose", "social media post")
            target_audience = design_info.get("target_audience", "general")
            tone = design_info.get("tone", "professional")
            overall_style = design_info.get("overall_style", "modern")
            
            for area in template_analysis.get("content_areas", []):
                area_label = area["label"]
                area_type = area["type"]
                area_purpose = area.get("purpose", area_label)
                content_guidelines = area.get("content_guidelines", "")
                max_length = area.get("max_length", 100)
                
                if area_type == "text":
                    # Generate context-aware content for this specific text area
                    content_prompt = f"""
                    You are a professional content creator specializing in {template_purpose} content.
                    
                    TEMPLATE CONTEXT:
                    - Template Purpose: {template_purpose}
                    - Target Audience: {target_audience}
                    - Tone: {tone}
                    - Design Style: {overall_style}
                    - Content Area: {area_label} ({area_purpose})
                    - Content Guidelines: {content_guidelines}
                    - Maximum Length: {max_length} characters
                    
                    ORIGINAL CONTENT TO ADAPT:
                    "{current_content}"
                    
                    CONTENT STRATEGY:
                    - Main Goal: {content_strategy.get('main_goal', 'inform and engage')}
                    - Key Message: {content_strategy.get('key_message', 'highlight important information')}
                    - Call to Action: {content_strategy.get('call_to_action', 'encourage engagement')}
                    
                    TASK:
                    Create compelling {area_label} text that:
                    1. Perfectly fits the {area_purpose} role in this template
                    2. Adapts the original content to match the {tone} tone
                    3. Appeals to the {target_audience} audience
                    4. Follows the {overall_style} design aesthetic
                    5. Stays within {max_length} characters
                    6. Follows the content guidelines: {content_guidelines}
                    7. Supports the main goal: {content_strategy.get('main_goal', 'inform and engage')}
                    
                    CRITICAL QUALITY REQUIREMENTS:
                    - ZERO spelling mistakes or typos
                    - Perfect grammar and punctuation
                    - Professional language appropriate for {tone} tone
                    - Clear, concise, and impactful messaging
                    - Proper capitalization and formatting
                    - Double-check all words for accuracy
                    
                    SPECIAL CONSIDERATIONS:
                    - If this is a title/headline: Make it attention-grabbing and concise
                    - If this is a subtitle: Provide supporting details that complement the title
                    - If this is body text: Expand on the main message with relevant details
                    - If this is a CTA: Create a clear, actionable instruction
                    - If this is a date/time: Format appropriately for the context
                    - If this is a location: Make it specific and relevant
                    - If this is a hashtag: Skip this area as hashtags are not embedded in images
                    
                    QUALITY CONTROL:
                    Before finalizing, verify:
                    ✓ All words are spelled correctly
                    ✓ Grammar and punctuation are perfect
                    ✓ Text is appropriate for the {tone} tone
                    ✓ Message is clear and impactful
                    ✓ Length is within {max_length} characters
                    
                    Return only the optimized, perfectly spelled text content, no additional formatting or explanations.
                    """
                    
                    client = openai.OpenAI()
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "user", "content": content_prompt}
                        ],
                        max_tokens=300
                    )
                    
                    generated_content = response.choices[0].message.content.strip()
                    
                    # Post-process content for quality assurance
                    # Validate spelling and grammar with a follow-up check
                    validation_prompt = f"""
                    Review this text for spelling and grammar errors:
                    "{generated_content}"
                    
                    Requirements:
                    - Check for spelling mistakes
                    - Verify grammar and punctuation
                    - Ensure professional tone
                    - Maintain clarity and impact
                    
                    If there are any errors, provide the corrected version.
                    If the text is perfect, return it exactly as is.
                    
                    Return only the corrected text, no explanations.
                    """
                    
                    validation_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "user", "content": validation_prompt}
                        ],
                        max_tokens=200
                    )
                    
                    validated_content = validation_response.choices[0].message.content.strip()
                    
                    # Track token usage
                    user_id = state.get('user_id')
                    if user_id and self.token_tracker:
                        await self.token_tracker.track_chat_completion_usage(
                            user_id=user_id,
                            feature_type="template_editing",
                            model_name="gpt-4o-mini",
                            response=validation_response,
                            request_metadata={"action": "validate_content"}
                        )
                    
                    # Ensure content fits within max_length
                    if len(validated_content) > max_length:
                        # Truncate intelligently (at word boundary)
                        truncated = validated_content[:max_length]
                        last_space = truncated.rfind(' ')
                        if last_space > max_length * 0.8:  # Only truncate at word if it's not too short
                            validated_content = truncated[:last_space] + "..."
                        else:
                            validated_content = truncated + "..."
                    
                    content_pieces[area_label] = validated_content
            
            state["content_pieces"] = content_pieces
            state["current_node"] = "content_modifier"
            print("✅ Content modification completed")
            
            # Log data being sent to next node
            print("📤 SENDING TO IMAGE MODIFIER (NORMAL PATH):")
            print(f"   - content_pieces: {'Present' if state.get('content_pieces') else 'None'}")
            print(f"   - has_custom_prompt: {state.get('has_custom_prompt', False)}")
            print(f"   - template_analysis: {'Present' if state.get('template_analysis') else 'None'}")
            print(f"   - user_logo: {'Present' if state.get('user_logo') else 'None'}")
            if state.get('content_pieces'):
                print(f"   - content_pieces keys: {list(state.get('content_pieces', {}).keys())}")
                print(f"   - title: {state.get('content_pieces', {}).get('title', 'None')}")
                print(f"   - subtitle: {state.get('content_pieces', {}).get('subtitle', 'None')[:50]}..." if state.get('content_pieces', {}).get('subtitle') else "   - subtitle: None")
            
        except Exception as e:
            state["error_message"] = f"Content modification failed: {str(e)}"
            print(f"❌ Content modification error: {e}")
        
        return state
    
    async def image_modifier(self, state: TemplateEditorState) -> TemplateEditorState:
        """Node 4: Image modifier - adapts current image for template"""
        try:
            print("🖼️ Image Modifier: Adapting image for template...")
            
            if not state.get("current_image_url"):
                print("⚠️ No current image provided, skipping image modification")
                state["image_modifications"] = {"skip": True}
                return state
            
            # Download current image
            response = requests.get(state["current_image_url"])
            current_image = Image.open(BytesIO(response.content))
            
            # Analyze current image using OpenAI vision
            image_analysis_prompt = """
            Analyze this image and suggest modifications needed to fit into a social media template.
            Consider:
            - Aspect ratio adjustments
            - Color scheme modifications
            - Cropping suggestions
            - Filter or style adjustments
            - Text overlay areas to avoid
            
            Return a JSON structure with modification suggestions.
            """
            
            # Convert image to base64 for analysis
            buffered = BytesIO()
            current_image.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            client = openai.OpenAI()
            analysis_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": image_analysis_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            # Track token usage
            user_id = state.get('user_id')
            if user_id and self.token_tracker:
                await self.token_tracker.track_chat_completion_usage(
                    user_id=user_id,
                    feature_type="template_editing",
                    model_name="gpt-4o-mini",
                    response=analysis_response,
                    request_metadata={"action": "analyze_image"}
                )
            
            try:
                modifications = json.loads(analysis_response.choices[0].message.content)
            except json.JSONDecodeError:
                modifications = {
                    "aspect_ratio": "16:9",
                    "crop_suggestion": "center",
                    "color_adjustments": "enhance_contrast",
                    "text_avoid_areas": []
                }
            
            state["image_modifications"] = modifications
            state["current_node"] = "image_modifier"
            print("✅ Image modification analysis completed")
            
            # Log data being sent to next node
            print("📤 SENDING TO CONTENT OUTPUT GENERATOR:")
            print(f"   - image_modifications: {'Present' if state.get('image_modifications') else 'None'}")
            print(f"   - content_pieces: {'Present' if state.get('content_pieces') else 'None'}")
            print(f"   - template_analysis: {'Present' if state.get('template_analysis') else 'None'}")
            print(f"   - template_image: {'Present' if state.get('template_image') else 'None'}")
            print(f"   - user_logo: {'Present' if state.get('user_logo') else 'None'}")
            print(f"   - current_image_url: {state.get('current_image_url', 'None')}")
            
        except Exception as e:
            state["error_message"] = f"Image modification failed: {str(e)}"
            print(f"❌ Image modification error: {e}")
        
        return state
    
    async def content_output_generator(self, state: TemplateEditorState) -> TemplateEditorState:
        """Node 5: Content output image generator - creates final template using Gemini API"""
        try:
            print("🎨 Content Output Generator: Creating final template with Gemini...")
            
            # Debug: Check what data we have
            print(f"🔍 Debug - template_image: {bool(state.get('template_image'))}")
            print(f"🔍 Debug - content_pieces: {bool(state.get('content_pieces'))}")
            print(f"🔍 Debug - template_analysis: {bool(state.get('template_analysis'))}")
            if state.get('content_pieces'):
                print(f"🔍 Debug - content_pieces keys: {list(state.get('content_pieces', {}).keys())}")
            if state.get('template_analysis'):
                print(f"🔍 Debug - template_analysis keys: {list(state.get('template_analysis', {}).keys())}")
            
            if not all([state.get("template_image"), state.get("content_pieces"), state.get("template_analysis")]):
                missing = []
                if not state.get("template_image"):
                    missing.append("template_image")
                if not state.get("content_pieces"):
                    missing.append("content_pieces")
                if not state.get("template_analysis"):
                    missing.append("template_analysis")
                raise ValueError(f"Missing required data for template generation: {missing}")
            
            # Import Gemini
            import google.generativeai as genai
            
            # Configure Gemini API
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            if not gemini_api_key:
                print("❌ GEMINI_API_KEY not found in environment variables")
                raise ValueError("GEMINI_API_KEY not found in environment variables")
            
            print(f"🔑 Gemini API key found: {gemini_api_key[:10]}...")
            genai.configure(api_key=gemini_api_key)
            gemini_model = 'gemini-2.5-flash-image-preview'
            print(f"🤖 Using Gemini model: {gemini_model}")
            
            # Prepare the prompt for Gemini
            content_pieces = state["content_pieces"]
            template_analysis = state["template_analysis"]
            current_content = state["current_content"]
            
            # Create a comprehensive prompt for Gemini with template context
            design_info = template_analysis.get("design_info", {})
            content_strategy = template_analysis.get("content_strategy", {})
            
            # Build content text for overlay (exclude metadata and hashtags)
            content_text = ""
            metadata_fields = ['hashtags', 'hashtag', 'generated_by', 'template_name', 'prompt_version', 'main_text']
            for label, text in content_pieces.items():
                # Skip metadata fields and hashtags as they're not embedded in images
                if label.lower() not in metadata_fields:
                    content_text += f"{label.upper()}: {text}\n"
            
            # Check if user logo is available
            user_logo = state.get("user_logo")
            logo_info = ""
            if user_logo:
                logo_areas = user_logo.get("areas", [])
                business_name = user_logo.get("business_name", "Company")
                logo_info = f"\nLOGO REQUIREMENTS:\n- Company: {business_name}\n- Logo areas: {len(logo_areas)} detected\n- Logo URL: {user_logo.get('url', 'N/A')}\n"
            
            gemini_prompt = f"""
You are a professional graphic designer. Create a customized social media post IMAGE by modifying the provided template image.

TEMPLATE DESIGN ANALYSIS:
- Template Purpose: {design_info.get('template_purpose', 'social media post')}
- Design Style: {design_info.get('overall_style', 'modern')}
- Layout Type: {design_info.get('layout_type', 'centered')}
- Primary Colors: {design_info.get('primary_colors', ['#000000'])}
- Secondary Colors: {design_info.get('secondary_colors', ['#FFFFFF'])}
- Typography: {design_info.get('font_families', ['Arial'])}
- Target Audience: {design_info.get('target_audience', 'general')}
- Tone: {design_info.get('tone', 'professional')}

CONTENT STRATEGY:
- Main Goal: {content_strategy.get('main_goal', 'inform and engage')}
- Key Message: {content_strategy.get('key_message', 'highlight important information')}
- Call to Action: {content_strategy.get('call_to_action', 'encourage engagement')}

CUSTOMIZED CONTENT TO INTEGRATE:
{content_text}{logo_info}

DESIGN REQUIREMENTS:
1. Generate a NEW IMAGE that combines the template design with the customized content
2. Use the original image (first image) as your foundation
3. Apply the template's design aesthetic (second image) as your style guide
4. Integrate the customized content text in appropriate locations based on the template layout
5. Maintain visual hierarchy: {design_info.get('visual_hierarchy', ['title', 'subtitle', 'body', 'cta'])}
6. Use the template's color scheme and typography
7. Ensure all text is readable and properly positioned
8. Match the {design_info.get('tone', 'professional')} tone
9. Create a cohesive design that serves the {content_strategy.get('main_goal', 'inform and engage')} goal
10. OUTPUT: Return the final customized image, not text description

TEXT QUALITY REQUIREMENTS (CRITICAL):
- ZERO spelling mistakes or typos in any text
- Perfect grammar and punctuation
- Professional language appropriate for the {design_info.get('tone', 'professional')} tone
- Clear, concise, and impactful messaging
- Proper capitalization and formatting
- All text must be legible and well-positioned
- Double-check all words for accuracy before finalizing

TECHNICAL SPECIFICATIONS:
- Maintain high resolution and professional quality
- Ensure text contrast is sufficient for readability
- Preserve the original image's key visual elements
- Apply the template's layout structure
- Use appropriate font sizes and weights for each content area
- Verify all text is properly spelled and grammatically correct

QUALITY CONTROL CHECKLIST:
✓ All text is spelled correctly
✓ Grammar and punctuation are perfect
✓ Text is properly positioned and readable
✓ Font sizes are appropriate for each content area
✓ Color contrast ensures readability
✓ Overall design is professional and cohesive

OUTPUT: A single, professionally designed image that seamlessly combines the original image with the template's design aesthetic and the customized content, with perfect spelling and grammar throughout.
"""
            
            # Prepare contents for Gemini API call
            contents = []
            
            # Add the prompt
            contents.append(gemini_prompt)
            
            # Add the original image as the primary image to modify
            if state.get("current_image_url"):
                try:
                    # Download the original image
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.get(state["current_image_url"])
                        if response.status_code == 200:
                            original_image_data = base64.b64encode(response.content).decode()
                            contents.append({
                                "text": "BASE IMAGE: Transform this image to match the template style."
                            })
                            contents.append({
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": original_image_data
                                }
                            })
                except Exception as e:
                    print(f"⚠️ Could not include original image: {e}")
                    raise Exception("Original image is required for template modification")
            else:
                raise Exception("No original image provided for modification")
            
            # Add the template image as reference
            template_data = state["template_image"]
            if template_data.startswith('data:image'):
                template_data = template_data.split(',')[1]
            
            contents.append({
                "text": "STYLE REFERENCE: Apply this template's design aesthetic to the base image."
            })
            contents.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": template_data
                }
            })
            
            # Add user logo if available
            if user_logo and user_logo.get("url"):
                try:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        logo_response = await client.get(user_logo["url"])
                        if logo_response.status_code == 200:
                            logo_image_data = base64.b64encode(logo_response.content).decode()
                            contents.append({
                                "text": f"USER LOGO: Integrate this {user_logo.get('business_name', 'company')} logo into the design at the appropriate logo areas."
                            })
                            contents.append({
                                "inline_data": {
                                    "mime_type": "image/png",  # Assume PNG, could be enhanced to detect actual type
                                    "data": logo_image_data
                                }
                            })
                            print(f"✅ Added user logo to Gemini input: {user_logo.get('business_name', 'Company')}")
                        else:
                            print(f"⚠️ Could not download user logo: HTTP {logo_response.status_code}")
                except Exception as e:
                    print(f"⚠️ Error downloading user logo: {e}")
            else:
                print("ℹ️ No user logo available for integration")
            
            # Call Gemini API
            print("🤖 Calling Gemini API for image generation...")
            try:
                model = genai.GenerativeModel(gemini_model)
                response = model.generate_content(contents)
                
                print(f"🔍 Gemini response received successfully")
                print(f"🔍 Response candidates: {len(response.candidates) if response.candidates else 0}")
                
                # Extract the generated image from the response
                image_data = None
                if response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    print(f"🔍 Candidate content parts: {len(candidate.content.parts) if candidate.content.parts else 0}")
                    
                    for i, part in enumerate(candidate.content.parts):
                        if part.inline_data is not None:
                            image_data = part.inline_data.data
                            print(f"✅ Found image data: {len(image_data) if image_data else 0} bytes")
                            break
                    
                    if not image_data:
                        print("❌ No image data found in response parts")
                        # Try to get text response for debugging
                        text_content = ""
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                text_content += part.text
                        print(f"🔍 Text response: {text_content[:200]}...")
                        raise Exception("No image data returned from Gemini")
                else:
                    print("❌ No candidates in response")
                    raise Exception("No candidates returned from Gemini")
                    
            except Exception as gemini_error:
                print(f"❌ Gemini API error: {gemini_error}")
                print(f"❌ Error type: {type(gemini_error)}")
                raise Exception(f"Gemini API failed: {str(gemini_error)}")
            
            # Convert to base64
            if isinstance(image_data, bytes):
                image_bytes = image_data
            else:
                image_bytes = base64.b64decode(image_data)
            
            final_template_b64 = base64.b64encode(image_bytes).decode()
            final_template_url = f"data:image/png;base64,{final_template_b64}"
            
            # Update state
            state["final_template"] = final_template_url
            state["current_node"] = "content_output_generator"
            
            print("✅ Final template generated successfully with Gemini")
            
            # Log data being sent to next node
            print("📤 SENDING TO FLOW ROUTER:")
            print(f"   - final_template: {'Present' if state.get('final_template') else 'None'}")
            print(f"   - content_pieces: {'Present' if state.get('content_pieces') else 'None'}")
            print(f"   - template_analysis: {'Present' if state.get('template_analysis') else 'None'}")
            print(f"   - user_logo: {'Present' if state.get('user_logo') else 'None'}")
            print(f"   - has_custom_prompt: {state.get('has_custom_prompt', False)}")
            if state.get('content_pieces'):
                print(f"   - content_pieces keys: {list(state.get('content_pieces', {}).keys())}")
                print(f"   - title: {state.get('content_pieces', {}).get('title', 'None')}")
                print(f"   - subtitle: {state.get('content_pieces', {}).get('subtitle', 'None')[:50]}..." if state.get('content_pieces', {}).get('subtitle') else "   - subtitle: None")
            
        except Exception as e:
            state["error_message"] = f"Content output generation failed: {str(e)}"
            print(f"❌ Content output generation error: {e}")
        
        return state
    
    async def flow_router(self, state: TemplateEditorState) -> TemplateEditorState:
        """Node 6: Flow router - determines next step based on user input"""
        try:
            print("🔄 Flow Router: Determining next step...")
            
            # This would typically get user input from the frontend
            # For now, we'll simulate the decision
            user_decision = state.get("user_satisfied", False)
            custom_instructions = state.get("custom_instructions")
            needs_restart = state.get("needs_restart", False)
            
            if needs_restart:
                state["current_node"] = "restart"
            elif user_decision and not custom_instructions:
                state["current_node"] = "save"
            elif custom_instructions:
                state["current_node"] = "custom_edit"
            else:
                # Default to waiting for user input
                state["current_node"] = "waiting"
            
            print(f"✅ Flow routed to: {state['current_node']}")
            
            # Log final state summary
            print("📊 FINAL STATE SUMMARY:")
            print(f"   - current_node: {state.get('current_node', 'None')}")
            print(f"   - has_custom_prompt: {state.get('has_custom_prompt', False)}")
            print(f"   - content_pieces: {'Present' if state.get('content_pieces') else 'None'}")
            print(f"   - final_template: {'Present' if state.get('final_template') else 'None'}")
            print(f"   - template_analysis: {'Present' if state.get('template_analysis') else 'None'}")
            print(f"   - user_logo: {'Present' if state.get('user_logo') else 'None'}")
            print(f"   - error_message: {state.get('error_message', 'None')}")
            if state.get('content_pieces'):
                print(f"   - Generated title: {state.get('content_pieces', {}).get('title', 'None')}")
                print(f"   - Generated subtitle: {state.get('content_pieces', {}).get('subtitle', 'None')[:50]}..." if state.get('content_pieces', {}).get('subtitle') else "   - Generated subtitle: None")
            
        except Exception as e:
            state["error_message"] = f"Flow routing failed: {str(e)}"
            print(f"❌ Flow routing error: {e}")
        
        return state
    
    async def custom_edit_node(self, state: TemplateEditorState) -> TemplateEditorState:
        """Node 7: Custom edit node - handles user custom instructions"""
        try:
            print("✏️ Custom Edit Node: Processing custom instructions...")
            
            custom_instructions = state.get("custom_instructions", "")
            if not custom_instructions:
                state["error_message"] = "No custom instructions provided"
                return state
            
            # Process custom instructions using OpenAI
            edit_prompt = f"""
            Based on the current template and these custom instructions: "{custom_instructions}"
            
            Suggest specific modifications to the template. Consider:
            - Text changes
            - Color adjustments
            - Layout modifications
            - Image positioning
            - Style changes
            
            Return a JSON structure with specific edit instructions.
            """
            
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": edit_prompt}
                ],
                max_tokens=1000
            )
            
            # Track token usage
            user_id = state.get('user_id')
            if user_id and self.token_tracker:
                await self.token_tracker.track_chat_completion_usage(
                    user_id=user_id,
                    feature_type="template_editing",
                    model_name="gpt-4o-mini",
                    response=response,
                    request_metadata={"action": "custom_edit"}
                )
            
            try:
                edit_instructions = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError:
                edit_instructions = {"text_changes": [], "style_changes": []}
            
            # Apply the custom edits to the template
            # This would involve modifying the final_template based on edit_instructions
            # For now, we'll mark it as processed
            state["custom_instructions"] = None  # Clear after processing
            state["current_node"] = "custom_edit"
            print("✅ Custom edits processed")
            
        except Exception as e:
            state["error_message"] = f"Custom edit failed: {str(e)}"
            print(f"❌ Custom edit error: {e}")
        
        return state
    
    async def save_image(self, state: TemplateEditorState) -> TemplateEditorState:
        """Node 8: Save image - saves final template to Supabase"""
        try:
            print("💾 Save Image: Saving final template...")
            
            if not state.get("final_template"):
                raise ValueError("No final template to save")
            
            # Upload image to Supabase storage
            image_data = state["final_template"]
            if image_data.startswith('data:image'):
                image_data = image_data.split(',')[1]
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"template_editor_{state['user_id']}_{timestamp}.jpg"
            
            if supabase:
                # Upload to Supabase storage in ai-generated-images bucket
                file_path = f"template-edits/{filename}"
                upload_response = supabase.storage.from_("ai-generated-images").upload(
                    file_path,
                    base64.b64decode(image_data),
                    file_options={"content-type": "image/jpeg"}
                )
                
                if hasattr(upload_response, 'error') and upload_response.error:
                    raise Exception(f"Upload failed: {upload_response.error}")
                
                # Get public URL
                public_url = supabase.storage.from_("ai-generated-images").get_public_url(file_path)
                
                # Update content in database with new image URL
                if state.get("content_id"):
                    update_response = supabase.table("content").update({
                        "image_url": public_url,
                        "updated_at": datetime.now().isoformat()
                    }).eq("id", state["content_id"]).execute()
                    
                    if update_response.data:
                        print("✅ Content updated with new image URL")
            else:
                # Fallback: return the base64 data directly
                public_url = f"data:image/jpeg;base64,{image_data}"
                print("⚠️ Supabase not available, returning base64 data")
            
            state["current_node"] = "save"
            print("✅ Final template saved successfully")
            
        except Exception as e:
            state["error_message"] = f"Save failed: {str(e)}"
            print(f"❌ Save error: {e}")
        
        return state
    
    def _route_decision(self, state: TemplateEditorState) -> str:
        """Determine routing from flow_router"""
        if state.get("error_message"):
            return "error"
        elif state.get("needs_restart"):
            return "restart"
        elif state.get("user_satisfied") and not state.get("custom_instructions"):
            return "save"
        elif state.get("custom_instructions"):
            return "custom_edit"
        else:
            return "error"  # Default to error if unclear
    
    def _custom_edit_decision(self, state: TemplateEditorState) -> str:
        """Determine routing from custom_edit_node"""
        if state.get("error_message"):
            return "error"
        elif state.get("needs_restart"):
            return "restart"
        elif state.get("user_satisfied"):
            return "save"
        elif state.get("custom_instructions"):
            return "continue_edit"
        else:
            return "save"  # Default to save if no more instructions
    
    
    async def process_template_edit(self, 
                                  current_content: str,
                                  current_image_url: str,
                                  user_id: str,
                                  content_id: str,
                                  template_id: Optional[str] = None,
                                  template_image: Optional[str] = None) -> Dict[str, Any]:
        """Main entry point for template editing process"""
        try:
            # Initialize state
            initial_state = TemplateEditorState(
                current_content=current_content,
                current_image_url=current_image_url,
                user_id=user_id,
                content_id=content_id,
                template_id=template_id,
                template_image=template_image,
                template_type="premade" if template_id else "user_upload",
                template_analysis=None,
                content_pieces=None,
                image_modifications=None,
                modified_content=None,
                modified_image=None,
                final_template=None,
                user_satisfied=False,
                custom_instructions=None,
                needs_restart=False,
                current_node="template_uploader",
                error_message=None
            )
            
            # Run the workflow
            print("🚀 Starting LangGraph workflow...")
            print(f"🔍 Initial state keys: {list(initial_state.keys())}")
            print(f"🔍 Template image present: {bool(initial_state.get('template_image'))}")
            
            # Debug: Check if the graph is properly compiled
            print(f"🔍 Graph nodes: {list(self.graph.nodes.keys())}")
            
            print("🔍 About to invoke workflow...")
            result = await self.graph.ainvoke(initial_state)
            print("🔍 Workflow invocation completed")
            
            print(f"🔍 Final result keys: {list(result.keys())}")
            print(f"🔍 Final template present: {bool(result.get('final_template'))}")
            print(f"🔍 Error message: {result.get('error_message')}")
            print(f"🔍 Current node: {result.get('current_node')}")
            
            return {
                "success": not bool(result.get("error_message")),
                "final_template": result.get("final_template"),
                "error_message": result.get("error_message"),
                "current_node": result.get("current_node")
            }
            
        except Exception as e:
            return {
                "success": False,
                "error_message": f"Template editing process failed: {str(e)}",
                "final_template": None,
                "current_node": "error"
            }

# Create global instance
template_editor_agent = TemplateEditorAgent()
