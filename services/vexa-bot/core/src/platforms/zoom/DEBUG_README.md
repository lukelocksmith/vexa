# Zoom RTMS Interactive Debugging Guide

This guide explains how to use the interactive debugging tools for Zoom RTMS integration.

## Prerequisites

1. **Build the bot image and dist:**
   ```bash
   cd services/vexa-bot
   make build
   ```

2. **Start a Zoom meeting** and ensure RTMS is enabled (the meeting host needs to enable RTMS).

## Step 1: Capture the RTMS Webhook

When RTMS starts in your Zoom meeting, Zoom will send a webhook event to the bot-manager. You need to capture this event to get the RTMS connection details.

### Option A: From bot-manager logs

1. Start a bot via the API (this will fail initially, but that's OK):
   ```bash
   python3 services/bot-manager/test_start_zoom_bot.py \
     "https://us05web.zoom.us/j/YOUR_MEETING_ID?pwd=YOUR_PASSCODE" \
     "YOUR_API_TOKEN"
   ```

2. When RTMS starts, check bot-manager logs for the webhook:
   ```bash
   docker compose logs bot-manager --tail 1000 | grep -A 20 "meeting.rtms_started"
   ```

3. Copy the webhook JSON payload and save it to a file:
   ```bash
   # Save the webhook JSON to a file
   cat > /tmp/zoom-webhook.json <<'EOF'
   {
     "event": "meeting.rtms_started",
     "payload": {
       "object": {
         "uuid": "meeting-uuid-here",
         "id": 123456789,
         "rtms": {
           "stream_id": "stream-id-here",
           "server_urls": "wss://rtms.zoom.us",
           "access_token": "access-token-here"
         }
       }
     }
   }
   EOF
   ```

### Option B: Manual webhook capture

If you have access to the Zoom webhook endpoint or can manually trigger it:

```bash
cd services/vexa-bot/core/src/platforms/zoom
./capture-webhook.sh
```

The script will prompt you to paste the webhook JSON or provide a file path.

## Step 2: Extract RTMS Details

The `capture-webhook.sh` script automatically extracts RTMS details and saves them:

- `debug/zoom-webhook-rtms.json` - Full webhook payload
- `debug/zoom-rtms-details.json` - Extracted RTMS connection details

## Step 3: Run Interactive Debug Session

Once you have the RTMS details, start the interactive debug session:

```bash
cd services/vexa-bot
make test-zoom
```

This will:
1. Load RTMS details from `debug/zoom-rtms-details.json`
2. Start the bot container with hot-reload enabled
3. Connect to the Zoom RTMS stream using the captured details
4. Allow you to monitor logs and send Redis commands

## Step 4: Monitor and Control

### View bot logs:
```bash
docker logs -f vexa-bot-hot
```

### Send Redis commands:

**Leave the meeting:**
```bash
make publish-leave
```

**Update RTMS config (if needed):**
```bash
make publish-rtms-config \
  RTMS_STREAM_ID="your-stream-id" \
  SERVER_URLS="wss://rtms.zoom.us" \
  MEETING_UUID="meeting-uuid"
```

**Send custom command:**
```bash
make publish DATA='{"action":"your-action"}'
```

## Quick Reference

### Makefile Targets

- `make build` - Build Docker image and create dist/ for hot-reload
- `make rebuild` - Rebuild dist/ (fast, for code changes)
- `make capture-webhook [ZOOM_WEBHOOK_FILE=path]` - Capture Zoom RTMS webhook
- `make test-zoom [ZOOM_RTMS_DETAILS=path]` - Start interactive Zoom debug session
- `make publish DATA='...'` - Send Redis command to bot
- `make publish-leave` - Send leave command to bot
- `make publish-rtms-config RTMS_STREAM_ID=... SERVER_URLS=... MEETING_UUID=...` - Update RTMS config

### Environment Variables

The bot will use Zoom credentials from:
1. `.env` file (ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET)
2. Environment variables
3. Bot config (passed via BOT_CONFIG)

### RTMS Details Structure

The extracted RTMS details JSON contains:
```json
{
  "meeting_uuid": "zoom-meeting-uuid",
  "meeting_id_numeric": 123456789,
  "rtms_stream_id": "rtms-stream-id",
  "server_urls": "wss://rtms.zoom.us",
  "access_token": "rtms-access-token",
  "join_url": "https://zoom.us/j/..."
}
```

## Troubleshooting

### Bot fails with "RTMS stream ID is required"

- Ensure you've captured the webhook before RTMS starts
- Check that `debug/zoom-rtms-details.json` exists and contains valid data
- Verify the meeting has RTMS enabled

### Bot can't connect to RTMS

- Verify the `server_urls` in RTMS details are correct
- Check that the `access_token` hasn't expired
- Ensure the meeting UUID matches the one in RTMS details

### Webhook not received

- Check Zoom app webhook configuration
- Verify webhook endpoint is accessible: `http://your-domain/webhooks/zoom/rtms`
- Check bot-manager logs for webhook delivery attempts

## Example Workflow

```bash
# 1. Build once
cd services/vexa-bot
make build

# 2. Start a Zoom meeting and enable RTMS

# 3. Capture webhook (from logs or manually)
make capture-webhook

# 4. Start debug session
make test-zoom

# 5. In another terminal, monitor logs
docker logs -f vexa-bot-hot

# 6. When done, send leave command
make publish-leave
```





