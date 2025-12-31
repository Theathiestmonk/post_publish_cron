"""
Simplified Template Processor Service
Handles HTML template processing, content generation, and PNG conversion
"""

import os
import base64
import asyncio
import json
from typing import Dict, Any, Optional
from pathlib import Path
from bs4 import BeautifulSoup
import httpx
import openai
from supabase import create_client, Client
from datetime import datetime

# Import playwright with error handling
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Warning: Playwright not installed. PNG conversion will not work.")
    print("   Install with: pip install playwright && playwright install chromium")


class TemplateProcessor:
    """Processes HTML templates with user content and converts to PNG"""
    
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Initialize Supabase client
        if self.supabase_url and self.supabase_key:
            self.supabase: Optional[Client] = create_client(
                self.supabase_url,
                self.supabase_key
            )
        else:
            self.supabase = None
        
        # Initialize OpenAI client
        if self.openai_api_key:
            self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None
        
        # Load template prompts JSON
        self.template_prompts = self._load_template_prompts()
    
    def _load_template_prompts(self) -> Dict[str, Any]:
        """Load template prompts from JSON file"""
        try:
            # Get the templates directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(current_dir)
            prompts_path = os.path.join(backend_dir, 'templates', 'template_prompts.json')
            
            if os.path.exists(prompts_path):
                with open(prompts_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"⚠️ Template prompts file not found at {prompts_path}")
                return {"templates": {}, "default_prompt": ""}
        except Exception as e:
            print(f"⚠️ Error loading template prompts: {e}")
            return {"templates": {}, "default_prompt": ""}
    
    def _get_template_prompt(self, template_html_path: str) -> str:
        """Get the prompt for a specific template"""
        try:
            # Get relative path from templates directory
            templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
            relative_path = os.path.relpath(template_html_path, templates_dir)
            
            # Normalize path separators
            relative_path = relative_path.replace('\\', '/')
            
            # Try to find exact match
            if relative_path in self.template_prompts.get("templates", {}):
                prompt = self.template_prompts["templates"][relative_path].get("prompt", "")
                print(f"✅ Found specific prompt for template: {relative_path}")
                return prompt
            
            # Try with just filename
            filename = os.path.basename(template_html_path)
            for template_key, template_data in self.template_prompts.get("templates", {}).items():
                if template_data.get("filename") == filename:
                    prompt = template_data.get("prompt", "")
                    print(f"✅ Found prompt by filename: {filename}")
                    return prompt
            
            # Use default prompt
            default_prompt = self.template_prompts.get("default_prompt", "")
            print(f"⚠️ Using default prompt for template: {relative_path}")
            return default_prompt
            
        except Exception as e:
            print(f"⚠️ Error getting template prompt: {e}")
            return self.template_prompts.get("default_prompt", "")
    
    async def process_template(
        self,
        template_html_path: str,
        user_image_url: str,
        user_caption: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Main method to process template and return PNG URL
        
        Args:
            template_html_path: Path to HTML template file
            user_image_url: URL of user's image
            user_caption: User-provided caption/text
            user_id: User ID for logo fetching
            
        Returns:
            Dict with success status and PNG URL or error message
        """
        try:
            # Step 1: Load HTML template
            print("📄 Loading HTML template...")
            with open(template_html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Step 2: Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Step 3: Extract title-box text
            title_box = soup.find(class_='title-box')
            title_text = title_box.get_text(strip=True) if title_box else "Template"
            print(f"📝 Template title: {title_text}")
            
            # Step 4: Get user logo
            print("🖼️ Fetching user logo...")
            logo_url = await self._get_user_logo(user_id)
            
            # Step 5: Get user business information
            print("🏢 Fetching user business information...")
            business_info = await self._get_user_business_info(user_id)
            
            # Step 6: Get template-specific prompt from JSON
            print("📋 Loading template prompt...")
            template_prompt = self._get_template_prompt(template_html_path)
            
            # Step 7: Generate content with OpenAI (prompt + business info only, NO IMAGE, NO HTML, NO CAPTION)
            print("🤖 Generating content with OpenAI (prompt + business info only)...")
            generated_content = await self._generate_content_with_openai(
                template_prompt=template_prompt,
                business_info=business_info
            )
            
            # Step 9: Replace content, logo, and image in HTML template
            print("✏️ Replacing content, logo, and image in HTML...")
            modified_html = self._replace_content_logo_and_image(
                soup=soup,
                user_image_url=user_image_url,
                logo_url=logo_url,
                generated_content=generated_content
            )
            
            # Step 10: Convert HTML to PNG
            print("🖼️ Converting HTML to PNG...")
            png_data = await self._html_to_png(modified_html)
            
            # Step 11: Upload PNG to Supabase storage
            print("☁️ Uploading PNG to Supabase...")
            png_url = await self._upload_png_to_storage(png_data, user_id)
            
            return {
                "success": True,
                "png_url": png_url,
                "message": "Template processed successfully"
            }
            
        except Exception as e:
            print(f"❌ Error processing template: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error_message": f"Template processing failed: {str(e)}",
                "png_url": None
            }
    
    async def _get_user_logo(self, user_id: str) -> Optional[str]:
        """Fetch user logo URL from Supabase profiles table"""
        try:
            if not self.supabase:
                print("⚠️ Supabase client not initialized")
                return None
            
            response = self.supabase.table("profiles").select("logo_url").eq("id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                logo_url = response.data[0].get("logo_url")
                if logo_url:
                    print(f"✅ Found user logo: {logo_url}")
                    return logo_url
                else:
                    print("⚠️ User has no logo_url")
                    return None
            else:
                print("⚠️ User profile not found")
                return None
                
        except Exception as e:
            print(f"⚠️ Error fetching user logo: {e}")
            return None
    
    async def _get_user_business_info(self, user_id: str) -> Dict[str, Any]:
        """Fetch user business information from Supabase profiles table"""
        try:
            if not self.supabase:
                print("⚠️ Supabase client not initialized")
                return {}
            
            response = self.supabase.table("profiles").select(
                "business_name, industry, business_description, target_audience, brand_voice, brand_tone, products_or_services"
            ).eq("id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                profile = response.data[0]
                business_info = {
                    "business_name": profile.get("business_name", ""),
                    "industry": profile.get("industry", ""),
                    "business_description": profile.get("business_description", ""),
                    "target_audience": profile.get("target_audience", ""),
                    "brand_voice": profile.get("brand_voice", ""),
                    "brand_tone": profile.get("brand_tone", ""),
                    "products_or_services": profile.get("products_or_services", "")
                }
                print(f"✅ Found user business info: {business_info.get('business_name', 'N/A')}")
                return business_info
            else:
                print("⚠️ User profile not found")
                return {}
                
        except Exception as e:
            print(f"⚠️ Error fetching user business info: {e}")
            return {}
    
    async def _download_image_to_base64(self, image_url: str) -> str:
        """Download image from URL and convert to base64 for OpenAI Vision API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                response.raise_for_status()
                image_data = response.content
                
                # Convert to base64
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                
                # Determine image format
                content_type = response.headers.get('content-type', 'image/jpeg')
                if 'png' in content_type.lower():
                    mime_type = 'image/png'
                elif 'jpeg' in content_type.lower() or 'jpg' in content_type.lower():
                    mime_type = 'image/jpeg'
                elif 'webp' in content_type.lower():
                    mime_type = 'image/webp'
                else:
                    mime_type = 'image/jpeg'
                
                return f"data:{mime_type};base64,{image_base64}"
                
        except Exception as e:
            print(f"❌ Error downloading image: {e}")
            raise
    
    async def _generate_content_with_openai(
        self,
        template_prompt: str,
        business_info: Dict[str, Any]
    ) -> str:
        """
        Send prompt + business info to OpenAI for content generation (NO IMAGE, NO HTML, NO CAPTION)
        Returns only the text content (not HTML)
        """
        try:
            if not self.openai_client:
                raise Exception("OpenAI client not initialized")
            
            # Format business info for the prompt
            business_context = ""
            if business_info:
                business_context = f"""
Business Information:
- Business Name: {business_info.get('business_name', 'Not specified')}
- Industry: {business_info.get('industry', 'Not specified')}
- Business Description: {business_info.get('business_description', 'Not specified')}
- Target Audience: {business_info.get('target_audience', 'Not specified')}
- Brand Voice: {business_info.get('brand_voice', 'Not specified')}
- Brand Tone: {business_info.get('brand_tone', 'Not specified')}
- Products/Services: {business_info.get('products_or_services', 'Not specified')}
"""
            
            # Create the full prompt (ONLY template prompt + business info, NO CAPTION)
            full_prompt = f"""{template_prompt}
{business_context}

Generate the content based on the prompt above. Use the business information provided to create content that aligns with the business context.

IMPORTANT:
- Return ONLY the text content (1-2 sentences as specified in prompt)
- Do NOT return HTML code
- Do NOT include explanations or markdown
- You can use <br> tags for line breaks if needed
- Keep it engaging and appropriate for social media"""

            # Call OpenAI API with prompt only (NO IMAGE, NO HTML, NO CAPTION)
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": full_prompt
                            }
                        ]
                    }
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            generated_content = response.choices[0].message.content.strip()
            
            # Clean up if OpenAI wrapped it in markdown
            if generated_content.startswith("```"):
                lines = generated_content.split('\n')
                generated_content = '\n'.join(lines[1:-1]) if len(lines) > 2 else generated_content
            generated_content = generated_content.strip()
            
            print(f"✅ Generated content from OpenAI ({len(generated_content)} chars): {generated_content[:100]}...")
            return generated_content
            
        except Exception as e:
            print(f"❌ Error generating content with OpenAI: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: return a default message instead of user caption
            print("⚠️ Falling back to default content")
            return "Content generation failed. Please try again."
    
    def _replace_content_logo_and_image(
        self,
        soup: BeautifulSoup,
        user_image_url: str,
        logo_url: Optional[str],
        generated_content: str
    ) -> str:
        """Replace content, logo, and image in HTML template"""
        try:
            # Step 1: Replace the main image src (the <img> tag, NOT the logo tag)
            image_box = soup.find(class_='image-box')
            if image_box:
                main_img = image_box.find('img')
                if main_img:
                    main_img['src'] = user_image_url
                    main_img['alt'] = 'User image'
                    print(f"✅ Replaced main image src (img tag): {user_image_url[:50]}...")
                else:
                    print("⚠️ No main image tag found in image-box")
            
            # Step 2: Replace logo tag (custom <logo> tag) with user's logo
            logo_tag = soup.find('logo')
            if logo_tag and logo_url:
                new_logo = soup.new_tag('img')
                new_logo['src'] = logo_url
                new_logo['alt'] = 'Logo'
                new_logo['class'] = logo_tag.get('class', [])
                new_logo['aria-label'] = logo_tag.get('aria-label', 'Logo')
                new_logo['style'] = 'width: 55px; height: 55px; object-fit: contain;'
                logo_tag.replace_with(new_logo)
                print("✅ Replaced logo tag with user logo")
            elif logo_tag:
                print("⚠️ No logo URL, keeping original logo tag")
            
            # Step 3: Replace desc-text content with OpenAI generated content
            desc_text = soup.find(class_='desc-text')
            if desc_text:
                desc_text.clear()
                # Parse the generated content (may contain <br> tags)
                parsed_content = BeautifulSoup(generated_content, 'html.parser')
                desc_text.append(parsed_content)
                print(f"✅ Replaced desc-text with generated content")
            
            # Return modified HTML as string
            return str(soup)
            
        except Exception as e:
            print(f"❌ Error replacing HTML elements: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def _html_to_png(self, html_content: str) -> bytes:
        """Convert HTML content to PNG using Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            raise Exception(
                "Playwright is not installed. Please install it with: "
                "pip install playwright && playwright install chromium"
            )
        
        try:
            # Create temporary HTML file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(html_content)
                tmp_file_path = tmp_file.name
            
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    
                    # Set viewport size
                    await page.set_viewport_size({"width": 800, "height": 600})
                    
                    # Load HTML from file
                    html_url = Path(tmp_file_path).as_uri()
                    await page.goto(html_url, wait_until='networkidle')
                    
                    # Wait for images to load
                    await page.wait_for_timeout(2000)
                    
                    # Take screenshot
                    png_data = await page.screenshot(full_page=True, type='png')
                    
                    await browser.close()
                    
                    return png_data
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ Error converting HTML to PNG: {e}")
            raise
    
    async def _upload_png_to_storage(self, png_data: bytes, user_id: str) -> str:
        """Upload PNG to Supabase storage and return public URL"""
        try:
            if not self.supabase:
                raise Exception("Supabase client not initialized")
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"template_applied_{user_id}_{timestamp}.png"
            file_path = f"template-edits/{filename}"
            
            # Upload to Supabase storage
            upload_result = self.supabase.storage.from_('ai-generated-images').upload(
                file_path,
                png_data,
                file_options={"content-type": "image/png"}
            )
            
            if hasattr(upload_result, 'error') and upload_result.error:
                raise Exception(f"Failed to upload PNG: {upload_result.error}")
            
            # Get public URL
            public_url = self.supabase.storage.from_('ai-generated-images').get_public_url(file_path)
            print(f"✅ PNG uploaded: {public_url}")
            
            return public_url
            
        except Exception as e:
            print(f"❌ Error uploading PNG to storage: {e}")
            raise


# Global instance
template_processor = TemplateProcessor()

