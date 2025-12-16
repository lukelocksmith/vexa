#!/usr/bin/env python3
"""
Manually send a Zoom RTMS webhook to the bot-manager endpoint.
Use this when you have RTMS details from a Zoom meeting but the webhook wasn't received automatically.

Usage:
    python3 send_rtms_webhook.py <meeting_id> <meeting_uuid> <rtms_stream_id> <server_urls> [access_token]
    
Example:
    python3 send_rtms_webhook.py 86593345515 abc-def-ghi jkl-mno-pqr "wss://rtms.zoom.us" "access_token_here"
"""

import sys
import json
import httpx
import hmac
import hashlib
import os
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass

BOT_MANAGER_URL = os.getenv("BOT_MANAGER_URL", "http://localhost:8080")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET", "")


def generate_webhook_signature(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for Zoom webhook."""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def send_rtms_webhook(meeting_id: str, meeting_uuid: str, rtms_stream_id: str, 
                     server_urls: str, access_token: str = None):
    """Send a manual RTMS webhook to bot-manager."""
    
    # Construct webhook payload
    webhook_payload = {
        "event": "meeting.rtms_started",
        "payload": {
            "account_id": os.getenv("ZOOM_ACCOUNT_ID", ""),
            "object": {
                "uuid": meeting_uuid,
                "id": int(meeting_id),
                "rtms": {
                    "stream_id": rtms_stream_id,
                    "server_urls": server_urls,
                    "access_token": access_token or ""
                }
            }
        },
        "event_ts": int(__import__('time').time())
    }
    
    payload_str = json.dumps(webhook_payload)
    
    # Generate signature
    signature = generate_webhook_signature(payload_str, ZOOM_CLIENT_SECRET)
    
    # Send webhook
    url = f"{BOT_MANAGER_URL}/webhooks/zoom/rtms"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {signature}"
    }
    
    print(f"Sending RTMS webhook to: {url}")
    print(f"Meeting ID: {meeting_id}")
    print(f"Meeting UUID: {meeting_uuid}")
    print(f"RTMS Stream ID: {rtms_stream_id[:20]}...")
    print()
    
    try:
        response = httpx.post(url, json=webhook_payload, headers=headers, timeout=10.0)
        response.raise_for_status()
        print(f"✅ Webhook sent successfully!")
        print(f"Response: {response.json()}")
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(__doc__)
        print("\nRequired arguments:")
        print("  1. Meeting ID (numeric, e.g., 86593345515)")
        print("  2. Meeting UUID (from Zoom, e.g., abc-def-ghi)")
        print("  3. RTMS Stream ID (from Zoom RTMS)")
        print("  4. Server URLs (e.g., wss://rtms.zoom.us)")
        print("  5. Access Token (optional)")
        sys.exit(1)
    
    meeting_id = sys.argv[1]
    meeting_uuid = sys.argv[2]
    rtms_stream_id = sys.argv[3]
    server_urls = sys.argv[4]
    access_token = sys.argv[5] if len(sys.argv) > 5 else None
    
    send_rtms_webhook(meeting_id, meeting_uuid, rtms_stream_id, server_urls, access_token)





