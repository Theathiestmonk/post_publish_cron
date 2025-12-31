"""
Lead Management Agent using LangGraph
Handles lead capture, personalized communications, and AI-powered conversations
"""

import json
import asyncio
import logging
import base64
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

import openai
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from supabase import create_client, Client
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    RESPONDED = "responded"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    LOST = "lost"

class MessageType(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"

class LeadManagementState(BaseModel):
    user_id: str
    lead_data: Optional[Dict[str, Any]] = None
    lead_id: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    email_content: Optional[str] = None
    email_subject: Optional[str] = None
    email_sent: bool = False
    whatsapp_content: Optional[str] = None
    whatsapp_sent: bool = False
    conversation_history: List[Dict[str, Any]] = []
    error: Optional[str] = None
    progress: int = 0

class LeadManagementAgent:
    def __init__(self, supabase_url: str, supabase_key: str, openai_api_key: str):
        self.supabase = create_client(supabase_url, supabase_key)
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        # Initialize token tracker for usage tracking
        from services.token_usage_service import TokenUsageService
        self.token_tracker = TokenUsageService(supabase_url, supabase_key)
        self.graph = self._build_graph()
    
    def get_supabase_admin(self):
        """Get Supabase admin client for database operations"""
        import os
        return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for lead management"""
        workflow = StateGraph(LeadManagementState)
        
        # Add nodes
        workflow.add_node("capture_lead", self._capture_lead)
        workflow.add_node("get_user_profile", self._get_user_profile)
        workflow.add_node("store_lead", self._store_lead)
        workflow.add_node("generate_personalized_email", self._generate_personalized_email)
        workflow.add_node("send_email", self._send_email)
        workflow.add_node("generate_personalized_whatsapp", self._generate_personalized_whatsapp)
        workflow.add_node("send_whatsapp", self._send_whatsapp)
        workflow.add_node("initialize_conversation", self._initialize_conversation)
        workflow.add_node("error_handler", self._error_handler)
        
        # Add edges
        workflow.set_entry_point("capture_lead")
        workflow.add_edge("capture_lead", "get_user_profile")
        workflow.add_edge("get_user_profile", "store_lead")
        workflow.add_edge("store_lead", "generate_personalized_email")
        workflow.add_edge("generate_personalized_email", "send_email")
        workflow.add_edge("send_email", "generate_personalized_whatsapp")
        workflow.add_edge("generate_personalized_whatsapp", "send_whatsapp")
        workflow.add_edge("send_whatsapp", "initialize_conversation")
        workflow.add_edge("initialize_conversation", END)
        workflow.add_edge("error_handler", END)
        
        return workflow.compile()
    
    async def _capture_lead(self, state: LeadManagementState) -> LeadManagementState:
        """Process incoming lead from webhook"""
        try:
            logger.info(f"Capturing lead for user: {state.user_id}")
            
            if not state.lead_data:
                state.error = "No lead data provided"
                return state
            
            # Extract lead information
            lead_info = {
                "name": state.lead_data.get("name", ""),
                "email": state.lead_data.get("email", ""),
                "phone": state.lead_data.get("phone_number", ""),
                "ad_id": state.lead_data.get("ad_id", ""),
                "campaign_id": state.lead_data.get("campaign_id", ""),
                "form_id": state.lead_data.get("form_id", ""),
                "leadgen_id": state.lead_data.get("leadgen_id", ""),
                "source_platform": state.lead_data.get("source_platform", "facebook"),
                "form_data": state.lead_data.get("form_data", {})
            }
            
            state.lead_data = lead_info
            state.progress = 10
            
            logger.info(f"Captured lead: {lead_info.get('name')} ({lead_info.get('email')})")
            return state
            
        except Exception as e:
            logger.error(f"Error in capture_lead: {e}")
            state.error = str(e)
            return state
    
    async def _get_user_profile(self, state: LeadManagementState) -> LeadManagementState:
        """Get user profile for personalization"""
        try:
            logger.info(f"Getting user profile for: {state.user_id}")
            
            supabase_admin = self.get_supabase_admin()
            profile_response = supabase_admin.table("profiles").select("*").eq("id", state.user_id).execute()
            
            if not profile_response.data:
                logger.warning(f"User profile not found for {state.user_id}")
                state.profile = {}
            else:
                state.profile = profile_response.data[0]
            
            state.progress = 20
            return state
            
        except Exception as e:
            logger.error(f"Error in get_user_profile: {e}")
            state.error = str(e)
            return state
    
    async def _store_lead(self, state: LeadManagementState) -> LeadManagementState:
        """Store lead in database"""
        try:
            logger.info("Storing lead in database")
            
            supabase_admin = self.get_supabase_admin()
            
            # Check if lead already exists (by leadgen_id)
            if state.lead_data.get("leadgen_id"):
                existing = supabase_admin.table("leads").select("*").eq("leadgen_id", state.lead_data["leadgen_id"]).execute()
                if existing.data:
                    state.lead_id = existing.data[0]["id"]
                    logger.info(f"Lead already exists: {state.lead_id}")
                    state.progress = 30
                    return state
            
            # Create new lead
            lead_record = {
                "user_id": state.user_id,
                "name": state.lead_data.get("name"),
                "email": state.lead_data.get("email"),
                "phone_number": state.lead_data.get("phone"),
                "ad_id": state.lead_data.get("ad_id"),
                "campaign_id": state.lead_data.get("campaign_id"),
                "adgroup_id": state.lead_data.get("adgroup_id"),
                "form_id": state.lead_data.get("form_id"),
                "leadgen_id": state.lead_data.get("leadgen_id"),
                "source_platform": state.lead_data.get("source_platform", "facebook"),
                "status": "new",
                "form_data": state.lead_data.get("form_data", {}),
                "metadata": {
                    "captured_at": datetime.now().isoformat(),
                    "captured_by": "lead_management_agent"
                }
            }
            
            result = supabase_admin.table("leads").insert(lead_record).execute()
            if result.data:
                state.lead_id = result.data[0]["id"]
                logger.info(f"Stored lead: {state.lead_id}")
            else:
                state.error = "Failed to store lead"
                return state
            
            state.progress = 30
            return state
            
        except Exception as e:
            logger.error(f"Error in store_lead: {e}")
            state.error = str(e)
            return state
    
    async def _generate_personalized_email(self, state: LeadManagementState) -> LeadManagementState:
        """Generate personalized email using OpenAI"""
        try:
            logger.info("Generating personalized email")
            
            lead_name = state.lead_data.get("name", "there")
            lead_email = state.lead_data.get("email", "")
            business_name = state.profile.get("business_name", "our business")
            business_description = state.profile.get("business_description", "")
            brand_voice = state.profile.get("brand_voice", "professional")
            brand_tone = state.profile.get("brand_tone", "friendly")
            
            # Build context from form data
            form_context = ""
            if state.lead_data.get("form_data"):
                form_context = "\n".join([f"- {k}: {v}" for k, v in state.lead_data["form_data"].items()])
            
            prompt = f"""
You are an expert email marketer writing a personalized welcome email to a new lead.

Business Information:
- Business Name: {business_name}
- Business Description: {business_description}
- Brand Voice: {brand_voice}
- Brand Tone: {brand_tone}

Lead Information:
- Name: {lead_name}
- Email: {lead_email}
- Form Responses: {form_context}

Create a personalized, warm, and engaging welcome email that:
1. Thanks them for their interest
2. Introduces the business briefly
3. Highlights key value propositions
4. Includes a clear call-to-action
5. Matches the brand voice and tone
6. Is concise (under 200 words)

Return a JSON object with:
- "subject": Email subject line
- "body": Email body (HTML format preferred)
"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert email marketer. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            # Track token usage (non-blocking)
            user_id = state.profile.get("user_id") if state.profile else None
            if user_id and self.token_tracker:
                try:
                    import asyncio
                    asyncio.create_task(
                        self.token_tracker.track_chat_completion_usage(
                            user_id=user_id,
                            feature_type="lead_email",
                            model_name="gpt-4o-mini",
                            response=response,
                            request_metadata={"action": "generate_email", "lead_id": state.lead_id if hasattr(state, 'lead_id') else None}
                        )
                    )
                except Exception as e:
                    logger.error(f"Error tracking token usage: {str(e)}")
            
            try:
                email_data = json.loads(response.choices[0].message.content)
                state.email_subject = email_data.get("subject", f"Thank you for your interest in {business_name}")
                state.email_content = email_data.get("body", f"Thank you {lead_name} for your interest!")
                logger.info("Generated personalized email")
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                content = response.choices[0].message.content
                state.email_subject = f"Thank you for your interest in {business_name}"
                state.email_content = content
            
            state.progress = 50
            return state
            
        except Exception as e:
            logger.error(f"Error in generate_personalized_email: {e}")
            state.error = str(e)
            return state
    
    async def _send_email(self, state: LeadManagementState) -> LeadManagementState:
        """Send email via Gmail API"""
        try:
            logger.info("Sending email via Gmail")
            
            if not state.email_content or not state.lead_data.get("email"):
                logger.warning("Skipping email send - missing content or email")
                state.progress = 60
                return state
            
            # Get Google connection
            supabase_admin = self.get_supabase_admin()
            connection = supabase_admin.table('platform_connections').select('*').eq('platform', 'google').eq('is_active', True).eq('user_id', state.user_id).execute()
            
            if not connection.data:
                logger.warning("No Google connection found, skipping email")
                state.progress = 60
                return state
            
            conn = connection.data[0]
            
            # Import decryption functions
            import os
            from cryptography.fernet import Fernet
            
            def decrypt_token(encrypted_token: str) -> str:
                key = os.getenv('ENCRYPTION_KEY')
                if not key:
                    raise ValueError("ENCRYPTION_KEY not found")
                f = Fernet(key.encode())
                return f.decrypt(encrypted_token.encode()).decode()
            
            def get_google_credentials_from_token(access_token: str, refresh_token: str = None) -> Credentials:
                creds = Credentials(
                    token=access_token,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=os.getenv('GOOGLE_CLIENT_ID'),
                    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                    scopes=['https://www.googleapis.com/auth/gmail.send']
                )
                try:
                    if creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                except:
                    pass
                return creds
            
            # Decrypt tokens
            access_token = decrypt_token(conn['access_token_encrypted'])
            refresh_token = decrypt_token(conn['refresh_token_encrypted']) if conn.get('refresh_token_encrypted') else None
            
            # Create credentials
            credentials = get_google_credentials_from_token(access_token, refresh_token)
            
            # Build Gmail service
            service = build('gmail', 'v1', credentials=credentials)
            
            # Create message
            to_email = state.lead_data.get("email")
            message = {
                'raw': base64.urlsafe_b64encode(
                    f"To: {to_email}\r\nSubject: {state.email_subject}\r\nContent-Type: text/html; charset=utf-8\r\n\r\n{state.email_content}".encode()
                ).decode()
            }
            
            # Send message
            result = service.users().messages().send(userId='me', body=message).execute()
            
            # Store conversation
            if state.lead_id:
                supabase_admin.table("lead_conversations").insert({
                    "lead_id": state.lead_id,
                    "message_type": "email",
                    "content": state.email_content,
                    "sender": "agent",
                    "direction": "outbound",
                    "message_id": result.get('id'),
                    "status": "sent",
                    "metadata": {
                        "subject": state.email_subject,
                        "gmail_message_id": result.get('id')
                    }
                }).execute()
                
                # Update lead status from "new" to "contacted" if it's currently "new"
                lead = supabase_admin.table("leads").select("status").eq("id", state.lead_id).execute()
                if lead.data and lead.data[0].get("status") == "new":
                    from datetime import datetime
                    supabase_admin.table("leads").update({
                        "status": "contacted",
                        "updated_at": datetime.now().isoformat()
                    }).eq("id", state.lead_id).execute()
                    
                    # Create status history entry
                    supabase_admin.table("lead_status_history").insert({
                        "lead_id": state.lead_id,
                        "old_status": "new",
                        "new_status": "contacted",
                        "changed_by": "system",
                        "reason": "Automatic welcome email sent"
                    }).execute()
                    logger.info(f"Updated lead {state.lead_id} status from 'new' to 'contacted' after sending email")
                
                # Create chatbot message from Chase
                try:
                    # Get business name from profile
                    business_name = "your business"
                    if state.profile:
                        business_name = state.profile.get("business_name", "your business")
                    
                    # Get user's timezone from profile, default to UTC
                    user_timezone_str = "UTC"
                    if state.profile:
                        user_timezone_str = state.profile.get("timezone", "UTC")
                    
                    # Get lead name
                    lead_name = state.lead_data.get("name", "Unknown") if state.lead_data else "Unknown"
                    
                    # Format date and time in user's timezone
                    now_utc = datetime.now(timezone.utc)
                    
                    # Convert to user's timezone for display
                    try:
                        import pytz
                        user_tz = pytz.timezone(user_timezone_str)
                        now_user_tz = now_utc.astimezone(user_tz)
                        date_time_str = now_user_tz.strftime("%B %d, %Y at %I:%M %p")
                    except Exception:
                        # If timezone conversion fails, use UTC
                        date_time_str = now_utc.strftime("%B %d, %Y at %I:%M %p")
                    
                    # Create message content
                    message_content = f"Dear {business_name}, you just received a new lead: **{lead_name}** on {date_time_str}.\n\nI have contacted the lead and sent an Email for now."
                    
                    # Create chatbot conversation message
                    # Use UTC timezone to match database storage
                    chatbot_message_data = {
                        "user_id": state.user_id,
                        "message_type": "bot",
                        "content": message_content,
                        "intent": "lead_notification",
                        "created_at": now_utc.isoformat(),
                        "metadata": {
                            "sender": "chase",
                            "lead_id": state.lead_id,
                            "lead_name": lead_name,
                            "email_content": state.email_content,
                            "email_subject": state.email_subject,
                            "notification_type": "new_lead_email_sent"
                        }
                    }
                    
                    supabase_admin.table("chatbot_conversations").insert(chatbot_message_data).execute()
                    logger.info(f"Created Chase notification message for lead {state.lead_id}")
                except Exception as chatbot_msg_error:
                    logger.error(f"Error creating chatbot message: {chatbot_msg_error}")
                    # Don't fail email sending if chatbot message fails
            
            state.email_sent = True
            state.progress = 60
            logger.info(f"Email sent successfully: {result.get('id')}")
            return state
            
        except Exception as e:
            logger.error(f"Error in send_email: {e}")
            # Don't fail the entire process if email fails
            logger.warning("Email sending failed, continuing with WhatsApp")
            state.progress = 60
            return state
    
    async def _generate_personalized_whatsapp(self, state: LeadManagementState) -> LeadManagementState:
        """Generate personalized WhatsApp message using OpenAI"""
        try:
            logger.info("Generating personalized WhatsApp message")
            
            lead_name = state.lead_data.get("name", "there")
            business_name = state.profile.get("business_name", "our business")
            brand_voice = state.profile.get("brand_voice", "professional")
            brand_tone = state.profile.get("brand_tone", "friendly")
            
            prompt = f"""
You are an expert at writing WhatsApp messages for business communication.

Business Information:
- Business Name: {business_name}
- Brand Voice: {brand_voice}
- Brand Tone: {brand_tone}

Lead Information:
- Name: {lead_name}

Create a personalized, warm, and engaging WhatsApp message that:
1. Thanks them for their interest
2. Introduces the business briefly
3. Is conversational and friendly
4. Includes a clear call-to-action
5. Uses appropriate emojis (2-3 max)
6. Is concise (under 150 characters)
7. Matches WhatsApp communication style

Return just the message text, no JSON, no quotes.
"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at writing WhatsApp business messages. Return only the message text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            state.whatsapp_content = response.choices[0].message.content.strip().strip('"').strip("'")
            logger.info("Generated personalized WhatsApp message")
            
            state.progress = 70
            return state
            
        except Exception as e:
            logger.error(f"Error in generate_personalized_whatsapp: {e}")
            state.error = str(e)
            return state
    
    async def _send_whatsapp(self, state: LeadManagementState) -> LeadManagementState:
        """Send WhatsApp message via WhatsApp Business API"""
        try:
            logger.info("Sending WhatsApp message")
            
            if not state.whatsapp_content or not state.lead_data.get("phone"):
                logger.warning("Skipping WhatsApp send - missing content or phone")
                state.progress = 80
                return state
            
            # Import WhatsApp service
            from services.whatsapp_service import WhatsAppService
            
            whatsapp_service = WhatsAppService()
            
            # Send message
            phone_number = state.lead_data.get("phone")
            result = await whatsapp_service.send_message(
                user_id=state.user_id,
                phone_number=phone_number,
                message=state.whatsapp_content
            )
            
            # Store conversation
            if state.lead_id and result.get("success"):
                supabase_admin = self.get_supabase_admin()
                supabase_admin.table("lead_conversations").insert({
                    "lead_id": state.lead_id,
                    "message_type": "whatsapp",
                    "content": state.whatsapp_content,
                    "sender": "agent",
                    "direction": "outbound",
                    "message_id": result.get("message_id"),
                    "status": "sent",
                    "metadata": {
                        "whatsapp_message_id": result.get("message_id")
                    }
                }).execute()
            
            state.whatsapp_sent = result.get("success", False)
            state.progress = 80
            logger.info(f"WhatsApp message sent: {result.get('message_id')}")
            return state
            
        except Exception as e:
            logger.error(f"Error in send_whatsapp: {e}")
            # Don't fail the entire process if WhatsApp fails
            logger.warning("WhatsApp sending failed, continuing")
            state.progress = 80
            return state
    
    async def _initialize_conversation(self, state: LeadManagementState) -> LeadManagementState:
        """Initialize conversation tracking"""
        try:
            logger.info("Initializing conversation")
            
            # Update lead status to contacted
            if state.lead_id:
                supabase_admin = self.get_supabase_admin()
                supabase_admin.table("leads").update({
                    "status": "contacted",
                    "updated_at": datetime.now().isoformat()
                }).eq("id", state.lead_id).execute()
            
            state.progress = 100
            return state
            
        except Exception as e:
            logger.error(f"Error in initialize_conversation: {e}")
            state.error = str(e)
            return state
    
    async def _error_handler(self, state: LeadManagementState) -> LeadManagementState:
        """Handle errors in the workflow"""
        logger.error(f"Error in lead management workflow: {state.error}")
        return state
    
    async def process_lead(self, user_id: str, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a new lead through the workflow"""
        try:
            logger.info(f"Processing lead for user: {user_id}")
            
            # Initialize state
            state = LeadManagementState(
                user_id=user_id,
                lead_data=lead_data
            )
            
            # Run the workflow
            result = await self.graph.ainvoke(state)
            
            if hasattr(result, 'error') and result.error:
                return {
                    "success": False,
                    "error": result.error,
                    "lead_id": result.lead_id
                }
            
            return {
                "success": True,
                "lead_id": result.lead_id,
                "email_sent": result.email_sent,
                "whatsapp_sent": result.whatsapp_sent
            }
            
        except Exception as e:
            logger.error(f"Error in process_lead: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_ai_response(
        self,
        lead_id: str,
        incoming_message: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Generate AI response to incoming message from lead"""
        try:
            logger.info(f"Generating AI response for lead: {lead_id}")
            
            supabase_admin = self.get_supabase_admin()
            
            # Get lead data
            lead = supabase_admin.table("leads").select("*").eq("id", lead_id).execute()
            if not lead.data:
                raise ValueError("Lead not found")
            
            lead_data = lead.data[0]
            
            # Get conversation history
            conversations = supabase_admin.table("lead_conversations").select("*").eq("lead_id", lead_id).order("created_at").execute()
            conversation_history = conversations.data if conversations.data else []
            
            # Get user profile
            profile = supabase_admin.table("profiles").select("*").eq("id", user_id).execute()
            profile_data = profile.data[0] if profile.data else {}
            
            # Build conversation context
            history_text = ""
            for conv in conversation_history[-10:]:  # Last 10 messages
                sender = "Lead" if conv["sender"] == "lead" else "Agent"
                history_text += f"{sender}: {conv['content']}\n"
            
            # Generate response
            prompt = f"""
You are a helpful customer service agent for {profile_data.get('business_name', 'the business')}.

Business Context:
- Business: {profile_data.get('business_name', '')}
- Description: {profile_data.get('business_description', '')}
- Brand Voice: {profile_data.get('brand_voice', 'professional')}
- Brand Tone: {profile_data.get('brand_tone', 'friendly')}

Lead Information:
- Name: {lead_data.get('name', 'Customer')}
- Previous interactions: {history_text}

Incoming Message from Lead:
"{incoming_message}"

Generate a helpful, professional, and friendly response that:
1. Addresses the lead's question or concern
2. Maintains brand voice and tone
3. Is concise and clear
4. Uses appropriate emojis if needed (1-2 max)
5. Provides value and moves the conversation forward

Return just the response text, no JSON, no quotes.
"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful customer service agent. Return only the response text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            # Track token usage (non-blocking)
            user_id = state.profile.get("user_id") if state.profile else None
            if user_id and self.token_tracker:
                try:
                    import asyncio
                    asyncio.create_task(
                        self.token_tracker.track_chat_completion_usage(
                            user_id=user_id,
                            feature_type="lead_email",
                            model_name="gpt-4o-mini",
                            response=response,
                            request_metadata={"action": "generate_ai_response", "lead_id": state.lead_id if hasattr(state, 'lead_id') else None}
                        )
                    )
                except Exception as e:
                    logger.error(f"Error tracking token usage: {str(e)}")
            
            ai_response = response.choices[0].message.content.strip().strip('"').strip("'")
            
            return {
                "success": True,
                "response": ai_response
            }
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return {
                "success": False,
                "error": str(e)
            }



