# Zoom App Setup Guide for RTMS SDK

## Overview
This guide documents the process for creating a Zoom OAuth app in the Zoom Marketplace to enable RTMS SDK integration for real-time audio streaming.

## Prerequisites
- Zoom account with developer access
- Access to Zoom App Marketplace (https://marketplace.zoom.us/)
- Webhook endpoint URL ready (for event subscriptions)

## Manual Setup Steps (Requires Authentication)

### Step 1: Sign In to Zoom Marketplace
1. Navigate to: https://marketplace.zoom.us/
2. Click "Sign in" in the top right
3. Authenticate with your Zoom account

### Step 2: Access Developer Section
1. After signing in, click "Develop" in the header
2. This should take you to the developer dashboard
3. If you don't see "Develop", you may need to request developer access

### Step 3: Create New App
1. Click "Build App" or "Create App"
2. Select "General App" type
3. Choose "User-Managed" app type (for RTMS SDK)

### Step 4: Configure App Basic Information
- **App Name**: e.g., "Vexa RTMS Bot"
- **App Description**: Describe your app's purpose
- **Company Name**: Your organization name
- **Developer Contact Information**: Email address
- **OAuth Redirect URL**: Your callback URL (e.g., `https://your-domain.com/oauth/callback`)

### Step 5: Enable Event Subscriptions (REQUIRED for RTMS)
1. Navigate to "Features" → "Event Subscription"
2. Enable "Event Subscription"
3. Add a new subscription:
   - **Subscription Name**: e.g., "RTMS Events"
   - **Event Notification Endpoint URL**: Your webhook endpoint (e.g., `https://your-domain.com/webhooks/zoom`)
4. Subscribe to RTMS events:
   - `meeting.rtms_started` - Triggered when RTMS session starts
   - `meeting.rtms_stopped` - Triggered when RTMS session ends
5. Save the **Webhook Secret Token** (you'll need this for webhook verification)

### Step 6: Configure OAuth Scopes (REQUIRED)
Navigate to "Scopes" and add the following scopes:

**Meeting Scopes:**
- `meeting:read:meeting_audio` - Read meeting audio (REQUIRED for RTMS)
- `meeting:read:meeting_video` - Read meeting video (optional)
- `meeting:read:meeting_transcript` - Read transcripts (optional)

**RTMS Scopes:**
- `rtms:read:rtms_started` - RTMS start events
- `rtms:read:rtms_stopped` - RTMS stop events

### Step 7: Obtain Credentials
After saving your app configuration, you'll receive:
- **Client ID** - OAuth app identifier
- **Client Secret** - OAuth app secret (keep secure!)
- **Webhook Secret Token** - For webhook verification

### Step 8: Activate App
1. Review all settings
2. Click "Activate" or "Submit for Review" (if publishing to marketplace)
3. For development/testing, you can activate without marketplace review

## Automation Limitations

The following steps **CANNOT** be fully automated via browser automation because:
1. **Authentication Required**: Zoom Marketplace requires user sign-in
2. **Account Verification**: May require email verification or 2FA
3. **Developer Access**: May need to request developer access first
4. **Security**: OAuth credentials should be manually copied and stored securely

## What CAN Be Automated (After Manual Setup)

Once you have the app created, you can automate:
- Testing webhook endpoints
- Verifying OAuth token generation
- Testing RTMS SDK connection
- Validating event subscriptions

## Environment Variables to Set

After obtaining credentials, add to your environment:

```bash
ZOOM_CLIENT_ID=your_client_id_here
ZOOM_CLIENT_SECRET=your_client_secret_here
ZOOM_WEBHOOK_SECRET=your_webhook_secret_here
ZOOM_REDIRECT_URI=https://your-domain.com/oauth/callback
ZOOM_WEBHOOK_URL=https://your-domain.com/webhooks/zoom
```

## Next Steps

1. Store credentials securely (use environment variables or secret management)
2. Implement webhook endpoint to receive RTMS events
3. Implement OAuth token generation/refresh
4. Test RTMS SDK connection with meeting access token
5. Verify audio streaming and speaker detection

## References

- [Zoom Developer Portal](https://developers.zoom.us/)
- [RTMS SDK Documentation](https://developers.zoom.us/docs/rtms/)
- [OAuth App Setup Guide](https://developers.zoom.us/docs/api/rest/using-oauth-apis/)
- [Event Subscriptions](https://developers.zoom.us/docs/api/rest/webhook-reference/)

