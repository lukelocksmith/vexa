#!/bin/bash
# Quick test script for Meeting SDK integration

set -e

MEETING_URL="${1:-https://us05web.zoom.us/j/82491759979?pwd=aDdPBnIV4uMSI0I3N7Ff16gWf8NFc1.1}"

echo "🧪 Testing Meeting SDK Integration"
echo "=================================="
echo ""

# Check prerequisites
echo "1. Checking prerequisites..."

# Check Meeting SDK binary
MEETING_SDK_BINARY="../meetingsdk-headless-linux-sample/build/zoomsdk"
if [ -f "$MEETING_SDK_BINARY" ]; then
  echo "   ✅ Meeting SDK binary found: $MEETING_SDK_BINARY"
else
  echo "   ❌ Meeting SDK binary not found: $MEETING_SDK_BINARY"
  echo "      Build it first: cd ../meetingsdk-headless-linux-sample && ./bin/entry.sh --help"
  exit 1
fi

# Check Docker image
if docker images | grep -q "vexa-bot:test"; then
  echo "   ✅ Docker image 'vexa-bot:test' found"
else
  echo "   ⚠️  Docker image 'vexa-bot:test' not found"
  echo "      Building it now..."
  make build
fi

# Check dist directory
if [ -d "core/dist" ]; then
  echo "   ✅ TypeScript dist directory found"
else
  echo "   ⚠️  TypeScript dist directory not found"
  echo "      Building it now..."
  make rebuild
fi

echo ""
echo "2. Running test with meeting URL:"
echo "   $MEETING_URL"
echo ""

# Run the test
make test-zoom MEETING_URL="$MEETING_URL"





