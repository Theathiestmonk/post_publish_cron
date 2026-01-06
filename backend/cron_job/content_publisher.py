"""
Content Publisher Service
Handles publishing content to social media platforms for both created_content and content_posts tables
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet
import httpx
import pytz

logger = logging.getLogger(__name__)

class ContentPublisherService:
    """Service for publishing content to social media platforms"""

    def __init__(self, supabase_client, cipher: Optional[Fernet] = None):
        self.supabase = supabase_client
        self.cipher = cipher

    async def publish_created_content(self, content: Dict[str, Any]) -> bool:
        """Publish a single piece of created content"""
        content_id = content.get("id")
        platform = content.get("platform", "").lower()
        channel = content.get("channel", "").lower()
        user_id = content.get("user_id")

        try:
            # Get user connection
            connection_response = self.supabase.table("platform_connections").select("*").eq(
                "user_id", user_id
            ).eq("platform", platform).eq("is_active", True).execute()

            if not connection_response.data:
                logger.warning(f"No active {platform} connection found for user {user_id}")
                return False

            connection = connection_response.data[0]

            # Prepare post data
            post_data = self.prepare_post_data(content, 'created_content')

            # Publish using platform-specific method
            success = await self.publish_to_platform(platform, post_data, connection)

            # Update status if successful
            if success:
                self.supabase.table("created_content").update({
                    "status": "published"
                }).eq("id", content_id).execute()
                logger.info(f"Status updated to published for {content_id}")

            return success

        except Exception as e:
            logger.error(f"Error publishing created content {content_id}: {e}")
            return False

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt an encrypted token"""
        if not self.cipher:
            return encrypted_token

        try:
            return self.cipher.decrypt(encrypted_token.encode()).decode()
        except Exception as e:
            logger.warning(f"Failed to decrypt token, trying as plaintext: {e}")
            # If decryption fails, try using as plaintext (for backward compatibility)
            if encrypted_token.startswith(('EAAB', 'EAA', 'AQA')):
                return encrypted_token
            raise

    def get_user_timezone(self, user_id: str) -> str:
        """Get user's timezone from profile or default to UTC"""
        try:
            response = self.supabase.table("profiles").select("timezone").eq("id", user_id).execute()
            if response.data and response.data[0].get("timezone"):
                return response.data[0]["timezone"]
            return "UTC"
        except Exception as e:
            logger.warning(f"Error getting timezone for user {user_id}: {e}, defaulting to UTC")
            return "UTC"

    def prepare_post_data(self, post: Dict[str, Any], table_type: str = "content_posts") -> Dict[str, Any]:
        """
        Prepare post data for publishing, handling differences between table structures

        Args:
            post: Post data from database
            table_type: "created_content" or "content_posts"

        Returns:
            Dict with standardized post data for publishing
        """
        post_id = post.get("id")
        platform = post.get("platform", "").lower()

        # Initialize post data
        post_data = {
            "message": post.get("content", ""),
            "title": post.get("title", ""),
            "hashtags": post.get("hashtags", []),
            "content_id": post_id
        }

        # Handle carousel images based on table type
        is_carousel = False
        carousel_images = []

        if table_type == "created_content":
            # For created_content: check metadata.carousel_images first, then images[] array
            metadata = post.get("metadata", {})
            content_type = post.get("content_type", "").lower()

            if metadata.get("carousel_images"):
                carousel_images = metadata["carousel_images"]
                is_carousel = True
            elif content_type == "carousel" and post.get("images"):
                carousel_images = post.get("images", [])
                is_carousel = True

        elif table_type == "content_posts":
            # For content_posts: check metadata.carousel_images
            metadata = post.get("metadata", {})
            post_type = post.get("post_type", "").lower()

            if metadata.get("carousel_images"):
                carousel_images = metadata["carousel_images"]
                is_carousel = True
            elif post_type == "carousel":
                # Fallback for older posts
                is_carousel = True

        # Set carousel data if applicable
        if is_carousel and carousel_images:
            post_data["post_type"] = "carousel"
            post_data["carousel_images"] = carousel_images
        else:
            # Handle single image/video
            image_url = ""

            if table_type == "created_content":
                # For created_content: use first image from images[] array
                images = post.get("images", [])
                if images and len(images) > 0:
                    image_url = images[0]
            elif table_type == "content_posts":
                # For content_posts: use primary_image_url
                image_url = post.get("primary_image_url", "")

            # Check if media is a video
            is_video = False
            if image_url:
                post_type = post.get("post_type", "") if table_type == "content_posts" else post.get("content_type", "")
                metadata = post.get("metadata", {})

                # Check post_type first
                if post_type and post_type.lower() == 'video':
                    is_video = True
                    logger.info(f"Video detected from post_type for post {post_id}")
                # Check metadata.media_type
                elif metadata and metadata.get('media_type') == 'video':
                    is_video = True
                    logger.info(f"Video detected from metadata.media_type for post {post_id}")
                # Check file extension as fallback
                else:
                    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.wmv', '.flv', '.3gp']
                    url_lower = image_url.lower().split('?')[0]
                    is_video = any(url_lower.endswith(ext) for ext in video_extensions)
                    if is_video:
                        logger.info(f"Video detected from file extension for post {post_id}")

                if is_video:
                    post_data["is_video"] = True
                    post_data["video_url"] = image_url
                    post_data["image_url"] = ""  # Clear image_url for video
                else:
                    post_data["image_url"] = image_url
                    post_data["video_url"] = ""  # Clear video_url for image
            else:
                post_data["image_url"] = ""
                post_data["video_url"] = ""

        return post_data

    async def publish_to_platform(self, platform: str, post_data: Dict[str, Any], connection: Dict[str, Any]) -> bool:
        """
        Publish post data to a specific platform

        Args:
            platform: Platform name (facebook, instagram, linkedin, youtube)
            post_data: Prepared post data
            connection: Platform connection data

        Returns:
            bool: Success status
        """
        if platform == "facebook":
            return await self._publish_to_facebook(connection, post_data)
        elif platform == "instagram":
            return await self._publish_to_instagram(connection, post_data)
        elif platform == "linkedin":
            return await self._publish_to_linkedin(connection, post_data)
        elif platform == "youtube":
            return await self._publish_to_youtube(connection, post_data)
        else:
            logger.warning(f"Platform {platform} not supported for auto-publishing")
            return False

    async def _publish_to_facebook(self, connection: Dict[str, Any], post_data: Dict[str, Any]) -> bool:
        """Publish to Facebook"""
        try:
            access_token = self.decrypt_token(connection.get("access_token_encrypted", ""))
            page_id = connection.get("page_id") or connection.get("facebook_page_id")

            if not page_id:
                logger.error("No page_id found in Facebook connection")
                return False

            if not access_token:
                logger.error("No access token found in Facebook connection")
                return False

            # Prepare message
            message = post_data.get("message", "")
            title = post_data.get("title", "")
            hashtags = post_data.get("hashtags", [])

            full_message = ""
            if title:
                full_message += f"{title}\n\n"
            full_message += message
            if hashtags:
                hashtag_string = " ".join([f"#{tag.replace('#', '')}" for tag in hashtags])
                full_message += f"\n\n{hashtag_string}"

            image_url = post_data.get("image_url", "")
            carousel_images = post_data.get("carousel_images", [])
            is_carousel = post_data.get("post_type") == "carousel" or (carousel_images and len(carousel_images) > 0)

            async with httpx.AsyncClient(timeout=60.0) as client:
                if is_carousel and carousel_images:
                    # Handle carousel post
                    logger.info(f"Publishing Facebook carousel with {len(carousel_images)} images")

                    # Step 1: Create photo containers for each image (published=false)
                    photo_ids = []
                    for idx, img_url in enumerate(carousel_images):
                        try:
                            photo_url = f"https://graph.facebook.com/v18.0/{page_id}/photos"
                            photo_params = {
                                "url": img_url,
                                "published": "false",
                                "access_token": access_token
                            }

                            photo_response = await client.post(photo_url, params=photo_params)
                            if photo_response.status_code == 200:
                                photo_data = photo_response.json()
                                photo_id = photo_data.get('id')
                                if photo_id:
                                    photo_ids.append({"media_fbid": photo_id})
                                    logger.info(f"Created photo container {idx + 1}/{len(carousel_images)}: {photo_id}")
                                else:
                                    logger.warning(f"Photo container {idx + 1} created but no ID returned")
                            else:
                                error_data = photo_response.json() if photo_response.headers.get('content-type', '').startswith('application/json') else {"error": photo_response.text}
                                logger.error(f"Failed to create photo container {idx + 1}: {error_data}")
                                return False
                        except Exception as e:
                            logger.error(f"Error creating photo container {idx + 1}: {e}")
                            return False

                    if not photo_ids:
                        logger.error("Failed to create photo containers for carousel")
                        return False

                    # Step 2: Create carousel post with attached_media
                    import json
                    url = f"https://graph.facebook.com/v18.0/{page_id}/feed"
                    params = {
                        "message": full_message,
                        "attached_media": json.dumps(photo_ids),
                        "access_token": access_token
                    }

                    logger.info(f"Posting carousel to feed endpoint with {len(photo_ids)} photos")
                    response = await client.post(url, params=params)

                    # Parse response
                    try:
                        response_data = response.json()
                    except:
                        response_text = response.text
                        logger.error(f"Facebook API returned non-JSON response: {response_text}")
                        return False

                    if response.status_code == 200:
                        if response_data.get("id"):
                            logger.info(f"Facebook carousel post published: {response_data.get('id')}")
                            return True
                        else:
                            logger.error(f"Facebook carousel post failed - no ID in response: {response_data}")
                            return False
                    else:
                        error_message = response_data.get("error", {}).get("message", "Unknown error") if isinstance(response_data, dict) else str(response_data)
                        logger.error(f"Facebook carousel API error: {error_message}")
                        return False

                # Handle single image/video post
                if image_url:
                    if post_data.get("is_video"):
                        # For videos, use videos endpoint
                        url = f"https://graph.facebook.com/v18.0/{page_id}/videos"
                        params = {
                            "file_url": image_url,
                            "description": full_message,
                            "access_token": access_token
                        }
                    else:
                        # For images, use photos endpoint
                        url = f"https://graph.facebook.com/v18.0/{page_id}/photos"
                        params = {
                            "url": image_url,
                            "caption": full_message,
                            "access_token": access_token
                        }
                else:
                    # For text-only posts, use feed endpoint
                    url = f"https://graph.facebook.com/v18.0/{page_id}/feed"
                    params = {
                        "message": full_message,
                        "access_token": access_token
                    }

                response = await client.post(url, params=params)

                # Parse response
                try:
                    response_data = response.json()
                except:
                    response_text = response.text
                    logger.error(f"Facebook API returned non-JSON response: {response_text}")
                    return False

                if response.status_code == 200:
                    if response_data.get("id"):
                        logger.info(f"Facebook post published: {response_data.get('id')}")
                        return True
                    else:
                        logger.error(f"Facebook post failed - no ID in response: {response_data}")
                        return False
                else:
                    error_message = response_data.get("error", {}).get("message", "Unknown error") if isinstance(response_data, dict) else str(response_data)
                    error_code = response_data.get("error", {}).get("code", response.status_code) if isinstance(response_data, dict) else response.status_code
                    error_type = response_data.get("error", {}).get("type", "Unknown") if isinstance(response_data, dict) else "Unknown"
                    logger.error(f"Facebook API error ({error_code}, {error_type}): {error_message}. Full response: {response_data}")
                    return False

        except httpx.HTTPStatusError as e:
            error_data = {}
            try:
                error_data = e.response.json() if e.response else {}
            except:
                error_data = {"error": str(e)}
            error_msg = error_data.get("error", {}).get("message", str(e)) if isinstance(error_data, dict) else str(e)
            logger.error(f"HTTP error publishing to Facebook: {error_msg}. Status: {e.response.status_code if e.response else 'unknown'}. Response: {error_data}")
            return False
        except Exception as e:
            logger.error(f"Error publishing to Facebook: {type(e).__name__}: {str(e)}", exc_info=True)
            return False

    async def _publish_to_instagram(self, connection: Dict[str, Any], post_data: Dict[str, Any]) -> bool:
        """Publish to Instagram"""
        try:
            access_token = self.decrypt_token(connection.get("access_token_encrypted", ""))
            page_id = connection.get("page_id") or connection.get("instagram_page_id")

            if not page_id:
                logger.error("No page_id found in Instagram connection")
                return False

            # Check if this is a carousel post
            carousel_images = post_data.get("carousel_images", [])
            is_carousel = post_data.get("post_type") == "carousel" or (carousel_images and len(carousel_images) > 0)

            if is_carousel and carousel_images:
                # Handle carousel post
                logger.info(f"Publishing Instagram carousel with {len(carousel_images)} images")

                # Prepare caption
                message = post_data.get("message", "")
                title = post_data.get("title", "")
                hashtags = post_data.get("hashtags", [])

                caption = ""
                if title:
                    caption += f"{title}\n\n"
                caption += message
                if hashtags:
                    hashtag_string = " ".join([f"#{tag.replace('#', '')}" for tag in hashtags])
                    caption += f"\n\n{hashtag_string}"

                async with httpx.AsyncClient(timeout=60.0) as client:
                    # Step 1: Create media containers for each image (is_carousel_item=true)
                    container_ids = []
                    for idx, img_url in enumerate(carousel_images):
                        try:
                            container_url = f"https://graph.facebook.com/v18.0/{page_id}/media"
                            container_params = {
                                "image_url": img_url,
                                "is_carousel_item": "true",
                                "access_token": access_token
                            }

                            container_response = await client.post(container_url, params=container_params)
                            if container_response.status_code == 200:
                                container_result = container_response.json()
                                container_id = container_result.get('id')
                                if container_id:
                                    container_ids.append(container_id)
                                    logger.info(f"Created media container {idx + 1}/{len(carousel_images)}: {container_id}")
                                else:
                                    logger.warning(f"Media container {idx + 1} created but no ID returned")
                            else:
                                error_data = container_response.json() if container_response.headers.get('content-type', '').startswith('application/json') else {"error": container_response.text}
                                logger.error(f"Failed to create media container {idx + 1}: {error_data}")
                                return False
                        except Exception as e:
                            logger.error(f"Error creating media container {idx + 1}: {e}")
                            return False

                    if not container_ids:
                        logger.error("Failed to create media containers for carousel")
                        return False

                    # Step 2: Create carousel container with children parameter
                    carousel_url = f"https://graph.facebook.com/v18.0/{page_id}/media"
                    carousel_params = {
                        "media_type": "CAROUSEL",
                        "children": ",".join(container_ids),
                        "caption": caption,
                        "access_token": access_token
                    }

                    logger.info(f"Creating Instagram carousel container with {len(container_ids)} children")
                    carousel_response = await client.post(carousel_url, params=carousel_params)

                    if carousel_response.status_code != 200:
                        error_data = carousel_response.json() if carousel_response.headers.get('content-type', '').startswith('application/json') else {"error": carousel_response.text}
                        logger.error(f"Failed to create carousel container: {error_data}")
                        return False

                    carousel_result = carousel_response.json()
                    creation_id = carousel_result.get('id')

                    if not creation_id:
                        logger.error("Failed to create carousel container - no creation ID returned")
                        return False

                    # Step 3: Publish the carousel
                    publish_url = f"https://graph.facebook.com/v18.0/{page_id}/media_publish"
                    publish_params = {
                        "creation_id": creation_id,
                        "access_token": access_token
                    }

                    logger.info(f"Publishing Instagram carousel: {creation_id}")
                    publish_response = await client.post(publish_url, params=publish_params)

                    if publish_response.status_code == 200:
                        publish_result = publish_response.json()
                        post_id = publish_result.get('id')
                        logger.info(f"Instagram carousel post published: {post_id}")
                        return True
                    else:
                        # Handle HTTP errors gracefully for carousel
                        error_data = publish_response.json() if publish_response.headers.get('content-type', '').startswith('application/json') else {"error": publish_response.text}
                        logger.error(f"Error publishing Instagram carousel: {error_data}")

                        # Log specific error details for debugging
                        if publish_response.status_code == 400:
                            logger.warning("400 Bad Request - Possible causes:")
                            logger.warning("- Invalid creation_id or expired")
                            logger.warning("- Insufficient token permissions")
                            logger.warning("- Content violates Instagram policies")
                            logger.warning("- Rate limiting or duplicate content")
                        elif publish_response.status_code == 401:
                            logger.warning("401 Unauthorized - Token may be invalid or expired")
                        elif publish_response.status_code == 403:
                            logger.warning("403 Forbidden - Token lacks publish permissions")

                        return False

            # Instagram requires image or video, so check if we have one
            image_url = post_data.get("image_url", "")
            video_url = post_data.get("video_url", "")
            media_url = video_url if video_url else image_url

            if not media_url:
                logger.warning("Instagram post requires an image or video, but none provided")
                return False

            # Check if media is a video or image
            is_video = post_data.get("is_video", False)
            if not is_video and media_url:
                # Fallback: Check if URL is a video by file extension
                video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.wmv', '.flv', '.3gp']
                media_url_lower = media_url.lower()
                url_without_query = media_url_lower.split('?')[0]
                is_video = any(url_without_query.endswith(ext) for ext in video_extensions)

            if is_video:
                logger.info(f"Media type detection: Video/Reel - URL: {media_url[:100] if media_url else 'N/A'}...")
            else:
                logger.info(f"Media type detection: Image - URL: {media_url[:100] if media_url else 'N/A'}...")

            # Prepare caption
            message = post_data.get("message", "")
            title = post_data.get("title", "")
            hashtags = post_data.get("hashtags", [])

            caption = ""
            if title:
                caption += f"{title}\n\n"
            caption += message
            if hashtags:
                hashtag_string = " ".join([f"#{tag.replace('#', '')}" for tag in hashtags])
                caption += f"\n\n{hashtag_string}"

            # Validate caption length (Instagram limit is 2200 characters)
            if len(caption) > 2200:
                logger.warning(f"Caption too long ({len(caption)} chars), truncating to 2200...")
                caption = caption[:2197] + "..."

            # Validate image URL accessibility (basic check)
            if not is_video and media_url:
                # Check if URL is accessible
                try:
                    async with httpx.AsyncClient(timeout=10.0) as check_client:
                        head_response = await check_client.head(media_url)
                        if head_response.status_code != 200:
                            logger.warning(f"Image URL returned {head_response.status_code}: {media_url[:100]}...")
                            logger.warning("Instagram may not be able to access this image")
                except Exception as e:
                    logger.warning(f"Could not verify image URL accessibility: {e}")
                    logger.warning("Instagram may not be able to access this image")

            # Step 1: Create media container
            container_url = f"https://graph.facebook.com/v18.0/{page_id}/media"

            # Prepare container params based on media type
            if is_video:
                # For videos/reels - keep URL approach (videos are complex to upload)
                container_params = {
                    "media_type": "REELS",
                    "video_url": media_url,
                    "caption": caption,
                    "access_token": access_token
                }
                logger.info(f"Creating Instagram reel with video URL")
                files = None
            else:
                # For images - USE URL APPROACH (Instagram requires public URLs)
                logger.info(f"Using URL approach for Instagram image: {media_url[:100]}...")
                files = None
                container_params = {
                    "image_url": media_url,
                    "caption": caption,
                    "access_token": access_token
                }

            # Use longer timeout for videos/reels
            timeout = 180.0 if is_video else 60.0
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Create container
                logger.info(f"Creating Instagram media container for {'video' if is_video else 'image'}...")
                logger.info(f"Using URL approach: {media_url[:100]}...")
                logger.info(f"Caption length: {len(caption)} characters")

                try:
                    # All Instagram uploads now use URL approach with params
                    container_response = await client.post(container_url, params=container_params)
                    container_response.raise_for_status()
                    container_result = container_response.json()
                    creation_id = container_result.get("id")

                    if not creation_id:
                        logger.error(f"Failed to create Instagram media container: {container_result}")
                        return False

                except httpx.HTTPStatusError as e:
                    # Handle HTTP errors specifically for media container creation
                    error_data = {}
                    try:
                        error_data = e.response.json() if e.response else {}
                    except:
                        error_data = {"error": str(e)}

                    logger.error(f"Instagram media container creation failed: {error_data}")

                    # Log specific error details for debugging
                    if e.response.status_code == 400:
                        logger.warning("400 Bad Request - Media container creation failed:")
                        logger.warning("- Image/video URL may not be accessible by Instagram")
                        logger.warning("- Image may be too large (>8MB) or wrong format")
                        logger.warning("- Caption may be too long (>2200 characters)")
                        logger.warning("- Access token may lack publish_to_instagram permission")
                        logger.warning("- Instagram Business account may not be properly set up")
                        logger.warning("- The image URL might be from a private/supabase storage that Instagram can't access")
                    elif e.response.status_code == 401:
                        logger.warning("401 Unauthorized - Token may be invalid or expired")
                    elif e.response.status_code == 403:
                        logger.warning("403 Forbidden - Token lacks Instagram publish permissions")

                    return False

                # Wait for media processing before publishing (both images and videos)
                status_url = f"https://graph.facebook.com/v18.0/{creation_id}"
                max_wait_time = 120 if is_video else 60  # Videos get 2 minutes, images get 1 minute
                wait_interval = 5  # Check every 5 seconds
                elapsed_time = 0

                logger.info(f"Waiting for {'video' if is_video else 'image'} processing (max {max_wait_time}s)...")

                while elapsed_time < max_wait_time:
                    await asyncio.sleep(wait_interval)
                    elapsed_time += wait_interval

                    try:
                        status_response = await client.get(status_url, params={"access_token": access_token, "fields": "status_code"})
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            status_code = status_data.get("status_code")

                            # Status codes: "FINISHED" = ready, "IN_PROGRESS" = still processing, "ERROR" = failed
                            if status_code == "FINISHED":
                                logger.info(f"{'Video' if is_video else 'Image'} processing finished, ready to publish")
                                break
                            elif status_code == "ERROR":
                                logger.error(f"{'Video' if is_video else 'Image'} processing failed with error status")
                                return False
                            elif status_code == "IN_PROGRESS":
                                logger.info(f"Still processing... ({elapsed_time}s elapsed)")
                            # If IN_PROGRESS, continue waiting
                        else:
                            logger.warning(f"Could not check media status, proceeding anyway (HTTP {status_response.status_code})")
                            break
                    except Exception as status_error:
                        logger.warning(f"Error checking media status: {status_error}, proceeding anyway")
                        break

                if elapsed_time >= max_wait_time:
                    logger.warning(f"Media processing timeout after {max_wait_time}s, proceeding with publish attempt")

                # Step 2: Publish the container
                publish_url = f"https://graph.facebook.com/v18.0/{page_id}/media_publish"
                publish_params = {
                    "creation_id": creation_id,
                    "access_token": access_token
                }

                publish_response = await client.post(publish_url, params=publish_params)

                if publish_response.status_code == 200:
                    publish_result = publish_response.json()
                    if publish_result.get("id"):
                        post_id = publish_result.get("id")
                        logger.info(f"Instagram {'reel' if is_video else 'post'} published: {post_id}")
                        return True
                    else:
                        logger.error(f"Instagram post failed: {publish_result}")
                        return False
                else:
                    # Handle HTTP errors gracefully
                    error_data = publish_response.json() if publish_response.headers.get('content-type', '').startswith('application/json') else {"error": publish_response.text}
                    logger.error(f"Error publishing to Instagram: {error_data}")

                    # Log specific error details for debugging
                    if publish_response.status_code == 400:
                        logger.warning("400 Bad Request - Possible causes:")
                        logger.warning("- Invalid creation_id or expired")
                        logger.warning("- Insufficient token permissions")
                        logger.warning("- Content violates Instagram policies")
                        logger.warning("- Rate limiting or duplicate content")
                    elif publish_response.status_code == 401:
                        logger.warning("401 Unauthorized - Token may be invalid or expired")
                    elif publish_response.status_code == 403:
                        logger.warning("403 Forbidden - Token lacks publish permissions")

                    return False

        except Exception as e:
            logger.error(f"Error publishing to Instagram: {e}")
            return False

    async def _publish_to_linkedin(self, connection: Dict[str, Any], post_data: Dict[str, Any]) -> bool:
        """Publish to LinkedIn"""
        try:
            access_token = self.decrypt_token(connection.get("access_token_encrypted", ""))
            linkedin_id = connection.get("linkedin_id") or connection.get("page_id")

            if not linkedin_id:
                logger.error("No linkedin_id found in LinkedIn connection")
                return False

            # Prepare message
            message = post_data.get("message", "")
            title = post_data.get("title", "")
            hashtags = post_data.get("hashtags", [])

            full_message = ""
            if title:
                full_message += f"{title}\n\n"
            full_message += message
            if hashtags:
                hashtag_string = " ".join([f"#{tag.replace('#', '')}" for tag in hashtags])
                full_message += f"\n\n{hashtag_string}"

            # Post to LinkedIn using UGC API
            url = "https://api.linkedin.com/v2/ugcPosts"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            }

            # Determine if posting to organization or personal profile
            organization_id = connection.get("organization_id")
            if organization_id:
                author_urn = f"urn:li:organization:{organization_id}"
            else:
                author_urn = f"urn:li:person:{linkedin_id}"

            payload = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": full_message
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            # Add image if available (simplified - LinkedIn image upload is complex)
            image_url = post_data.get("image_url", "")
            if image_url:
                # For LinkedIn, we'd need to upload the image first and get an asset URN
                # For now, we'll skip image support in auto-publish
                pass

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()

                if result.get("id"):
                    logger.info(f"LinkedIn post published: {result.get('id')}")
                    return True
                else:
                    logger.error(f"LinkedIn post failed: {result}")
                    return False

        except Exception as e:
            logger.error(f"Error publishing to LinkedIn: {e}")
            return False

    async def _publish_to_youtube(self, connection: Dict[str, Any], post_data: Dict[str, Any]) -> bool:
        """Publish to YouTube (Community Post)"""
        try:
            # YouTube community posts require different API calls
            # For now, we'll skip YouTube auto-publishing as it's more complex
            logger.warning("YouTube auto-publishing not yet implemented")
            return False
        except Exception as e:
            logger.error(f"Error publishing to YouTube: {e}")
            return False
