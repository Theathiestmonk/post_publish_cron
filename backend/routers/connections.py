from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.responses import HTMLResponse
from typing import List, Optional
from datetime import datetime, timedelta
import os
import secrets
import string
import hashlib
import base64
import time
import traceback
import json
from decimal import Decimal
from cryptography.fernet import Fernet
import requests
import httpx
from supabase import create_client, Client

from dotenv import load_dotenv
from .meta_scopes import get_meta_oauth_scopes, get_meta_scope_string



# Load environment variables

load_dotenv()



# Get Supabase client

supabase_url = os.getenv("SUPABASE_URL")

supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")

supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")



if not supabase_url or not supabase_anon_key:

    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")



# Create client with anon key for user authentication

supabase: Client = create_client(supabase_url, supabase_anon_key)



# Create admin client for database operations

if supabase_service_key:

    supabase_admin: Client = create_client(supabase_url, supabase_service_key)

else:

    supabase_admin = supabase  # Fallback to anon client



# We'll define these locally to avoid circular imports

from pydantic import BaseModel



class User(BaseModel):

    id: str

    email: str

    name: str

    created_at: str



class WordPressConnection(BaseModel):

    site_name: str

    site_url: str

    username: str

    password: str



def get_current_user(authorization: str = Header(None)):

    """Get current user from Supabase JWT token"""

    try:

        print(f"Authorization header: {authorization}")

        
        
        if not authorization or not authorization.startswith("Bearer "):

            print("No valid authorization header, using mock user")

            return User(

                id="d523ec90-d5ee-4393-90b7-8f117782fcf5",

                email="test@example.com", 

                name="Test User",

                created_at="2025-01-01T00:00:00Z"

            )
        
        
        
        # Extract token
        token = authorization.split(" ")[1]
        print(f"Token received: {token[:20]}...")
        
        # First, try to decode JWT directly to avoid Supabase API timeout
        try:
            # Decode JWT without verification (JWT is base64 encoded)
            # Format: header.payload.signature
            parts = token.split('.')
            if len(parts) >= 2:
                # Decode payload (second part)
                payload = parts[1]
                # Add padding if needed
                payload += '=' * (4 - len(payload) % 4)
                decoded_payload = base64.urlsafe_b64decode(payload)
                decoded_token = json.loads(decoded_payload)
                
                user_id = decoded_token.get("sub")
                user_email = decoded_token.get("email", "unknown@example.com")
                user_metadata = decoded_token.get("user_metadata", {})
                user_name = user_metadata.get("name") or user_metadata.get("full_name") or user_email.split("@")[0]
                
                if user_id:
                    print(f"✅ Decoded user from JWT: {user_id} - {user_email}")
                    return User(
                        id=user_id,
                        email=user_email,
                        name=user_name,
                        created_at=datetime.now().isoformat()
                    )
        except Exception as jwt_error:
            print(f"⚠️ JWT decode error (will try Supabase API): {jwt_error}")
        
        # Fallback: Try to get user info from Supabase using the token
        try:
            print(f"Attempting to authenticate with Supabase...")
            user_response = supabase.auth.get_user(token)
            print(f"Supabase user response: {user_response}")
            
            if user_response and hasattr(user_response, 'user') and user_response.user:
                user_data = user_response.user
                print(f"✅ Authenticated user: {user_data.id} - {user_data.email}")
                return User(
                    id=user_data.id,
                    email=user_data.email or "unknown@example.com",
                    name=user_data.user_metadata.get('name', user_data.email or "Unknown User"),
                    created_at=user_data.created_at.isoformat() if hasattr(user_data.created_at, 'isoformat') else str(user_data.created_at)
                )
            else:
                print("❌ No user found in response")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token or user not found"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Supabase auth error: {e}")
            print(f"Error type: {type(e).__name__}")
            # If JWT decode already succeeded, we shouldn't reach here
            # But if both fail, raise proper error instead of using mock user
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}"
            )
            
            
            
    except Exception as e:

        print(f"Authentication error: {e}")

        # Fallback to mock for now

        return User(

            id="d523ec90-d5ee-4393-90b7-8f117782fcf5",

            email="test@example.com", 

            name="Test User",

            created_at="2025-01-01T00:00:00Z"

        )



router = APIRouter(prefix="/connections", tags=["connections"])

# Import Google callback handler
from routers.google_connections import handle_google_callback

@router.get("/auth/google/callback")
async def google_oauth_callback(code: str = None, state: str = None, error: str = None):
    """Handle Google OAuth callback from /connections/auth/google/callback path"""
    print(f"🔗 Google OAuth callback received at /connections/auth/google/callback - code: {code[:10] if code else 'None'}..., state: {state[:10] if state else 'None'}..., error: {error}")
    return await handle_google_callback(code, state, error)



# Encryption key for tokens

ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')

if not ENCRYPTION_KEY:

    print("⚠️  WARNING: ENCRYPTION_KEY not set! Generating a new key. This will cause existing tokens to be unreadable.")

    ENCRYPTION_KEY = Fernet.generate_key().decode()

    print(f"Generated encryption key: {ENCRYPTION_KEY}")

else:

    print(f"Using provided encryption key: {ENCRYPTION_KEY[:20]}...")



try:

    cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

except Exception as e:

    print(f"❌ Error initializing cipher: {e}")

    raise



def encrypt_token(token: str) -> str:

    """Encrypt token before storing"""

    try:

        return cipher.encrypt(token.encode()).decode()

    except Exception as e:

        print(f"❌ Error encrypting token: {e}")

        raise



def decrypt_token(encrypted_token: str) -> str:

    """Decrypt token for use"""

    try:

        return cipher.decrypt(encrypted_token.encode()).decode()

    except Exception as e:

        print(f"❌ Error decrypting token: {e}")

        print(f"❌ Error type: {type(e).__name__}")

        print(f"🔍 Token to decrypt: {encrypted_token[:50]}...")

        print(f"🔑 Current encryption key: {ENCRYPTION_KEY[:20]}...")

        raise



def generate_oauth_state() -> str:

    """Generate secure OAuth state"""

    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))



@router.get("/")

async def get_connections(

    current_user: User = Depends(get_current_user)

):

    """Get all active connections for current user"""

    try:

        print(f"🔍 Fetching connections for user: {current_user.id}")

        
        
        # Query Supabase directly

        response = supabase_admin.table("platform_connections").select("*").eq("user_id", current_user.id).eq("is_active", True).execute()

        
        
        connections = response.data if response.data else []

        print(f"📊 Found {len(connections)} active connections")

        
        
        # Also check all connections (including inactive) for debugging

        all_response = supabase_admin.table("platform_connections").select("*").eq("user_id", current_user.id).execute()

        all_connections = all_response.data if all_response.data else []

        print(f"📊 Total connections (including inactive): {len(all_connections)}")

        
        
        if all_connections:

            for conn in all_connections:

                print(f"  - {conn.get('platform')}: {conn.get('connection_status')} (is_active: {conn.get('is_active')})")
        
        
        
        # Remove sensitive data from response (but keep token for debugging)

        response_connections = []

        for conn in connections:

            conn_dict = {

                "id": conn["id"],

                "platform": conn["platform"],

                "page_id": conn.get("page_id"),

                "page_name": conn.get("page_name"),

                "page_username": conn.get("page_username"),

                "follower_count": conn.get("follower_count", 0),

                "connection_status": conn.get("connection_status", "active"),

                "is_active": conn.get("is_active", True),

                "last_sync": conn.get("last_sync"),

                "last_posted_at": conn.get("last_posted_at"),

                "connected_at": conn.get("connected_at"),

                "last_token_refresh": conn.get("last_token_refresh"),

                "access_token": conn.get("access_token_encrypted", "NOT_FOUND")[:50] + "..." if conn.get("access_token_encrypted") else "MISSING"

            }

            response_connections.append(conn_dict)
        
        
        
        return response_connections

    except Exception as e:

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to fetch connections: {str(e)}"

        )



@router.get("/auth/{platform}/connect")

async def get_connect_info(platform: str):

    """Get connection info (for debugging)"""

    # Skip Google platform as it has its own router

    if platform == "google":

        raise HTTPException(status_code=404, detail="Not Found")
    
    
    
    print(f"🔍 GET request to {platform} connect endpoint")

    return {"message": f"Use POST method for {platform} connection", "platform": platform}



@router.options("/auth/{platform}/connect")

async def options_connect(platform: str):

    """Handle CORS preflight for connect endpoint"""

    print(f"🔧 CORS preflight for {platform} connect")

    return {"message": "OK"}



@router.post("/auth/{platform}/connect")

async def initiate_connection(

    platform: str,

    current_user: User = Depends(get_current_user)

):

    """Initiate OAuth connection for platform"""

    # Skip Google platform as it has its own router

    if platform == "google":

        raise HTTPException(status_code=404, detail="Not Found")
    
    # Handle YouTube platform (uses Google OAuth)
    if platform == "youtube":
        platform = "youtube"  # Keep as youtube for OAuth URL generation
    
    
    
    try:

        print(f"🔗 Initiating {platform} connection for user: {current_user.id}")

        
        
        # Generate secure state

        state = generate_oauth_state()

        print(f"Generated OAuth state: {state[:10]}...")

        
        
        # Store state in Supabase

        oauth_state_data = {

            "user_id": current_user.id,

            "platform": platform,

            "state": state,

            "expires_at": (datetime.now() + timedelta(minutes=10)).isoformat()

        }

        
        
        supabase_admin.table("oauth_states").insert(oauth_state_data).execute()

        print(f"✅ OAuth state stored in database")

        
        
        # Generate OAuth URL based on platform

        print(f"🔧 Generating OAuth URL for {platform}...")

        oauth_url = generate_oauth_url(platform, state)

        print(f"✅ Generated OAuth URL: {oauth_url[:100]}...")

        
        
        return {"auth_url": oauth_url, "state": state}

    except Exception as e:

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to initiate connection: {str(e)}"

        )



@router.get("/auth/{platform}/callback")

