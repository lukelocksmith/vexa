#!/usr/bin/env python3
"""
Acquire RTMS details for a Zoom meeting by attempting to request them via API.
This script tries multiple approaches to get RTMS connection details.

Usage:
    python3 acquire_rtms_details.py <meeting_id>
    
Example:
    python3 acquire_rtms_details.py 86593345515
"""

import sys
import asyncio
import os
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    # Try multiple possible .env locations
    env_paths = [
        Path(__file__).parent.parent.parent / '.env',  # repo root
        Path(__file__).parent.parent / '.env',  # services root
        Path(__file__).parent / '.env',  # bot-manager root
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"📄 Loaded .env from: {env_path}")
            break
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from app.services.zoom_api import ZoomAPIService


async def acquire_rtms_details(meeting_id: str):
    """Try to acquire RTMS details for a meeting."""
    api = ZoomAPIService()
    
    print(f"🔍 Attempting to acquire RTMS details for meeting: {meeting_id}")
    print("=" * 70)
    
    # Step 1: Try to get meeting info and UUID
    print("\n1️⃣ Getting meeting information...")
    try:
        meeting_info = await api.get_meeting_info(meeting_id)
        meeting_uuid = meeting_info.get("uuid")
        print(f"   ✅ Meeting found!")
        print(f"   📋 Topic: {meeting_info.get('topic', 'N/A')}")
        print(f"   🔑 UUID: {meeting_uuid}")
        
        if not meeting_uuid:
            print("   ⚠️  No UUID in meeting info. This is an instant meeting.")
            print("   💡 For instant meetings, RTMS details come via webhook when RTMS starts.")
            return None
            
    except ValueError as e:
        if "not found" in str(e).lower():
            print(f"   ⚠️  Meeting {meeting_id} not found via API.")
            print("   💡 This is normal for instant meetings.")
            print("   💡 RTMS details must be provided via webhook when RTMS starts.")
            print("\n   To get RTMS details for instant meetings:")
            print("   1. Join the meeting and enable RTMS")
            print("   2. Configure webhook in Zoom App Marketplace")
            print("   3. Wait for meeting.rtms_started webhook event")
            return None
        else:
            print(f"   ❌ Error: {e}")
            return None
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return None
    
    # Step 2: Try to request RTMS connection
    print(f"\n2️⃣ Requesting RTMS connection for UUID: {meeting_uuid}...")
    try:
        rtms_details = await api.request_rtms_connection(meeting_uuid)
        print(f"   ✅ RTMS connection details acquired!")
        print(f"   📡 Stream ID: {rtms_details.get('rtms_stream_id', 'N/A')[:30]}...")
        print(f"   🌐 Server URLs: {rtms_details.get('server_urls', 'N/A')}")
        print(f"   🔑 Access Token: {'***' if rtms_details.get('access_token') else 'N/A'}")
        
        return {
            "meeting_uuid": meeting_uuid,
            **rtms_details
        }
    except ValueError as e:
        print(f"   ⚠️  {e}")
        print("\n   💡 RTMS details are typically provided via webhook when RTMS starts.")
        print("   💡 To get RTMS details:")
        print("      1. Ensure RTMS is enabled in your Zoom account")
        print("      2. Start RTMS in the meeting")
        print("      3. Configure webhook URL in Zoom App Marketplace")
        print("      4. Wait for meeting.rtms_started webhook event")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 acquire_rtms_details.py <meeting_id>")
        print("\nExample:")
        print("  python3 acquire_rtms_details.py 86593345515")
        sys.exit(1)
    
    meeting_id = sys.argv[1]
    
    result = await acquire_rtms_details(meeting_id)
    
    if result:
        print("\n" + "=" * 70)
        print("✅ Successfully acquired RTMS details!")
        print("=" * 70)
        print("\nYou can now:")
        print("1. Use these details to manually send a webhook:")
        print(f"   python3 send_rtms_webhook.py {meeting_id} {result['meeting_uuid']} {result['rtms_stream_id']} {result['server_urls']} {result.get('access_token', '')}")
        print("\n2. Or capture the webhook and use interactive debug:")
        print("   cd services/vexa-bot")
        print("   make capture-webhook")
        print("   make test-zoom")
    else:
        print("\n" + "=" * 70)
        print("⚠️  Could not acquire RTMS details via API")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Ensure RTMS is enabled in your Zoom account")
        print("2. Join the meeting and start RTMS")
        print("3. Configure webhook in Zoom App Marketplace")
        print("4. Wait for meeting.rtms_started webhook event")


if __name__ == "__main__":
    asyncio.run(main())

