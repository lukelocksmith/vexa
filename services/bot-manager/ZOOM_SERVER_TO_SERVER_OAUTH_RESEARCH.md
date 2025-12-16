# Zoom Server-to-Server OAuth Research & Solution

## Problem Summary

The current "General app 179" is configured as Admin-managed but still returns `unsupported_grant_type` when attempting Server-to-Server OAuth authentication. This is because **General apps do NOT support Server-to-Server OAuth**, regardless of whether they are User-managed or Admin-managed.

## Root Cause

**General apps** and **Server-to-Server OAuth apps** are different app types in Zoom:
- **General apps**: Support User Authorization OAuth flow (requires user interaction)
- **Server-to-Server OAuth apps**: Support Server-to-Server OAuth flow (no user interaction required)

Even if a General app is set to "Admin-managed", it cannot use Server-to-Server OAuth authentication. This is a fundamental limitation of the app type, not a configuration issue.

## Solution: Create a Server-to-Server OAuth App

### Step 1: Create New App Type

1. Navigate to [Zoom App Marketplace](https://marketplace.zoom.us/)
2. Click "Develop" → "Build App"
3. **IMPORTANT**: Select **"Server-to-Server OAuth"** app type (NOT "General app")
4. Click "Create"
5. Provide app name and details

### Step 2: Retrieve Credentials

After creation, you'll receive:
- **Client ID**
- **Client Secret**  
- **Account ID** (same as your account number: `5102261788`)

### Step 3: Configure Scopes

Navigate to "Scopes" section and add:

**Required for RTMS:**
- `rtms:read:rtms_notification:admin` - Real-time media streams notifications

**Required for Meeting Access:**
- `meeting:read:admin` - View meetings
- `meeting:read:meeting:admin` - View specific meeting details

**Optional but Recommended:**
- `user:read:admin` - View user information
- `account:read:admin` - View account information

### Step 4: Activate the App

1. Navigate to "Activation" section
2. Click "Activate your app"
3. Ensure all required fields are completed

**Note**: If activation is disabled, ensure:
- Your role has "Server-to-Server OAuth app" permission enabled
- All required scopes are added
- All required fields in Basic Information are completed

### Step 5: Update Environment Variables

Once the new Server-to-Server OAuth app is created, update `.env`:

```bash
ZOOM_CLIENT_ID=<new_client_id_from_server_to_server_app>
ZOOM_CLIENT_SECRET=<new_client_secret_from_server_to_server_app>
ZOOM_ACCOUNT_ID=5102261788  # Same account ID
```

## Open Source Examples

### 1. Zoom MCP Server
- **Repository**: https://github.com/osomai/zoom-mcp
- **Auth Method**: Server-to-Server OAuth 2.0
- **Use Case**: Model Context Protocol server for Zoom integration

### 2. Zoom Server-to-Server OAuth Token Generator
- **Repository**: https://github.com/zoom/server-to-server-oauth-token
- **Purpose**: Utility script demonstrating token generation
- **Language**: Python

### 3. Zoom Server-to-Server OAuth Starter API
- **Repository**: https://github.com/zoom/server-to-server-oauth-starter-api
- **Purpose**: Boilerplate for building internal apps with Zoom REST APIs
- **Features**: Handles authentication and token refresh

## Key Differences: General App vs Server-to-Server OAuth App

| Feature | General App | Server-to-Server OAuth App |
|---------|------------|----------------------------|
| OAuth Flow | User Authorization (requires user interaction) | Server-to-Server (no user interaction) |
| Grant Type | `authorization_code` | `account_credentials` |
| Use Case | User-facing apps, marketplace apps | Backend integrations, server-to-server |
| RTMS Support | ❌ Not supported | ✅ Supported |
| Admin-managed | ✅ Supported | ✅ Supported |
| User-managed | ✅ Supported | ❌ Not available |

## RTMS-Specific Requirements

For RTMS (Real-Time Media Streams) integration:
1. **App Type**: Must be "Server-to-Server OAuth" app
2. **Scopes**: 
   - `rtms:read:rtms_notification:admin` (required)
   - `meeting:read:admin` (required for meeting access)
3. **Authentication**: Uses Server-to-Server OAuth with `account_credentials` grant type
4. **Webhooks**: RTMS stream details (stream_id, server_urls, access_token) are provided via webhook events (`meeting.rtms_started`)

## References

1. **Official Zoom Documentation**: 
   - [Create a Server-to-Server OAuth app](https://marketplace.zoom.us/docs/guides/build/server-to-server-oauth-app/)

2. **Community Discussions**:
   - [Server-to-Server OAuth option is disabled](https://community.zoom.com/t5/Zoom-App-Marketplace/Server-to-Server-OAuth-option-is-disabled-for-me/m-p/240369)
   - [Cannot activate server-to-server OAuth app](https://community.zoom.com/t5/Zoom-App-Marketplace/Cannot-activate-server-to-server-OAuth-app/m-p/123288)

3. **Video Tutorial**:
   - [How to create and use a Server to Server OAuth app](https://www.youtube.com/watch?v=OkBE7CHVzho)

## Relevance of Official Zoom RTMS Repository

The [official Zoom RTMS repository](https://github.com/zoom/rtms) is **directly relevant** to our integration:

### What It Provides

1. **Official SDK Package**: This repository is the source of the `@zoom/rtms` npm package we're using in our codebase
2. **Cross-Platform Support**: Provides Node.js, Python, and Go bindings for the Zoom RTMS C SDK
3. **Authentication Method**: The RTMS SDK uses **Client ID and Client Secret** (not OAuth tokens) to generate signatures for connecting to RTMS WebSocket servers

### How Authentication Works

The RTMS integration requires **two levels of authentication**:

1. **Server-to-Server OAuth** (for Zoom REST API):
   - Used to call Zoom's REST API endpoints
   - Needed to get meeting information (UUID, details)
   - Needed to receive RTMS stream details via webhooks
   - Uses: `Client ID`, `Client Secret`, `Account ID`
   - Grant type: `account_credentials`

2. **RTMS SDK Signature** (for RTMS WebSocket connection):
   - The RTMS SDK uses `Client ID` and `Client Secret` to generate signatures
   - Signature is generated using `rtms.generateSignature()` method
   - Used to authenticate the WebSocket connection to RTMS servers
   - **Both credentials come from the same Server-to-Server OAuth app**

### Code Reference

In our implementation (`zoom-rtms.ts`), we can see:

```typescript
// Generate signature using Client ID and Secret
signature = rtms.generateSignature({
  client: this.config.clientId,
  secret: this.config.clientSecret,
  uuid: meetingUuid,
  streamId: rtmsStreamId,
});

// Join parameters include both client/secret AND signature
const joinParams: JoinParams = {
  meeting_uuid: meetingUuid,
  rtms_stream_id: rtmsStreamId,
  server_urls: serverUrls,
  client: this.config.clientId,
  secret: this.config.clientSecret,
  signature: signature,
  pollInterval: 10,
};
```

### Why Server-to-Server OAuth App is Required

1. **To get RTMS stream details**: The `rtms_stream_id` and `server_urls` are provided via:
   - Webhook events (`meeting.rtms_started`) - requires Server-to-Server OAuth app
   - OR Zoom REST API (if available) - requires Server-to-Server OAuth app

2. **To get meeting UUID**: Need to call `/meetings/{meetingId}` API endpoint - requires Server-to-Server OAuth

3. **To generate RTMS signatures**: The Client ID and Secret from the Server-to-Server OAuth app are used by the RTMS SDK to generate connection signatures

### Conclusion

The official RTMS repository confirms that:
- ✅ We're using the correct SDK (`@zoom/rtms`)
- ✅ Our authentication approach is correct (Client ID/Secret for signatures)
- ❌ **We MUST have a Server-to-Server OAuth app** to:
  - Get meeting information via REST API
  - Receive RTMS webhook events
  - Obtain the Client ID/Secret needed for RTMS SDK signatures

## Next Steps

1. ✅ **Create new Server-to-Server OAuth app** in Zoom Marketplace
2. ✅ **Configure RTMS and meeting scopes**
3. ✅ **Activate the app**
4. ✅ **Update `.env` with new credentials**
5. ✅ **Test OAuth token generation**
6. ✅ **Test meeting info retrieval**
7. ✅ **Test RTMS integration**

## Current Status

- ✅ URL parsing: Working
- ✅ Credentials retrieved: Client ID, Client Secret, Account ID
- ✅ App switched to Admin-managed: Done (but insufficient - wrong app type)
- ✅ Scopes added: RTMS and meeting scopes added (but to wrong app type)
- ✅ RTMS SDK integration: Code is correct, using official `@zoom/rtms` package
- ❌ **Server-to-Server OAuth**: Blocked - need to create new app with correct type