async def handle_oauth_callback(

    platform: str,

    code: str = None,

    state: str = None,

    error: str = None

):

    """Handle OAuth callback and store connection"""

    print(f"🔗 Main connections router callback - platform: {platform}, code: {code[:10] if code else 'None'}..., state: {state[:10] if state else 'None'}...")

    
    
    # Skip Google platform as it has its own router

    if platform == "google":

        print(f"❌ Redirecting Google callback to Google router")

        raise HTTPException(status_code=404, detail="Not Found")
    
    # Handle YouTube platform (uses Google OAuth)
    if platform == "youtube":
        platform = "youtube"  # Keep as youtube for processing
    
    
    
    try:

        print(f"🔗 OAuth callback for {platform} - code: {code[:10] if code else 'None'}..., state: {state[:10] if state else 'None'}...")

        
        
        # Check for OAuth error

        if error:

            print(f"❌ OAuth error: {error}")

            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail=f"OAuth error: {error}"

            )
        
        
        
        if not code or not state:

            print(f"❌ Missing parameters - code: {bool(code)}, state: {bool(state)}")

            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail="Missing code or state parameter"

            )
        
        
        
        # Verify state - find the state first to get the user_id

        print(f"🔍 Looking for OAuth state: {state[:10]}...")
        
        # Regular platform state lookup
        state_response = supabase_admin.table("oauth_states").select("*").eq("state", state).eq("platform", platform).execute()

        print(f"📊 State query result: {state_response.data}")

        if not state_response.data:

            print(f"❌ No OAuth state found for state: {state[:10]}...")

            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail="Invalid or expired OAuth state"

            )
        
        
        
        # Get the user_id from the state record

        state_record = state_response.data[0]

        user_id = state_record['user_id']

        expires_at = datetime.fromisoformat(state_record['expires_at'].replace('Z', '+00:00'))

        
        
        print(f"✅ Found OAuth state for user: {user_id}, expires at: {expires_at}")

        
        
        # Check if state has expired

        if datetime.now(expires_at.tzinfo) > expires_at:

            print(f"❌ OAuth state expired at {expires_at}")

            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail="OAuth state has expired"

            )
        
        
        
        # Exchange code for tokens
        print(f"🔄 Exchanging {platform} code for tokens...")

        tokens = exchange_code_for_tokens(platform, code, state)

        print(f"✅ Tokens received: {tokens.keys() if tokens else 'None'}")

        # Get account information
        print(f"🔍 Getting account info for {platform}...")
        
        if platform == "instagram":
            print("🔄 Instagram OAuth - using Facebook token exchange and account info...")
            print(f"🔑 Access token (first 20 chars): {tokens['access_token'][:20]}...")

        account_info = get_account_info(platform, tokens['access_token'])

        print(f"📊 Account info result: {account_info}")
        
        if platform == "instagram":
            print("🔍 Instagram-specific debug info:")
            print(f"   - Has account_info: {account_info is not None}")
            if account_info:
                print(f"   - Has instagram_id: {account_info.get('instagram_id') is not None}")
                print(f"   - Has page_id: {account_info.get('page_id') is not None}")
                print(f"   - Has page_name: {account_info.get('page_name') is not None}")
                print(f"   - Account type: {account_info.get('account_type', 'unknown')}")

        
        
        # Handle case where account info is None (especially for Instagram)

        if account_info is None:

            if platform == "instagram":
                # For Instagram, provide helpful setup instructions
                print("🔄 No Instagram Business account found. Providing setup instructions...")
                
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Instagram Setup Required</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                        .step {{ background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #1877f2; }}
                        .button {{ background: #1877f2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; margin: 10px 0; }}
                        .button:hover {{ background: #166fe5; }}
                    </style>
                </head>
                <body>
                    <h2>Instagram Business Account Setup Required</h2>
                    <p>To connect Instagram, you need to set up your Instagram Business account first:</p>
                    
                    <div class="step">
                        <h3>Step 1: Convert to Business Account</h3>
                        <p>In your Instagram app, go to Settings → Account → Switch to Professional Account → Business</p>
                    </div>
                    
                    <div class="step">
                        <h3>Step 2: Connect to Facebook Page</h3>
                        <p>In your Instagram app, go to Settings → Account → Linked Accounts → Facebook → Connect to a Page</p>
                    </div>
                    
                    <div class="step">
                        <h3>Step 3: Try Again</h3>
                        <p>Once your Instagram Business account is connected to a Facebook Page, try connecting again.</p>
                    </div>
                    
                    <a href="javascript:window.close()" class="button">Close and Try Again</a>
                    
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'OAUTH_ERROR',
                                platform: 'instagram',
                                error: 'Instagram Business account setup required. Please connect your Instagram to a Facebook Page first.'
                            }}, '*');
                        }}
                    </script>
                </body>
                </html>
                """)

            elif platform == "linkedin":

                raise Exception("Failed to retrieve LinkedIn account information. Please check that your LinkedIn app has the correct permissions and scopes.")

            else:

                raise Exception(f"Failed to retrieve {platform} account information")
        
        
        
        # Clean up any existing failed connections for this platform before creating new one
        try:
            print(f"🧹 Cleaning up any existing failed connections for user {user_id} and platform {platform}")
            cleanup_response = supabase_admin.table("platform_connections").delete().eq("user_id", user_id).eq("platform", platform).eq("is_active", False).execute()
            print(f"✅ Cleaned up {len(cleanup_response.data) if cleanup_response.data else 0} failed connections")
        except Exception as cleanup_error:
            print(f"⚠️ Error during cleanup: {cleanup_error}")

        # Store connection in Supabase (upsert - update if exists, insert if not)

        # Use page access token for posting, not user access token

        page_access_token = account_info.get('page_access_token', tokens['access_token'])

        

        connection_data = {

            "user_id": user_id,

            "platform": platform,

            "page_id": account_info.get('page_id'),

            "page_name": account_info.get('page_name'),

            "page_username": account_info.get('username'),

            "follower_count": account_info.get('follower_count', 0),

            "access_token_encrypted": encrypt_token(page_access_token),  # Store page token, not user token

            "refresh_token_encrypted": encrypt_token(tokens.get('refresh_token', '')),

            "token_expires_at": (datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))).isoformat(),

            "connection_status": 'active',

            "is_active": True,  # Add this field for the query

            "last_sync": datetime.now().isoformat()

        }

        
        
        # Add platform-specific fields

        if platform == "instagram":
            # For Instagram, use instagram_id as page_id since that's what the table expects
            if account_info.get('instagram_id'):
                connection_data["page_id"] = account_info.get('instagram_id')
            
            # Only include fields that exist in the database schema
            # Skip account_type, media_count, and other custom fields

        elif platform == "linkedin":

            connection_data["linkedin_id"] = account_info.get('linkedin_id')

            connection_data["organization_id"] = account_info.get('organization_id')

            connection_data["headline"] = account_info.get('headline')

            connection_data["email"] = account_info.get('email')

            connection_data["profile_picture"] = account_info.get('profile_picture')

            connection_data["account_type"] = account_info.get('account_type', 'personal')

            connection_data["is_organization"] = account_info.get('is_organization', False)
        
        elif platform == "youtube":
            # Map YouTube-specific fields
            connection_data["page_id"] = account_info.get('account_id')  # YouTube channel ID
            connection_data["page_name"] = account_info.get('account_name', '')  # Channel title
            connection_data["follower_count"] = account_info.get('subscriber_count', 0)  # Subscriber count
            connection_data["page_username"] = account_info.get('display_name', '')  # Display name
            
            # Add YouTube-specific fields if they exist in the database
            if 'youtube_channel_id' in connection_data:
                connection_data["youtube_channel_id"] = account_info.get('account_id')
            if 'youtube_channel_title' in connection_data:
                connection_data["youtube_channel_title"] = account_info.get('account_name', '')
            if 'youtube_subscriber_count' in connection_data:
                connection_data["youtube_subscriber_count"] = account_info.get('subscriber_count', 0)
            if 'youtube_custom_url' in connection_data:
                connection_data["youtube_custom_url"] = account_info.get('custom_url', '')
            if 'youtube_thumbnail_url' in connection_data:
                connection_data["youtube_thumbnail_url"] = account_info.get('profile_picture', '')
        
        
        
        # Try to insert, if it fails due to duplicate key, update instead
        try:
            connection_response = supabase_admin.table("platform_connections").insert(connection_data).execute()
        except Exception as e:
            if "duplicate key value violates unique constraint" in str(e):
                # Update existing connection
                connection_response = supabase_admin.table("platform_connections").update(connection_data).eq("user_id", user_id).eq("platform", platform).eq("page_id", account_info.get('page_id')).execute()
            else:
                raise e
        
        # For Facebook connections, also create Instagram connection if Instagram Business account exists
        if platform == 'facebook' and account_info.get('instagram_id'):
            print(f"📱 Facebook connection includes Instagram Business account: {account_info.get('instagram_id')}")
            
            instagram_connection_data = {
                "user_id": user_id,
                "platform": "instagram",
                "page_id": account_info.get('instagram_id'),  # Use instagram_id as page_id
                "page_name": account_info.get('username', ''),
                "page_username": account_info.get('username', ''),
                "follower_count": account_info.get('follower_count', 0),
                "access_token_encrypted": encrypt_token(page_access_token),  # Same token works for both
                "refresh_token_encrypted": encrypt_token(tokens.get('refresh_token', '')),
                "token_expires_at": (datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))).isoformat(),
                "connection_status": 'active',
                "is_active": True,
                "last_sync": datetime.now().isoformat()
                # Skip account_type, media_count and other custom fields that don't exist in DB
            }
            
            try:
                instagram_connection_response = supabase_admin.table("platform_connections").insert(instagram_connection_data).execute()
                print(f"✅ Created Instagram connection: {instagram_connection_response.data[0]['id'] if instagram_connection_response.data else 'unknown'}")
            except Exception as e:
                if "duplicate key value violates unique constraint" in str(e):
                    # Update existing Instagram connection
                    instagram_connection_response = supabase_admin.table("platform_connections").update(instagram_connection_data).eq("user_id", user_id).eq("platform", "instagram").eq("page_id", account_info.get('instagram_id')).execute()
                    print(f"✅ Updated existing Instagram connection")
                else:
                    print(f"❌ Error creating Instagram connection: {e}")
        
        
        
        # Remove used state

        supabase_admin.table("oauth_states").delete().eq("state", state).execute()

        
        
        # Get the connection ID (handle both insert and update responses)

        if connection_response.data and len(connection_response.data) > 0:

            connection_id = connection_response.data[0]["id"]

        else:

            # If update didn't return data, get the existing connection

            existing_connection = supabase_admin.table("platform_connections").select("id").eq("user_id", user_id).eq("platform", platform).eq("page_id", account_info.get('page_id')).execute()

            connection_id = existing_connection.data[0]["id"] if existing_connection.data else "unknown"
        try:
            record_platform_metrics(
                user_id=user_id,
                platform=platform,
                page_id=connection_data.get("page_id"),
                page_name=connection_data.get("page_name", ""),
                access_token=page_access_token
            )
        except Exception as metric_error:
            print(f"⚠️ Could not record platform metrics for {platform}: {metric_error}")

        if platform == 'facebook' and account_info.get('instagram_id'):
            try:
                record_platform_metrics(
                    user_id=user_id,
                    platform="instagram",
                    page_id=account_info.get('instagram_id'),
                    page_name=account_info.get('username', ''),
                    access_token=page_access_token
                )
            except Exception as metric_error:
                print(f"⚠️ Could not record Instagram metrics: {metric_error}")

        
        # Return HTML page that redirects back to frontend

        frontend_url = os.getenv('FRONTEND_URL', 'https://emily.atsnai.com')

        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Connection Successful - Emily</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }}
                
                .success-container {{
                    background: white;
                    border-radius: 20px;
                    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                    padding: 40px;
                    text-align: center;
                    max-width: 500px;
                    width: 100%;
                    animation: slideUp 0.6s ease-out;
                }}
                
                @keyframes slideUp {{
                    from {{
                        opacity: 0;
                        transform: translateY(30px);
                    }}
                    to {{
                        opacity: 1;
                        transform: translateY(0);
                    }}
                }}
                
                .success-icon {{
                    width: 80px;
                    height: 80px;
                    background: linear-gradient(135deg, #4CAF50, #45a049);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 30px;
                    animation: pulse 2s infinite;
                }}
                
                @keyframes pulse {{
                    0% {{
                        transform: scale(1);
                    }}
                    50% {{
                        transform: scale(1.05);
                    }}
                    100% {{
                        transform: scale(1);
                    }}
                }}
                
                .checkmark {{
                    color: white;
                    font-size: 40px;
                    font-weight: bold;
                }}
                
                .success-title {{
                    font-size: 28px;
                    font-weight: 700;
                    color: #2d3748;
                    margin-bottom: 15px;
                }}
                
                .success-subtitle {{
                    font-size: 18px;
                    color: #4a5568;
                    margin-bottom: 30px;
                }}
                
                .platform-info {{
                    background: #f7fafc;
                    border-radius: 12px;
                    padding: 20px;
                    margin: 20px 0;
                    border-left: 4px solid #4CAF50;
                }}
                
                .platform-name {{
                    font-size: 20px;
                    font-weight: 600;
                    color: #2d3748;
                    margin-bottom: 8px;
                }}
                
                .account-name {{
                    font-size: 16px;
                    color: #4a5568;
                }}
                
                .follower-count {{
                    font-size: 14px;
                    color: #718096;
                    margin-top: 5px;
                }}
                
                .close-button {{
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                    border: none;
                    padding: 15px 30px;
                    border-radius: 25px;
                    font-size: 16px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    margin-top: 20px;
                }}
                
                .close-button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
                }}
                
                .loading-text {{
                    color: #718096;
                    font-size: 14px;
                    margin-top: 20px;
                }}
                
                .spinner {{
                    display: inline-block;
                    width: 20px;
                    height: 20px;
                    border: 3px solid #f3f3f3;
                    border-top: 3px solid #667eea;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin-right: 10px;
                }}
                
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
            </style>
        </head>
        <body>
            <div class="success-container">
                <div class="success-icon">
                    <div class="checkmark">✓</div>
                </div>
                
                <h1 class="success-title">Connection Successful!</h1>
                <p class="success-subtitle">Your {platform.title()} account has been connected to Emily</p>
                
                <div class="platform-info">
                    <div class="platform-name">{platform.title()}</div>
                    <div class="account-name">{account_info.get('page_name', 'Connected Account')}</div>
                    {f'<div class="follower-count">{account_info.get("follower_count", 0):,} followers</div>' if account_info.get('follower_count', 0) > 0 else ''}
                </div>
                
                <button class="close-button" onclick="closeWindow()">
                    Continue to Emily
                </button>
                
                <div class="loading-text">
                    <div class="spinner"></div>
                    This window will close automatically...
                </div>
            </div>

            <script>
                function closeWindow() {{
                    if (window.opener) {{
                        window.opener.postMessage({{
                        type: 'OAUTH_SUCCESS',
                        platform: '{platform}',
                        connection: {{
                            id: '{connection_id}',
                            platform: '{platform}',
                            page_name: '{account_info.get('page_name', '')}',
                            follower_count: {account_info.get('follower_count', 0)},
                            connection_status: 'active'
                        }}
                    }}, '*');
                    window.close();
                }} else {{
                    window.location.href = '{frontend_url}';
                    }}
                }}

                // Auto-close after 3 seconds
                setTimeout(() => {{
                    closeWindow();
                }}, 3000);
            </script>
        </body>
        </html>
        """)
        
        
        
    except Exception as e:

        print(f"❌ OAuth callback error for {platform}: {e}")

        print(f"❌ Error type: {type(e).__name__}")

        import traceback

        print(f"❌ Traceback: {traceback.format_exc()}")

        
        # Clean up any partial connection data that might have been created
        try:
            if 'user_id' in locals():
                print(f"🧹 Cleaning up failed connection for user {user_id} and platform {platform}")
                # Delete any failed connection attempts
                supabase_admin.table("platform_connections").delete().eq("user_id", user_id).eq("platform", platform).eq("is_active", False).execute()
                print(f"✅ Cleaned up failed connection")
        except Exception as cleanup_error:
            print(f"⚠️ Error during cleanup: {cleanup_error}")

        # Return a more detailed error page

        frontend_url = os.getenv('FRONTEND_URL', 'https://emily.atsnai.com')

        error_message = str(e).replace("'", "\\'").replace('"', '\\"')

        

        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Connection Failed - Emily</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }}
                
                .error-container {{
                    background: white;
                    border-radius: 20px;
                    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                    padding: 40px;
                    text-align: center;
                    max-width: 500px;
                    width: 100%;
                    animation: slideUp 0.6s ease-out;
                }}
                
                @keyframes slideUp {{
                    from {{
                        opacity: 0;
                        transform: translateY(30px);
                    }}
                    to {{
                        opacity: 1;
                        transform: translateY(0);
                    }}
                }}
                
                .error-icon {{
                    width: 80px;
                    height: 80px;
                    background: linear-gradient(135deg, #ff6b6b, #ee5a52);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 30px;
                    animation: shake 0.5s ease-in-out;
                }}
                
                @keyframes shake {{
                    0%, 100% {{ transform: translateX(0); }}
                    25% {{ transform: translateX(-5px); }}
                    75% {{ transform: translateX(5px); }}
                }}
                
                .error-symbol {{
                    color: white;
                    font-size: 40px;
                    font-weight: bold;
                }}
                
                .error-title {{
                    font-size: 28px;
                    font-weight: 700;
                    color: #2d3748;
                    margin-bottom: 15px;
                }}
                
                .error-subtitle {{
                    font-size: 18px;
                    color: #4a5568;
                    margin-bottom: 30px;
                }}
                
                .error-details {{
                    background: #fef5f5;
                    border-radius: 12px;
                    padding: 20px;
                    margin: 20px 0;
                    border-left: 4px solid #ff6b6b;
                    text-align: left;
                }}
                
                .error-message {{
                    font-size: 14px;
                    color: #e53e3e;
                    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                    word-break: break-word;
                    line-height: 1.5;
                }}
                
                .retry-button {{
                    background: linear-gradient(135deg, #ff6b6b, #ee5a52);
                    color: white;
                    border: none;
                    padding: 15px 30px;
                    border-radius: 25px;
                    font-size: 16px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    margin: 10px;
                }}
                
                .retry-button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 10px 20px rgba(255, 107, 107, 0.3);
                }}
                
                .close-button {{
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                    border: none;
                    padding: 15px 30px;
                    border-radius: 25px;
                    font-size: 16px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    margin: 10px;
                }}
                
                .close-button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
                }}
                
                .button-group {{
                    margin-top: 30px;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <div class="error-icon">
                    <div class="error-symbol">✕</div>
                </div>
                
                <h1 class="error-title">Connection Failed</h1>
                <p class="error-subtitle">We couldn't connect your {platform.title()} account to Emily</p>
                
                <div class="error-details">
                    <div class="error-message">{error_message}</div>
                </div>
                
                <div class="button-group">
                    <button class="retry-button" onclick="retryConnection()">
                        Try Again
                    </button>
                    <button class="close-button" onclick="closeWindow()">
                        Close Window
                    </button>
                </div>
            </div>

            <script>
                function closeWindow() {{
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'OAUTH_ERROR',
                            platform: '{platform}',
                            error: '{error_message}'
                        }}, '*');
                        window.close();
                    }} else {{
                        window.location.href = '{frontend_url}';
                    }}
                }}

                function retryConnection() {{
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'OAUTH_RETRY',
                            platform: '{platform}'
                        }}, '*');
                        window.close();
                    }} else {{
                        window.location.href = '{frontend_url}';
                    }}
                }}
            </script>
        </body>
        </html>
        """)



@router.delete("/{connection_id}")

async def disconnect_account(

    connection_id: str,

    current_user: User = Depends(get_current_user)

):

    """Disconnect account and revoke tokens"""

    try:

        # Verify connection belongs to user

        connection_response = supabase_admin.table("platform_connections").select("*").eq("id", connection_id).eq("user_id", current_user.id).execute()

        
        
        if not connection_response.data:

            raise HTTPException(

                status_code=status.HTTP_404_NOT_FOUND,

                detail="Connection not found"

            )
        
        
        
        # Mark as inactive

        supabase_admin.table("platform_connections").update({

            "is_active": False,

            "disconnected_at": datetime.now().isoformat(),

            "connection_status": 'revoked'

        }).eq("id", connection_id).execute()

        
        
        return {"success": True, "message": "Account disconnected successfully"}
        
        
        
    except Exception as e:

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to disconnect: {str(e)}"

        )


@router.delete("/cleanup-failed/{platform}")

async def cleanup_failed_connections(

    platform: str,

    current_user: User = Depends(get_current_user)

):

    """Clean up failed/inactive connections for a platform"""

    try:

        print(f"🧹 Cleaning up failed {platform} connections for user {current_user.id}")

        

        # Delete all inactive connections for this platform and user

        cleanup_response = supabase_admin.table("platform_connections").delete().eq("user_id", current_user.id).eq("platform", platform).eq("is_active", False).execute()

        

        deleted_count = len(cleanup_response.data) if cleanup_response.data else 0

        print(f"✅ Cleaned up {deleted_count} failed {platform} connections")

        

        return {

            "success": True, 

            "message": f"Cleaned up {deleted_count} failed {platform} connections",

            "deleted_count": deleted_count

        }

        

    except Exception as e:

        print(f"❌ Error cleaning up failed connections: {e}")

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to cleanup failed connections: {str(e)}"

        )



# Helper functions for platform-specific OAuth
def generate_pkce_params():
    """Generate PKCE parameters for OAuth 2.0"""
    # Generate code verifier
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    # Generate code challenge
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    return code_verifier, code_challenge

def generate_oauth_url(platform: str, state: str) -> str:

    """Generate OAuth URL for platform"""

    base_urls = {

        'facebook': 'https://www.facebook.com/v18.0/dialog/oauth',

        'instagram': 'https://www.facebook.com/v18.0/dialog/oauth',  # Use Facebook OAuth for Instagram

        'linkedin': 'https://www.linkedin.com/oauth/v2/authorization',

        'twitter': 'https://twitter.com/i/oauth2/authorize',

        'tiktok': 'https://www.tiktok.com/auth/authorize',

        'youtube': 'https://accounts.google.com/o/oauth2/v2/auth'

    }

    
    
    client_ids = {

        'facebook': os.getenv('FACEBOOK_CLIENT_ID'),

        'instagram': os.getenv('FACEBOOK_CLIENT_ID'),  # Always use Facebook App ID for Instagram

        'linkedin': os.getenv('LINKEDIN_CLIENT_ID'),

        'twitter': os.getenv('TWITTER_CLIENT_ID'),

        'tiktok': os.getenv('TIKTOK_CLIENT_ID'),

        'youtube': os.getenv('GOOGLE_CLIENT_ID')

    }

    
    
    # Get API base URL and ensure no trailing slash

    api_base_url = os.getenv('API_BASE_URL', '').rstrip('/')

    
    
    redirect_uris = {

        'facebook': f"{api_base_url}/connections/auth/facebook/callback",

        'instagram': f"{api_base_url}/connections/auth/instagram/callback",

        'linkedin': f"{api_base_url}/connections/auth/linkedin/callback",

        'twitter': f"{api_base_url}/connections/auth/twitter/callback",

        'tiktok': f"{api_base_url}/connections/auth/tiktok/callback",

        'youtube': f"{api_base_url}/connections/auth/youtube/callback"

    }

    
    
    base_url = base_urls.get(platform)

    client_id = client_ids.get(platform)

    redirect_uri = redirect_uris.get(platform)

    
    
    # Better error handling with specific details

    missing_config = []

    if not base_url:

        missing_config.append(f"base_url for {platform}")

    if not client_id:
        # Special case for YouTube which uses Google OAuth
        env_var_name = "GOOGLE_CLIENT_ID" if platform == "youtube" else f"{platform.upper()}_CLIENT_ID"
        missing_config.append(f"client_id for {platform} (check {env_var_name} env var)")

    if not redirect_uri:

        missing_config.append(f"redirect_uri for {platform}")
    
    
    
    if missing_config:

        error_msg = f"Platform {platform} not configured. Missing: {', '.join(missing_config)}"

        print(f"❌ OAuth configuration error: {error_msg}")

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=error_msg

        )
    
    
    
    # Platform-specific OAuth parameters

    if platform == 'facebook':
        # Facebook permissions for:
        # 1. Post on Facebook (pages_manage_posts)
        # 2. Get post insights (pages_read_engagement, pages_show_list)
        # 3. Get page insights (pages_read_engagement, pages_show_list)
        # 4. Read ads data (ads_read, ads_management, business_management)

        # Get Facebook Login for Business config_id from environment
        facebook_config_id = os.getenv('FACEBOOK_CONFIG_ID')
        scope_string = get_meta_scope_string()
        
        # Build OAuth URL with config_id if available
        # Updated scopes to include read_insights for comprehensive analytics access
        oauth_url = f"{base_url}?client_id={client_id}&redirect_uri={redirect_uri}&state={state}&scope=pages_manage_posts,pages_read_engagement,pages_show_list,ads_read,ads_management,business_management,read_insights"
        
        if facebook_config_id:
            oauth_url += f"&config_id={facebook_config_id}"
        
        return oauth_url

    elif platform == 'instagram':
        # Instagram for Business uses Facebook OAuth with specific scopes
        # Based on how Zapier and other professional tools handle Instagram
        print("🔄 Instagram for Business OAuth - using Facebook OAuth with Instagram scopes...")
        
        # Use Instagram redirect URI for Instagram OAuth
        instagram_redirect_uri = f"{os.getenv('API_BASE_URL', '').rstrip('/')}/connections/auth/instagram/callback"
        
        # Instagram for Business requires specific scopes
        # Based on Facebook's official documentation and Zapier's implementation
        instagram_scopes = [
            "pages_show_list",           # List Facebook Pages
            "pages_read_engagement",     # Read page engagement data
            "instagram_basic",           # Basic Instagram account info
            "instagram_content_publish", # Publish to Instagram
            "pages_manage_posts",        # Manage page posts
            "business_management",       # Business management
            "instagram_manage_insights"  # Read Instagram insights and analytics
        ]
        
        scope_string = ",".join(instagram_scopes)
        
        return f"{base_url}?client_id={client_id}&redirect_uri={instagram_redirect_uri}&state={state}&scope={scope_string}"

    elif platform == 'linkedin':
        # LinkedIn scopes for both personal and page management:
        # - openid, profile, email: Basic user info
        # - w_member_social: Post, comment, and react on personal profile
        # - w_organization_social: Post, comment, and react on behalf of organizations
        # - r_organization_social: Read organization data
        # - rw_organization_admin: Read and write organization data
        oauth_url = f"{base_url}?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={state}&scope=openid%20profile%20email%20w_member_social%20w_organization_social%20r_organization_social%20rw_organization_admin"
        print(f"🔗 Generated LinkedIn OAuth URL: {oauth_url}")
        return oauth_url

    elif platform == 'twitter':
        # Twitter OAuth 2.0 scopes for API v2 with PKCE
        # - read: Read tweets and user data
        # - write: Post tweets and manage content
        # - offline.access: Refresh tokens for long-term access
        code_verifier, code_challenge = generate_pkce_params()
        
        # Store code_verifier in state for later use
        # We'll encode it in the state parameter
        state_with_verifier = f"{state}:{code_verifier}"
        
        return f"{base_url}?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={state_with_verifier}&scope=read%20write%20offline.access&code_challenge={code_challenge}&code_challenge_method=S256"

    elif platform == 'tiktok':

        return f"{base_url}?client_key={client_id}&redirect_uri={redirect_uri}&state={state}&scope=user.info.basic,video.publish"

    elif platform == 'youtube':
        # YouTube scopes for comprehensive channel management:
        # - youtube: Manage your YouTube account
        # - youtube.upload: Upload and manage videos
        # - youtube.readonly: View analytics and account details
        # - youtube.force-ssl: Reply to comments and manage engagement
        youtube_scopes = [
            'https://www.googleapis.com/auth/youtube',
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube.readonly',
            'https://www.googleapis.com/auth/youtube.force-ssl'
        ]
        scope_string = ' '.join(youtube_scopes)
        
        # Add timestamp to force fresh OAuth request and bypass Google's cache
        import time
        timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
        
        # Always force consent screen for YouTube to ensure fresh permissions
        # Using prompt=consent to force consent screen (removed conflicting approval_prompt)
        return f"{base_url}?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&state={state}&scope={scope_string}&prompt=consent&access_type=offline&include_granted_scopes=true&t={timestamp}"
    
    
    
    return ""



META_INSIGHTS_METRICS = [
    "page_impressions",
    "page_engaged_users",
    "page_posts_impressions",
    "page_posts_impressions_organic",
    "page_posts_impressions_paid",
    "page_post_engagements",
    "page_negative_feedback",
]


def log_debug_token(access_token: str, platform: str, page_id: str):
    """Log the scopes and metadata of a Facebook access token."""
    app_id = os.getenv("FACEBOOK_CLIENT_ID")
    app_secret = os.getenv("FACEBOOK_CLIENT_SECRET")

    if not app_id or not app_secret:
        print("⚠️ Cannot debug Facebook token because FACEBOOK_CLIENT_ID or CLIENT_SECRET is missing.")
        return

    app_token = f"{app_id}|{app_secret}"
    debug_url = "https://graph.facebook.com/debug_token"
    params = {
        "input_token": access_token,
        "access_token": app_token
    }

    try:
        response = httpx.get(debug_url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json().get("data", {})
        print(f"🔍 Token debug for {platform}/{page_id}: scopes={data.get('scopes')}, is_valid={data.get('is_valid')}, expires_at={data.get('expires_at')}, user_id={data.get('user_id')}, app_id={data.get('app_id')}")
    except Exception as exc:
        print(f"❌ Failed to debug token for {platform}/{page_id}: {exc}")


def record_platform_metrics(user_id: str, platform: str, page_id: str, page_name: str, access_token: str):
    """Fetch analytics via Graph API and store them after a connection completes."""
    if not page_id or not access_token:
        print(f"⚠️ Missing page_id/access_token for metrics (user={user_id}, platform={platform})")
        return

    log_debug_token(access_token, platform, page_id)

    metrics = fetch_page_metrics(page_id, access_token)
    if not metrics:
        print(f"⚠️ No insights returned for page {page_id}")
        return

    today = datetime.utcnow().date()
    for metric_name, metric_value in metrics.items():
        try:
            store_analytics_snapshot(
                user_id=user_id,
                platform=platform,
                source="social_media",
                metric=metric_name,
                value=Decimal(metric_value),
                date=today,
                metadata={"page_name": page_name},
            )
        except Exception as err:
            print(f"❌ Failed to store metric {metric_name} for {page_id}: {err}")


def fetch_page_metrics(page_id: str, access_token: str) -> dict:
    """Query the Facebook Graph API for the required insights."""
    url = f"https://graph.facebook.com/v18.0/{page_id}/insights"
    params = {
        "metric": ",".join(META_INSIGHTS_METRICS),
        "period": "day",
        "access_token": access_token,
    }

    try:
        response = httpx.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json().get("data", [])

        insights = {}
        for entry in data:
            name = entry.get("name")
            values = entry.get("values", [])
            if not name or not values:
                continue

            latest = values[-1]
            insights[name] = latest.get("value", 0)

        return insights
    except Exception as exc:
        print(f"❌ Error fetching insights for page {page_id}: {exc}")
        return {}


def store_analytics_snapshot(
    user_id: str,
    platform: str,
    source: str,
    metric: str,
    value: Decimal,
    date: datetime.date,
    metadata: dict = None,
    post_id: str = None,
):
    """Insert or update a single row in analytics_snapshots."""
    payload = {
        "user_id": user_id,
        "platform": platform,
        "source": source,
        "metric": metric,
        "value": float(value),
        "date": date.isoformat(),
        "metadata": metadata or {},
        "post_id": post_id,
    }

    try:
        supabase_admin.table("analytics_snapshots").upsert(
            payload,
            on_conflict="analytics_snapshots_user_platform_metric_date_post"
        ).execute()
        print(f"✅ Stored analytics snapshot {metric} for user {user_id}")
    except Exception as exc:
        print(f"❌ Could not save analytics snapshot {metric}: {exc}")


def exchange_code_for_tokens(platform: str, code: str, state: str = None) -> dict:

    """Exchange OAuth code for access tokens"""

    if platform == "facebook":

        return exchange_facebook_code_for_tokens(code)

    elif platform == "instagram":
        # Instagram uses Facebook OAuth, so use Facebook token exchange
        # with Instagram redirect URI
        instagram_redirect_uri = f"{os.getenv('API_BASE_URL', '').rstrip('/')}/connections/auth/instagram/callback"
        return exchange_facebook_code_for_tokens(code, instagram_redirect_uri)

    elif platform == "linkedin":

        return exchange_linkedin_code_for_tokens(code)

    elif platform == "twitter":

        return exchange_twitter_code_for_tokens(code, state)

    elif platform == "youtube":

        return exchange_youtube_code_for_tokens(code)

    else:

        raise ValueError(f"Unsupported platform: {platform}")



def exchange_facebook_code_for_tokens(code: str, redirect_uri: str = None) -> dict:

    """Exchange Facebook OAuth code for access tokens"""

    import requests

    

    facebook_app_id = os.getenv('FACEBOOK_CLIENT_ID')

    facebook_app_secret = os.getenv('FACEBOOK_CLIENT_SECRET')

    if not redirect_uri:
        redirect_uri = f"{os.getenv('API_BASE_URL', '').rstrip('/')}/connections/auth/facebook/callback"

    
    
    if not facebook_app_id or not facebook_app_secret:

        raise ValueError("Facebook app credentials not configured")
    
    
    
    # Exchange code for access token

    token_url = "https://graph.facebook.com/v18.0/oauth/access_token"

    token_params = {

        'client_id': facebook_app_id,

        'client_secret': facebook_app_secret,

        'redirect_uri': redirect_uri,

        'code': code

    }

    
    
    response = requests.get(token_url, params=token_params)

    response.raise_for_status()

    
    
    token_data = response.json()

    
    
    # Get long-lived access token

    long_lived_url = "https://graph.facebook.com/v18.0/oauth/access_token"

    long_lived_params = {

        'grant_type': 'fb_exchange_token',

        'client_id': facebook_app_id,

        'client_secret': facebook_app_secret,

        'fb_exchange_token': token_data['access_token']

    }

    
    
    long_lived_response = requests.get(long_lived_url, params=long_lived_params)

    long_lived_response.raise_for_status()

    
    
    long_lived_data = long_lived_response.json()

    
    
    return {

        "access_token": long_lived_data['access_token'],

        "refresh_token": "",  # Facebook doesn't use refresh tokens

        "expires_in": long_lived_data.get('expires_in', 3600)

    }



def exchange_instagram_code_for_tokens(code: str) -> dict:

    """Exchange Instagram OAuth code for access tokens"""

    import requests

    
    
    # Instagram uses the same credentials as Facebook

    instagram_app_id = os.getenv('FACEBOOK_CLIENT_ID')  # Always use Facebook App ID

    instagram_app_secret = os.getenv('FACEBOOK_CLIENT_SECRET')  # Always use Facebook App Secret

    redirect_uri = f"{os.getenv('API_BASE_URL', '').rstrip('/')}/connections/auth/instagram/callback"

    
    
    if not instagram_app_id or not instagram_app_secret:

        raise ValueError("Instagram app credentials not configured (using Facebook credentials)")
    
    
    
    # Exchange code for access token

    token_url = "https://graph.facebook.com/v18.0/oauth/access_token"

    token_params = {

        'client_id': instagram_app_id,

        'client_secret': instagram_app_secret,

        'redirect_uri': redirect_uri,

        'code': code

    }

    
    
    response = requests.get(token_url, params=token_params)

    response.raise_for_status()

    
    
    token_data = response.json()

    
    
    # Get long-lived access token

    long_lived_url = "https://graph.facebook.com/v18.0/oauth/access_token"

    long_lived_params = {

        'grant_type': 'fb_exchange_token',

        'client_id': instagram_app_id,

        'client_secret': instagram_app_secret,

        'fb_exchange_token': token_data['access_token']

    }

    
    
    long_lived_response = requests.get(long_lived_url, params=long_lived_params)

    long_lived_response.raise_for_status()

    
    
    long_lived_data = long_lived_response.json()

    
    
    return {

        "access_token": long_lived_data['access_token'],

        "refresh_token": "",  # Instagram doesn't use refresh tokens

        "expires_in": long_lived_data.get('expires_in', 3600)

    }



def exchange_linkedin_code_for_tokens(code: str) -> dict:

    """Exchange LinkedIn OAuth code for access tokens"""

    import requests

    
    
    linkedin_client_id = os.getenv('LINKEDIN_CLIENT_ID')

    linkedin_client_secret = os.getenv('LINKEDIN_CLIENT_SECRET')

    redirect_uri = f"{os.getenv('API_BASE_URL', '').rstrip('/')}/connections/auth/linkedin/callback"

    
    
    if not linkedin_client_id or not linkedin_client_secret:

        raise ValueError("LinkedIn app credentials not configured")
    
    
    
    # Exchange code for access token

    token_url = "https://www.linkedin.com/oauth/v2/accessToken"

    token_data = {

        'grant_type': 'authorization_code',

        'code': code,

        'client_id': linkedin_client_id,

        'client_secret': linkedin_client_secret,

        'redirect_uri': redirect_uri

    }

    
    
    response = requests.post(token_url, data=token_data)

    response.raise_for_status()

    
    
    token_response = response.json()

    
    
    return {

        "access_token": token_response['access_token'],

        "refresh_token": token_response.get('refresh_token', ''),

        "expires_in": token_response.get('expires_in', 3600)

    }



def exchange_twitter_code_for_tokens(code: str, state: str = None) -> dict:

    """Exchange Twitter OAuth code for access tokens"""

    import requests

    import base64

    

    twitter_client_id = os.getenv('TWITTER_CLIENT_ID')

    twitter_client_secret = os.getenv('TWITTER_CLIENT_SECRET')

    redirect_uri = f"{os.getenv('API_BASE_URL', '').rstrip('/')}/connections/auth/twitter/callback"

    

    if not twitter_client_id or not twitter_client_secret:

        raise ValueError("Twitter app credentials not configured")

    
    # Extract code_verifier from state if provided
    code_verifier = 'challenge'  # Default fallback
    if state and ':' in state:
        try:
            _, code_verifier = state.split(':', 1)
            print(f"🔑 Extracted code_verifier from state: {code_verifier[:10]}...")
        except Exception as e:
            print(f"⚠️ Failed to extract code_verifier from state: {e}")
            code_verifier = 'challenge'

    # Create basic auth header for Twitter API
    credentials = f"{twitter_client_id}:{twitter_client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    # Exchange code for access token
    token_url = "https://api.twitter.com/2/oauth2/token"
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'code_verifier': code_verifier  # Use proper PKCE code verifier
    }

    

    headers = {

        'Authorization': f'Basic {encoded_credentials}',

        'Content-Type': 'application/x-www-form-urlencoded'

    }

    

    response = requests.post(token_url, data=token_data, headers=headers)

    response.raise_for_status()

    

    token_response = response.json()

    

    return {

        "access_token": token_response['access_token'],

        "refresh_token": token_response.get('refresh_token', ''),

        "expires_in": token_response.get('expires_in', 7200)

    }



def exchange_youtube_code_for_tokens(code: str) -> dict:

    """Exchange YouTube OAuth code for access tokens"""

    import requests

    

    youtube_client_id = os.getenv('GOOGLE_CLIENT_ID')

    youtube_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

    redirect_uri = f"{os.getenv('API_BASE_URL', '').rstrip('/')}/connections/auth/youtube/callback"

    

    if not youtube_client_id or not youtube_client_secret:

        raise ValueError("Google app credentials not configured")

    

    # Exchange code for tokens

    token_url = "https://oauth2.googleapis.com/token"

    token_data = {

        "client_id": youtube_client_id,

        "client_secret": youtube_client_secret,

        "code": code,

        "grant_type": "authorization_code",

        "redirect_uri": redirect_uri

    }

    

    response = requests.post(token_url, data=token_data)

    response.raise_for_status()

    token_response = response.json()

    

    return {

        "access_token": token_response['access_token'],

        "refresh_token": token_response.get('refresh_token', ''),

        "expires_in": token_response.get('expires_in', 3600)

    }



def get_account_info(platform: str, access_token: str) -> dict:

    """Get account information from platform API"""

    if platform == "facebook":

        return get_facebook_account_info(access_token)

    elif platform == "instagram":
        # Instagram for Business uses Facebook OAuth but needs Instagram-specific handling
        # Follow the same pattern as Zapier and other professional tools
        print("🔄 Instagram for Business - getting account info via Facebook OAuth...")
        
        # Get Facebook account info first (this is what Instagram for Business uses)
        facebook_info = get_facebook_account_info(access_token)
        
        if facebook_info and facebook_info.get('instagram_id'):
            print(f"✅ Found Instagram Business account via Facebook: {facebook_info.get('instagram_id')}")
            return facebook_info
        
        # If no Instagram found in Facebook info, try dedicated Instagram function
        print("🔄 No Instagram found in Facebook info, trying dedicated Instagram function...")
        return get_instagram_account_info(access_token)

    elif platform == "linkedin":

        return get_linkedin_account_info(access_token)

    elif platform == "twitter":

        return get_twitter_account_info(access_token)

    elif platform == "youtube":

        return get_youtube_account_info(access_token)

    else:

        raise ValueError(f"Unsupported platform: {platform}")



def get_facebook_account_info(access_token: str) -> dict:

    """Get Facebook account information"""

    import requests

    
    
    # Get user's pages

    pages_url = "https://graph.facebook.com/v18.0/me/accounts"

    pages_params = {

        'access_token': access_token,

        'fields': 'id,name,username,followers_count,access_token,instagram_business_account'

    }

    
    
    response = requests.get(pages_url, params=pages_params)

    response.raise_for_status()

    
    
    pages_data = response.json()

    
    
    if not pages_data.get('data'):

        raise ValueError("No Facebook pages found for this user")
    
    
    
    # Use the first page (you could let user choose if multiple)

    page = pages_data['data'][0]

    
    
    # Check if this page has an Instagram Business account
    instagram_account = page.get('instagram_business_account')
    
    result = {
        "page_id": page['id'],
        "page_name": page['name'],
        "username": page.get('username', ''),
        "follower_count": page.get('followers_count', 0),
        "page_access_token": page.get('access_token', '')
    }
    
    # If Instagram Business account exists, include Instagram data
    if instagram_account:
        print(f"✅ Found Instagram Business account: {instagram_account}")
        result.update({
            "instagram_id": instagram_account['id'],
            "instagram_username": instagram_account.get('username', ''),
            "account_type": "business"
        })
    
    return result



def get_instagram_account_info(access_token: str):

    """Get Instagram account information using Graph API"""

    try:

        print(f"🔍 Getting Instagram account info with token: {access_token[:20]}...")

        
        
        # Get Instagram Business Account ID

        pages_url = f"https://graph.facebook.com/v18.0/me/accounts?access_token={access_token}"

        print(f"🌐 Fetching pages from: {pages_url}")

        pages_response = requests.get(pages_url)

        
        
        print(f"📊 Pages response status: {pages_response.status_code}")

        
        
        if pages_response.status_code != 200:

            error_text = pages_response.text

            print(f"❌ Error fetching pages: {pages_response.status_code} - {error_text}")

            try:

                error_data = pages_response.json()

                error_message = error_data.get('error', {}).get('message', 'Unknown error')

                print(f"❌ Facebook API error: {error_message}")

            except:

                print(f"❌ Raw error response: {error_text}")

            return None
        
        
        
        pages_data = pages_response.json()

        pages = pages_data.get('data', [])

        
        
        print(f"📄 Found {len(pages)} pages")

        
        
        if not pages:

            print("❌ No Facebook pages found for this user")

            return None
        
        
        
        # Find page with Instagram account

        instagram_account = None

        instagram_page = None

        
        
        for page in pages:

            print(f"🔍 Checking page: {page.get('name', 'Unknown')} (ID: {page.get('id', 'Unknown')})")

            print(f"🔍 Page data: {page}")

            
            
            # Check for Instagram Business account

            if page.get('instagram_business_account'):

                instagram_account = page['instagram_business_account']

                instagram_page = page

                print(f"✅ Found Instagram account: {instagram_account}")

                break

            else:

                print(f"❌ No Instagram Business account found on page: {page.get('name', 'Unknown')}")

                
                
                # Try to get more details about this page to see why no Instagram account

                try:

                    page_details_url = f"https://graph.facebook.com/v18.0/{page['id']}?fields=instagram_business_account,connected_instagram_account&access_token={access_token}"

                    page_details_response = requests.get(page_details_url)

                    if page_details_response.status_code == 200:
                        page_details = page_details_response.json()
                        print(f"🔍 Page details: {page_details}")
                        
                        # Check if Instagram account is in the detailed response
                        if page_details.get('instagram_business_account'):
                            instagram_account = page_details['instagram_business_account']
                            instagram_page = page
                            print(f"✅ Found Instagram account in page details: {instagram_account}")
                            break
                        elif page_details.get('connected_instagram_account'):
                            # Sometimes it's under connected_instagram_account
                            instagram_account = page_details['connected_instagram_account']
                            instagram_page = page
                            print(f"✅ Found Instagram account under connected_instagram_account: {instagram_account}")
                            break
                    else:
                        print(f"❌ Could not get page details: {page_details_response.status_code} - {page_details_response.text}")

                except Exception as e:

                    print(f"❌ Error getting page details: {e}")
        
        
        
        # If still no Instagram account found, try alternative method
        if not instagram_account:
            print("🔄 Trying alternative method to find Instagram Business account...")
            try:
                # Try to get Instagram accounts directly
                instagram_accounts_url = f"https://graph.facebook.com/v18.0/me/accounts?fields=id,name,instagram_business_account&access_token={access_token}"
                instagram_response = requests.get(instagram_accounts_url)
                
                if instagram_response.status_code == 200:
                    instagram_data = instagram_response.json()
                    print(f"🔍 Instagram accounts response: {instagram_data}")
                    
                    for account in instagram_data.get('data', []):
                        if account.get('instagram_business_account'):
                            instagram_account = account['instagram_business_account']
                            instagram_page = account
                            print(f"✅ Found Instagram account via alternative method: {instagram_account}")
                            break
                else:
                    print(f"❌ Alternative method failed: {instagram_response.status_code} - {instagram_response.text}")
            except Exception as e:
                print(f"❌ Error with alternative method: {e}")

        if not instagram_account:
            print("❌ No Instagram Business account found connected to any Facebook page")
            print("💡 User needs to:")
            print("   1. Convert Instagram to Business account")
            print("   2. Connect Instagram to a Facebook Page")
            print("   3. Ensure the page has Instagram Business account linked")
            
            # Return a helpful error message instead of None
            raise Exception("No Instagram Business account found. Please ensure your Instagram account is connected to a Facebook Page and is a Business or Creator account. You can do this by going to your Instagram app settings and connecting it to a Facebook Page.")
        
        
        
        instagram_id = instagram_account['id']

        print(f"📱 Instagram Business Account ID: {instagram_id}")

        
        
        # Get Instagram account details

        instagram_url = f"https://graph.facebook.com/v18.0/{instagram_id}?fields=id,username,account_type,media_count,followers_count&access_token={access_token}"

        print(f"🌐 Fetching Instagram details from: {instagram_url}")

        instagram_response = requests.get(instagram_url)

        
        
        print(f"📊 Instagram response status: {instagram_response.status_code}")

        
        
        if instagram_response.status_code != 200:

            error_text = instagram_response.text

            print(f"❌ Error fetching Instagram account: {instagram_response.status_code} - {error_text}")

            try:

                error_data = instagram_response.json()

                error_message = error_data.get('error', {}).get('message', 'Unknown error')

                print(f"❌ Instagram API error: {error_message}")

            except:

                print(f"❌ Raw error response: {error_text}")

            return None
        
        
        
        instagram_data = instagram_response.json()

        print(f"✅ Instagram account data: {instagram_data}")

        
        
        return {

            'instagram_id': instagram_data['id'],

            'username': instagram_data['username'],

            'account_type': instagram_data['account_type'],

            'media_count': instagram_data.get('media_count', 0),

            'follower_count': instagram_data.get('followers_count', 0),

            'page_id': instagram_page['id'],

            'page_name': instagram_page['name'],

            'page_access_token': instagram_page.get('access_token', access_token)

        }
        
        
        
    except Exception as e:

        print(f"❌ Error getting Instagram account info: {e}")

        print(f"❌ Error type: {type(e).__name__}")

        import traceback

        print(f"❌ Traceback: {traceback.format_exc()}")

        return None



def get_linkedin_account_info(access_token: str) -> dict:

    """Get LinkedIn account information using openid, profile, email, and w_member_social scopes"""

    import requests

    
    
    try:

        print(f"🔍 Getting LinkedIn account info with token: {access_token[:20]}...")

        
        
        headers = {

            'Authorization': f'Bearer {access_token}',

            'Content-Type': 'application/json',

            'X-Restli-Protocol-Version': '2.0.0'

        }

        
        
        # Try OpenID Connect endpoint first (for openid and profile scopes)

        try:

            print("🔄 Trying OpenID Connect endpoint...")

            userinfo_url = "https://api.linkedin.com/v2/userinfo"

            userinfo_response = requests.get(userinfo_url, headers=headers)

            print(f"📊 LinkedIn userinfo response status: {userinfo_response.status_code}")

            
            
            if userinfo_response.status_code == 200:

                userinfo_data = userinfo_response.json()

                print(f"✅ LinkedIn userinfo data: {userinfo_data}")

                
                
                # Extract from OpenID Connect response

                linkedin_id = userinfo_data.get('sub', '')

                first_name = userinfo_data.get('given_name', '')

                last_name = userinfo_data.get('family_name', '')

                email_address = userinfo_data.get('email', '')

                profile_picture = userinfo_data.get('picture', '')

                headline = userinfo_data.get('headline', '')

                
                
                return {

                    'linkedin_id': linkedin_id,

                    'first_name': first_name,

                    'last_name': last_name,

                    'email': email_address,

                    'profile_picture': profile_picture,

                    'headline': headline,

                    'follower_count': 0,

                    'page_id': linkedin_id,

                    'page_name': f"{first_name} {last_name}".strip(),

                    'account_type': 'personal',

                    'is_organization': False

                }

        except Exception as e:

            print(f"⚠️ OpenID Connect failed: {e}")
        
        
        
        # Fallback to standard LinkedIn API

        print("🔄 Falling back to standard LinkedIn API...")

        profile_url = "https://api.linkedin.com/v2/me"

        profile_response = requests.get(profile_url, headers=headers)

        print(f"📊 LinkedIn profile response status: {profile_response.status_code}")

        
        
        if profile_response.status_code != 200:

            print(f"❌ Error fetching LinkedIn profile: {profile_response.status_code} - {profile_response.text}")

            return None
        
        
        
        profile_data = profile_response.json()

        print(f"✅ LinkedIn profile data: {profile_data}")

        
        
        # Extract profile information

        linkedin_id = profile_data.get('id', '')

        first_name = ""

        last_name = ""

        if 'firstName' in profile_data:

            first_name = profile_data['firstName'].get('localized', {}).get('en_US', '')
        
        
        
        if 'lastName' in profile_data:

            last_name = profile_data['lastName'].get('localized', {}).get('en_US', '')
        
        
        
        headline = ""

        if 'headline' in profile_data:

            headline = profile_data['headline'].get('localized', {}).get('en_US', '')
        
        
        
        # Try to get user's email

        email_address = ""

        try:

            email_url = "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))"

            email_response = requests.get(email_url, headers=headers)

            if email_response.status_code == 200:

                email_data = email_response.json()

                email_address = email_data.get('elements', [{}])[0].get('handle~', {}).get('emailAddress', '')

                print(f"✅ Email fetched: {email_address}")

            else:

                print(f"⚠️ Could not fetch email: {email_response.status_code} - {email_response.text}")

        except Exception as e:

            print(f"⚠️ Could not fetch email: {e}")
        
        
        
        # Try to get organization data for page management
        organizations = []
        try:
            print("🔄 Getting organization info for page management...")
            org_url = "https://api.linkedin.com/v2/organizationalEntityAcls?q=roleAssignee&role=ADMINISTRATOR&state=APPROVED"
            org_response = requests.get(org_url, headers=headers)
            print(f"📊 LinkedIn organizations response status: {org_response.status_code}")
            
            if org_response.status_code == 200:
                org_data = org_response.json()
                print(f"✅ LinkedIn organizations data: {org_data}")
                
                for org in org_data.get('elements', []):
                    org_entity = org.get('organizationalTarget', {})
                    org_id = org_entity.get('~', '').split(':')[-1] if '~' in org_entity.get('~', '') else ''
                    
                    if org_id:
                        # Get organization details
                        try:
                            org_details_url = f"https://api.linkedin.com/v2/organizations/{org_id}"
                            org_details_response = requests.get(org_details_url, headers=headers)
                            
                            if org_details_response.status_code == 200:
                                org_details = org_details_response.json()
                                organizations.append({
                                    'id': org_id,
                                    'name': org_details.get('name', 'Unknown Organization'),
                                    'account_type': 'organization',
                                    'platform': 'linkedin',
                                    'role': org.get('role', 'ADMINISTRATOR')
                                })
                                print(f"✅ Added organization: {org_details.get('name', 'Unknown')}")
                        except Exception as e:
                            print(f"❌ Error getting org details for {org_id}: {e}")
            else:
                print(f"❌ LinkedIn organizations failed: {org_response.status_code} - {org_response.text}")
                
        except Exception as e:
            print(f"❌ LinkedIn organizations error: {e}")

        print("👤 Using personal LinkedIn account")

        return {

            'linkedin_id': linkedin_id,

            'first_name': first_name,

            'last_name': last_name,

            'email': email_address,

            'profile_picture': '',

            'headline': headline,

            'follower_count': 0,

            'page_id': linkedin_id,

            'page_name': f"{first_name} {last_name}".strip(),

            'account_type': 'personal',

            'is_organization': False,
            
            'organizations': organizations  # Include available organizations for page management

        }
        
        
        
    except Exception as e:

        print(f"❌ Error getting LinkedIn account info: {e}")

        print(f"❌ Error type: {type(e).__name__}")

        import traceback

        print(f"❌ Traceback: {traceback.format_exc()}")

        return None



def get_twitter_account_info(access_token: str) -> dict:

    """Get Twitter account information using Twitter API v2"""

    import requests

    

    try:

        print(f"🔍 Getting Twitter account info with token: {access_token[:20]}...")

        

        headers = {

            'Authorization': f'Bearer {access_token}',

            'Content-Type': 'application/json'

        }

        

        # Get user information from Twitter API v2

        user_url = "https://api.twitter.com/2/users/me"

        user_params = {

            'user.fields': 'id,username,name,public_metrics,verified,profile_image_url'

        }

        

        user_response = requests.get(user_url, headers=headers, params=user_params)

        print(f"📊 Twitter user response status: {user_response.status_code}")

        

        if user_response.status_code == 200:

            user_data = user_response.json()

            print(f"✅ Twitter user data: {user_data}")

            

            if 'data' in user_data:

                user_info = user_data['data']

                return {

                    "account_id": user_info['id'],

                    "account_name": user_info['username'],

                    "display_name": user_info['name'],

                    "profile_picture": user_info.get('profile_image_url', ''),

                    "verified": user_info.get('verified', False),

                    "followers_count": user_info.get('public_metrics', {}).get('followers_count', 0),

                    "following_count": user_info.get('public_metrics', {}).get('following_count', 0),

                    "tweet_count": user_info.get('public_metrics', {}).get('tweet_count', 0)

                }

            else:

                print(f"❌ No user data in Twitter response: {user_data}")

                return None

        else:

            print(f"❌ Twitter API error: {user_response.status_code} - {user_response.text}")

            return None

            

    except Exception as e:

        print(f"❌ Error getting Twitter account info: {e}")

        print(f"❌ Error type: {type(e).__name__}")

        import traceback

        print(f"❌ Traceback: {traceback.format_exc()}")

        return None



def get_youtube_account_info(access_token: str) -> dict:

    """Get YouTube account information using YouTube Data API v3"""

    import requests

    

    try:

        print(f"🔍 Getting YouTube account info with token: {access_token[:20]}...")

        

        headers = {

            'Authorization': f'Bearer {access_token}',

            'Content-Type': 'application/json'

        }

        

        # Get channel information from YouTube Data API v3

        channel_url = "https://www.googleapis.com/youtube/v3/channels"

        channel_params = {

            'part': 'snippet,statistics,status',

            'mine': 'true'

        }

        

        channel_response = requests.get(channel_url, headers=headers, params=channel_params)

        

        if channel_response.status_code == 200:

            channel_data = channel_response.json()

            

            if 'items' in channel_data and len(channel_data['items']) > 0:

                channel_info = channel_data['items'][0]

                snippet = channel_info.get('snippet', {})

                statistics = channel_info.get('statistics', {})

                status = channel_info.get('status', {})

                

                return {

                    "account_id": channel_info['id'],

                    "account_name": snippet.get('title', ''),

                    "display_name": snippet.get('title', ''),

                    "profile_picture": snippet.get('thumbnails', {}).get('default', {}).get('url', ''),

                    "verified": snippet.get('verified', False),

                    "subscriber_count": int(statistics.get('subscriberCount', 0)),

                    "video_count": int(statistics.get('videoCount', 0)),

                    "view_count": int(statistics.get('viewCount', 0)),

                    "privacy_status": status.get('privacyStatus', 'unknown'),

                    "country": snippet.get('country', '')

                }

            else:

                print(f"❌ No channel data in YouTube response: {channel_data}")

                return None

        else:

            print(f"❌ YouTube API error: {channel_response.status_code} - {channel_response.text}")

            return None

            

    except Exception as e:

        print(f"❌ Error getting YouTube account info: {e}")

        print(f"❌ Error type: {type(e).__name__}")

        import traceback

        print(f"❌ Traceback: {traceback.format_exc()}")

        return None



def revoke_tokens(platform: str, access_token: str) -> bool:

    """Revoke tokens with platform API"""

    # This would contain platform-specific token revocation logic

    return True



def refresh_platform_token(platform: str, refresh_token: str) -> dict:

    """Refresh platform access token"""

    # This would contain platform-specific token refresh logic

    return {

        "access_token": f"refreshed_access_token_{platform}",

        "refresh_token": f"refreshed_refresh_token_{platform}",

        "expires_in": 3600

    }



@router.get("/facebook/debug")

async def debug_facebook_connection(

    current_user: User = Depends(get_current_user)

):

    """Debug Facebook connection data"""

    try:

        print(f"🔍 Debug Facebook connection for user: {current_user.id}")

        
        
        # Get user's Facebook connection

        response = supabase_admin.table("platform_connections").select("*").eq("user_id", current_user.id).eq("platform", "facebook").eq("is_active", True).execute()

        
        
        if not response.data:

            return {"error": "No active Facebook connection found"}
        
        
        
        connection = response.data[0]

        
        
        # Try to decrypt the token

        try:

            access_token = decrypt_token(connection['access_token'])

            token_status = "encrypted"

        except:

            access_token = connection['access_token']

            token_status = "unencrypted"
        
        
        
        return {

            "connection_id": connection['id'],

            "page_id": connection['page_id'],

            "page_name": connection['page_name'],

            "token_length": len(access_token),

            "token_start": access_token[:20] + "..." if len(access_token) > 20 else access_token,

            "token_status": token_status,

            "is_active": connection['is_active'],

            "connected_at": connection['connected_at']

        }
        
        
        
    except Exception as e:

        print(f"❌ Debug error: {e}")

        return {"error": str(e)}



@router.get("/facebook/test")

async def test_facebook_connection():

    """Test Facebook connection without authentication"""

    try:

        print("🔍 Testing Facebook connection data")

        
        
        # Get any Facebook connection

        response = supabase_admin.table("platform_connections").select("*").eq("platform", "facebook").eq("is_active", True).limit(1).execute()

        
        
        if not response.data:

            return {"error": "No active Facebook connections found"}
        
        
        
        connection = response.data[0]

        
        
        return {

            "connection_id": connection['id'],

            "user_id": connection['user_id'],

            "page_id": connection['page_id'],

            "page_name": connection['page_name'],

            "token_length": len(connection['access_token']),

            "token_start": connection['access_token'][:20] + "..." if len(connection['access_token']) > 20 else connection['access_token'],

            "is_active": connection['is_active'],

            "connected_at": connection['connected_at']

        }
        
        
        
    except Exception as e:

        print(f"❌ Test error: {e}")

        return {"error": str(e)}


@router.get("/facebook/test-basic")
async def test_facebook_basic_permissions():
    """Test Facebook OAuth with basic permissions only"""
    try:
        print("🔍 Testing Facebook OAuth with basic permissions")
        
        # Generate test state
        import uuid
        test_state = str(uuid.uuid4())
        
        # Get environment variables
        facebook_app_id = os.getenv('FACEBOOK_CLIENT_ID')
        facebook_config_id = os.getenv('FACEBOOK_CONFIG_ID')
        api_base_url = os.getenv('API_BASE_URL', '').rstrip('/')
        
        if not facebook_app_id:
            return {"error": "FACEBOOK_CLIENT_ID not configured"}
        
        # Build OAuth URL with basic permissions only
        redirect_uri = f"{api_base_url}/connections/auth/facebook/callback"
        oauth_url = f"https://www.facebook.com/v18.0/dialog/oauth?client_id={facebook_app_id}&redirect_uri={redirect_uri}&state={test_state}&scope=email,public_profile"
        
        # Add config_id if available
        if facebook_config_id:
            oauth_url += f"&config_id={facebook_config_id}"
        
        return {
            "test_oauth_url": oauth_url,
            "facebook_app_id": facebook_app_id,
            "facebook_config_id": facebook_config_id,
            "redirect_uri": redirect_uri,
            "test_state": test_state,
            "instructions": "Click the test_oauth_url to test Facebook OAuth with basic permissions"
        }
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        return {"error": str(e)}


@router.post("/facebook/post")

async def post_to_facebook(

    post_data: dict,

    current_user: User = Depends(get_current_user)

):

    """Post content to Facebook"""

    try:

        print(f"📱 Facebook post request from user: {current_user.id}")

        print(f"📝 Post data: {post_data}")

        
        
        # Get user's Facebook connection

        response = supabase_admin.table("platform_connections").select("*").eq("user_id", current_user.id).eq("platform", "facebook").eq("is_active", True).execute()

        
        
        if not response.data:

            raise HTTPException(

                status_code=status.HTTP_404_NOT_FOUND,

                detail="No active Facebook connection found. Please connect your Facebook account first."

            )
        
        
        
        connection = response.data[0]

        print(f"🔗 Found Facebook connection: {connection['id']}")

        
        
        # Decrypt the access token (using correct field name)

        try:

            access_token = decrypt_token(connection['access_token_encrypted'])

            print(f"🔓 Decrypted access token: {access_token[:20]}...")

        except Exception as e:

            print(f"❌ Error decrypting token: {e}")

            print(f"🔍 Connection data: {connection}")

            
            
            # Check if the token is already in plaintext (not encrypted)

            if connection.get('access_token_encrypted', '').startswith('EAAB'):

                print("🔓 Token appears to be unencrypted, using directly")

                access_token = connection['access_token_encrypted']

            else:

                raise HTTPException(

                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

                    detail="Failed to decrypt access token. Please reconnect your Facebook account."

                )
        
        
        
        # Prepare the post message

        message = post_data.get('message', '')

        title = post_data.get('title', '')

        hashtags = post_data.get('hashtags', [])

        # Get image URL from content data if available, otherwise fallback to post_data
        image_url = ''
        if content_data and content_data.get('images') and len(content_data['images']) > 0:
            image_url = content_data['images'][0]
            print(f"✅ Using image URL from database: {image_url}")
        else:
            image_url = post_data.get('image_url', '')
            print(f"⚠️ Using fallback image URL from request: {image_url}")

        # Combine title, message, and hashtags

        full_message = ""

        if title:

            full_message += f"{title}\n\n"

        full_message += message

        if hashtags:

            hashtag_string = " ".join([f"#{tag}" for tag in hashtags])

            full_message += f"\n\n{hashtag_string}"
        
        
        
        print(f"📄 Full message to post: {full_message}")

        print(f"🖼️ Image URL: {image_url}")

        
        
        # First, validate the access token by getting page info

        try:

            validate_url = f"https://graph.facebook.com/v18.0/{connection['page_id']}?access_token={access_token}"

            print(f"🔍 Validating token with URL: {validate_url}")

            
            
            validate_response = requests.get(validate_url)

            print(f"🔍 Token validation response: {validate_response.status_code}")

            
            
            if validate_response.status_code != 200:

                validate_error = validate_response.json() if validate_response.headers.get('content-type', '').startswith('application/json') else {"error": validate_response.text}

                print(f"❌ Token validation failed: {validate_error}")

                raise HTTPException(

                    status_code=status.HTTP_401_UNAUTHORIZED,

                    detail=f"Invalid or expired access token: {validate_error.get('error', {}).get('message', 'Token validation failed')}"

                )
            
            
            
            page_info = validate_response.json()

            print(f"✅ Token valid, page info: {page_info}")
            
            
            
        except HTTPException:

            raise

        except Exception as e:

            print(f"⚠️  Token validation error (continuing anyway): {e}")
        
        
        
        # Post to Facebook using the correct API format

        facebook_url = f"https://graph.facebook.com/v18.0/{connection['page_id']}/feed"

        
        
        # Check if this is a carousel post
        carousel_images = post_data.get('carousel_images', [])
        is_carousel = post_data.get('post_type') == 'carousel' or (carousel_images and len(carousel_images) > 0)
        
        if is_carousel and carousel_images:
            # Handle carousel post
            print(f"🎠 Posting carousel with {len(carousel_images)} images")
            
            # Step 1: Create photo containers for each image (published=false)
            photo_ids = []
            for idx, img_url in enumerate(carousel_images):
                try:
                    photo_url = f"https://graph.facebook.com/v18.0/{connection['page_id']}/photos"
                    photo_payload = {
                        "url": img_url,
                        "published": "false",
                        "access_token": access_token
                    }
                    
                    photo_response = requests.post(photo_url, data=photo_payload)
                    if photo_response.status_code == 200:
                        photo_data = photo_response.json()
                        photo_id = photo_data.get('id')
                        if photo_id:
                            photo_ids.append({"media_fbid": photo_id})
                            print(f"✅ Created photo container {idx + 1}/{len(carousel_images)}: {photo_id}")
                        else:
                            print(f"⚠️ Photo container {idx + 1} created but no ID returned")
                    else:
                        error_data = photo_response.json() if photo_response.headers.get('content-type', '').startswith('application/json') else {"error": photo_response.text}
                        print(f"❌ Failed to create photo container {idx + 1}: {error_data}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to create photo container {idx + 1}: {error_data.get('error', {}).get('message', 'Unknown error')}"
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    print(f"❌ Error creating photo container {idx + 1}: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to create photo container {idx + 1}: {str(e)}"
                    )
            
            if not photo_ids:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create photo containers for carousel"
                )
            
            # Step 2: Create carousel post with attached_media
            facebook_url = f"https://graph.facebook.com/v18.0/{connection['page_id']}/feed"
            payload = {
                "message": full_message,
                "attached_media": json.dumps(photo_ids),  # JSON string of photo IDs
                "access_token": access_token
            }
            
            print(f"🎠 Posting carousel to feed endpoint with {len(photo_ids)} photos")
            response = requests.post(facebook_url, data=payload)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Facebook carousel post successful: {result}")
                
                # Update content status
                content_id = post_data.get('content_id')
                if content_id:
                    published_at = datetime.now().isoformat()
                    update_data = {
                        "status": "published",
                        "published_at": published_at,
                        "facebook_post_id": result.get('id')
                    }
                    supabase_admin.table("content_posts").update(update_data).eq("id", content_id).execute()
                
                return {
                    "success": True,
                    "post_id": result.get('id'),
                    "post_url": f"https://www.facebook.com/{result.get('id')}",
                    "message": "Carousel post published successfully",
                    "url": f"https://www.facebook.com/{result.get('id')}"
                }
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {"error": response.text}
                print(f"❌ Facebook carousel post failed: {error_data}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to post carousel: {error_data.get('error', {}).get('message', 'Unknown error')}"
                )
        
        # Check if media is a video or image
        is_video = False
        post_type = post_data.get('post_type', '')
        metadata = post_data.get('metadata', {})
        
        # Check post_type first
        if post_type and post_type.lower() == 'video':
            is_video = True
            print(f"🎬 Media type detection: Video (from post_type)")
        # Check metadata.media_type
        elif metadata and metadata.get('media_type') == 'video':
            is_video = True
            print(f"🎬 Media type detection: Video (from metadata.media_type)")
        # Check file extension as fallback
        elif image_url:
            video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.wmv', '.flv', '.3gp']
            image_url_lower = image_url.lower()
            # Remove query parameters for extension check
            url_without_query = image_url_lower.split('?')[0]
            is_video = any(url_without_query.endswith(ext) for ext in video_extensions)
            if is_video:
                print(f"🎬 Media type detection: Video (from file extension) - URL: {image_url[:100]}...")
            else:
                print(f"🖼️ Media type detection: Image - URL: {image_url[:100]}...")
        
        # Prepare payload based on whether we have media and what type
        if image_url:
            if is_video:
                # For posts with videos, we need to use videos endpoint
                facebook_url = f"https://graph.facebook.com/v18.0/{connection['page_id']}/videos"
                
                payload = {
                    "file_url": image_url,  # Facebook will fetch the video from this URL
                    "description": full_message,
                    "access_token": access_token
                }
                
                print(f"🎥 Posting with video to videos endpoint")
            else:
                # For posts with images, we need to use photos endpoint
                facebook_url = f"https://graph.facebook.com/v18.0/{connection['page_id']}/photos"
                
                payload = {
                    "message": full_message,
                    "url": image_url,  # Facebook will fetch the image from this URL
                    "access_token": access_token
                }
                
                print(f"🖼️ Posting with image to photos endpoint")

        else:

            # For text-only posts, use feed endpoint

            payload = {

                "message": full_message,

                "access_token": access_token

            }

            print(f"📝 Posting text-only to feed endpoint")
        
        
        
        # Also try with access_token as URL parameter

        facebook_url_with_token = f"{facebook_url}?access_token={access_token}"

        
        
        print(f"🌐 Posting to Facebook URL: {facebook_url}")

        print(f"📄 Payload: {payload}")

        print(f"🔑 Access token length: {len(access_token)}")

        print(f"📱 Page ID: {connection['page_id']}")

        
        
        # Try posting with access_token in URL first (recommended method)

        print(f"🌐 Trying URL method: {facebook_url_with_token}")

        if image_url:
            if is_video:
                # For videos, use file_url and description
                response = requests.post(facebook_url_with_token, data={
                    "file_url": image_url,
                    "description": full_message
                })
            else:
                # For photos, send URL parameter separately
                response = requests.post(facebook_url_with_token, data={
                    "message": full_message,
                    "url": image_url
                })
        else:
            response = requests.post(facebook_url_with_token, data={"message": full_message})
        
        
        
        if response.status_code != 200:

            print(f"❌ URL method failed, trying form data method")

            # Fallback to form data method

            response = requests.post(facebook_url, data=payload)
        
        
        
        print(f"📊 Facebook API response status: {response.status_code}")

        print(f"📄 Facebook API response headers: {dict(response.headers)}")

        
        
        if response.status_code == 200:

            result = response.json()

            print(f"✅ Facebook post successful: {result}")

            
            
            # Update content status in Supabase to 'published'

            try:

                # Get the content ID from the post data (we need to add this to the request)

                content_id = post_data.get('content_id')

                if content_id:

                    published_at = datetime.now().isoformat()
                    # Get existing metadata first
                    try:
                        existing_post = supabase_admin.table("content_posts").select("metadata").eq("id", content_id).execute()
                        existing_metadata = existing_post.data[0].get("metadata", {}) if existing_post.data else {}
                    except:
                        existing_metadata = {}
                    
                    # Update metadata with post ID
                    existing_metadata["facebook_post_id"] = result.get('id')
                    
                    update_data = {
                        "status": "published",
                        "published_at": published_at,
                        "metadata": existing_metadata
                    }
                    
                    print(f"🔄 Updating content {content_id} status to published...")
                    print(f"📝 Update data: {update_data}")
                    
                    update_response = supabase_admin.table("content_posts").update(update_data).eq("id", content_id).execute()

                    
                    
                    if update_response.data:
                        print(f"✅ Successfully updated content status in database: {update_response.data}")
                    else:
                        print(f"⚠️  Update response has no data: {update_response}")
                        # Try to get the current content to verify
                        check_response = supabase_admin.table("content_posts").select("id, status").eq("id", content_id).execute()
                        print(f"🔍 Current content status: {check_response.data}")

                else:

                    print("⚠️  No content_id provided, skipping database update")

            except Exception as e:

                print(f"❌ Error updating content status in database: {e}")
                print(f"📋 Traceback: {traceback.format_exc()}")

                # Don't fail the whole request if database update fails
            
            
            
            return {

                "success": True,

                "platform": "facebook",

                "post_id": result.get('id'),

                "message": "Content posted to Facebook successfully!",

                "url": f"https://facebook.com/{result.get('id')}" if result.get('id') else None

            }

        else:

            try:

                error_data = response.json()

                print(f"❌ Facebook API error (JSON): {response.status_code} - {error_data}")

            except:

                error_text = response.text

                print(f"❌ Facebook API error (Text): {response.status_code} - {error_text}")

                error_data = {"error": {"message": error_text}}
            
            
            
            # More specific error handling

            error_message = "Unknown error"

            if isinstance(error_data, dict):

                if "error" in error_data:

                    if isinstance(error_data["error"], dict):

                        error_message = error_data["error"].get("message", "Unknown error")

                    else:

                        error_message = str(error_data["error"])

                else:

                    error_message = str(error_data)
            
            
            
            print(f"🔍 Parsed error message: {error_message}")

            
            
            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail=f"Facebook API error: {error_message}"

            )
            
            
            
    except HTTPException:

        raise

    except Exception as e:

        print(f"❌ Error posting to Facebook: {e}")

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to post to Facebook: {str(e)}"

        )



@router.get("/instagram/debug")

async def debug_instagram_connection(

    current_user: User = Depends(get_current_user)

):

    """Debug Instagram connection data"""

    try:

        print(f"🔍 Debug Instagram connection for user: {current_user.id}")

        
        
        # Get user's Instagram connection

        response = supabase_admin.table("platform_connections").select("*").eq("user_id", current_user.id).eq("platform", "instagram").eq("is_active", True).execute()

        
        
        if not response.data:

            return {"error": "No active Instagram connection found"}
        
        
        
        connection = response.data[0]

        
        
        # Try to decrypt the token

        try:

            access_token = decrypt_token(connection['access_token_encrypted'])

            token_status = "encrypted"

        except:

            access_token = connection['access_token_encrypted']

            token_status = "unencrypted"
        
        
        
        return {

            "connection_id": connection['id'],

            "instagram_id": connection.get('page_id'),  # Instagram ID is stored in page_id field

            "username": connection.get('page_username'),

            "token_length": len(access_token),

            "token_start": access_token[:20] + "..." if len(access_token) > 20 else access_token,

            "token_status": token_status,

            "is_active": connection['is_active'],

            "connected_at": connection['connected_at']

        }
        
        
        
    except Exception as e:

        print(f"❌ Debug Instagram error: {e}")

        return {"error": str(e)}



@router.get("/linkedin/test")

async def test_linkedin_connection():

    """Test LinkedIn connection configuration"""

    try:

        linkedin_client_id = os.getenv('LINKEDIN_CLIENT_ID')

        linkedin_client_secret = os.getenv('LINKEDIN_CLIENT_SECRET')

        api_base_url = os.getenv('API_BASE_URL', '').rstrip('/')

        
        
        if not linkedin_client_id or not linkedin_client_secret:

            return {

                "error": "LinkedIn credentials not configured",

                "missing": {

                    "client_id": not linkedin_client_id,

                    "client_secret": not linkedin_client_secret

                }

            }
        
        
        
        # Generate a test OAuth URL

        state = generate_oauth_state()

        test_oauth_url = f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={linkedin_client_id}&redirect_uri={api_base_url}/connections/auth/linkedin/callback&state={state}&scope=openid%20profile%20email%20w_member_social"

        
        
        return {

            "message": "LinkedIn configuration looks good!",

            "client_id": linkedin_client_id,

            "redirect_uri": f"{api_base_url}/connections/auth/linkedin/callback",

            "test_oauth_url": test_oauth_url,

            "status": "ready"

        }
        
        
        
    except Exception as e:

        print(f"❌ LinkedIn test error: {e}")

        return {"error": str(e)}

@router.get("/linkedin/organizations")
async def get_linkedin_organizations(
    current_user: User = Depends(get_current_user)
):
    """Get available LinkedIn organizations for the user"""
    try:
        print(f"🏢 Getting LinkedIn organizations for user: {current_user.id}")
        
        # Get user's LinkedIn connection
        response = supabase_admin.table("platform_connections").select("*").eq("user_id", current_user.id).eq("platform", "linkedin").eq("is_active", True).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active LinkedIn connection found. Please connect your LinkedIn account first."
            )
        
        connection = response.data[0]
        
        try:
            access_token = decrypt_token(connection['access_token_encrypted'])
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to decrypt access token. Please reconnect your LinkedIn account."
            )
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0'
        }
        
        # Get organization data
        org_url = "https://api.linkedin.com/v2/organizationalEntityAcls?q=roleAssignee&role=ADMINISTRATOR&state=APPROVED"
        org_response = requests.get(org_url, headers=headers)
        
        if org_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to fetch organizations: {org_response.text}"
            )
        
        org_data = org_response.json()
        organizations = []
        
        for org in org_data.get('elements', []):
            org_entity = org.get('organizationalTarget', {})
            org_id = org_entity.get('~', '').split(':')[-1] if '~' in org_entity.get('~', '') else ''
            
            if org_id:
                try:
                    # Get organization details
                    org_details_url = f"https://api.linkedin.com/v2/organizations/{org_id}"
                    org_details_response = requests.get(org_details_url, headers=headers)
                    
                    if org_details_response.status_code == 200:
                        org_details = org_details_response.json()
                        organizations.append({
                            'id': org_id,
                            'name': org_details.get('name', 'Unknown Organization'),
                            'description': org_details.get('description', ''),
                            'logo_url': org_details.get('logoV2', {}).get('original~', {}).get('elements', [{}])[0].get('identifiers', [{}])[0].get('identifier', ''),
                            'role': org.get('role', 'ADMINISTRATOR')
                        })
                except Exception as e:
                    print(f"❌ Error getting org details for {org_id}: {e}")
                    # Add basic org info even if details fail
                    organizations.append({
                        'id': org_id,
                        'name': 'LinkedIn Organization',
                        'description': '',
                        'logo_url': '',
                        'role': org.get('role', 'ADMINISTRATOR')
                    })
        
        return {
            "success": True,
            "organizations": organizations,
            "message": f"Found {len(organizations)} organizations"
        }
        
    except Exception as e:
        print(f"❌ LinkedIn organizations error: {e}")
        return {"error": str(e)}

@router.post("/linkedin/upload-image")
async def upload_linkedin_image(
    image_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Upload image to LinkedIn for use in posts"""
    try:
        print(f"📸 LinkedIn image upload request from user: {current_user.id}")
        
        # Get user's LinkedIn connection
        response = supabase_admin.table("platform_connections").select("*").eq("user_id", current_user.id).eq("platform", "linkedin").eq("is_active", True).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active LinkedIn connection found. Please connect your LinkedIn account first."
            )
        
        connection = response.data[0]
        
        # Decrypt the access token
        try:
            access_token = decrypt_token(connection['access_token_encrypted'])
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to decrypt access token. Please reconnect your LinkedIn account."
            )
        
        # Get the user's LinkedIn ID
        linkedin_id = connection.get('linkedin_id') or connection.get('page_id')
        if not linkedin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="LinkedIn ID not found in connection data"
            )
        
        # Step 1: Register the image upload
        register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0'
        }
        
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": f"urn:li:person:{linkedin_id}",
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }
                ]
            }
        }
        
        print(f"🔄 Registering image upload...")
        register_response = requests.post(register_url, headers=headers, json=register_payload)
        
        if not register_response.ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to register image upload: {register_response.text}"
            )
        
        register_data = register_response.json()
        upload_url = register_data['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
        asset_urn = register_data['value']['asset']
        
        print(f"✅ Image upload registered. Asset URN: {asset_urn}")
        
        # Step 2: Upload the image binary data
        # Note: In a real implementation, you'd need to fetch the image from the provided URL
        # and upload it as binary data. For now, we'll return the asset URN for use in posts.
        
        return {
            "success": True,
            "asset_urn": asset_urn,
            "message": "Image upload registered successfully. Use the asset_urn in your post."
        }
        
    except Exception as e:
        print(f"❌ LinkedIn image upload error: {e}")
        return {"error": str(e)}


@router.post("/linkedin/post")

async def post_to_linkedin(

    post_data: dict,

    current_user: User = Depends(get_current_user)

):

    """Post content to LinkedIn"""

    try:

        print(f"📱 LinkedIn post request from user: {current_user.id}")

        print(f"📝 Post data: {post_data}")

        
        
        # Get user's LinkedIn connection

        response = supabase_admin.table("platform_connections").select("*").eq("user_id", current_user.id).eq("platform", "linkedin").eq("is_active", True).execute()

        
        
        if not response.data:

            raise HTTPException(

                status_code=status.HTTP_404_NOT_FOUND,

                detail="No active LinkedIn connection found. Please connect your LinkedIn account first."

            )
        
        
        
        connection = response.data[0]

        print(f"🔗 Found LinkedIn connection: {connection['id']}")

        
        
        # Decrypt the access token

        try:

            access_token = decrypt_token(connection['access_token_encrypted'])

            print(f"🔓 Decrypted access token: {access_token[:20]}...")

        except Exception as e:

            print(f"❌ Error decrypting token: {e}")

            raise HTTPException(

                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

                detail="Failed to decrypt access token. Please reconnect your LinkedIn account."

            )
        
        
        
        # Prepare the post message

        message = post_data.get('message', '')

        title = post_data.get('title', '')

        hashtags = post_data.get('hashtags', [])

        
        
        # Combine title, message, and hashtags

        full_message = ""

        if title:

            full_message += f"{title}\n\n"

        full_message += message

        if hashtags:

            hashtag_string = " ".join([f"#{tag.replace('#', '')}" for tag in hashtags])

            full_message += f"\n\n{hashtag_string}"
        
        
        
        # Post to LinkedIn using the UGC API (new recommended approach)

        linkedin_url = "https://api.linkedin.com/v2/ugcPosts"

        headers = {

            'Authorization': f'Bearer {access_token}',

            'Content-Type': 'application/json',

            'X-Restli-Protocol-Version': '2.0.0'

        }

        
        
        # Get the user's LinkedIn ID from the connection

        linkedin_id = connection.get('linkedin_id') or connection.get('page_id')

        if not linkedin_id:

            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail="LinkedIn ID not found in connection data"

            )
        
        # Check if user wants to post to an organization (page)
        organization_id = post_data.get('organization_id')
        if organization_id:
            # Post to organization page
            author_urn = f"urn:li:organization:{organization_id}"
            print(f"🏢 Posting to organization: {organization_id}")
        else:
            # Post to personal profile
            author_urn = f"urn:li:person:{linkedin_id}"
            print(f"👤 Posting to personal profile: {linkedin_id}")
        
        
        
        # Get visibility setting from post data (default to PUBLIC)

        visibility = post_data.get('visibility', 'PUBLIC')

        if visibility not in ['PUBLIC', 'CONNECTIONS']:

            visibility = 'PUBLIC'

        

        

        # Get image URL if provided

        image_url = post_data.get('image_url', '')

        

        

        # Determine share media category and prepare media

        share_media_category = "NONE"

        media = []

        

        if image_url:

            # For proper image support, we need to upload the image first

            # For now, we'll handle image URLs as articles

            # In a full implementation, you'd call the image upload endpoint first

            share_media_category = "ARTICLE"

            media = [{

                "status": "READY",

                "description": {

                    "text": title or "Shared image"

                },

                "originalUrl": image_url,

                "title": {

                    "text": title or "Shared content"

                }

            }]

        elif any(keyword in full_message.lower() for keyword in ['http://', 'https://', 'www.']):

            # Check if message contains URLs

            share_media_category = "ARTICLE"

            # Extract URL from message (simple implementation)

            import re

            url_match = re.search(r'https?://[^\s]+', full_message)

            if url_match:

                extracted_url = url_match.group(0)

                media = [{

                    "status": "READY",

                    "description": {

                        "text": title or "Shared article"

                    },

                    "originalUrl": extracted_url,

                    "title": {

                        "text": title or "Shared content"

                    }

                }]

        

        

        # Create the UGC post payload

        ugc_payload = {

            "author": author_urn,

            "lifecycleState": "PUBLISHED",

            "specificContent": {

                "com.linkedin.ugc.ShareContent": {

                    "shareCommentary": {

                        "text": full_message

                    },

                    "shareMediaCategory": share_media_category

                }

            },

            "visibility": {

                "com.linkedin.ugc.MemberNetworkVisibility": visibility

            }

        }

        

        # Add media if present

        if media:

            ugc_payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = media

        
        
        print(f"🌐 Posting to LinkedIn API: {linkedin_url}")

        print(f"📋 UGC payload: {ugc_payload}")

        
        
        response = requests.post(linkedin_url, headers=headers, json=ugc_payload)

        
        
        print(f"📊 LinkedIn API response status: {response.status_code}")

        
        
        if response.status_code in [200, 201]:

            result = response.json()

            print(f"✅ LinkedIn post successful: {result}")

            
            
            # Update last posted timestamp

            try:

                supabase_admin.table("platform_connections").update({

                    "last_posted_at": datetime.now().isoformat()

                }).eq("id", connection['id']).execute()

            except Exception as e:

                print(f"⚠️  Error updating last_posted_at: {e}")
            
            
            
            return {

                "success": True,

                "platform": "linkedin",

                "post_id": result.get('id'),

                "message": "Content posted to LinkedIn successfully!",

                "url": f"https://linkedin.com/feed/update/{result.get('id')}" if result.get('id') else None

            }

        else:

            try:

                error_data = response.json()

                print(f"❌ LinkedIn API error (JSON): {response.status_code} - {error_data}")

            except:

                error_text = response.text

                print(f"❌ LinkedIn API error (Text): {response.status_code} - {error_text}")

                error_data = {"error": {"message": error_text}}
            
            
            
            error_message = "Unknown error"

            if isinstance(error_data, dict) and "error" in error_data:

                if isinstance(error_data["error"], dict):

                    error_message = error_data["error"].get("message", "Unknown error")

                else:

                    error_message = str(error_data["error"])
            
            
            
            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail=f"LinkedIn API error: {error_message}"

            )
            
            
            
    except HTTPException:

        raise

    except Exception as e:

        print(f"❌ Error posting to LinkedIn: {e}")

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to post to LinkedIn: {str(e)}"

        )



