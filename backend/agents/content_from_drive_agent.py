"""
Content from Drive Agent using LangGraph
Automatically processes photos from Google Drive and creates scheduled posts
Scans the 'emily' folder for platform-specific subfolders and processes images
"""

import json
import asyncio
import logging
import base64
import uuid
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, TypedDict
from dataclasses import dataclass
from enum import Enum

import openai
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from supabase import create_client, Client
import httpx
import os
from dotenv import load_dotenv

# Google Drive imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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

# Platform folder name mappings
PLATFORM_FOLDER_MAPPING = {
    "instagram": "instagram",
    "facebook": "facebook",
    "youtube": "youtube",
    "twitter": "twitter",
    "x": "twitter",  # Alternative name
    "linkedin": "linkedin",
    "tiktok": "tiktok",
    "pinterest": "pinterest"
}

# Platform name normalization for frontend compatibility
PLATFORM_NAME_NORMALIZATION = {
    "instagram": "instagram",
    "facebook": "facebook",
    "youtube": "youtube",
    "twitter": "twitter",
    "x": "twitter",
    "x (twitter)": "twitter",
    "linkedin": "linkedin",
    "pinterest": "pinterest",
    "tiktok": "tiktok",
    "whatsapp": "whatsapp",
    "whatsapp business": "whatsapp",
    "google business profile": "google business profile",
    "google business": "google business profile",
    "google": "google business profile",
    "snapchat": "snapchat",
    "quora": "quora",
    "reddit": "reddit",
}

def normalize_platform_name(platform: str) -> str:
    """Normalize platform name to match frontend expectations"""
    if not platform:
        return platform
    
    platform_lower = platform.lower().strip()
    return PLATFORM_NAME_NORMALIZATION.get(platform_lower, platform_lower)

class ProcessingStep(str, Enum):
    INITIALIZE = "initialize"
    CHECK_DRIVE_CONNECTION = "check_drive_connection"
    SCAN_EMILY_FOLDER = "scan_emily_folder"
    FIND_PLATFORM_FOLDERS = "find_platform_folders"
    PROCESS_PLATFORM_FOLDER = "process_platform_folder"
    PARSE_FILENAMES = "parse_filenames"
    ANALYZE_PHOTOS = "analyze_photos"
    GENERATE_CAPTIONS = "generate_captions"
    SCHEDULE_POSTS = "schedule_posts"
    COMPLETE = "complete"
    ERROR = "error"

class ContentFromDriveState(TypedDict):
    """State for the content from drive processing"""
    user_id: str
    current_step: ProcessingStep
    google_credentials: Optional[Credentials]
    emily_folder_id: Optional[str]
    platform_folders: Dict[str, str]  # platform -> folder_id
    connected_platforms: List[str]
    files_to_process: List[Dict[str, Any]]  # List of files with parsed info
    carousel_posts_to_process: List[Dict[str, Any]]  # List of carousel posts to process
    processed_files: List[Dict[str, Any]]  # Files that have been processed
    analyzed_photos: List[Dict[str, Any]]  # Photos with analysis
    generated_posts: List[Dict[str, Any]]  # Generated post data
    saved_posts: List[str]  # Post IDs that were saved
    error_message: Optional[str]
    progress_percentage: int
    current_platform: Optional[str]
    current_file_index: int

