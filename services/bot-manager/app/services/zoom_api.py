"""
Zoom API Service for RTMS credential acquisition.

This service handles:
- OAuth token management (Server-to-Server OAuth)
- Meeting information retrieval
- RTMS stream details acquisition
"""
import os
import httpx
import base64
import time
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger("bot_manager.zoom_api")


class ZoomAPIService:
    """Service for interacting with Zoom API to get RTMS credentials."""
    
    def __init__(self):
        self.client_id = os.getenv("ZOOM_CLIENT_ID")
        self.client_secret = os.getenv("ZOOM_CLIENT_SECRET")
        self.account_id = os.getenv("ZOOM_ACCOUNT_ID")  # For Server-to-Server OAuth
        self.base_url = "https://api.zoom.us/v2"
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
    
    async def get_access_token(self) -> str:
        """Get OAuth access token using Server-to-Server OAuth."""
        # Check if token is still valid
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        
        if not self.client_id or not self.client_secret or not self.account_id:
            raise ValueError(
                "Zoom credentials not configured. Required: ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET, ZOOM_ACCOUNT_ID"
            )
        
        # Server-to-Server OAuth token request
        token_url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={self.account_id}"
        
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    token_url,
                    headers={
                        "Authorization": f"Basic {encoded_credentials}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = time.time() + expires_in - 60  # Refresh 1 min early
                
                logger.info("Successfully obtained Zoom OAuth access token")
                return self._access_token
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            logger.error(f"Failed to get Zoom OAuth token: {e.response.status_code} - {error_text}")
            
            # Check if it's an unsupported grant type (User-managed apps don't support Server-to-Server OAuth)
            if "unsupported_grant_type" in error_text.lower():
                raise ValueError(
                    "User-managed OAuth apps do not support Server-to-Server OAuth. "
                    "For RTMS integration, you need to either:\n"
                    "1. Switch to Admin-managed app in Zoom Marketplace\n"
                    "2. Use User Authorization OAuth flow (requires user interaction)\n"
                    "3. Contact Zoom support to enable Server-to-Server OAuth for your account"
                )
            raise ValueError(f"Failed to authenticate with Zoom API: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error getting Zoom OAuth token: {e}", exc_info=True)
            raise
    
    async def get_meeting_info(self, meeting_id: str) -> Dict[str, Any]:
        """Get meeting information including UUID from meeting ID."""
        access_token = await self.get_access_token()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/meetings/{meeting_id}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    }
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Meeting {meeting_id} not found")
            logger.error(f"Failed to get meeting info: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Failed to get meeting information: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error getting meeting info: {e}", exc_info=True)
            raise
    
    async def get_rtms_stream_details(self, meeting_id: str) -> Dict[str, str]:
        """
        Get RTMS stream details for a meeting.
        
        Note: RTMS stream details are typically provided via webhook when RTMS starts.
        This method attempts to get the meeting UUID from the API, but for instant meetings
        or personal meeting rooms, the meeting may not be available via API. In such cases,
        RTMS details (including UUID) must come from webhook events.
        
        For instant meetings:
        - Meeting may not exist in API (404 error)
        - RTMS details will be provided via webhook when RTMS starts
        - The webhook event contains: meeting_uuid, rtms_stream_id, server_urls, access_token
        
        Returns:
            Dict with keys: meeting_uuid (None if not available), rtms_stream_id (None), 
            server_urls (None), access_token (None)
        """
        # Try to get meeting info to get UUID
        try:
            meeting_info = await self.get_meeting_info(meeting_id)
            meeting_uuid = meeting_info.get("uuid")
            
            if not meeting_uuid:
                logger.warning(f"Meeting {meeting_id} found but no UUID in response")
                meeting_uuid = None
            else:
                logger.info(f"Retrieved meeting UUID {meeting_uuid} for meeting ID {meeting_id}")
        except ValueError as e:
            # Meeting not found (404) - common for instant meetings
            if "not found" in str(e).lower():
                logger.warning(
                    f"Meeting {meeting_id} not found via API. This is normal for instant meetings. "
                    f"RTMS details will be provided via webhook when RTMS starts."
                )
            else:
                logger.error(f"Error getting meeting info: {e}")
            meeting_uuid = None
        except Exception as e:
            logger.error(f"Unexpected error getting meeting info: {e}", exc_info=True)
            meeting_uuid = None
        
        # Note: RTMS stream_id, server_urls, and access_token are provided via webhook
        # when meeting.rtms_started event is triggered. For instant meetings, even the
        # meeting UUID comes from the webhook.
        return {
            "meeting_uuid": meeting_uuid,  # None for instant meetings - will come from webhook
            "rtms_stream_id": None,  # Will be provided via webhook
            "server_urls": None,  # Will be provided via webhook
            "access_token": None,  # Will be provided via webhook
        }
    
    async def request_rtms_connection(self, meeting_uuid: str) -> Dict[str, str]:
        """
        Request RTMS connection details for a meeting.
        
        This attempts to request RTMS connection via API. Note that RTMS must be:
        - Enabled in the Zoom account
        - Active in the meeting (RTMS must have started)
        
        If RTMS is not active, this will fail and webhook is the recommended approach.
        
        Returns:
            Dict with keys: rtms_stream_id, server_urls, access_token
        """
        access_token = await self.get_access_token()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try to request RTMS connection
                # Note: The exact endpoint may vary - this is based on typical Zoom API patterns
                response = await client.post(
                    f"{self.base_url}/meetings/{meeting_uuid}/rtms",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "action": "start"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Successfully requested RTMS connection for meeting {meeting_uuid}")
                    return {
                        "rtms_stream_id": data.get("stream_id"),
                        "server_urls": data.get("server_urls"),
                        "access_token": data.get("access_token"),
                    }
                elif response.status_code == 404:
                    logger.warning(f"RTMS endpoint not found for meeting {meeting_uuid}. RTMS may not be available via API for this meeting type.")
                    raise ValueError("RTMS connection cannot be requested via API. RTMS details must be provided via webhook when RTMS starts.")
                else:
                    error_text = response.text
                    logger.warning(f"Failed to request RTMS connection: {response.status_code} - {error_text}")
                    raise ValueError(f"Failed to request RTMS connection: {response.status_code}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("RTMS API endpoint may not be available. RTMS details are typically provided via webhook.")
                raise ValueError("RTMS connection cannot be requested via API. RTMS details must be provided via webhook when RTMS starts.")
            raise ValueError(f"Failed to request RTMS connection: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"Error requesting RTMS connection: {e}", exc_info=True)
            raise

