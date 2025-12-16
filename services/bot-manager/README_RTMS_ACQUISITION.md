# Acquiring RTMS Details for Zoom Meetings

## The Challenge

For **instant meetings** (personal meeting rooms), RTMS details cannot be obtained via Zoom API. They are only provided via webhook events when RTMS starts.

## Solutions

### Option 1: Configure Webhook in Zoom Marketplace (Recommended for Production)

1. **Expose your webhook endpoint publicly:**
   - Use ngrok: `ngrok http 8080` (or your bot-manager port)
   - Or deploy to a public server
   - Get the public URL (e.g., `https://abc123.ngrok.io`)

2. **Configure in Zoom App Marketplace:**
   - Go to: https://marketplace.zoom.us/develop/apps
   - Edit your Server-to-Server OAuth app
   - Navigate to "Event Subscriptions"
   - Add webhook URL: `https://your-public-url/webhooks/zoom/rtms`
   - Enable events:
     - `meeting.rtms_started`
     - `meeting.rtms_stopped`
   - Save and activate

3. **Start RTMS in meeting:**
   - Join the meeting
   - Enable RTMS (if not auto-enabled)
   - When RTMS starts, Zoom will send webhook to your endpoint
   - Bot-manager will receive and process the webhook automatically

### Option 2: Use ngrok for Local Testing

```bash
# Terminal 1: Start ngrok tunnel
ngrok http 8080

# Terminal 2: Note the public URL (e.g., https://abc123.ngrok.io)
# Configure this URL in Zoom App Marketplace Event Subscriptions

# Terminal 3: Start bot and wait for webhook
python3 services/bot-manager/test_start_zoom_bot.py \
  "https://us05web.zoom.us/j/86593345515?pwd=..." \
  "your_api_token"
```

### Option 3: Manual Webhook (When You Have RTMS Details)

If you have RTMS details from another source (e.g., Zoom meeting interface, logs, etc.):

```bash
python3 services/bot-manager/send_rtms_webhook.py \
  <meeting_id> \
  <meeting_uuid> \
  <rtms_stream_id> \
  <server_urls> \
  [access_token]
```

### Option 4: Interactive Debug with Captured Webhook

If you receive a webhook payload (from logs, Zoom dashboard, etc.):

```bash
# Save webhook JSON to a file
cat > /tmp/zoom-webhook.json <<'EOF'
{
  "event": "meeting.rtms_started",
  "payload": {
    "object": {
      "uuid": "...",
      "rtms": {
        "stream_id": "...",
        "server_urls": "...",
        "access_token": "..."
      }
    }
  }
}
EOF

# Capture and use for debugging
cd services/vexa-bot
make capture-webhook ZOOM_WEBHOOK_FILE=/tmp/zoom-webhook.json
make test-zoom
```

## Current Status

- ✅ Webhook endpoint implemented: `/webhooks/zoom/rtms`
- ✅ Bot can wait for RTMS details via webhook
- ✅ Bot can receive RTMS config updates via Redis
- ⚠️  Webhook URL not configured in Zoom Marketplace (needs public URL)
- ⚠️  Meeting is instant meeting (RTMS details not available via API)

## Next Steps

1. **For immediate testing:** Set up ngrok and configure webhook URL in Zoom Marketplace
2. **For production:** Deploy bot-manager with public domain and configure webhook URL
3. **Alternative:** Manually provide RTMS details if you have them from the meeting





