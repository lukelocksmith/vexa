#!/bin/bash
# Rebuild TypeScript and test Meeting SDK

set -e

echo "🔨 Rebuilding TypeScript code..."
cd /Users/dmitriygrankin/dev/vexa/services/vexa-bot
make rebuild

echo ""
echo "🧪 Running test..."
make test-zoom MEETING_URL="https://us05web.zoom.us/j/82491759979?pwd=aDdPBnIV4uMSI0I3N7Ff16gWf8NFc1.1"