class ContentFromDriveAgent:
    """Content from Drive Agent using LangGraph"""
    
    def __init__(self, openai_api_key: str):
        self.openai_api_key = openai_api_key
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.supabase = supabase
        # Initialize token tracker for usage tracking
        if supabase_url and supabase_key:
            from services.token_usage_service import TokenUsageService
            self.token_tracker = TokenUsageService(supabase_url, supabase_key)
        else:
            self.token_tracker = None
        
    def create_graph(self) -> StateGraph:
        """Create the LangGraph workflow"""
        graph = StateGraph(ContentFromDriveState)
        
        # Add nodes
        graph.add_node("initialize", self.initialize)
        graph.add_node("check_drive_connection", self.check_drive_connection)
        graph.add_node("scan_emily_folder", self.scan_emily_folder)
        graph.add_node("find_platform_folders", self.find_platform_folders)
        graph.add_node("process_platform_folder", self.process_platform_folder)
        graph.add_node("parse_filenames", self.parse_filenames)
        graph.add_node("analyze_photos", self.analyze_photos)
        graph.add_node("generate_captions", self.generate_captions)
        graph.add_node("schedule_posts", self.schedule_posts)
        graph.add_node("complete", self.complete)
        graph.add_node("handle_error", self.handle_error)
        
        # Set entry point
        graph.set_entry_point("initialize")
        
        # Add edges
        graph.add_edge("initialize", "check_drive_connection")
        graph.add_edge("check_drive_connection", "scan_emily_folder")
        graph.add_edge("scan_emily_folder", "find_platform_folders")
        graph.add_edge("find_platform_folders", "process_platform_folder")
        graph.add_edge("process_platform_folder", "parse_filenames")
        graph.add_edge("parse_filenames", "analyze_photos")
        graph.add_edge("analyze_photos", "generate_captions")
        graph.add_edge("generate_captions", "schedule_posts")
        graph.add_edge("schedule_posts", "complete")
        graph.add_edge("handle_error", END)
        graph.add_edge("complete", END)
        
        return graph.compile()
    
    async def initialize(self, state: ContentFromDriveState) -> ContentFromDriveState:
        """Initialize the processing state"""
        try:
            state["current_step"] = ProcessingStep.INITIALIZE
            state["progress_percentage"] = 0
            state["platform_folders"] = {}
            state["files_to_process"] = []
            state["processed_files"] = []
            state["analyzed_photos"] = []
            state["generated_posts"] = []
            state["saved_posts"] = []
            state["current_file_index"] = 0
            
            # Get user's connected platforms
            user_id = state["user_id"]
            response = self.supabase.table("platform_connections").select("platform").eq("user_id", user_id).eq("is_active", True).execute()
            
            if response.data:
                connected_platforms = [conn["platform"].lower() for conn in response.data]
                state["connected_platforms"] = connected_platforms
            else:
                state["connected_platforms"] = []
                state["error_message"] = "No active platform connections found"
                state["current_step"] = ProcessingStep.ERROR
                return state
            
            logger.info(f"Initialized for user {user_id} with platforms: {state['connected_platforms']}")
            return state
            
        except Exception as e:
            logger.error(f"Error in initialize: {e}")
            state["error_message"] = f"Initialization failed: {str(e)}"
            state["current_step"] = ProcessingStep.ERROR
            return state
    
    async def check_drive_connection(self, state: ContentFromDriveState) -> ContentFromDriveState:
        """Check and get Google Drive credentials"""
        try:
            state["current_step"] = ProcessingStep.CHECK_DRIVE_CONNECTION
            state["progress_percentage"] = 10
            
            user_id = state["user_id"]
            
            # Get Google connection from database
            response = self.supabase.table("platform_connections").select("*").eq("platform", "google").eq("user_id", user_id).eq("is_active", True).execute()
            
            if not response.data:
                state["error_message"] = "No active Google connection found. Please connect your Google account first."
                state["current_step"] = ProcessingStep.ERROR
                return state
            
            conn = response.data[0]
            
            # Decrypt tokens using the same method as google_connections.py
            from routers.google_connections import decrypt_token, get_google_credentials_from_token, refresh_and_update_tokens
            
            try:
                access_token = decrypt_token(conn['access_token_encrypted'])
                refresh_token = decrypt_token(conn['refresh_token_encrypted']) if conn.get('refresh_token_encrypted') else None
            except Exception as decrypt_error:
                logger.error(f"Failed to decrypt tokens: {decrypt_error}")
                state["error_message"] = "Failed to decrypt Google credentials. Please reconnect your Google account."
                state["current_step"] = ProcessingStep.ERROR
                return state
            
            # Create credentials using the helper function
            try:
                credentials = get_google_credentials_from_token(access_token, refresh_token)
                
                # Try to refresh and update tokens if needed
                if credentials.expired and credentials.refresh_token:
                    logger.info("Credentials expired, attempting to refresh...")
                    try:
                        credentials.refresh(Request())
                        # Update database with new tokens
                        refresh_and_update_tokens(user_id, credentials)
                        logger.info("Tokens refreshed and updated successfully")
                    except Exception as refresh_error:
                        logger.error(f"Token refresh failed: {refresh_error}")
                        # Check if it's an unauthorized_client error (usually means local/prod mismatch)
                        error_str = str(refresh_error)
                        if "unauthorized_client" in error_str.lower():
                            # This usually means tokens were created with different OAuth credentials
                            # (e.g., production tokens being used with local credentials or vice versa)
                            logger.warning("OAuth client mismatch detected. This may be due to local/production environment differences.")
                            logger.warning("Attempting to use existing token without refresh...")
                            # Don't fail immediately - try to use the existing token
                            # The token might still work for API calls even if refresh fails
                        else:
                            # For other errors, log but continue
                            logger.warning(f"Token refresh failed but continuing: {refresh_error}")
                
            except Exception as cred_error:
                logger.error(f"Failed to create credentials: {cred_error}")
                error_msg = str(cred_error)
                if "unauthorized_client" in error_msg.lower():
                    state["error_message"] = "Google authentication failed. This may be due to using production tokens with local credentials (or vice versa). Please reconnect your Google account in Settings to create new tokens for this environment."
                else:
                    state["error_message"] = f"Failed to authenticate with Google Drive: {error_msg}. Please reconnect your Google account."
                state["current_step"] = ProcessingStep.ERROR
                return state
            
            state["google_credentials"] = credentials
            
            logger.info(f"Google Drive credentials obtained for user {user_id}")
            return state
            
        except Exception as e:
            logger.error(f"Error in check_drive_connection: {e}")
            state["error_message"] = f"Failed to connect to Google Drive: {str(e)}"
            state["current_step"] = ProcessingStep.ERROR
            return state
    
    async def scan_emily_folder(self, state: ContentFromDriveState) -> ContentFromDriveState:
        """Scan Google Drive for the 'emily' folder"""
        try:
            state["current_step"] = ProcessingStep.SCAN_EMILY_FOLDER
            state["progress_percentage"] = 20
            
            credentials = state["google_credentials"]
            
            # Try to build the service - this will fail if credentials are invalid
            # Build Drive service with cache disabled to ensure fresh downloads
            try:
                service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
            except Exception as build_error:
                logger.error(f"Failed to build Drive service: {build_error}")
                error_str = str(build_error)
                if "unauthorized_client" in error_str.lower() or "invalid_grant" in error_str.lower():
                    state["error_message"] = "Google Drive authentication failed. The tokens may have been created with different OAuth credentials (local vs production). Please reconnect your Google account in Settings."
                else:
                    state["error_message"] = f"Failed to connect to Google Drive: {error_str}. Please reconnect your Google account."
                state["current_step"] = ProcessingStep.ERROR
                return state
            
            # Search for folder named 'emily' (case-insensitive search)
            # First try exact match
            query = "name='emily' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = service.files().list(q=query, fields="files(id, name, parents)").execute()
            files = results.get('files', [])
            
            # If not found, try case-insensitive by getting all folders and filtering
            if not files:
                logger.info("Exact match not found, searching all folders...")
                query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
                all_folders = service.files().list(q=query, fields="files(id, name, parents)", pageSize=1000).execute()
                all_files = all_folders.get('files', [])
                
                # Filter for folders named 'emily' (case-insensitive)
                files = [f for f in all_files if f.get('name', '').lower() == 'emily']
                logger.info(f"Found {len(files)} folder(s) named 'emily' (case-insensitive)")
            
            if not files:
                state["error_message"] = "No 'emily' folder found in Google Drive. Please create a folder named 'emily' in your Drive."
                state["current_step"] = ProcessingStep.ERROR
                logger.error("No 'emily' folder found in Google Drive")
                return state
            
            # Use the first 'emily' folder found (prefer root level if multiple exist)
            emily_folder = files[0]
            state["emily_folder_id"] = emily_folder['id']
            
            logger.info(f"✅ Found emily folder: {emily_folder['name']} (ID: {emily_folder['id']})")
            return state
            
        except Exception as e:
            logger.error(f"Error in scan_emily_folder: {e}")
            state["error_message"] = f"Failed to scan for emily folder: {str(e)}"
            state["current_step"] = ProcessingStep.ERROR
            return state
    
    async def find_platform_folders(self, state: ContentFromDriveState) -> ContentFromDriveState:
        """Find platform-specific folders inside the emily folder"""
        try:
            state["current_step"] = ProcessingStep.FIND_PLATFORM_FOLDERS
            state["progress_percentage"] = 30
            
            credentials = state["google_credentials"]
            emily_folder_id = state["emily_folder_id"]
            connected_platforms = state["connected_platforms"]
            
            # Build Drive service with cache disabled to ensure fresh downloads
            service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
            
            # Get all folders inside emily folder
            query = f"'{emily_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = service.files().list(q=query, fields="files(id, name)").execute()
            folders = results.get('files', [])
            
            logger.info(f"Found {len(folders)} folder(s) inside 'emily' folder: {[f['name'] for f in folders]}")
            logger.info(f"Connected platforms: {connected_platforms}")
            
            platform_folders = {}
            
            # Match folder names to connected platforms (case-insensitive)
            for folder in folders:
                folder_name_lower = folder['name'].lower().strip()
                for platform in connected_platforms:
                    platform_lower = platform.lower().strip()
                    # Check if folder name matches platform (case-insensitive)
                    if folder_name_lower == platform_lower or folder_name_lower == PLATFORM_FOLDER_MAPPING.get(platform_lower, platform_lower):
                        platform_folders[platform] = folder['id']
                        logger.info(f"✅ Matched platform folder: '{folder['name']}' -> platform: {platform} (ID: {folder['id']})")
                        break
            
            if not platform_folders:
                found_folder_names = [f['name'] for f in folders]
                state["error_message"] = f"No matching platform folders found in 'emily' folder. Found folders: {found_folder_names}. Connected platforms: {connected_platforms}"
                state["current_step"] = ProcessingStep.ERROR
                logger.error(f"No platform folders matched. Found: {found_folder_names}, Connected: {connected_platforms}")
                return state
            
            logger.info(f"✅ Found {len(platform_folders)} matching platform folder(s): {list(platform_folders.keys())}")
            
            state["platform_folders"] = platform_folders
            return state
            
        except Exception as e:
            logger.error(f"Error in find_platform_folders: {e}")
            state["error_message"] = f"Failed to find platform folders: {str(e)}"
            state["current_step"] = ProcessingStep.ERROR
            return state
    
    async def _is_file_already_processed(self, user_id: str, file_id: str = None, file_name: str = None, folder_name: str = None) -> bool:
        """Check if a file or carousel folder has already been processed by checking content_posts metadata"""
        try:
            # Get campaign ID for this user's drive content
            campaign_response = self.supabase.table("content_campaigns").select("id").eq("user_id", user_id).eq("campaign_name", "Drive Content").execute()
            
            if not campaign_response.data:
                # No campaign exists, so no files processed yet
                return False
            
            campaign_id = campaign_response.data[0]["id"]
            
            # Query posts in this campaign and check metadata
            posts_response = self.supabase.table("content_posts").select("metadata").eq("campaign_id", campaign_id).execute()
            
            for post in posts_response.data:
                metadata = post.get("metadata", {})
                if metadata.get("generated_by") == "content_from_drive_agent":
                    # Check by file_id first (most reliable) for regular images
                    if file_id and metadata.get("file_id") == file_id:
                        logger.info(f"File {file_name or 'unknown'} (ID: {file_id}) already processed - skipping")
                        return True
                    # Check by file_name for regular images
                    if file_name and metadata.get("file_name") == file_name:
                        logger.info(f"File {file_name} already processed (by name) - skipping")
                        return True
                    # Check by folder_name for carousel posts
                    if folder_name and metadata.get("folder_name") == folder_name:
                        logger.info(f"Carousel folder {folder_name} already processed - skipping")
                        return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking if file/folder is processed: {e}")
            # On error, assume not processed to avoid blocking new files
            return False
    
    async def _process_carousel_folder(self, credentials, platform_folder_id: str, platform: str, user_id: str) -> List[Dict[str, Any]]:
        """Process carousel folder and collect all carousel subfolders with their images"""
        carousel_posts = []
        
        try:
            # Build Drive service with cache disabled to ensure fresh downloads
            service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
            
            # Get all folders inside platform folder and filter for those starting with "carousel"
            all_folders_query = f"'{platform_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            all_folders = service.files().list(q=all_folders_query, fields="files(id, name)").execute()
            
            # Filter folders that start with "carousel" (case-insensitive)
            carousel_folders = []
            for folder in all_folders.get('files', []):
                folder_name_lower = folder['name'].lower().strip()
                if folder_name_lower.startswith('carousel'):
                    carousel_folders.append(folder)
            
            if not carousel_folders:
                logger.info(f"No carousel folders found in {platform} folder (folders starting with 'carousel')")
                return carousel_posts
            
            logger.info(f"Found {len(carousel_folders)} carousel folder(s) in {platform}")
            
            # Process each carousel folder (these should be named like "carousel_description_date")
            for carousel_folder in carousel_folders:
                subfolder_id = carousel_folder['id']
                subfolder_name = carousel_folder['name']
                
                logger.info(f"Processing carousel folder: {subfolder_name} (ID: {subfolder_id})")
                
                # Parse folder name: "carousel_description_date"
                # Remove "carousel_" prefix (case-insensitive)
                folder_name_clean = subfolder_name
                folder_name_lower = subfolder_name.lower().strip()
                if folder_name_lower.startswith('carousel_'):
                    # Remove "carousel_" prefix (preserve original case for description)
                    folder_name_clean = subfolder_name[len('carousel_'):].strip()
                elif folder_name_lower.startswith('carousel'):
                    # Handle case where there's no underscore after "carousel"
                    folder_name_clean = subfolder_name[len('carousel'):].strip('_ ').strip()
                
                # Parse description and date from folder name
                parsed = self.parse_filename(folder_name_clean)
                description = parsed.get("description", folder_name_clean)
                date_obj = parsed.get("date")
                
                logger.info(f"Parsed carousel folder '{subfolder_name}': description='{description}', date={date_obj}")
                
                # Get all images from this carousel folder
                image_mime_types = [
                    'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
                    'image/webp', 'image/bmp', 'image/svg+xml'
                ]
                mime_query = " or ".join([f"mimeType='{mime}'" for mime in image_mime_types])
                images_query = f"'{subfolder_id}' in parents and ({mime_query}) and trashed=false"
                
                images = service.files().list(q=images_query, fields="files(id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink)").execute()
                image_files = images.get('files', [])
                
                if not image_files:
                    logger.warning(f"No images found in carousel folder: {subfolder_name}")
                    continue
                
                logger.info(f"Found {len(image_files)} image(s) in carousel folder: {subfolder_name}")
                
                # Check if this carousel folder is already processed (check by folder name)
                if await self._is_file_already_processed(user_id, folder_name=subfolder_name):
                    logger.info(f"Carousel folder {subfolder_name} already processed - skipping")
                    continue
                
                # Collect all images for this carousel
                carousel_images = []
                for img_file in image_files:
                    carousel_images.append({
                        "file_id": img_file['id'],
                        "file_name": img_file['name'],
                        "mime_type": img_file.get('mimeType', ''),
                        "size": img_file.get('size', 0),
                        "modified_time": img_file.get('modifiedTime', ''),
                        "web_view_link": img_file.get('webViewLink', ''),
                        "thumbnail_link": img_file.get('thumbnailLink', '')
                    })
                
                # Create carousel post entry
                carousel_posts.append({
                    "post_type": "carousel",
                    "platform": platform,
                    "folder_name": subfolder_name,
                    "description": description,
                    "date": date_obj,
                    "date_string": parsed.get("date_string"),
                    "images": carousel_images,  # All images for this carousel
                    "total_images": len(carousel_images)
                })
                
                logger.info(f"✅ Prepared carousel post: {subfolder_name} with {len(carousel_images)} images")
            
            return carousel_posts
            
        except Exception as e:
            logger.error(f"Error processing carousel folder: {e}")
            return carousel_posts
    
    async def process_platform_folder(self, state: ContentFromDriveState) -> ContentFromDriveState:
        """Process each platform folder and collect image files and carousel posts"""
        try:
            state["current_step"] = ProcessingStep.PROCESS_PLATFORM_FOLDER
            state["progress_percentage"] = 40
            
            credentials = state["google_credentials"]
            platform_folders = state["platform_folders"]
            user_id = state["user_id"]
            
            # Build Drive service with cache disabled to ensure fresh downloads
            service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
            
            files_to_process = []
            carousel_posts_to_process = []
            skipped_files = []
            
            # Process each platform folder
            for platform, folder_id in platform_folders.items():
                # First, check for carousel folder and process carousel posts
                carousel_posts = await self._process_carousel_folder(credentials, folder_id, platform, user_id)
                carousel_posts_to_process.extend(carousel_posts)
                
                # Then, get regular image files from this folder (excluding carousel folder)
                # Supported image MIME types
                image_mime_types = [
                    'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
                    'image/webp', 'image/bmp', 'image/svg+xml'
                ]
                
                mime_query = " or ".join([f"mimeType='{mime}'" for mime in image_mime_types])
                # Exclude carousel folder from regular image search
                query = f"'{folder_id}' in parents and ({mime_query}) and trashed=false"
                
                logger.info(f"Searching for regular images in {platform} folder (ID: {folder_id})...")
                results = service.files().list(q=query, fields="files(id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink)").execute()
                files = results.get('files', [])
                
                logger.info(f"Found {len(files)} regular image file(s) in {platform} folder")
                
                for file in files:
                    file_id = file['id']
                    file_name = file['name']
                    
                    # Check if file already processed
                    if await self._is_file_already_processed(user_id, file_id, file_name):
                        skipped_files.append(file_name)
                        continue
                    
                    files_to_process.append({
                        "file_id": file_id,
                        "file_name": file_name,
                        "platform": platform,
                        "mime_type": file.get('mimeType', ''),
                        "size": file.get('size', 0),
                        "modified_time": file.get('modifiedTime', ''),
                        "web_view_link": file.get('webViewLink', ''),
                        "thumbnail_link": file.get('thumbnailLink', ''),
                        "post_type": "image"  # Regular image post
                    })
                    logger.info(f"  - {file_name} ({file.get('mimeType', 'unknown type')}) - NEW")
            
            if skipped_files:
                logger.info(f"Skipped {len(skipped_files)} already processed file(s): {', '.join(skipped_files[:5])}{'...' if len(skipped_files) > 5 else ''}")
            
            if not files_to_process and not carousel_posts_to_process:
                if skipped_files:
                    state["error_message"] = f"All {len(skipped_files)} image files have already been processed. No new files to process."
                else:
                    state["error_message"] = "No image files found in platform folders"
                state["current_step"] = ProcessingStep.ERROR
                return state
            
            state["files_to_process"] = files_to_process
            state["carousel_posts_to_process"] = carousel_posts_to_process  # Store carousel posts separately
            logger.info(f"Found {len(files_to_process)} new regular files and {len(carousel_posts_to_process)} carousel posts to process (skipped {len(skipped_files)} already processed)")
            return state
            
        except Exception as e:
            logger.error(f"Error in process_platform_folder: {e}")
            state["error_message"] = f"Failed to process platform folders: {str(e)}"
            state["current_step"] = ProcessingStep.ERROR
            return state
    
    def parse_filename(self, filename: str) -> Dict[str, Any]:
        """
        Parse filename in format: description_date.png
        Date format at the end: "9 dec", "9 Dec", "9 December", "9 dec 2024", etc.
        Returns: {description: str, date: datetime, extension: str}
        """
        try:
            # Remove extension
            name_without_ext = os.path.splitext(filename)[0]
            extension = os.path.splitext(filename)[1].lower()
            
            date_str = None
            date_obj = None
            
            # Month abbreviations and full names (case-insensitive)
            months = {
                'jan': 1, 'january': 1,
                'feb': 2, 'february': 2,
                'mar': 3, 'march': 3,
                'apr': 4, 'april': 4,
                'may': 5,
                'jun': 6, 'june': 6,
                'jul': 7, 'july': 7,
                'aug': 8, 'august': 8,
                'sep': 9, 'september': 9,
                'oct': 10, 'october': 10,
                'nov': 11, 'november': 11,
                'dec': 12, 'december': 12
            }
            
            # First try standard date patterns (YYYY-MM-DD, etc.)
            date_patterns = [
                r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
                r'(\d{4}_\d{2}_\d{2})',  # YYYY_MM_DD
                r'(\d{2}-\d{2}-\d{4})',  # MM-DD-YYYY
                r'(\d{2}_\d{2}_\d{4})',  # MM_DD_YYYY
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, name_without_ext)
                if match:
                    date_str = match.group(1)
                    try:
                        # Try different date formats
                        for fmt in ['%Y-%m-%d', '%Y_%m_%d', '%m-%d-%Y', '%m_%d_%Y']:
                            try:
                                date_obj = datetime.strptime(date_str, fmt)
                                break
                            except ValueError:
                                continue
                    except:
                        pass
                    if date_obj:
                        break
            
            # If no standard pattern found, try "day month" or "day month year" format at the end
            if not date_obj:
                # Pattern to match date at the end: "9 dec", "9 Dec", "9 dec 2024", "09 dec", etc.
                # Look for patterns like: _9 dec, _9 Dec, _9 dec 2024, _09 dec, etc.
                date_patterns_text = [
                    r'_(\d{1,2})\s+([a-zA-Z]{3,9})(?:\s+(\d{4}))?$',  # _9 dec or _9 dec 2024
                    r'-(\d{1,2})\s+([a-zA-Z]{3,9})(?:\s+(\d{4}))?$',  # -9 dec or -9 dec 2024
                    r'(\d{1,2})\s+([a-zA-Z]{3,9})(?:\s+(\d{4}))?$',   # 9 dec or 9 dec 2024 (at end)
                ]
                
                for pattern in date_patterns_text:
                    match = re.search(pattern, name_without_ext, re.IGNORECASE)
                    if match:
                        day = int(match.group(1))
                        month_str = match.group(2).lower()
                        year_str = match.group(3) if len(match.groups()) >= 3 and match.group(3) else None
                        
                        # Find month number
                        month = None
                        for month_name, month_num in months.items():
                            if month_str.startswith(month_name):
                                month = month_num
                                break
                        
                        if month:
                            # Use provided year or current year
                            if year_str:
                                year = int(year_str)
                            else:
                                year = datetime.now().year
                            
                            try:
                                date_obj = datetime(year, month, day)
                                date_str = match.group(0).strip('-_')
                                break
                            except ValueError:
                                # Invalid date (e.g., Feb 30)
                                continue
            
            # Extract description (everything before the date)
            if date_str:
                # Remove the date part from the end
                description = name_without_ext
                # Try to remove the date pattern
                for pattern in [r'_\d{1,2}\s+[a-zA-Z]{3,9}(?:\s+\d{4})?$', 
                               r'-\d{1,2}\s+[a-zA-Z]{3,9}(?:\s+\d{4})?$',
                               r'\d{1,2}\s+[a-zA-Z]{3,9}(?:\s+\d{4})?$']:
                    description = re.sub(pattern, '', description, flags=re.IGNORECASE)
                description = description.strip('-_ ').strip()
            else:
                description = name_without_ext.strip()
            
            return {
                "description": description if description else "Untitled",
                "date": date_obj,
                "date_string": date_str,
                "extension": extension
            }
            
        except Exception as e:
            logger.error(f"Error parsing filename {filename}: {e}")
            return {
                "description": filename,
                "date": None,
                "date_string": None,
                "extension": os.path.splitext(filename)[1].lower()
            }
    
    async def parse_filenames(self, state: ContentFromDriveState) -> ContentFromDriveState:
        """Parse filenames to extract description and date"""
        try:
            state["current_step"] = ProcessingStep.PARSE_FILENAMES
            state["progress_percentage"] = 50
            
            files_to_process = state["files_to_process"]
            parsed_files = []
            
            for file_info in files_to_process:
                parsed = self.parse_filename(file_info["file_name"])
                file_info.update(parsed)
                parsed_files.append(file_info)
            
            state["files_to_process"] = parsed_files
            logger.info(f"Parsed {len(parsed_files)} filenames")
            return state
            
        except Exception as e:
            logger.error(f"Error in parse_filenames: {e}")
            state["error_message"] = f"Failed to parse filenames: {str(e)}"
            state["current_step"] = ProcessingStep.ERROR
            return state
    
    async def analyze_photos(self, state: ContentFromDriveState) -> ContentFromDriveState:
        """Analyze photos using OpenAI Vision API (including first image from carousel posts)"""
        try:
            state["current_step"] = ProcessingStep.ANALYZE_PHOTOS
            state["progress_percentage"] = 60
            
            credentials = state["google_credentials"]
            files_to_process = state["files_to_process"]
            carousel_posts_to_process = state.get("carousel_posts_to_process", [])
            
            # Build Drive service with cache disabled to ensure fresh downloads
            service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
            analyzed_photos = []
            
            logger.info(f"Starting photo analysis: {len(files_to_process)} regular images, {len(carousel_posts_to_process)} carousel posts")
            
            # Process regular image files
            for idx, file_info in enumerate(files_to_process):
                try:
                    state["progress_percentage"] = 60 + int((idx / len(files_to_process)) * 20)
                    
                    file_id = file_info["file_id"]
                    file_name = file_info["file_name"]
                    
                    logger.info(f"📥 Downloading image: {file_name} (ID: {file_id})")
                    
                    # Download file content from Google Drive
                    request = service.files().get_media(fileId=file_id)
                    file_content = request.execute()
                    
                    logger.info(f"✅ Downloaded {len(file_content)} bytes for {file_name}")
                    
                    # Check file size (OpenAI Vision has limits - max 20MB)
                    file_size = len(file_content)
                    max_size = 20 * 1024 * 1024  # 20MB limit
                    
                    if file_size > max_size:
                        logger.warning(f"⚠️ File {file_name} is too large ({file_size} bytes), using thumbnail for analysis")
                        # Use thumbnail URL if available
                        if file_info.get("thumbnail_link"):
                            image_url = file_info.get("thumbnail_link")
                            image_content = [{
                                "type": "image_url",
                                "image_url": {"url": image_url}
                            }]
                        else:
                            # Skip if too large and no thumbnail
                            analyzed_photos.append({
                                **file_info,
                                "analysis": "Image too large for analysis. Please use a smaller image file."
                            })
                            continue
                    else:
                        # Convert downloaded image to base64 for OpenAI Vision
                        image_base64 = base64.b64encode(file_content).decode('utf-8')
                        mime_type = file_info.get("mime_type", "image/jpeg")
                        
                        # Create data URL for OpenAI Vision API
                        image_data_url = f"data:{mime_type};base64,{image_base64}"
                        
                        image_content = [{
                            "type": "image_url",
                            "image_url": {
                                "url": image_data_url
                            }
                        }]
                        
                        logger.info(f"🖼️ Converted {file_name} to base64 ({len(image_base64)} chars), ready for ChatGPT analysis")
                    
                    # Analyze with OpenAI Vision (using gpt-4o-mini - the current vision model)
                    response = self.client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Analyze this image in detail. Describe what you see, the mood, colors, composition, any text visible, and suggest what kind of social media post this would be good for. Be specific and detailed."
                                    }
                                ] + image_content
                            }
                        ],
                        max_tokens=500
                    )
                    
                    analysis = response.choices[0].message.content
                    
                    # Track token usage (non-blocking)
                    if self.token_tracker and state.get("user_id"):
                        try:
                            import asyncio
                            asyncio.create_task(
                                self.token_tracker.track_chat_completion_usage(
                                    user_id=state["user_id"],
                                    feature_type="content_generation",
                                    model_name="gpt-4o-mini",
                                    response=response,
                                    request_metadata={"action": "analyze_photo", "file_name": file_name}
                                )
                            )
                        except Exception as e:
                            logger.error(f"Error tracking token usage: {str(e)}")
                    
                    analyzed_photos.append({
                        **file_info,
                        "analysis": analysis,
                        "image_bytes": file_content if file_size <= max_size else None  # Store image bytes for later upload
                    })
                    
                    logger.info(f"Analyzed photo {idx + 1}/{len(files_to_process)}: {file_info['file_name']}")
                    
                except Exception as e:
                    logger.error(f"Error analyzing photo {file_info['file_name']}: {e}")
                    # Continue with other photos even if one fails
                    analyzed_photos.append({
                        **file_info,
                        "analysis": f"Error analyzing image: {str(e)}",
                        "post_type": "image"
                    })
            
            # Process carousel posts - analyze first image from each carousel
            if carousel_posts_to_process:
                logger.info(f"🔄 Processing {len(carousel_posts_to_process)} carousel post(s)...")
                total_items = len(files_to_process) + len(carousel_posts_to_process)
                carousel_start_idx = len(files_to_process)
                
                for idx, carousel_post in enumerate(carousel_posts_to_process):
                    try:
                        carousel_idx = carousel_start_idx + idx
                        state["progress_percentage"] = 60 + int((carousel_idx / total_items) * 20) if total_items > 0 else 80
                        
                        if not carousel_post.get("images") or len(carousel_post["images"]) == 0:
                            logger.warning(f"Carousel post {carousel_post.get('folder_name', 'unknown')} has no images - skipping")
                            continue
                        
                        # Get first image for analysis
                        first_image = carousel_post["images"][0]
                        file_id = first_image["file_id"]
                        file_name = first_image["file_name"]
                        
                        logger.info(f"📥 Downloading first image from carousel: {file_name} (ID: {file_id})")
                        
                        # Download first image for analysis
                        request = service.files().get_media(fileId=file_id)
                        file_content = request.execute()
                        file_size = len(file_content)
                        max_size = 20 * 1024 * 1024  # 20MB limit
                        
                        logger.info(f"✅ Downloaded {len(file_content)} bytes for first carousel image: {file_name}")
                        
                        if file_size > max_size:
                            logger.warning(f"⚠️ First image in carousel {carousel_post.get('folder_name')} is too large, using thumbnail")
                            if first_image.get("thumbnail_link"):
                                image_url = first_image.get("thumbnail_link")
                                image_content = [{
                                    "type": "image_url",
                                    "image_url": {"url": image_url}
                                }]
                            else:
                                analyzed_photos.append({
                                    **carousel_post,
                                    "analysis": "First image too large for analysis",
                                    "post_type": "carousel"
                                })
                                continue
                        else:
                            # Convert to base64 for OpenAI Vision
                            image_base64 = base64.b64encode(file_content).decode('utf-8')
                            mime_type = first_image.get("mime_type", "image/jpeg")
                            image_data_url = f"data:{mime_type};base64,{image_base64}"
                            image_content = [{
                                "type": "image_url",
                                "image_url": {"url": image_data_url}
                            }]
                            logger.info(f"🖼️ Converted first carousel image to base64 ({len(image_base64)} chars), ready for ChatGPT analysis")
                        
                        # Analyze with OpenAI Vision
                        response = self.client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "Analyze this image in detail. This is the first image of a carousel post. Describe what you see, the mood, colors, composition, any text visible, and suggest what kind of social media carousel post this would be good for. Be specific and detailed, considering this is part of a multi-image sequence."
                                        }
                                    ] + image_content
                                }
                            ],
                            max_tokens=500
                        )
                        
                        analysis = response.choices[0].message.content
                        
                        # Track token usage (non-blocking)
                        if self.token_tracker and state.get("user_id"):
                            try:
                                import asyncio
                                asyncio.create_task(
                                    self.token_tracker.track_chat_completion_usage(
                                        user_id=state["user_id"],
                                        feature_type="content_generation",
                                        model_name="gpt-4o-mini",
                                        response=response,
                                        request_metadata={"action": "analyze_carousel_photo", "folder_name": carousel_post.get("folder_name")}
                                    )
                                )
                            except Exception as e:
                                logger.error(f"Error tracking token usage: {str(e)}")
                        
                        # Download all carousel images for later upload to Supabase
                        carousel_image_bytes = []
                        logger.info(f"📥 Downloading all {len(carousel_post['images'])} images for carousel post...")
                        for img_idx, img in enumerate(carousel_post["images"]):
                            try:
                                img_request = service.files().get_media(fileId=img["file_id"])
                                img_content = img_request.execute()
                                if len(img_content) <= max_size:
                                    carousel_image_bytes.append({
                                        "file_id": img["file_id"],
                                        "file_name": img["file_name"],
                                        "bytes": img_content,
                                        "mime_type": img.get("mime_type", "image/jpeg")
                                    })
                                    logger.info(f"✅ Downloaded carousel image {img_idx + 1}/{len(carousel_post['images'])}: {img['file_name']}")
                                else:
                                    logger.warning(f"⚠️ Carousel image {img['file_name']} is too large, skipping upload")
                            except Exception as e:
                                logger.error(f"Error downloading image {img['file_name']} for carousel: {e}")
                        
                        analyzed_photos.append({
                            **carousel_post,
                            "analysis": analysis,
                            "first_image_file_id": file_id,
                            "first_image_file_name": file_name,
                            "carousel_image_bytes": carousel_image_bytes,  # Store all image bytes
                            "post_type": "carousel"
                        })
                        
                        logger.info(f"✅ Analyzed carousel post {idx + 1}/{len(carousel_posts_to_process)}: {carousel_post.get('folder_name')} (first image: {file_name}, total images: {len(carousel_image_bytes)})")
                    
                    except Exception as e:
                        logger.error(f"Error analyzing carousel post {carousel_post.get('folder_name', 'unknown')}: {e}")
                        analyzed_photos.append({
                            **carousel_post,
                            "analysis": f"Error analyzing carousel: {str(e)}",
                            "post_type": "carousel"
                        })
            else:
                logger.info("No carousel posts to process")
            
            state["analyzed_photos"] = analyzed_photos
            logger.info(f"✅ Photo analysis complete: {len(analyzed_photos)} items total ({len(files_to_process)} regular images + {len(carousel_posts_to_process)} carousel posts)")
            return state
            
        except Exception as e:
            logger.error(f"Error in analyze_photos: {e}")
            state["error_message"] = f"Failed to analyze photos: {str(e)}"
            state["current_step"] = ProcessingStep.ERROR
            return state
    
    async def generate_captions(self, state: ContentFromDriveState) -> ContentFromDriveState:
        """Generate captions for each photo based on description and analysis"""
        try:
            state["current_step"] = ProcessingStep.GENERATE_CAPTIONS
            state["progress_percentage"] = 80
            
            analyzed_photos = state["analyzed_photos"]
            generated_posts = []
            
            # Get user profile for context
            user_id = state["user_id"]
            profile_response = self.supabase.table("profiles").select("*").eq("id", user_id).execute()
            profile = profile_response.data[0] if profile_response.data else None
            
            for idx, photo in enumerate(analyzed_photos):
                try:
                    platform = photo["platform"]
                    post_type = photo.get("post_type", "image")
                    is_carousel = post_type == "carousel"
                    
                    # For carousel posts, use folder_name; for regular posts, use file_name
                    if is_carousel:
                        folder_name = photo.get("folder_name", "")
                        # Description and date are already parsed from folder name during processing
                        description = photo.get("description", "")
                        scheduled_date = photo.get("date")
                        # For carousel, don't use individual image file names - use folder name structure
                        file_name = folder_name  # Use folder name for display
                    else:
                        file_name = photo.get("file_name", "")
                        description = photo.get("description", "")
                        scheduled_date = photo.get("date")
                        folder_name = None  # Not applicable for regular posts
                    
                    analysis = photo.get("analysis", "")
                    
                    # Build comprehensive prompt similar to custom content agent
                    # Extract business context from profile
                    business_name = profile.get('business_name', 'Not specified') if profile else 'Not specified'
                    industry = profile.get('industry', [])
                    if isinstance(industry, list):
                        industry = ', '.join(industry) if industry else 'Not specified'
                    else:
                        industry = str(industry) if industry else 'Not specified'
                    
                    target_audience = profile.get('target_audience', [])
                    if isinstance(target_audience, list):
                        target_audience = ', '.join(target_audience) if target_audience else 'General audience'
                    else:
                        target_audience = str(target_audience) if target_audience else 'General audience'
                    
                    brand_voice = profile.get('brand_voice', 'Professional and friendly') if profile else 'Professional and friendly'
                    brand_tone = profile.get('brand_tone', 'Approachable') if profile else 'Approachable'
                    business_description = profile.get('business_description', '') if profile else ''
                    unique_value = profile.get('unique_value_proposition', '') if profile else ''
                    
                    # Build comprehensive prompt with emphasis on title generation
                    if is_carousel:
                        total_images = photo.get("total_images", 0)
                        carousel_note = f"For carousel: Create a narrative that works across all images in the sequence. The caption should tell a story that flows through the carousel."
                        prompt = f"""Create a compelling {platform} CAROUSEL post with title and caption based on the following information:

CAROUSEL INFORMATION:
- Carousel Folder Name: {folder_name}
- Description (from structured folder name): {description}
- Total Images in Carousel: {total_images}
- First Image Analysis: {analysis}
- Note: This is a carousel post with {total_images} images. The caption should work for the entire carousel sequence.
- IMPORTANT: Use the description "{description}" from the folder name as the main context. Do NOT use individual image file names.

BUSINESS CONTEXT:
- Business Name: {business_name}
- Industry: {industry}
- Business Description: {business_description[:300] if business_description else 'Not specified'}
- Unique Value Proposition: {unique_value[:200] if unique_value else 'Not specified'}
- Brand Voice: {brand_voice}
- Brand Tone: {brand_tone}
- Target Audience: {target_audience}

PLATFORM: {platform}

REQUIREMENTS:

1. TITLE (CRITICAL - DO NOT USE FOLDER NAME OR DESCRIPTION):
   - Generate a catchy, attention-grabbing title (5-10 words maximum)
   - Should be engaging and relevant to the carousel and business
   - MUST NOT simply repeat the folder name "{folder_name}" or description "{description}"
   - Should capture the essence of what makes this carousel post interesting
   - Should reflect the business context and image analysis
   - Examples of good titles: "Transforming Ideas into Reality", "Behind the Scenes: Innovation in Action", "Celebrating Our Latest Achievement", "Where Creativity Meets Technology"
   - Examples of BAD titles (DO NOT USE): "{file_name}", "{description}", "Image from Drive"

2. CAPTION:
   - Create a caption that perfectly complements and references the carousel images
   - Use the image analysis to craft engaging, visual storytelling
   - {carousel_note}
   - Optimize for {platform} best practices (consider character limits, engagement patterns, and platform culture)
   - Match the brand voice ({brand_voice}) and tone ({brand_tone})
   - Make it authentic to the business context and industry
   - Create a compelling narrative that connects the images to the business
   - Use the visual elements from the analysis to enhance the message
   - Make it engaging and shareable
   - Keep it authentic and aligned with the business's unique value proposition

3. HASHTAGS:
   - Include relevant hashtags (5-10 hashtags appropriate for {platform})
   - Mix of industry-specific, brand-specific, and trending hashtags

4. CALL TO ACTION:
   - Suggest an appropriate call to action that encourages engagement

CRITICAL INSTRUCTIONS:
- Return ONLY a valid JSON object
- Do NOT use markdown code blocks (no ```json or ```)
- Do NOT include any text before or after the JSON
- The JSON must be parseable directly
- Use these exact field names:

{{
  "title": "A catchy, original title (NOT the folder name or description - be creative and relevant!)",
  "caption": "The main post caption that references the carousel images and connects them to the business",
  "hashtags": ["array", "of", "relevant", "hashtags", "for", "{platform}"],
  "call_to_action": "Suggested call to action"
}}"""
                    else:
                        prompt = f"""Create a compelling {platform} post with title and caption based on the following information:

IMAGE INFORMATION:
- Image Filename: {file_name}
- Image Description (from filename): {description}
- Image Analysis: {analysis}

BUSINESS CONTEXT:
- Business Name: {business_name}
- Industry: {industry}
- Business Description: {business_description[:300] if business_description else 'Not specified'}
- Unique Value Proposition: {unique_value[:200] if unique_value else 'Not specified'}
- Brand Voice: {brand_voice}
- Brand Tone: {brand_tone}
- Target Audience: {target_audience}

PLATFORM: {platform}

REQUIREMENTS:

1. TITLE (CRITICAL - DO NOT USE FILENAME OR DESCRIPTION):
   - Generate a catchy, attention-grabbing title (5-10 words maximum)
   - Should be engaging and relevant to the image and business
   - MUST NOT simply repeat the filename "{file_name}" or description "{description}"
   - Should capture the essence of what makes this post interesting
   - Should reflect the business context and image analysis
   - Examples of good titles: "Transforming Ideas into Reality", "Behind the Scenes: Innovation in Action", "Celebrating Our Latest Achievement", "Where Creativity Meets Technology"
   - Examples of BAD titles (DO NOT USE): "{file_name}", "{description}", "Image from Drive"

2. CAPTION:
   - Create a caption that perfectly complements and references the image
   - Use the image analysis to craft engaging, visual storytelling
   - Optimize for {platform} best practices (consider character limits, engagement patterns, and platform culture)
   - Match the brand voice ({brand_voice}) and tone ({brand_tone})
   - Make it authentic to the business context and industry
   - Create a compelling narrative that connects the image to the business
   - Use the visual elements from the analysis to enhance the message
   - Make it engaging and shareable
   - Keep it authentic and aligned with the business's unique value proposition

3. HASHTAGS:
   - Include relevant hashtags (5-10 hashtags appropriate for {platform})
   - Mix of industry-specific, brand-specific, and trending hashtags

4. CALL TO ACTION:
   - Suggest an appropriate call to action that encourages engagement

CRITICAL INSTRUCTIONS:
- Return ONLY a valid JSON object
- Do NOT use markdown code blocks (no ```json or ```)
- Do NOT include any text before or after the JSON
- The JSON must be parseable directly
- Use these exact field names:

{{
  "title": "A catchy, original title (NOT the filename or description - be creative and relevant!)",
  "caption": "The main post caption that references the image and connects it to the business",
  "hashtags": ["array", "of", "relevant", "hashtags", "for", "{platform}"],
  "call_to_action": "Suggested call to action"
}}"""
                    
                    # Use gpt-4o-mini model (supports vision and better JSON generation)
                    # Don't use response_format as gpt-4 doesn't support it, parse JSON from response
                    response = self.client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are an expert social media content creator specializing in {platform}. Generate engaging, platform-optimized captions that connect visual content with business messaging. Always return valid JSON without markdown formatting."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=800
                    )
                    
                    # Parse JSON from response (handle markdown code blocks if present)
                    raw_response = response.choices[0].message.content.strip()
                    
                    # Try to extract JSON from markdown code blocks if present
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_response, re.DOTALL)
                    if json_match:
                        raw_response = json_match.group(0)
                    
                    content_data = json.loads(raw_response)
                    
                    # Track token usage (non-blocking)
                    if self.token_tracker and state.get("user_id"):
                        try:
                            import asyncio
                            asyncio.create_task(
                                self.token_tracker.track_chat_completion_usage(
                                    user_id=state["user_id"],
                                    feature_type="content_generation",
                                    model_name="gpt-4o-mini",
                                    response=response,
                                    request_metadata={"action": "generate_caption", "platform": platform, "is_carousel": is_carousel}
                                )
                            )
                        except Exception as e:
                            logger.error(f"Error tracking token usage: {str(e)}")
                    
                    if is_carousel:
                        # For carousel posts, include all images and carousel-specific data
                        generated_posts.append({
                            "platform": platform,
                            "post_type": "carousel",
                            "folder_name": photo.get("folder_name", ""),
                            "description": description,
                            "analysis": analysis,
                            "title": content_data.get("title", ""),
                            "caption": content_data.get("caption", ""),
                            "hashtags": content_data.get("hashtags", []),
                            "call_to_action": content_data.get("call_to_action", ""),
                            "scheduled_date": scheduled_date,
                            "images": photo.get("images", []),  # All images in carousel
                            "total_images": photo.get("total_images", 0),
                            "carousel_image_bytes": photo.get("carousel_image_bytes", []),  # All image bytes for upload
                            "first_image_file_id": photo.get("first_image_file_id"),
                            "first_image_file_name": photo.get("first_image_file_name")
                        })
                    else:
                        # For regular image posts
                        generated_posts.append({
                            "platform": platform,
                            "post_type": "image",
                            "file_id": photo.get("file_id"),
                            "file_name": photo.get("file_name", ""),
                            "description": description,
                            "analysis": analysis,
                            "title": content_data.get("title", ""),
                            "caption": content_data.get("caption", ""),
                            "hashtags": content_data.get("hashtags", []),
                            "call_to_action": content_data.get("call_to_action", ""),
                            "scheduled_date": scheduled_date,
                            "image_url": photo.get("web_view_link", ""),
                            "thumbnail_url": photo.get("thumbnail_link", ""),
                            "image_bytes": photo.get("image_bytes"),  # Include image bytes for Supabase upload
                            "mime_type": photo.get("mime_type", "image/jpeg")  # Include MIME type
                        })
                    
                    # Log with appropriate name based on post type
                    if is_carousel:
                        display_name = photo.get("folder_name", "unknown")
                    else:
                        display_name = photo.get("file_name", "unknown")
                    logger.info(f"Generated caption for {idx + 1}/{len(analyzed_photos)}: {display_name}")
                    
                except Exception as e:
                    # Log with appropriate name based on post type
                    if is_carousel:
                        display_name = photo.get("folder_name", "unknown")
                    else:
                        display_name = photo.get("file_name", "unknown")
                    logger.error(f"Error generating caption for {display_name}: {e}")
                    # Continue with other photos
                    continue
            
            state["generated_posts"] = generated_posts
            logger.info(f"Generated {len(generated_posts)} captions")
            return state
            
        except Exception as e:
            logger.error(f"Error in generate_captions: {e}")
            state["error_message"] = f"Failed to generate captions: {str(e)}"
            state["current_step"] = ProcessingStep.ERROR
            return state
    
    async def schedule_posts(self, state: ContentFromDriveState) -> ContentFromDriveState:
        """Save posts to database and schedule them"""
        try:
            state["current_step"] = ProcessingStep.SCHEDULE_POSTS
            state["progress_percentage"] = 90
            
            user_id = state["user_id"]
            generated_posts = state["generated_posts"]
            saved_posts = []
            
            # Get user profile for business context
            profile_response = self.supabase.table("profiles").select("*").eq("id", user_id).execute()
            profile = profile_response.data[0] if profile_response.data else None
            business_name = profile.get('business_name', 'Not specified') if profile else 'Not specified'
            
            # Get or create campaign
            campaign_id = await self._get_or_create_drive_content_campaign(user_id)
            
            if not campaign_id:
                logger.error(f"Failed to get or create campaign for user {user_id}")
                state["error_message"] = "Failed to create campaign for posts. Please try again."
                state["current_step"] = ProcessingStep.ERROR
                return state
            
            logger.info(f"Using campaign_id: {campaign_id} for user {user_id}")
            
            for idx, post_data in enumerate(generated_posts):
                try:
                    # Normalize platform name to match frontend expectations
                    original_platform = post_data["platform"]
                    platform = normalize_platform_name(original_platform)
                    scheduled_date = post_data.get("scheduled_date")
                    post_type = post_data.get("post_type", "image")
                    is_carousel = post_type == "carousel"
                    
                    logger.info(f"Platform normalization: '{original_platform}' -> '{platform}' for {'carousel' if is_carousel else 'image'} post {post_data.get('file_name') or post_data.get('folder_name', 'unknown')}")
                    
                    # Determine scheduled datetime
                    if scheduled_date:
                        # Use the date from filename/folder name, default to 9 AM
                        scheduled_datetime = scheduled_date.replace(hour=9, minute=0, second=0)
                    else:
                        # Default to tomorrow at 9 AM
                        scheduled_datetime = datetime.now() + timedelta(days=1)
                        scheduled_datetime = scheduled_datetime.replace(hour=9, minute=0, second=0)
                    
                    # Determine status
                    now = datetime.now()
                    if scheduled_datetime > now:
                        status = "scheduled"
                    else:
                        status = "draft"
                    
                    # Use generated title from AI, fallback to a generic title if not available
                    generated_title = post_data.get("title", "")
                    if not generated_title or generated_title.strip() == "":
                        # Fallback: create a simple title based on business name
                        generated_title = f"{business_name} Update" if business_name and business_name != "Not specified" else "New Post"
                    
                    if is_carousel:
                        # Handle carousel post - upload all images
                        carousel_image_bytes = post_data.get("carousel_image_bytes", [])
                        carousel_image_urls = []
                        
                        logger.info(f"Uploading {len(carousel_image_bytes)} images for carousel post...")
                        for img_data in carousel_image_bytes:
                            try:
                                img_url = await self._upload_image_to_supabase(
                                    img_data["bytes"],
                                    user_id,
                                    platform,
                                    img_data.get("file_name", "carousel_image"),
                                    img_data.get("mime_type", "image/jpeg")
                                )
                                carousel_image_urls.append(img_url)
                                logger.info(f"Uploaded carousel image {len(carousel_image_urls)}/{len(carousel_image_bytes)}: {img_url}")
                            except Exception as upload_error:
                                logger.error(f"Failed to upload carousel image {img_data.get('file_name', 'unknown')}: {upload_error}")
                                # Continue with other images
                        
                        if not carousel_image_urls:
                            logger.error(f"No images uploaded for carousel post {post_data.get('folder_name', 'unknown')} - skipping")
                            continue
                        
                        # Use first image as primary for preview
                        primary_image_url = carousel_image_urls[0]
                        
                        post_record = {
                            "campaign_id": campaign_id,
                            "platform": platform,
                            "post_type": "carousel",
                            "title": generated_title,
                            "content": post_data.get("caption", ""),
                            "hashtags": post_data.get("hashtags", []),
                            "scheduled_date": scheduled_datetime.date().isoformat(),
                            "scheduled_time": scheduled_datetime.time().isoformat(),
                            "status": status,
                            "primary_image_url": primary_image_url,  # First image for preview
                            "metadata": {
                                "generated_by": "content_from_drive_agent",
                                "user_id": user_id,
                                "folder_name": post_data.get("folder_name", ""),
                                "description": post_data.get("description"),
                                "analysis": post_data.get("analysis"),
                                "call_to_action": post_data.get("call_to_action", ""),
                                "carousel_images": carousel_image_urls,  # All carousel image URLs
                                "total_images": len(carousel_image_urls),
                                "carousel_image_source": "drive"
                            }
                        }
                    else:
                        # Handle regular image post
                        # Upload image to Supabase if we have image bytes
                        image_url = post_data.get("image_url", "")
                        if post_data.get("image_bytes"):
                            try:
                                mime_type = post_data.get("mime_type", "image/jpeg")
                                image_url = await self._upload_image_to_supabase(
                                    post_data["image_bytes"],
                                    user_id,
                                    platform,
                                    post_data.get("file_name", "image"),
                                    mime_type
                                )
                                logger.info(f"Uploaded image to Supabase for post: {image_url}")
                            except Exception as upload_error:
                                logger.error(f"Failed to upload image to Supabase, using original URL: {upload_error}")
                                # Fallback to original image URL if upload fails
                                image_url = post_data.get("image_url", "") or post_data.get("thumbnail_url", "")
                        
                        post_record = {
                            "campaign_id": campaign_id,
                            "platform": platform,
                            "post_type": "image",
                            "title": generated_title,  # Use AI-generated title, not filename
                            "content": post_data.get("caption", ""),
                            "hashtags": post_data.get("hashtags", []),
                            "scheduled_date": scheduled_datetime.date().isoformat(),
                            "scheduled_time": scheduled_datetime.time().isoformat(),
                            "status": status,
                            "primary_image_url": image_url,  # Use Supabase URL
                            "metadata": {
                                "generated_by": "content_from_drive_agent",
                                "user_id": user_id,
                                "file_id": post_data.get("file_id"),
                                "file_name": post_data.get("file_name"),
                                "description": post_data.get("description"),  # Keep original description in metadata
                                "analysis": post_data.get("analysis"),
                                "call_to_action": post_data.get("call_to_action", ""),
                                "thumbnail_url": post_data.get("thumbnail_url", ""),
                                "original_drive_url": post_data.get("image_url", "")  # Keep original URL in metadata
                            }
                        }
                    
                    # Save to Supabase
                    if not campaign_id:
                        logger.error(f"Cannot save post: campaign_id is missing for user {user_id}")
                        continue
                    
                    result = self.supabase.table("content_posts").insert(post_record).execute()
                    
                    if result.data:
                        post_id = result.data[0]["id"]
                        saved_posts.append(post_id)
                        
                        # Register with scheduler if scheduled
                        if status == "scheduled":
                            try:
                                from scheduler.post_publisher import post_publisher
                                scheduled_at = f"{post_record['scheduled_date']}T{post_record['scheduled_time']}"
                                await post_publisher.register_scheduled_post(
                                    post_id=post_id,
                                    scheduled_at=scheduled_at,
                                    platform=platform,
                                    user_id=user_id
                                )
                                logger.info(f"Registered scheduled post {post_id} with scheduler")
                            except Exception as e:
                                logger.error(f"Failed to register scheduled post: {e}")
                        
                        logger.info(f"Saved post {idx + 1}/{len(generated_posts)}: {post_id}")
                    
                except Exception as e:
                    logger.error(f"Error saving post {post_data.get('file_name', 'unknown')}: {e}")
                    continue
            
            state["saved_posts"] = saved_posts
            logger.info(f"Saved {len(saved_posts)} posts to database")
            return state
            
        except Exception as e:
            logger.error(f"Error in schedule_posts: {e}")
            state["error_message"] = f"Failed to schedule posts: {str(e)}"
            state["current_step"] = ProcessingStep.ERROR
            return state
    
    async def _upload_image_to_supabase(self, image_bytes: bytes, user_id: str, platform: str, file_name: str, mime_type: str) -> str:
        """Upload image to Supabase storage, similar to custom content agent"""
        try:
            # Generate unique filename
            file_extension = mime_type.split("/")[1] if "/" in mime_type else "jpg"
            # Handle common extensions
            if file_extension == "jpeg":
                file_extension = "jpg"
            elif file_extension not in ["jpg", "png", "gif", "webp", "jpeg"]:
                file_extension = "jpg"  # Default to jpg
            
            # Create a safe filename from original filename
            safe_filename = "".join(c for c in file_name if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            safe_filename = safe_filename[:50]  # Limit length
            
            filename = f"drive_content_{user_id}_{platform}_{uuid.uuid4().hex[:8]}_{safe_filename}.{file_extension}"
            file_path = filename  # Store directly in bucket root
            
            # Use user-uploads bucket for drive content images
            bucket_name = "user-uploads"
            
            logger.info(f"Uploading image to Supabase storage: {bucket_name}/{file_path}, content_type: {mime_type}")
            
            # Upload to Supabase storage
            storage_response = self.supabase.storage.from_(bucket_name).upload(
                file_path,
                image_bytes,
                file_options={"content-type": mime_type}
            )
            
            # Check for upload errors
            if hasattr(storage_response, 'error') and storage_response.error:
                raise Exception(f"Storage upload failed: {storage_response.error}")
            
            # Get public URL
            public_url = self.supabase.storage.from_(bucket_name).get_public_url(file_path)
            
            logger.info(f"Successfully uploaded image to Supabase: {public_url}")
            return public_url
            
        except Exception as e:
            logger.error(f"Error uploading image to Supabase: {e}")
            raise e
    
    async def _get_or_create_drive_content_campaign(self, user_id: str) -> str | None:
        """Get or create a campaign for drive content"""
        try:
            # Check if campaign exists (using campaign_name, not name)
            response = self.supabase.table("content_campaigns").select("id").eq("user_id", user_id).eq("campaign_name", "Drive Content").execute()
            
            if response.data and response.data[0]:
                campaign_id = response.data[0]["id"]
                logger.info(f"✅ Found existing 'Drive Content' campaign with ID: {campaign_id} for user {user_id}")
                return campaign_id
            
            # Create new campaign
            from datetime import datetime, timedelta
            now = datetime.now()
            week_start = now - timedelta(days=now.weekday())
            week_end = week_start + timedelta(days=6)
            
            campaign_data = {
                "user_id": user_id,
                "campaign_name": "Drive Content",
                "week_start_date": week_start.date().isoformat(),
                "week_end_date": week_end.date().isoformat(),
                "status": "active"
            }
            
            result = self.supabase.table("content_campaigns").insert(campaign_data).execute()
            
            if result.data and result.data[0]:
                campaign_id = result.data[0]["id"]
                logger.info(f"✅ Created new 'Drive Content' campaign with ID: {campaign_id} for user {user_id}")
                return campaign_id
            else:
                logger.error(f"Failed to create campaign: No data returned from insert")
                return None
                
        except Exception as e:
            logger.error(f"Error getting/creating campaign: {e}")
            logger.error(f"Campaign creation failed for user_id: {user_id}, campaign_data: {campaign_data}")
            # Return None instead of raising to allow error handling upstream
            return None
    
    async def complete(self, state: ContentFromDriveState) -> ContentFromDriveState:
        """Mark processing as complete"""
        state["current_step"] = ProcessingStep.COMPLETE
        state["progress_percentage"] = 100
        logger.info(f"Processing complete. Saved {len(state.get('saved_posts', []))} posts")
        return state
    
    async def handle_error(self, state: ContentFromDriveState) -> ContentFromDriveState:
        """Handle errors"""
        state["current_step"] = ProcessingStep.ERROR
        logger.error(f"Error: {state.get('error_message', 'Unknown error')}")
        return state