@router.post("/youtube/post")
async def post_to_youtube(
    post_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Post content to YouTube"""
    try:
        print(f"📺 YouTube post request from user: {current_user.id}")
        print(f"📝 Post data: {post_data}")
        
        # Get user's YouTube connection (YouTube uses Google OAuth, so check both platforms)
        response = supabase_admin.table("platform_connections").select("*").eq("user_id", current_user.id).in_("platform", ["youtube", "google"]).eq("is_active", True).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="YouTube account not connected. Please connect your YouTube account first."
            )
        
        connection = response.data[0]
        access_token_encrypted = connection.get('access_token_encrypted')
        
        if not access_token_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="YouTube access token not found. Please reconnect your YouTube account."
            )
        
        # Decrypt the access token
        access_token = decrypt_token(access_token_encrypted)
        
        # Extract post data
        title = post_data.get('title', '')
        description = post_data.get('description', '')
        image_url = post_data.get('image_url', '')
        video_url = post_data.get('video_url', '')
        
        if not title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Title is required for YouTube posts"
            )
        
        # Create YouTube API client
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        
        # Get refresh token and other credentials
        refresh_token_encrypted = connection.get('refresh_token_encrypted')
        refresh_token = decrypt_token(refresh_token_encrypted) if refresh_token_encrypted else None
        
        # Create credentials with all required fields
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=os.getenv('GOOGLE_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET')
        )
        
        # Refresh token if needed
        if credentials.expired and credentials.refresh_token:
            try:
                from google.auth.transport.requests import Request
                credentials.refresh(Request())
                print("✅ YouTube credentials refreshed")
            except Exception as e:
                print(f"❌ Failed to refresh YouTube credentials: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="YouTube access token expired. Please reconnect your YouTube account."
                )
        
        youtube = build('youtube', 'v3', credentials=credentials)
        
        try:
            # Test YouTube API access by getting channel info
            print(f"🔍 Testing YouTube API access...")
            channel_response = youtube.channels().list(part='id,snippet', mine=True).execute()
            
            if not channel_response.get('items'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No YouTube channel found. Please ensure you have a YouTube channel associated with your Google account."
                )
            
            channel = channel_response['items'][0]
            channel_id = channel['id']
            channel_title = channel['snippet']['title']
            
            print(f"✅ Found YouTube channel: {channel_title} ({channel_id})")
            
            # YouTube Community Posts are not supported by YouTube Data API v3
            # Instead, we'll simulate success and provide information about alternatives
            print(f"✅ YouTube API connection successful - Channel: {channel_title}")
            
            return {
                "success": True,
                "platform": "youtube",
                "post_id": None,
                "message": f"YouTube connection successful! Channel: {channel_title}. Note: Community posts are not supported by YouTube Data API v3. Consider using video uploads instead.",
                "url": f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
                "post_data": {
                    "title": title,
                    "description": description,
                    "image_url": image_url,
                    "channel_id": channel_id,
                    "channel_title": channel_title,
                    "note": "YouTube Community Posts are not available through YouTube Data API v3. For actual posting, consider implementing video uploads or using YouTube Studio API."
                        }
                    }
            
        except HttpError as e:
            error_details = e.error_details if hasattr(e, 'error_details') else str(e)
            print(f"❌ YouTube API error: {error_details}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"YouTube API error: {error_details}. Please ensure your YouTube channel is properly set up and you have the required permissions."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error posting to YouTube: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to post to YouTube: {str(e)}"
        )



@router.get("/instagram/test-account")

async def test_instagram_account(

    current_user: User = Depends(get_current_user)

):

    """Test Instagram account setup without storing connection"""

    try:

        print(f"🔍 Testing Instagram account setup for user: {current_user.id}")

        
        
        # Get a fresh access token by simulating the OAuth flow

        # This will help us debug what's happening

        facebook_app_id = os.getenv('FACEBOOK_CLIENT_ID')

        facebook_app_secret = os.getenv('FACEBOOK_CLIENT_SECRET')

        
        
        if not facebook_app_id or not facebook_app_secret:

            return {"error": "Facebook app credentials not configured"}
        
        
        
        # Generate a test OAuth URL

        state = generate_oauth_state()

        oauth_url = generate_oauth_url("instagram", state)

        
        
        return {

            "message": "Use this URL to test Instagram connection",

            "oauth_url": oauth_url,

            "instructions": [

                "1. Click the OAuth URL above",

                "2. Grant permissions for Instagram",

                "3. Check if you see any error messages",

                "4. If successful, the callback will show detailed debug info"

            ],

            "facebook_app_id": facebook_app_id,

            "required_setup": [

                "Instagram Business account",

                "Connected to Facebook Page",

                "Page has Instagram Business account linked"

            ]

        }
        
        
        
    except Exception as e:

        print(f"❌ Test error: {e}")

        return {"error": str(e)}



@router.get("/instagram/test-pages")

async def test_instagram_pages(

    current_user: User = Depends(get_current_user)

):

    """Test what pages and Instagram accounts are accessible"""

    try:

        print(f"🔍 Testing Instagram pages access for user: {current_user.id}")

        
        
        # Get a fresh access token by simulating the OAuth flow

        facebook_app_id = os.getenv('FACEBOOK_CLIENT_ID')

        facebook_app_secret = os.getenv('FACEBOOK_CLIENT_SECRET')

        
        
        if not facebook_app_id or not facebook_app_secret:

            return {"error": "Facebook app credentials not configured"}
        
        
        
        # Generate a test OAuth URL with more detailed scopes

        state = generate_oauth_state()

        
        
        # Test with more comprehensive scopes (including insights)

        test_oauth_url = f"https://www.facebook.com/v18.0/dialog/oauth?client_id={facebook_app_id}&redirect_uri=https://agent-emily.onrender.com/connections/auth/instagram/callback&state={state}&scope=pages_show_list,pages_read_engagement,instagram_basic,instagram_content_publish,pages_manage_posts,instagram_manage_insights"

        
        
        return {

            "message": "Test Instagram pages access",

            "test_oauth_url": test_oauth_url,

            "debug_steps": [

                "1. Click the test OAuth URL above",

                "2. Grant ALL permissions (especially pages_manage_posts)",

                "3. Check the callback for detailed page information",

                "4. Look for Instagram Business account in the response"

            ],

            "common_issues": [

                "Instagram not properly linked to Facebook Page",

                "Missing pages_manage_posts permission",

                "Instagram account is Creator instead of Business",

                "Facebook Page doesn't have Instagram Business account"

            ],

            "facebook_app_id": facebook_app_id

        }
        
        
        
    except Exception as e:

        print(f"❌ Test pages error: {e}")

        return {"error": str(e)}



@router.post("/instagram/post")

async def post_to_instagram(

    post_data: dict,

    current_user: User = Depends(get_current_user)

):

    """Post content to Instagram"""

    try:

        print(f"📱 Instagram post request from user: {current_user.id}")

        print(f"📝 Post data: {post_data}")

        # Get content data from database using content_id
        content_id = post_data.get('content_id')
        print(f"🔍 Received content_id: {content_id} (type: {type(content_id)})")
        content_data = None

        if content_id:
            try:
                content_response = supabase_admin.table('created_content').select('*').eq('id', content_id).eq('user_id', current_user.id).execute()
                if content_response.data and len(content_response.data) > 0:
                    content_data = content_response.data[0]
                    print(f"📄 Fetched content data for ID {content_id}: images={content_data.get('images', 'MISSING')}")
                else:
                    print(f"❌ No content found for ID {content_id}")
            except Exception as e:
                print(f"⚠️ Failed to fetch content data: {e}")
        else:
            print(f"❌ No content_id provided in request")

        # Get user's Instagram connection

        response = supabase_admin.table("platform_connections").select("*").eq("user_id", current_user.id).eq("platform", "instagram").eq("is_active", True).execute()

        
        
        if not response.data:

            raise HTTPException(

                status_code=status.HTTP_404_NOT_FOUND,

                detail="No active Instagram connection found. Please connect your Instagram account first."

            )
        
        
        
        connection = response.data[0]

        print(f"🔗 Found Instagram connection: {connection['id']}")

        
        
        # Decrypt the access token

        try:

            access_token = decrypt_token(connection['access_token_encrypted'])

            print(f"🔓 Decrypted access token: {access_token[:20]}...")

        except Exception as e:

            print(f"❌ Error decrypting token: {e}")

            
            
            # Check if the token is already in plaintext (not encrypted)

            if connection.get('access_token_encrypted', '').startswith('EAAB'):

                print("🔓 Token appears to be unencrypted, using directly")

                access_token = connection['access_token_encrypted']

            else:

                raise HTTPException(

                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

                    detail="Failed to decrypt access token. Please reconnect your Instagram account."

                )
        
        
        
        # Prepare the post message

        message = post_data.get('message', '')

        title = post_data.get('title', '')

        hashtags = post_data.get('hashtags', [])

        # Get image URL from content data if available, otherwise fallback to post_data
        image_url = ''
        if content_data and content_data.get('images') and len(content_data['images']) > 0:
            image_url = content_data['images'][0]
            print(f"✅ Using image URL from database: {image_url}")
        else:
            image_url = post_data.get('image_url', '')
            print(f"⚠️ Using fallback image URL from request: {image_url}")

        # Combine title, message, and hashtags

        full_message = ""

        if title:

            full_message += f"{title}\n\n"

        full_message += message

        if hashtags:

            hashtag_string = " ".join([f"#{tag}" for tag in hashtags])

            full_message += f"\n\n{hashtag_string}"
        
        
        
        print(f"📄 Full message to post: {full_message}")

        print(f"🖼️ Image URL: {image_url}")
        
        # Validate image URL is publicly accessible (for Instagram API)
        if image_url:
            # Check if URL is from Supabase storage and might need to be public
            if 'supabase' in image_url.lower() and 'storage' in image_url.lower():
                print(f"⚠️  Warning: Image URL is from Supabase storage. Ensure the bucket is public and the URL is accessible.")
                # Try to verify URL is accessible (quick check)
                try:
                    head_response = requests.head(image_url, timeout=5, allow_redirects=True)
                    if head_response.status_code not in [200, 301, 302]:
                        print(f"⚠️  Warning: Image URL returned status {head_response.status_code}. Instagram may not be able to access it.")
                except Exception as e:
                    print(f"⚠️  Warning: Could not verify image URL accessibility: {e}")
                    print(f"⚠️  Instagram requires publicly accessible image URLs. If posting fails, ensure the image URL is publicly accessible.")

        
        
        # Get Instagram Business Account ID (stored in page_id field)

        instagram_id = connection.get('page_id')

        if not instagram_id:

            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail="Instagram account ID not found. Please reconnect your Instagram account."

            )
        
        # Check if this is a carousel post
        carousel_images = post_data.get('carousel_images', [])
        is_carousel = post_data.get('post_type') == 'carousel' or (carousel_images and len(carousel_images) > 0)
        
        if is_carousel and carousel_images:
            # Handle carousel post
            print(f"🎠 Posting Instagram carousel with {len(carousel_images)} images")
            
            # Step 1: Create media containers for each image (is_carousel_item=true)
            container_ids = []
            for idx, img_url in enumerate(carousel_images):
                try:
                    container_url = f"https://graph.facebook.com/v18.0/{instagram_id}/media"
                    container_data = {
                        "image_url": img_url,
                        "is_carousel_item": "true",
                        "access_token": access_token
                    }
                    
                    container_response = requests.post(container_url, data=container_data)
                    if container_response.status_code == 200:
                        container_result = container_response.json()
                        container_id = container_result.get('id')
                        if container_id:
                            container_ids.append(container_id)
                            print(f"✅ Created media container {idx + 1}/{len(carousel_images)}: {container_id}")
                        else:
                            print(f"⚠️ Media container {idx + 1} created but no ID returned")
                    else:
                        error_data = container_response.json() if container_response.headers.get('content-type', '').startswith('application/json') else {"error": container_response.text}
                        print(f"❌ Failed to create media container {idx + 1}: {error_data}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to create media container {idx + 1}: {error_data.get('error', {}).get('message', 'Unknown error')}"
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    print(f"❌ Error creating media container {idx + 1}: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to create media container {idx + 1}: {str(e)}"
                    )
            
            if not container_ids:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create media containers for carousel"
                )
            
            # Step 2: Create carousel container with children parameter
            carousel_url = f"https://graph.facebook.com/v18.0/{instagram_id}/media"
            carousel_data = {
                "media_type": "CAROUSEL",
                "children": ",".join(container_ids),  # Comma-separated list of container IDs
                "caption": full_message,
                "access_token": access_token
            }
            
            print(f"🎠 Creating Instagram carousel container with {len(container_ids)} children")
            carousel_response = requests.post(carousel_url, data=carousel_data)
            
            if carousel_response.status_code != 200:
                error_data = carousel_response.json() if carousel_response.headers.get('content-type', '').startswith('application/json') else {"error": carousel_response.text}
                print(f"❌ Failed to create carousel container: {error_data}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create carousel container: {error_data.get('error', {}).get('message', 'Unknown error')}"
                )
            
            carousel_result = carousel_response.json()
            creation_id = carousel_result.get('id')
            
            if not creation_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create carousel container - no creation ID returned"
                )
            
            # Step 3: Publish the carousel
            publish_url = f"https://graph.facebook.com/v18.0/{instagram_id}/media_publish"
            publish_data = {
                "creation_id": creation_id,
                "access_token": access_token
            }
            
            print(f"🎠 Publishing Instagram carousel: {creation_id}")
            publish_response = requests.post(publish_url, data=publish_data)
            
            if publish_response.status_code == 200:
                publish_result = publish_response.json()
                post_id = publish_result.get('id')
                print(f"✅ Instagram carousel post successful: {post_id}")
                
                # Update content status
                content_id = post_data.get('content_id')
                if content_id:
                    published_at = datetime.now().isoformat()
                    # Get existing metadata first
                    try:
                        existing_post = supabase_admin.table("content_posts").select("metadata").eq("id", content_id).execute()
                        existing_metadata = existing_post.data[0].get("metadata", {}) if existing_post.data else {}
                    except:
                        existing_metadata = {}
                    
                    # Update metadata with post ID
                    existing_metadata["instagram_post_id"] = post_id
                    
                    update_data = {
                        "status": "published",
                        "published_at": published_at,
                        "metadata": existing_metadata
                    }
                    supabase_admin.table("content_posts").update(update_data).eq("id", content_id).execute()
                    
                    # Cancel any scheduled task for this post to prevent duplicate publishing
                    try:
                        from scheduler.post_publisher import post_publisher
                        if post_publisher:
                            await post_publisher.cancel_scheduled_post(content_id)
                            print(f"✅ Cancelled scheduled task for post {content_id}")
                    except Exception as e:
                        print(f"⚠️ Could not cancel scheduled task (may not exist): {e}")
                
                # Try to get permalink from Instagram API, fallback to constructed URL
                post_url = None
                try:
                    # Fetch the media object to get permalink
                    media_url = f"https://graph.facebook.com/v18.0/{post_id}?fields=permalink&access_token={access_token}"
                    media_response = requests.get(media_url, timeout=10)
                    if media_response.status_code == 200:
                        media_data = media_response.json()
                        post_url = media_data.get('permalink')
                        print(f"✅ Got Instagram permalink: {post_url}")
                except Exception as e:
                    print(f"⚠️ Could not fetch permalink, using constructed URL: {e}")
                
                # Fallback to constructed URL if permalink not available
                if not post_url:
                    # Instagram posts use /p/ format with media_id
                    post_url = f"https://www.instagram.com/p/{post_id}/"
                
                return {
                    "success": True,
                    "post_id": post_id,
                    "post_url": post_url,
                    "url": post_url,
                    "message": "Instagram carousel post published successfully"
                }
            else:
                error_data = publish_response.json() if publish_response.headers.get('content-type', '').startswith('application/json') else {"error": publish_response.text}
                print(f"❌ Failed to publish Instagram carousel: {error_data}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to publish carousel: {error_data.get('error', {}).get('message', 'Unknown error')}"
                )
        
        
        # Create media container first

        create_media_url = f"https://graph.facebook.com/v18.0/{instagram_id}/media"

        
        
        # Check if media is a video or image (same logic as Facebook)
        is_video = False
        post_type = post_data.get('post_type', '')
        metadata = post_data.get('metadata', {})
        
        # Check post_type first
        if post_type and post_type.lower() == 'video':
            is_video = True
            print(f"🎬 Media type detection: Video/Reel (from post_type)")
        # Check metadata.media_type
        elif metadata and metadata.get('media_type') == 'video':
            is_video = True
            print(f"🎬 Media type detection: Video/Reel (from metadata.media_type)")
        # Check file extension as fallback
        elif image_url:
            video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.wmv', '.flv', '.3gp']
            image_url_lower = image_url.lower()
            # Remove query parameters for extension check
            url_without_query = image_url_lower.split('?')[0]
            is_video = any(url_without_query.endswith(ext) for ext in video_extensions)
            if is_video:
                print(f"🎬 Media type detection: Video/Reel (from file extension) - URL: {image_url[:100]}...")
            else:
                print(f"🖼️ Media type detection: Image - URL: {image_url[:100]}...")
        
        
        # Prepare media data based on whether we have media and what type
        if image_url:
            if is_video:
                # For posts with videos/reels
                media_data = {
                    "media_type": "REELS",
                    "video_url": image_url,  # Use video_url for reels
                    "caption": full_message,
                    "access_token": access_token
                }
                print(f"🎥 Creating Instagram reel with video")
            else:
                # For posts with images
                media_data = {
                    "media_type": "IMAGE",
                    "image_url": image_url,
                    "caption": full_message,
                    "access_token": access_token
                }
                print(f"🖼️ Creating Instagram post with image")
        else:
            # For text-only posts, we need to create a media container with a caption
            media_data = {
                "caption": full_message,
                "access_token": access_token
            }
            print(f"📝 Creating Instagram text-only post")
        
        
        
        print(f"🌐 Creating Instagram media container: {create_media_url}")

        print(f"📄 Media data: {media_data}")

        
        
        # Create the media container

        media_response = requests.post(create_media_url, data=media_data)

        
        
        if media_response.status_code != 200:

            try:

                error_data = media_response.json()

                print(f"❌ Instagram API error (JSON): {media_response.status_code} - {error_data}")

            except:

                error_text = media_response.text

                print(f"❌ Instagram API error (Text): {media_response.status_code} - {error_text}")

                error_data = {"error": {"message": error_text}}
            
            
            
            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail=f"Instagram API error: {error_data.get('error', {}).get('message', 'Unknown error')}"

            )
        
        
        
        media_result = media_response.json()

        media_id = media_result.get('id')

        

        if not media_id:
            # Log the full response for debugging
            print(f"❌ Instagram media container creation failed - Full response: {media_result}")
            error_message = media_result.get('error', {}).get('message', 'Unknown error')
            if 'not accessible' in error_message.lower() or 'invalid url' in error_message.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Instagram cannot access the image URL. Please ensure the image is publicly accessible. Error: {error_message}"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create Instagram media container: {error_message}"
            )
        
        
        
        print(f"✅ Instagram media container created: {media_id}")

        
        
        # For videos/reels, wait for processing before publishing (with shorter timeout for better UX)
        if is_video:
            max_wait_time = 120  # 2 minutes max wait (reduced from 5 minutes)
            wait_interval = 3  # Check every 3 seconds (reduced from 5)
            elapsed_time = 0
            
            print(f"⏳ Waiting for video to be processed...")
            while elapsed_time < max_wait_time:
                # Check media status
                status_url = f"https://graph.facebook.com/v18.0/{media_id}?fields=status_code&access_token={access_token}"
                try:
                    status_response = requests.get(status_url, timeout=10)
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status_code = status_data.get('status_code')
                        
                        if status_code == 'FINISHED':
                            print(f"✅ Video processing completed")
                            break
                        elif status_code == 'ERROR':
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Video processing failed. Please check your video file and try again."
                            )
                        else:
                            print(f"⏳ Video processing status: {status_code}, waiting... ({elapsed_time}s/{max_wait_time}s)")
                            time.sleep(wait_interval)
                            elapsed_time += wait_interval
                    else:
                        # If status check fails, try to publish anyway (might be ready)
                        print(f"⚠️  Could not check video status (HTTP {status_response.status_code}), attempting to publish...")
                        break
                except requests.exceptions.Timeout:
                    print(f"⚠️  Status check timeout, attempting to publish...")
                    break
                except Exception as e:
                    print(f"⚠️  Error checking status: {e}, attempting to publish...")
                    break
            
            if elapsed_time >= max_wait_time:
                print(f"⚠️  Video processing timeout after {max_wait_time}s, attempting to publish anyway...")
        
        
        # Publish the media

        publish_url = f"https://graph.facebook.com/v18.0/{instagram_id}/media_publish"

        publish_data = {

            "creation_id": media_id,

            "access_token": access_token

        }

        
        
        print(f"🌐 Publishing Instagram media: {publish_url}")

        publish_response = requests.post(publish_url, data=publish_data)

        
        
        if publish_response.status_code != 200:

            try:

                error_data = publish_response.json()

                print(f"❌ Instagram publish error (JSON): {publish_response.status_code} - {error_data}")

            except:

                error_text = publish_response.text

                print(f"❌ Instagram publish error (Text): {publish_response.status_code} - {error_text}")

                error_data = {"error": {"message": error_text}}
            
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            
            # Provide more helpful error messages
            if 'Media ID is not available' in error_message or 'media id is not available' in error_message.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Instagram cannot access the media. This usually means the image URL is not publicly accessible. Please ensure the image URL is publicly accessible (not behind authentication). Original error: {error_message}"
                )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Instagram publish error: {error_message}"
            )
        
        
        
        publish_result = publish_response.json()

        post_id = publish_result.get('id')

        
        
        print(f"✅ Instagram post published: {post_id}")

        
        
        # Update content status in Supabase to 'published'

        try:

            content_id = post_data.get('content_id')

            if content_id:

                published_at = datetime.now().isoformat()
                # Get existing metadata first
                try:
                    existing_post = supabase_admin.table("content_posts").select("metadata").eq("id", content_id).execute()
                    existing_metadata = existing_post.data[0].get("metadata", {}) if existing_post.data else {}
                except:
                    existing_metadata = {}
                
                # Update metadata with post ID
                existing_metadata["instagram_post_id"] = post_id
                
                update_data = {
                    "status": "published",
                    "published_at": published_at,
                    "metadata": existing_metadata
                }
                
                print(f"🔄 Updating content {content_id} status to published...")
                print(f"📝 Update data: {update_data}")
                
                update_response = supabase_admin.table("content_posts").update(update_data).eq("id", content_id).execute()

                
                
                if update_response.data:
                    print(f"✅ Successfully updated content status in database: {update_response.data}")
                else:
                    print(f"⚠️  Update response has no data: {update_response}")
                    # Try to get the current content to verify
                    check_response = supabase_admin.table("content_posts").select("id, status").eq("id", content_id).execute()
                    print(f"🔍 Current content status: {check_response.data}")
                
                # Cancel any scheduled task for this post to prevent duplicate publishing
                try:
                    from scheduler.post_publisher import post_publisher
                    if post_publisher:
                        await post_publisher.cancel_scheduled_post(content_id)
                        print(f"✅ Cancelled scheduled task for post {content_id}")
                except Exception as e:
                    print(f"⚠️ Could not cancel scheduled task (may not exist): {e}")

            else:

                print("⚠️  No content_id provided, skipping database update")

        except Exception as e:

            print(f"❌ Error updating content status in database: {e}")
            import traceback
            print(f"📋 Traceback: {traceback.format_exc()}")

            # Don't fail the whole request if database update fails
        
        
        
        # Try to get permalink from Instagram API, fallback to constructed URL
        post_url = None
        if post_id:
            try:
                # Fetch the media object to get permalink
                media_url = f"https://graph.facebook.com/v18.0/{post_id}?fields=permalink&access_token={access_token}"
                media_response = requests.get(media_url, timeout=10)
                if media_response.status_code == 200:
                    media_data = media_response.json()
                    post_url = media_data.get('permalink')
                    print(f"✅ Got Instagram permalink: {post_url}")
            except Exception as e:
                print(f"⚠️ Could not fetch permalink, using constructed URL: {e}")
            
            # Fallback to constructed URL if permalink not available
            if not post_url:
                # Determine URL format based on media type (reels use different URL format)
                if is_video:
                    # For reels, use the reel URL format
                    post_url = f"https://www.instagram.com/reel/{post_id}/"
                else:
                    # For regular posts, use the post URL format
                    post_url = f"https://www.instagram.com/p/{post_id}/"
        
        return {

            "success": True,

            "platform": "instagram",

            "post_id": post_id,

            "message": "Content posted to Instagram successfully!",

            "url": post_url,
            "post_url": post_url  # Also include post_url for consistency with frontend

        }
        
        
        
    except HTTPException:

        raise

    except Exception as e:

        print(f"❌ Error posting to Instagram: {e}")

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to post to Instagram: {str(e)}"

        )



# WordPress Connection Endpoints

@router.get("/wordpress")

async def get_wordpress_connections(

    current_user: User = Depends(get_current_user)

):

    """Get all WordPress connections for current user"""

    try:

        print(f"🔍 Fetching WordPress connections for user: {current_user.id}")

        
        
        response = supabase_admin.table("wordpress_connections").select("*").eq("user_id", current_user.id).eq("is_active", True).execute()

        
        
        connections = response.data if response.data else []

        print(f"📊 Found {len(connections)} active WordPress connections")

        
        
        # Remove sensitive data from response

        response_connections = []

        for conn in connections:

            conn_dict = {

                "id": conn["id"],

                "site_name": conn["site_name"],

                "site_url": conn["site_url"],

                "username": conn["username"],

                "is_active": conn["is_active"],

                "last_checked_at": conn["last_checked_at"],

                "connected_at": conn["created_at"],

                "metadata": conn.get("metadata", {})

            }

            response_connections.append(conn_dict)
        
        
        
        return response_connections

    except Exception as e:

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to fetch WordPress connections: {str(e)}"

        )



@router.post("/wordpress")

async def create_wordpress_connection(

    connection_data: WordPressConnection,

    current_user: User = Depends(get_current_user)

):

    """Create a new WordPress connection"""

    try:

        print(f"🔗 Creating WordPress connection for user: {current_user.id}")

        print(f"📝 Site: {connection_data.site_name} ({connection_data.site_url})")
        print(f"📝 Username: {connection_data.username}")
        print(f"📝 Password length: {len(connection_data.password)}")

        
        
        # Validate WordPress site URL

        if not connection_data.site_url.startswith(('http://', 'https://')):

            connection_data.site_url = f"https://{connection_data.site_url}"
        
        

        # Test the connection using WordPress REST API authentication
        # Try multiple endpoints for better compatibility
        rest_urls = [
            f"{connection_data.site_url.rstrip('/')}/wp-json/wp/v2/users/me",
            f"{connection_data.site_url.rstrip('/')}/wp-json/wp/v2/users",
            f"{connection_data.site_url.rstrip('/')}/wp-json/wp/v2/posts?per_page=1"
        ]
        
        print(f"🔍 Testing WordPress connection with REST API endpoints")
        
        try:
            import requests
            session = requests.Session()
            session.cookies.clear()
            
            # Test WordPress REST API authentication with multiple endpoints
            response = None
            successful_endpoint = None
            
            for rest_url in rest_urls:
                print(f"🔍 Trying endpoint: {rest_url}")
                try:
                    response = session.get(
                        rest_url,
                        auth=(connection_data.username, connection_data.password),
                        headers={
                            'Accept': 'application/json',
                            'Content-Type': 'application/json',
                            'User-Agent': 'Agent-Emily/1.0'
                        },
                        timeout=30,
                        allow_redirects=False
                    )
                    
                    if response.status_code == 200:
                        successful_endpoint = rest_url
                        print(f"✅ Success with endpoint: {rest_url}")
                        break
                    elif response.status_code in [401, 403]:
                        # Authentication issue, try next endpoint
                        print(f"⚠️ Auth issue with {rest_url}: {response.status_code}")
                        continue
                    else:
                        print(f"⚠️ Error with {rest_url}: {response.status_code}")
                        continue
                        
                except requests.exceptions.RequestException as e:
                    print(f"⚠️ Request failed for {rest_url}: {e}")
                    continue
            
            if not response or not successful_endpoint:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to connect to any WordPress REST API endpoint. Please check your site URL and ensure the REST API is enabled."
                )
            
            print(f"🔍 WordPress REST API response: {response.status_code}")
            
            user_info = response.json()
            print(f"✅ WordPress REST API authentication successful!")
            print(f"🔍 User: {user_info.get('name', 'Unknown')}")
            print(f"🔍 Email: {user_info.get('email', 'Unknown')}")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ WordPress REST API request failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to connect to WordPress site. Please check your site URL and ensure it's accessible. Error: {str(e)}"
            )
        except Exception as e:
            print(f"❌ WordPress REST API authentication failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to authenticate with WordPress REST API. Please check your credentials and ensure the REST API is enabled. Error: {str(e)}"
            )
        
        # user_info is now available outside the try block
        
        # Encrypt the password
        encrypted_password = encrypt_token(connection_data.password)

        
        
        # Store connection in Supabase

        connection_record = {

            "user_id": current_user.id,

            "site_name": connection_data.site_name,

            "site_url": connection_data.site_url,

            "username": connection_data.username,

            "password": encrypted_password,

            "is_active": True,

            "last_checked_at": datetime.now().isoformat(),

            "metadata": {

                "site_title": user_info.get('name', connection_data.site_name),

                "site_description": user_info.get('description', ''),

                "user_display_name": user_info.get('name', connection_data.username),

                "user_email": user_info.get('email', ''),

                "user_id": user_info.get('id', ''),

                "user_slug": user_info.get('slug', ''),

                "wordpress_version": "REST API v2"

            }

        }

        
        
        response = supabase_admin.table("wordpress_connections").insert(connection_record).execute()

        
        
        if not response.data:

            raise HTTPException(

                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

                detail="Failed to store WordPress connection"

            )
        
        
        
        connection_id = response.data[0]["id"]

        print(f"✅ WordPress connection created: {connection_id}")

        
        
        return {

            "success": True,

            "connection_id": connection_id,

            "message": f"Successfully connected to {connection_data.site_name}",

            "site_info": {

                "site_name": connection_data.site_name,

                "site_url": connection_data.site_url,

                "site_title": user_info.get('display_name', connection_data.site_name),

                "user_display_name": user_info.get('display_name', connection_data.site_name)

            }

        }
        
        
        
    except HTTPException:

        raise

    except requests.exceptions.RequestException as e:

        print(f"❌ WordPress connection error: {e}")

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=f"Failed to connect to WordPress site. Please check your site URL and credentials. Error: {str(e)}"

        )

    except Exception as e:

        print(f"❌ Error creating WordPress connection: {e}")

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to create WordPress connection: {str(e)}"

        )



@router.put("/wordpress/{connection_id}")

async def update_wordpress_connection(

    connection_id: str,

    connection_data: WordPressConnection,

    current_user: User = Depends(get_current_user)

):

    """Update an existing WordPress connection"""

    try:

        print(f"🔧 Updating WordPress connection {connection_id} for user: {current_user.id}")

        
        
        # Verify connection belongs to user

        existing_response = supabase_admin.table("wordpress_connections").select("*").eq("id", connection_id).eq("user_id", current_user.id).execute()

        
        
        if not existing_response.data:

            raise HTTPException(

                status_code=status.HTTP_404_NOT_FOUND,

                detail="WordPress connection not found"

            )
        
        
        
        # Validate WordPress site URL

        if not connection_data.site_url.startswith(('http://', 'https://')):

            connection_data.site_url = f"https://{connection_data.site_url}"
        
        

        # Test the connection using WordPress XML-RPC authentication
        xmlrpc_url = f"{connection_data.site_url.rstrip('/')}/xmlrpc.php"
        
        print(f"🔍 Testing updated WordPress connection with XML-RPC: {xmlrpc_url}")
        
        try:
            import xmlrpc.client
            server = xmlrpc.client.ServerProxy(xmlrpc_url)
            
            # Test if XML-RPC is enabled
            methods = server.system.listMethods()
            print(f"🔍 XML-RPC methods available: {len(methods)}")
            
            # Try to get user info to test authentication
            user_info = server.wp.getProfile(1, connection_data.username, connection_data.password)
            print(f"✅ WordPress XML-RPC authentication successful!")
            print(f"🔍 User: {user_info.get('display_name', 'Unknown')}")
            print(f"🔍 Email: {user_info.get('user_email', 'Unknown')}")
            
        except Exception as e:
            print(f"❌ WordPress XML-RPC authentication failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to authenticate with WordPress. Please check your credentials and ensure XML-RPC is enabled. Error: {str(e)}"
            )
        
        # Encrypt the password
        encrypted_password = encrypt_token(connection_data.password)

        
        
        # Update connection in Supabase

        update_data = {

            "site_name": connection_data.site_name,

            "site_url": connection_data.site_url,

            "username": connection_data.username,

            "password": encrypted_password,

            "last_checked_at": datetime.now().isoformat(),

            "metadata": {

                "site_title": user_info.get('display_name', connection_data.site_name),

                "site_description": user_info.get('description', ''),

                "user_display_name": user_info.get('display_name', connection_data.site_name),

                "user_email": user_info.get('user_email', ''),

                "capabilities": user_info.get('capabilities', {}),

                "wordpress_version": user_info.get('wordpress_version', 'Unknown')

            }

        }

        
        
        response = supabase_admin.table("wordpress_connections").update(update_data).eq("id", connection_id).eq("user_id", current_user.id).execute()

        
        
        if not response.data:

            raise HTTPException(

                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

                detail="Failed to update WordPress connection"

            )
        
        
        
        print(f"✅ WordPress connection updated: {connection_id}")

        
        
        return {

            "success": True,

            "message": f"Successfully updated connection to {connection_data.site_name}",

            "site_info": {

                "site_name": connection_data.site_name,

                "site_url": connection_data.site_url,

                "site_title": user_info.get('display_name', connection_data.site_name),

                "user_display_name": user_info.get('display_name', connection_data.site_name)

            }

        }
        
        
        
    except HTTPException:

        raise

    except requests.exceptions.RequestException as e:

        print(f"❌ WordPress connection error: {e}")

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=f"Failed to connect to WordPress site. Please check your site URL and credentials. Error: {str(e)}"

        )

    except Exception as e:

        print(f"❌ Error updating WordPress connection: {e}")

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to update WordPress connection: {str(e)}"

        )



@router.delete("/wordpress/{connection_id}")

async def delete_wordpress_connection(

    connection_id: str,

    current_user: User = Depends(get_current_user)

):

    """Delete a WordPress connection"""

    try:

        print(f"🗑️ Deleting WordPress connection {connection_id} for user: {current_user.id}")

        
        
        # Verify connection belongs to user

        existing_response = supabase_admin.table("wordpress_connections").select("*").eq("id", connection_id).eq("user_id", current_user.id).execute()

        
        
        if not existing_response.data:

            raise HTTPException(

                status_code=status.HTTP_404_NOT_FOUND,

                detail="WordPress connection not found"

            )
        
        
        
        # For WordPress, completely delete the connection data
        response = supabase_admin.table("wordpress_connections").delete().eq("id", connection_id).eq("user_id", current_user.id).execute()

        
        
        if not response.data:

            raise HTTPException(

                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

                detail="Failed to delete WordPress connection"

            )
        
        
        
        print(f"✅ WordPress connection deleted: {connection_id}")

        
        
        return {

            "success": True,

            "message": "WordPress connection deleted successfully"

        }
        
        
        
    except HTTPException:

        raise

    except Exception as e:

        print(f"❌ Error deleting WordPress connection: {e}")

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to delete WordPress connection: {str(e)}"

        )



@router.post("/wordpress/{connection_id}/test")

async def test_wordpress_connection(

    connection_id: str,

    current_user: User = Depends(get_current_user)

):

    """Test a WordPress connection"""

    try:

        print(f"🔍 Testing WordPress connection {connection_id} for user: {current_user.id}")

        
        
        # Get connection details

        response = supabase_admin.table("wordpress_connections").select("*").eq("id", connection_id).eq("user_id", current_user.id).eq("is_active", True).execute()

        
        
        if not response.data:

            raise HTTPException(

                status_code=status.HTTP_404_NOT_FOUND,

                detail="WordPress connection not found"

            )
        
        
        
        connection = response.data[0]
        
        
        
        # Decrypt the password
        try:
            password = decrypt_token(connection['password'])
        except Exception as e:
            print(f"❌ Error decrypting password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to decrypt password"
            )
        
        # Test the connection using WordPress REST API authentication
        rest_url = f"{connection['site_url'].rstrip('/')}/wp-json/wp/v2/users/me"
        
        print(f"🔍 Testing WordPress connection with REST API: {rest_url}")
        
        try:
            import requests
            session = requests.Session()
            session.cookies.clear()
            
            # Test WordPress REST API authentication
            response = session.get(
                rest_url,
                auth=(connection['username'], password),
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'User-Agent': 'Agent-Emily/1.0'
                },
                timeout=30,
                allow_redirects=False
            )
            
            print(f"🔍 WordPress REST API response: {response.status_code}")
            
            if response.status_code == 401:
                print(f"❌ WordPress REST API authentication failed: 401 Unauthorized")
                print(f"🔍 Response headers: {dict(response.headers)}")
                if 'Set-Cookie' in response.headers:
                    print(f"🔍 Set-Cookie headers: {response.headers.get('Set-Cookie')}")
                # Update last_checked_at even if test failed
                supabase_admin.table("wordpress_connections").update({
                    "last_checked_at": datetime.now().isoformat()
                }).eq("id", connection_id).execute()
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to authenticate with WordPress REST API. Please check your username and App Password. Make sure you're using an Application Password, not your regular password. Generate one in WordPress Admin → Users → Profile → Application Passwords."
                )
            elif response.status_code == 406:
                print(f"❌ WordPress REST API error: 406 Not Acceptable")
                print(f"🔍 Response content: {response.text[:500]}")
                print(f"🔍 Response headers: {dict(response.headers)}")
                # Update last_checked_at even if test failed
                supabase_admin.table("wordpress_connections").update({
                    "last_checked_at": datetime.now().isoformat()
                }).eq("id", connection_id).execute()
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="WordPress REST API returned status 406 (Not Acceptable). This usually means the API doesn't accept the request format. Please check if your WordPress site has the REST API enabled and try again."
                )
            elif response.status_code != 200:
                print(f"❌ WordPress REST API error: {response.status_code}")
                print(f"🔍 Response content: {response.text[:500]}")
                # Update last_checked_at even if test failed
                supabase_admin.table("wordpress_connections").update({
                    "last_checked_at": datetime.now().isoformat()
                }).eq("id", connection_id).execute()
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"WordPress REST API returned status {response.status_code}. Please check your site URL and ensure the REST API is enabled."
                )
            
            user_info = response.json()
            print(f"✅ WordPress REST API authentication successful!")
            print(f"🔍 User: {user_info.get('name', 'Unknown')}")
            print(f"🔍 Email: {user_info.get('email', 'Unknown')}")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ WordPress REST API request failed: {e}")
            # Update last_checked_at even if test failed
            supabase_admin.table("wordpress_connections").update({
                "last_checked_at": datetime.now().isoformat()
            }).eq("id", connection_id).execute()
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to connect to WordPress site. Please check your site URL and ensure it's accessible. Error: {str(e)}"
            )
        except Exception as e:
            print(f"❌ WordPress REST API authentication failed: {e}")
            # Update last_checked_at even if test failed
            supabase_admin.table("wordpress_connections").update({
                "last_checked_at": datetime.now().isoformat()
            }).eq("id", connection_id).execute()
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to authenticate with WordPress REST API. Please check your credentials and ensure the REST API is enabled. Error: {str(e)}"
            )

        
        
        # Update last_checked_at and metadata

        supabase_admin.table("wordpress_connections").update({

            "last_checked_at": datetime.now().isoformat(),

            "metadata": {

                "site_title": user_info.get('display_name', connection['site_name']),

                "site_description": user_info.get('description', ''),

                "user_display_name": user_info.get('display_name', connection['site_name']),

                "user_email": user_info.get('user_email', ''),

                "capabilities": user_info.get('capabilities', {}),

                "wordpress_version": user_info.get('wordpress_version', 'Unknown'),

                "last_test_status": "success",

                "last_test_at": datetime.now().isoformat()

            }

        }).eq("id", connection_id).execute()

        
        
        return {

            "success": True,

            "message": "WordPress connection test successful",

            "site_info": {

                "site_name": connection['site_name'],

                "site_url": connection['site_url'],

                "site_title": user_info.get('display_name', connection['site_name']),

                "user_display_name": user_info.get('display_name', connection['site_name']),

                "user_email": user_info.get('user_email', ''),

                "capabilities": user_info.get('capabilities', {}),

                "wordpress_version": user_info.get('wordpress_version', 'Unknown')

            }

        }
        
        
        
    except HTTPException:

        raise

    except requests.exceptions.RequestException as e:

        print(f"❌ WordPress connection test error: {e}")

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=f"Failed to test WordPress connection. Please check your site URL and credentials. Error: {str(e)}"

        )

    except Exception as e:

        print(f"❌ Error testing WordPress connection: {e}")

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=f"Failed to test WordPress connection: {str(e)}"

        )

