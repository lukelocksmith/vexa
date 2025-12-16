#!/usr/bin/env python3
"""
Quick test for Zoom URL parsing and API integration with a specific meeting URL.
"""

import asyncio
import os
import sys
import re
from pathlib import Path

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


async def test_with_url():
    """Test with the provided Zoom URL."""
    test_url = "https://us05web.zoom.us/j/83307709878?pwd=w5DHmbN9NTxvPwExHPYoKmsGwTRbJK.1"
    
    print("=" * 70)
    print("Testing Zoom Integration with Provided URL")
    print("=" * 70)
    print(f"\nURL: {test_url}\n")
    
    # Parse URL
    try:
        meeting_id, passcode = parse_zoom_url(test_url)
        print(f"✓ URL Parsed Successfully:")
        print(f"  Meeting ID: {meeting_id}")
        print(f"  Passcode: {'***' if passcode else None}")
    except Exception as e:
        print(f"✗ URL Parsing Failed: {e}")
        return
    
    # Check for credentials
    required_vars = ["ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET", "ZOOM_ACCOUNT_ID"]
    missing = [v for v in required_vars if not os.getenv(v)]
    
    if missing:
        print(f"\n⚠ Missing Environment Variables: {', '.join(missing)}")
        print("\nTo test the API, set these environment variables:")
        print("  export ZOOM_CLIENT_ID='your_client_id'")
        print("  export ZOOM_CLIENT_SECRET='your_client_secret'")
        print("  export ZOOM_ACCOUNT_ID='your_account_id'")
        print("\nThen run this script again.")
        return
    
    # Test API
    print("\n" + "-" * 70)
    print("Testing Zoom API Service")
    print("-" * 70)
    
    try:
        from app.services.zoom_api import ZoomAPIService
        
        service = ZoomAPIService()
        
        print("\n1. Getting OAuth access token...")
        token = await service.get_access_token()
        print(f"   ✓ Token acquired: {token[:30]}...")
        
        print(f"\n2. Getting meeting info for ID: {meeting_id}...")
        meeting_info = await service.get_meeting_info(meeting_id)
        print(f"   ✓ Meeting info retrieved:")
        print(f"     UUID: {meeting_info.get('uuid')}")
        print(f"     Topic: {meeting_info.get('topic', 'N/A')}")
        print(f"     Type: {meeting_info.get('type', 'N/A')}")
        print(f"     Start Time: {meeting_info.get('start_time', 'N/A')}")
        print(f"     Duration: {meeting_info.get('duration', 'N/A')} minutes")
        
        print(f"\n3. Getting RTMS stream details...")
        rtms_details = await service.get_rtms_stream_details(meeting_id)
        print(f"   ✓ RTMS details:")
        print(f"     Meeting UUID: {rtms_details.get('meeting_uuid')}")
        print(f"     RTMS Stream ID: {rtms_details.get('rtms_stream_id') or 'None (requires webhook)'}")
        print(f"     Server URLs: {rtms_details.get('server_urls') or 'None (requires webhook)'}")
        print(f"     Access Token: {rtms_details.get('access_token') or 'None (requires webhook)'}")
        
        print("\n" + "=" * 70)
        print("✓ All API tests passed!")
        print("=" * 70)
        print("\nNote: RTMS stream_id, server_urls, and access_token are provided")
        print("via webhook when the meeting starts. The bot will need to wait for")
        print("the 'meeting.rtms_started' webhook event to get these details.")
        
    except Exception as e:
        print(f"\n✗ API Test Failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_with_url())





