#!/usr/bin/env python3
"""
Test script to start a Zoom bot with a meeting URL.
Requires:
1. Bot-manager service running
2. Valid API token (or will create user and token)
"""

import asyncio
import os
import sys
import httpx
import json
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass

# Default values
BOT_MANAGER_URL = os.getenv("BOT_MANAGER_URL", "http://localhost:8080")
ADMIN_API_URL = os.getenv("ADMIN_API_URL", "http://localhost:18057")
ADMIN_API_KEY = os.getenv("ADMIN_API_TOKEN", "token")
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:18056")


async def create_user_and_token():
    """Create a test user and API token."""
    print("Creating test user and API token...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Create user
        user_data = {
            "email": f"test_zoom_{os.getpid()}@example.com",
            "name": "Zoom Test User",
            "max_concurrent_bots": 1
        }
        
        try:
            response = await client.post(
                f"{API_GATEWAY_URL}/admin/users",
                headers={
                    "X-Admin-API-Key": ADMIN_API_KEY,
                    "Content-Type": "application/json"
                },
                json=user_data
            )
            response.raise_for_status()
            user = response.json()
            print(f"  ✓ Created user: {user['email']} (ID: {user['id']})")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:  # User already exists
                # Try to get existing user
                response = await client.get(
                    f"{API_GATEWAY_URL}/admin/users",
                    headers={"X-Admin-API-Key": ADMIN_API_KEY},
                    params={"email": user_data["email"]}
                )
                if response.status_code == 200:
                    users = response.json()
                    if users:
                        user = users[0]
                        print(f"  ✓ Using existing user: {user['email']} (ID: {user['id']})")
                    else:
                        raise Exception("Failed to create or find user")
                else:
                    raise
            else:
                raise
        
        # Create API token
        try:
            response = await client.post(
                f"{API_GATEWAY_URL}/admin/users/{user['id']}/tokens",
                headers={"X-Admin-API-Key": ADMIN_API_KEY}
            )
            response.raise_for_status()
            token_info = response.json()
            api_token = token_info['token']
            print(f"  ✓ Created API token: {api_token[:20]}...")
            return api_token
        except Exception as e:
            print(f"  ✗ Failed to create token: {e}")
            raise


async def start_zoom_bot(meeting_url: str, api_token: str):
    """Start a Zoom bot for the given meeting URL."""
    print(f"\nStarting Zoom bot for meeting: {meeting_url}")
    
    # Parse meeting ID from URL
    import re
    meeting_id_match = re.search(r'/j/(\d{9,11})', meeting_url)
    if not meeting_id_match:
        raise ValueError(f"Invalid Zoom URL format: {meeting_url}")
    
    meeting_id = meeting_id_match.group(1)
    passcode_match = re.search(r'[?&]pwd=([^&]+)', meeting_url)
    passcode = passcode_match.group(1) if passcode_match else None
    
    print(f"  Meeting ID: {meeting_id}")
    print(f"  Passcode: {'***' if passcode else None}")
    
    # Prepare request
    request_data = {
        "platform": "zoom",
        "native_meeting_id": meeting_url,  # Pass full URL, will be parsed
        "bot_name": "Vexa Zoom Bot",
        "language": "en",
        "task": "transcribe"
    }
    
    if passcode:
        request_data["passcode"] = passcode
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"\nSending POST request to {API_GATEWAY_URL}/bots...")
            response = await client.post(
                f"{API_GATEWAY_URL}/bots",
                headers={
                    "X-API-Key": api_token,
                    "Content-Type": "application/json"
                },
                json=request_data
            )
            
            print(f"  Response status: {response.status_code}")
            
            if response.status_code == 201:
                meeting = response.json()
                print(f"\n✓ Bot started successfully!")
                print(f"  Meeting ID: {meeting.get('id')}")
                print(f"  Status: {meeting.get('status')}")
                print(f"  Platform: {meeting.get('platform')}")
                print(f"  Native Meeting ID: {meeting.get('native_meeting_id')}")
                print(f"\n⚠️  Note: RTMS details will be provided via webhook when RTMS starts")
                print(f"   Webhook endpoint: {BOT_MANAGER_URL}/webhooks/zoom/rtms")
                return meeting
            else:
                print(f"  ✗ Failed to start bot")
                print(f"  Response: {response.text}")
                response.raise_for_status()
                
        except httpx.HTTPStatusError as e:
            print(f"  ✗ HTTP Error: {e.response.status_code}")
            print(f"  Response: {e.response.text}")
            raise
        except Exception as e:
            print(f"  ✗ Error: {e}")
            raise


async def main():
    """Main test function."""
    if len(sys.argv) < 2:
        print("Usage: python test_start_zoom_bot.py <zoom_meeting_url> [api_token]")
        print("\nExample:")
        print("  python test_start_zoom_bot.py 'https://us05web.zoom.us/j/83307709878?pwd=w5DHmbN9NTxvPwExHPYoKmsGwTRbJK.1'")
        print("  python test_start_zoom_bot.py 'https://us05web.zoom.us/j/83307709878?pwd=w5DHmbN9NTxvPwExHPYoKmsGwTRbJK.1' tk7YodZVEzu19rn9SMSO9Ew7amtHbSau9BLvngfD")
        sys.exit(1)
    
    meeting_url = sys.argv[1]
    api_token = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("=" * 70)
    print("Zoom Bot Start Test")
    print("=" * 70)
    print(f"\nMeeting URL: {meeting_url}\n")
    
    try:
        # Use provided token or create user and get API token
        if api_token:
            print(f"Using provided API token: {api_token[:20]}...")
        else:
            # Create user and get API token
            api_token = await create_user_and_token()
        
        # Start bot
        meeting = await start_zoom_bot(meeting_url, api_token)
        
        print("\n" + "=" * 70)
        print("Test Complete")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Check bot logs to see if it's waiting for RTMS webhook")
        print("2. When RTMS starts, Zoom will send webhook to:")
        print(f"   {BOT_MANAGER_URL}/webhooks/zoom/rtms")
        print("3. Bot will receive RTMS details and connect to stream")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

