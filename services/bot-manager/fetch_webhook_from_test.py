#!/usr/bin/env python3
"""
Fetch and process Zoom RTMS webhook from webhook-test.com.

This script polls webhook-test.com API to get the webhook payload that Zoom sent,
then processes it and updates the bot configuration.

Usage:
    python3 fetch_webhook_from_test.py <webhook_id> [--meeting-id <meeting_id>]
    
Example:
    python3 fetch_webhook_from_test.py d6a97003dc5437b6502ef5120bf337db
    python3 fetch_webhook_from_test.py d6a97003dc5437b6502ef5120bf337db --meeting-id 86593345515
"""

import sys
import json
import httpx
import asyncio
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

# Load environment variables
try:
    from dotenv import load_dotenv
    env_paths = [
        Path(__file__).parent.parent / '.env',
        Path(__file__).parent.parent.parent / '.env',
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

BOT_MANAGER_URL = "http://localhost:8080"
WEBHOOK_TEST_API = "https://webhook-test.com/api/webhooks"


def fetch_webhook_payloads(webhook_id: str) -> list:
    """Fetch all webhook payloads from webhook-test.com."""
    # Try different API endpoints
    urls = [
        f"{WEBHOOK_TEST_API}/{webhook_id}",
        f"https://webhook-test.com/api/webhook/{webhook_id}",
        f"https://webhook-test.com/api/{webhook_id}",
    ]
    
    for url in urls:
        try:
            response = httpx.get(url, timeout=10.0, follow_redirects=True)
            if response.status_code == 200:
                data = response.json()
                
                # webhook-test.com returns payloads in different formats
                # Try to extract the requests/payloads
                if isinstance(data, dict):
                    if 'requests' in data:
                        return data['requests']
                    elif 'payloads' in data:
                        return data['payloads']
                    elif 'data' in data:
                        return data['data'] if isinstance(data['data'], list) else [data['data']]
                    elif 'body' in data:
                        # Single request with body
                        return [data]
                    else:
                        # Might be a single payload
                        return [data]
                elif isinstance(data, list):
                    return data
                else:
                    return []
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Authentication required - user needs to get payload manually
                continue
            elif e.response.status_code == 404:
                # Try next URL
                continue
            else:
                print(f"⚠️  HTTP {e.response.status_code} for {url}")
        except Exception as e:
            continue
    
    # If all API calls failed, return empty
    return []


def find_rtms_webhook(payloads: list) -> Optional[Dict[str, Any]]:
    """Find the RTMS webhook payload from the list."""
    for payload in payloads:
        # Check if it's a Zoom RTMS webhook
        if isinstance(payload, dict):
            # Check various possible structures
            event = payload.get('event') or payload.get('payload', {}).get('event')
            if event == 'meeting.rtms_started':
                return payload
            
            # Check if body contains RTMS event
            body = payload.get('body') or payload.get('data') or payload.get('payload')
            if isinstance(body, str):
                try:
                    body_data = json.loads(body)
                    if body_data.get('event') == 'meeting.rtms_started':
                        return body_data
                except:
                    pass
            elif isinstance(body, dict):
                if body.get('event') == 'meeting.rtms_started':
                    return body
    
    return None


def extract_rtms_details(webhook_payload: Dict[str, Any]) -> Dict[str, str]:
    """Extract RTMS details from webhook payload."""
    # Handle different payload structures
    event_obj = webhook_payload.get('payload', {}).get('object') or webhook_payload.get('object', {})
    rtms_data = event_obj.get('rtms', {})
    
    return {
        'meeting_uuid': event_obj.get('uuid') or event_obj.get('meeting_uuid'),
        'meeting_id_numeric': str(event_obj.get('id', '')),
        'rtms_stream_id': rtms_data.get('stream_id') or rtms_data.get('rtms_stream_id'),
        'server_urls': rtms_data.get('server_urls'),
        'access_token': rtms_data.get('access_token'),
        'join_url': event_obj.get('join_url', ''),
    }


def send_to_bot_manager(rtms_details: Dict[str, str], meeting_id: Optional[str] = None):
    """Send RTMS webhook to bot-manager endpoint."""
    # Construct webhook payload in the format bot-manager expects
    webhook_payload = {
        "event": "meeting.rtms_started",
        "payload": {
            "account_id": "",  # Will be filled by bot-manager if needed
            "object": {
                "uuid": rtms_details['meeting_uuid'],
                "id": int(rtms_details['meeting_id_numeric']) if rtms_details['meeting_id_numeric'] else 0,
                "rtms": {
                    "stream_id": rtms_details['rtms_stream_id'],
                    "server_urls": rtms_details['server_urls'],
                    "access_token": rtms_details['access_token'],
                }
            }
        },
        "event_ts": int(__import__('time').time())
    }
    
    url = f"{BOT_MANAGER_URL}/webhooks/zoom/rtms"
    
    print(f"\n📤 Sending RTMS webhook to bot-manager: {url}")
    
    try:
        response = httpx.post(url, json=webhook_payload, timeout=10.0)
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


def save_for_debug(rtms_details: Dict[str, str], output_file: str = None):
    """Save RTMS details for debugging."""
    if not output_file:
        output_file = Path(__file__).parent.parent / 'debug' / 'zoom-rtms-details.json'
        output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(rtms_details, f, indent=2)
    
    print(f"💾 Saved RTMS details to: {output_file}")


async def main():
    parser = argparse.ArgumentParser(description='Fetch and process Zoom RTMS webhook from webhook-test.com')
    parser.add_argument('webhook_id', help='Webhook ID from webhook-test.com (e.g., d6a97003dc5437b6502ef5120bf337db)')
    parser.add_argument('--meeting-id', help='Optional: Meeting ID to filter or verify')
    parser.add_argument('--poll', action='store_true', help='Poll continuously until webhook is received')
    parser.add_argument('--interval', type=int, default=5, help='Polling interval in seconds (default: 5)')
    parser.add_argument('--save-only', action='store_true', help='Only save to file, do not send to bot-manager')
    
    args = parser.parse_args()
    
    webhook_id = args.webhook_id
    webhook_url = f"https://webhook-test.com/{webhook_id}"
    
    print("=" * 70)
    print("🔍 Fetching Zoom RTMS Webhook from webhook-test.com")
    print("=" * 70)
    print(f"\n📡 Webhook URL: {webhook_url}")
    print(f"🔗 API URL: {WEBHOOK_TEST_API}/{webhook_id}")
    print("\n💡 Configure this URL in Zoom App Marketplace:")
    print(f"   1. Go to: https://marketplace.zoom.us/develop/apps")
    print(f"   2. Edit your Server-to-Server OAuth app")
    print(f"   3. Event Subscriptions → Add: {webhook_url}")
    print(f"   4. Enable events: meeting.rtms_started, meeting.rtms_stopped")
    print()
    
    if args.poll:
        print(f"🔄 Polling every {args.interval} seconds until RTMS webhook is received...")
        print("   Press Ctrl+C to stop\n")
    
    max_attempts = 1 if not args.poll else float('inf')
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        if args.poll and attempt > 1:
            print(f"⏳ Attempt {attempt}... (waiting {args.interval}s)")
            await asyncio.sleep(args.interval)
        
        # Fetch webhook payloads
        print(f"\n📥 Fetching webhook payloads...")
        payloads = fetch_webhook_payloads(webhook_id)
        
        if not payloads:
            if args.poll:
                continue
            else:
                print("❌ No webhook payloads found via API.")
                print("\n💡 To get the webhook payload manually:")
                print(f"   1. Open: https://webhook-test.com/{webhook_id}")
                print("   2. Copy the webhook payload JSON")
                print("   3. Save it to a file and use:")
                print("      python3 services/bot-manager/send_rtms_webhook.py <meeting_id> <uuid> <stream_id> <server_urls>")
                print("   4. Or use the capture script:")
                print("      cd services/vexa-bot")
                print("      make capture-webhook ZOOM_WEBHOOK_FILE=/path/to/webhook.json")
                print("\n💡 Make sure:")
                print("   1. The webhook URL is configured in Zoom App Marketplace")
                print("   2. RTMS has started in the meeting")
                print("   3. Zoom has sent the webhook")
                return
        
        print(f"✅ Found {len(payloads)} webhook payload(s)")
        
        # Find RTMS webhook
        rtms_webhook = find_rtms_webhook(payloads)
        
        if not rtms_webhook:
            if args.poll:
                print("⏳ No RTMS webhook yet, continuing to poll...")
                continue
            else:
                print("❌ No RTMS webhook (meeting.rtms_started) found in payloads.")
                print("\nAvailable payloads:")
                for i, p in enumerate(payloads[:3], 1):
                    print(f"  {i}. {json.dumps(p, indent=2)[:200]}...")
                return
        
        print("✅ Found RTMS webhook (meeting.rtms_started)!")
        
        # Extract RTMS details
        rtms_details = extract_rtms_details(rtms_webhook)
        
        print("\n📋 RTMS Details:")
        print(f"   Meeting UUID: {rtms_details['meeting_uuid']}")
        print(f"   Meeting ID: {rtms_details['meeting_id_numeric']}")
        print(f"   Stream ID: {rtms_details['rtms_stream_id'][:30]}..." if rtms_details['rtms_stream_id'] else "   Stream ID: None")
        print(f"   Server URLs: {rtms_details['server_urls']}")
        print(f"   Access Token: {'***' if rtms_details['access_token'] else 'None'}")
        
        # Verify meeting ID if provided
        if args.meeting_id:
            if rtms_details['meeting_id_numeric'] != args.meeting_id:
                print(f"\n⚠️  Warning: Meeting ID mismatch!")
                print(f"   Expected: {args.meeting_id}")
                print(f"   Found: {rtms_details['meeting_id_numeric']}")
                if args.poll:
                    print("   Continuing to poll...")
                    continue
        
        # Save for debugging
        save_for_debug(rtms_details)
        
        # Send to bot-manager
        if not args.save_only:
            send_to_bot_manager(rtms_details, args.meeting_id)
        
        print("\n" + "=" * 70)
        print("✅ Successfully processed RTMS webhook!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Bot-manager should have received the webhook and updated the bot")
        print("2. Check bot logs to see if it connected to RTMS")
        print("3. Or use interactive debug:")
        print("   cd services/vexa-bot")
        print("   make test-zoom")
        
        return
    
    print("\n⏰ Polling stopped (Ctrl+C or timeout)")


if __name__ == "__main__":
    asyncio.run(main())

