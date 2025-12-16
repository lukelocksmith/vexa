#!/usr/bin/env python3
"""
Full flow test for Zoom integration:
1. Parse Zoom URL
2. Get meeting UUID via API
3. Simulate bot request flow
"""

import asyncio
import os
import sys
import json
import re
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass  # dotenv not available, use system env vars

sys.path.insert(0, str(Path(__file__).parent))


def parse_zoom_url(meeting_url: str) -> tuple[str, str | None]:
    """Parse Zoom meeting URL."""
    meeting_id_match = re.search(r'/j/(\d{9,11})', meeting_url)
    if not meeting_id_match:
        raise ValueError(f"Invalid Zoom URL format: {meeting_url}")
    
    meeting_id = meeting_id_match.group(1)
    passcode_match = re.search(r'[?&]pwd=([^&]+)', meeting_url)
    passcode = passcode_match.group(1) if passcode_match else None
    
    return meeting_id, passcode


async def test_full_flow():
    """Test the full Zoom integration flow."""
    # Use URL from command line if provided, otherwise use default
    import sys
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://us05web.zoom.us/j/83307709878?pwd=w5DHmbN9NTxvPwExHPYoKmsGwTRbJK.1"
    
    print("=" * 70)
    print("Zoom Integration Full Flow Test")
    print("=" * 70)
    print(f"\nTest URL: {test_url}\n")
    
    # Step 1: Parse URL
    print("Step 1: Parsing Zoom URL...")
    try:
        meeting_id, passcode = parse_zoom_url(test_url)
        print(f"  ✓ Meeting ID: {meeting_id}")
        print(f"  ✓ Passcode: {'***' if passcode else None}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return
    
    # Step 2: Check credentials
    print("\nStep 2: Checking Zoom API credentials...")
    required_vars = ["ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET", "ZOOM_ACCOUNT_ID"]
    missing = [v for v in required_vars if not os.getenv(v)]
    
    if missing:
        print(f"  ⚠ Missing: {', '.join(missing)}")
        print("\n  To complete the test, set these environment variables:")
        print("    export ZOOM_CLIENT_ID='your_client_id'")
        print("    export ZOOM_CLIENT_SECRET='your_client_secret'")
        print("    export ZOOM_ACCOUNT_ID='your_account_id'")
        print("\n  You can get these from:")
        print("    https://marketplace.zoom.us/ -> Your App -> App Credentials")
        return
    
    print("  ✓ All credentials present")
    
    # Step 3: Test API service
    print("\nStep 3: Testing Zoom API Service...")
    try:
        from app.services.zoom_api import ZoomAPIService
        
        service = ZoomAPIService()
        
        # Get OAuth token
        print("  Getting OAuth access token...")
        token = await service.get_access_token()
        print(f"  ✓ Token acquired")
        
        # Get RTMS details (handles both scheduled and instant meetings)
        print(f"  Getting RTMS stream details for meeting ID: {meeting_id}...")
        rtms_details = await service.get_rtms_stream_details(meeting_id)
        meeting_uuid = rtms_details.get('meeting_uuid')
        
        if meeting_uuid:
            print(f"  ✓ Meeting UUID: {meeting_uuid}")
            # Try to get additional meeting info if UUID is available
            try:
                meeting_info = await service.get_meeting_info(meeting_id)
                print(f"  ✓ Topic: {meeting_info.get('topic', 'N/A')}")
            except Exception:
                pass  # Meeting info not critical
        else:
            print(f"  ⚠ Meeting not found via API (likely instant meeting)")
            print(f"  ℹ Meeting UUID and RTMS details will be provided via webhook when RTMS starts")
        
        # Step 4: Simulate bot config
        print("\nStep 4: Simulating Bot Configuration...")
        bot_config = {
            "platform": "zoom",
            "meetingUrl": test_url,
            "nativeMeetingId": rtms_details.get("meeting_uuid") or meeting_id,  # Use numeric ID if UUID not available
            "zoomClientId": os.getenv("ZOOM_CLIENT_ID"),
            "zoomClientSecret": os.getenv("ZOOM_CLIENT_SECRET"),
            "zoomRtmsStreamId": rtms_details.get("rtms_stream_id"),
            "zoomServerUrls": rtms_details.get("server_urls"),
            "zoomAccessToken": rtms_details.get("access_token"),
        }
        
        print("  Bot Config (simulated):")
        print(f"    Platform: {bot_config['platform']}")
        print(f"    Meeting ID/UUID: {bot_config['nativeMeetingId']}")
        if rtms_details.get("meeting_uuid"):
            print(f"      (UUID from API)")
        else:
            print(f"      (Numeric ID - UUID will come from webhook)")
        print(f"    Client ID: {bot_config['zoomClientId'][:20]}...")
        print(f"    RTMS Stream ID: {bot_config['zoomRtmsStreamId'] or 'None (requires webhook)'}")
        print(f"    Server URLs: {bot_config['zoomServerUrls'] or 'None (requires webhook)'}")
        print(f"    Access Token: {bot_config['zoomAccessToken'] or 'None (requires webhook)'}")
        
        # Step 5: Summary
        print("\n" + "=" * 70)
        print("Test Summary")
        print("=" * 70)
        print("✓ URL parsing: SUCCESS")
        print("✓ OAuth token: SUCCESS")
        if meeting_uuid:
            print("✓ Meeting UUID: SUCCESS (from API)")
        else:
            print("⚠ Meeting UUID: PENDING (will come from webhook for instant meetings)")
        print("⚠ RTMS stream details: PARTIAL (requires webhook)")
        print("\nNext Steps:")
        print("1. Set up webhook endpoint to receive 'meeting.rtms_started' events")
        print("2. When webhook is received, update bot config with RTMS details")
        print("3. Bot can then connect to RTMS stream using the details from webhook")
        print("=" * 70)
        
    except Exception as e:
        print(f"  ✗ API Test Failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_full_flow())

