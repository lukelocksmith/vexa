#!/usr/bin/env python3
"""
Process a webhook payload manually copied from webhook-test.com.

Usage:
    python3 process_webhook_from_test.py <webhook_json_file>
    python3 process_webhook_from_test.py -  # Read from stdin
    
Example:
    # Copy JSON from webhook-test.com and save to file
    python3 process_webhook_from_test.py /tmp/webhook.json
    
    # Or pipe directly
    echo '{"event":"meeting.rtms_started",...}' | python3 process_webhook_from_test.py -
"""

import sys
import json
import httpx
from pathlib import Path

BOT_MANAGER_URL = "http://localhost:8080"


def extract_rtms_details(webhook_payload: dict) -> dict:
    """Extract RTMS details from webhook payload."""
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


def send_to_bot_manager(rtms_details: dict):
    """Send RTMS webhook to bot-manager endpoint."""
    webhook_payload = {
        "event": "meeting.rtms_started",
        "payload": {
            "account_id": "",
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
    
    print(f"📤 Sending RTMS webhook to bot-manager: {url}")
    
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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    source = sys.argv[1]
    
    # Read webhook payload
    if source == '-':
        print("📥 Reading webhook payload from stdin...")
        webhook_json = sys.stdin.read()
    else:
        webhook_file = Path(source)
        if not webhook_file.exists():
            print(f"❌ File not found: {webhook_file}")
            sys.exit(1)
        print(f"📥 Reading webhook payload from: {webhook_file}")
        webhook_json = webhook_file.read_text()
    
    # Parse JSON
    try:
        webhook_payload = json.loads(webhook_json)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        sys.exit(1)
    
    # Check if it's an RTMS webhook
    event = webhook_payload.get('event')
    if event != 'meeting.rtms_started':
        print(f"⚠️  Warning: Expected 'meeting.rtms_started', got: {event}")
        if input("Continue anyway? (y/n): ").lower() != 'y':
            sys.exit(1)
    
    # Extract RTMS details
    rtms_details = extract_rtms_details(webhook_payload)
    
    print("\n📋 RTMS Details:")
    print(f"   Meeting UUID: {rtms_details['meeting_uuid']}")
    print(f"   Meeting ID: {rtms_details['meeting_id_numeric']}")
    print(f"   Stream ID: {rtms_details['rtms_stream_id'][:30]}..." if rtms_details['rtms_stream_id'] else "   Stream ID: None")
    print(f"   Server URLs: {rtms_details['server_urls']}")
    print(f"   Access Token: {'***' if rtms_details['access_token'] else 'None'}")
    
    # Save for debugging
    debug_file = Path(__file__).parent.parent / 'debug' / 'zoom-rtms-details.json'
    debug_file.parent.mkdir(exist_ok=True)
    with open(debug_file, 'w') as f:
        json.dump(rtms_details, f, indent=2)
    print(f"\n💾 Saved RTMS details to: {debug_file}")
    
    # Send to bot-manager
    send_to_bot_manager(rtms_details)
    
    print("\n✅ Successfully processed RTMS webhook!")
    print("\nNext steps:")
    print("1. Bot-manager should have received the webhook and updated the bot")
    print("2. Check bot logs to see if it connected to RTMS")
    print("3. Or use interactive debug:")
    print("   cd services/vexa-bot")
    print("   make test-zoom")


if __name__ == "__main__":
    main()





