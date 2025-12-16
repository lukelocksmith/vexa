#!/usr/bin/env python3
"""
Test script for Zoom API integration.

This script tests:
1. Zoom URL parsing
2. Zoom API service (OAuth token, meeting info)
3. RTMS details acquisition

Usage:
    python test_zoom_integration.py
"""

import asyncio
import os
import sys
import re
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent))


def parse_zoom_url(meeting_url: str) -> tuple[str, str | None]:
    """
    Parse Zoom meeting URL to extract meeting ID and passcode.
    
    Examples:
    - https://us05web.zoom.us/j/83307709878?pwd=w5DHmbN9NTxvPwExHPYoKmsGwTRbJK.1
    - https://zoom.us/j/83307709878
    
    Returns:
        Tuple of (meeting_id, passcode)
    """
    # Extract meeting ID (numeric, 9-11 digits)
    meeting_id_match = re.search(r'/j/(\d{9,11})', meeting_url)
    if not meeting_id_match:
        raise ValueError(f"Invalid Zoom URL format: {meeting_url}")
    
    meeting_id = meeting_id_match.group(1)
    
    # Extract passcode from pwd parameter
    passcode_match = re.search(r'[?&]pwd=([^&]+)', meeting_url)
    passcode = passcode_match.group(1) if passcode_match else None
    
    return meeting_id, passcode


async def test_url_parsing():
    """Test Zoom URL parsing."""
    print("=" * 60)
    print("Testing Zoom URL Parsing")
    print("=" * 60)
    
    test_urls = [
        "https://us05web.zoom.us/j/83307709878?pwd=w5DHmbN9NTxvPwExHPYoKmsGwTRbJK.1",
        "https://zoom.us/j/83307709878",
        "https://zoom.us/j/123456789",
    ]
    
    for url in test_urls:
        try:
            meeting_id, passcode = parse_zoom_url(url)
            print(f"✓ URL: {url}")
            print(f"  Meeting ID: {meeting_id}")
            print(f"  Passcode: {'***' if passcode else None}")
        except Exception as e:
            print(f"✗ URL: {url}")
            print(f"  Error: {e}")
        print()


async def test_zoom_api_service():
    """Test Zoom API service."""
    print("=" * 60)
    print("Testing Zoom API Service")
    print("=" * 60)
    
    # Check environment variables
    required_vars = ["ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET", "ZOOM_ACCOUNT_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠ Missing environment variables: {', '.join(missing_vars)}")
        print("  Set these to test the API service:")
        print("    export ZOOM_CLIENT_ID=...")
        print("    export ZOOM_CLIENT_SECRET=...")
        print("    export ZOOM_ACCOUNT_ID=...")
        return
    
    try:
        from app.services.zoom_api import ZoomAPIService
        service = ZoomAPIService()
        
        # Test OAuth token
        print("Testing OAuth token acquisition...")
        token = await service.get_access_token()
        print(f"✓ OAuth token acquired: {token[:20]}...")
        
        # Test meeting info (use a test meeting ID)
        test_meeting_id = "83307709878"  # From the URL provided
        print(f"\nTesting meeting info retrieval for meeting ID: {test_meeting_id}...")
        meeting_info = await service.get_meeting_info(test_meeting_id)
        print(f"✓ Meeting info retrieved:")
        print(f"  UUID: {meeting_info.get('uuid')}")
        print(f"  Topic: {meeting_info.get('topic', 'N/A')}")
        print(f"  Start Time: {meeting_info.get('start_time', 'N/A')}")
        
        # Test RTMS details
        print(f"\nTesting RTMS details retrieval...")
        rtms_details = await service.get_rtms_stream_details(test_meeting_id)
        print(f"✓ RTMS details retrieved:")
        print(f"  Meeting UUID: {rtms_details.get('meeting_uuid')}")
        print(f"  RTMS Stream ID: {rtms_details.get('rtms_stream_id') or 'None (from webhook)'}")
        print(f"  Server URLs: {rtms_details.get('server_urls') or 'None (from webhook)'}")
        print(f"  Access Token: {rtms_details.get('access_token') or 'None (from webhook)'}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Zoom API Integration Test Suite")
    print("=" * 60 + "\n")
    
    # Test URL parsing (no API calls needed)
    await test_url_parsing()
    
    # Test API service (requires credentials)
    await test_zoom_api_service()
    
    print("\n" + "=" * 60)
    print("Test Suite Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
