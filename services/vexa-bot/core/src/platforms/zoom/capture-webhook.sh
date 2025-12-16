#!/bin/bash

# Script to capture Zoom RTMS webhook event
# Usage:
#   1. Start a meeting and wait for RTMS to start
#   2. Copy the webhook payload from Zoom or bot-manager logs
#   3. Run: ./capture-webhook.sh <webhook-payload-file> or paste JSON

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || (cd "$SCRIPT_DIR/../../../.." && pwd))"
DEBUG_DIR="$REPO_ROOT/debug"
mkdir -p "$DEBUG_DIR"

WEBHOOK_FILE="${1:-}"
WEBHOOK_OUTPUT="$DEBUG_DIR/zoom-webhook-rtms.json"

echo "🔍 Zoom RTMS Webhook Capture"
echo "============================"

# Try to resolve file path (absolute, relative to script, or relative to repo root)
if [ -n "$WEBHOOK_FILE" ]; then
    # Try absolute path first
    if [ -f "$WEBHOOK_FILE" ]; then
        echo "📄 Reading webhook from file: $WEBHOOK_FILE"
        WEBHOOK_JSON=$(cat "$WEBHOOK_FILE")
    # Try relative to script directory
    elif [ -f "$SCRIPT_DIR/$WEBHOOK_FILE" ]; then
        echo "📄 Reading webhook from file: $SCRIPT_DIR/$WEBHOOK_FILE"
        WEBHOOK_JSON=$(cat "$SCRIPT_DIR/$WEBHOOK_FILE")
    # Try relative to repo root
    elif [ -f "$REPO_ROOT/$WEBHOOK_FILE" ]; then
        echo "📄 Reading webhook from file: $REPO_ROOT/$WEBHOOK_FILE"
        WEBHOOK_JSON=$(cat "$REPO_ROOT/$WEBHOOK_FILE")
    # Try relative to debug directory
    elif [ -f "$DEBUG_DIR/$WEBHOOK_FILE" ]; then
        echo "📄 Reading webhook from file: $DEBUG_DIR/$WEBHOOK_FILE"
        WEBHOOK_JSON=$(cat "$DEBUG_DIR/$WEBHOOK_FILE")
    else
        # Treat as JSON string if not a valid file path
        echo "📝 Using provided webhook JSON string"
        WEBHOOK_JSON="$WEBHOOK_FILE"
    fi
else
    echo ""
    echo "Please provide the Zoom RTMS webhook payload:"
    echo "  1. From bot-manager logs (look for 'meeting.rtms_started' event)"
    echo "  2. From Zoom webhook delivery (if configured)"
    echo "  3. Or paste the JSON payload below"
    echo ""
    echo "Expected format:"
    echo '  {"event":"meeting.rtms_started","payload":{"object":{"uuid":"...","rtms":{"stream_id":"...","server_urls":"...","access_token":"..."}}}}'
    echo ""
    read -p "Paste webhook JSON (or press Enter to read from file): " WEBHOOK_JSON
    
    if [ -z "$WEBHOOK_JSON" ]; then
        read -p "Enter webhook file path: " WEBHOOK_FILE
        if [ -f "$WEBHOOK_FILE" ]; then
            WEBHOOK_JSON=$(cat "$WEBHOOK_FILE")
        else
            echo "❌ File not found: $WEBHOOK_FILE"
            exit 1
        fi
    fi
fi

# Validate JSON
if ! echo "$WEBHOOK_JSON" | python3 -m json.tool >/dev/null 2>&1; then
    echo "❌ Invalid JSON format"
    exit 1
fi

# Extract RTMS details
echo ""
echo "📋 Extracting RTMS details..."

RTMS_DETAILS=$(python3 <<EOF
import json
import sys

try:
    webhook = json.loads('''$WEBHOOK_JSON''')
    
    if webhook.get('event') != 'meeting.rtms_started':
        print(f"⚠️  Warning: Expected 'meeting.rtms_started', got: {webhook.get('event')}", file=sys.stderr)
    
    obj = webhook.get('payload', {}).get('object', {})
    rtms = obj.get('rtms', {})
    
    if not rtms:
        print("❌ RTMS data not found in webhook", file=sys.stderr)
        sys.exit(1)
    
    details = {
        'meeting_uuid': obj.get('uuid'),
        'meeting_id_numeric': obj.get('id'),
        'rtms_stream_id': rtms.get('stream_id'),
        'server_urls': rtms.get('server_urls'),
        'access_token': rtms.get('access_token'),
        'join_url': obj.get('join_url', '')
    }
    
    print(json.dumps(details, indent=2))
except Exception as e:
    print(f"❌ Error parsing webhook: {e}", file=sys.stderr)
    sys.exit(1)
EOF
)

if [ $? -ne 0 ]; then
    echo "❌ Failed to extract RTMS details"
    exit 1
fi

# Save webhook and details
echo "$WEBHOOK_JSON" > "$WEBHOOK_OUTPUT"
echo "$RTMS_DETAILS" > "$DEBUG_DIR/zoom-rtms-details.json"

echo "✅ Webhook captured and saved to: $WEBHOOK_OUTPUT"
echo "✅ RTMS details saved to: $DEBUG_DIR/zoom-rtms-details.json"
echo ""
echo "📋 RTMS Details:"
echo "$RTMS_DETAILS" | python3 -m json.tool
echo ""
echo "🚀 Next step: Run 'make test-zoom' to start debugging with these RTMS details"

