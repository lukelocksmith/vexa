# Testing Meeting SDK Integration

## Prerequisites

1. **Meeting SDK Binary**: The Zoom Meeting SDK C++ binary must be built and available
2. **Docker Image**: The Vexa bot Docker image must be built
3. **TypeScript Build**: The TypeScript code must be compiled
4. **Zoom Credentials**: ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET must be set

## Step 1: Build Meeting SDK Binary

```bash
cd /Users/dmitriygrankin/dev/meetingsdk-headless-linux-sample

# Ensure the Zoom SDK library is in lib/zoomsdk/
# Then build the binary
./bin/entry.sh --help  # This will build it on first run
# Or manually:
mkdir -p build
cmake -B build -S . --preset debug
cmake --build build
# Binary will be at: build/zoomsdk
```

## Step 2: Build Vexa Bot Docker Image

```bash
cd /Users/dmitriygrankin/dev/vexa/services/vexa-bot
make build
```

## Step 3: Set Up Meeting SDK Binary Path

The Meeting SDK binary needs to be accessible to the Docker container. Options:

### Option A: Copy binary into Docker image (Recommended for testing)

Update `core/Dockerfile` to copy the Meeting SDK binary:

```dockerfile
# Add after line 24 (COPY . .)
COPY --from=meetingsdk /path/to/meetingsdk-headless-linux-sample/build/zoomsdk /app/zoomsdk
RUN chmod +x /app/zoomsdk
```

Or mount it as a volume in the hot-debug script.

### Option B: Mount binary from host

Update `core/src/platforms/hot-debug.sh` to mount the Meeting SDK binary:

```bash
-v /Users/dmitriygrankin/dev/meetingsdk-headless-linux-sample/build/zoomsdk:/app/zoomsdk:ro
```

And set environment variable:
```bash
-e ZOOM_MEETING_SDK_PATH=/app/zoomsdk
```

## Step 4: Run the Test

```bash
cd /Users/dmitriygrankin/dev/vexa/services/vexa-bot

# Set Zoom credentials (if not in .env)
export ZOOM_CLIENT_ID="your-client-id"
export ZOOM_CLIENT_SECRET="your-client-secret"

# Run test
make test-zoom MEETING_URL="https://us05web.zoom.us/j/82491759979?pwd=aDdPBnIV4uMSI0I3N7Ff16gWf8NFc1.1"
```

## Expected Behavior

1. Meeting SDK process should start
2. Bot should join the meeting
3. Audio should be captured via Unix socket (`/tmp/meeting.sock`)
4. Audio should be sent to WhisperLive
5. Bot should be able to leave gracefully

## Troubleshooting

### Meeting SDK binary not found
- Ensure the binary is built: `ls -la /Users/dmitriygrankin/dev/meetingsdk-headless-linux-sample/build/zoomsdk`
- Check that the path is correct in the Docker container
- Verify `ZOOM_MEETING_SDK_PATH` environment variable

### Socket connection failed
- Check that Meeting SDK is running: `ps aux | grep zoomsdk`
- Verify socket exists: `ls -la /tmp/meeting.sock`
- Check Meeting SDK logs for errors

### Audio not flowing
- Verify WhisperLive is running and accessible
- Check socket client connection status in logs
- Verify Meeting SDK is in transcribe mode (--transcribe flag)

## Notes

- The Meeting SDK binary must be built for the same architecture as the Docker container (Linux x86_64)
- The socket path `/tmp/meeting.sock` must be accessible within the container
- PulseAudio setup is required for Meeting SDK (handled in entry.sh)





