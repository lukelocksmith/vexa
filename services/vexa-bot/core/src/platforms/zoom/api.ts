import { log } from "../../utils";
import { BotConfig } from "../../types";

/**
 * Zoom API client for fetching RTMS connection details
 */
export class ZoomAPIClient {
  private clientId: string;
  private clientSecret: string;
  private baseUrl: string = "https://api.zoom.us/v2";

  constructor(clientId: string, clientSecret: string) {
    this.clientId = clientId;
    this.clientSecret = clientSecret;
  }

  /**
   * Get server-to-server OAuth token
   * Note: Requires account_id for server-to-server OAuth
   */
  private async getAccessToken(accountId?: string): Promise<string> {
    const credentials = Buffer.from(`${this.clientId}:${this.clientSecret}`).toString("base64");
    
    // For server-to-server OAuth, account_id is required
    // If not provided, try user-managed OAuth (may require different flow)
    const url = accountId 
      ? `https://zoom.us/oauth/token?grant_type=account_credentials&account_id=${accountId}`
      : "https://zoom.us/oauth/token?grant_type=client_credentials";

    try {
      // Use native fetch (Node 18+) or fallback to https module
      if (!globalThis.fetch) {
        throw new Error("fetch is not available. Node.js 18+ is required.");
      }
      
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Authorization": `Basic ${credentials}`,
          "Content-Type": "application/x-www-form-urlencoded",
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to get access token: ${response.status} ${errorText}`);
      }

      const data = await response.json();
      return data.access_token;
    } catch (error: any) {
      log(`[ZoomAPI] Error getting access token: ${error.message}`);
      log(`[ZoomAPI] Note: Server-to-server OAuth requires account_id. User-managed OAuth may require different flow.`);
      throw error;
    }
  }

  /**
   * Get meeting details by meeting ID
   */
  async getMeetingDetails(meetingId: string): Promise<{
    uuid: string;
    id: number;
    topic: string;
    join_url: string;
  }> {
    const accessToken = await this.getAccessToken();

    try {
      const response = await fetch(`${this.baseUrl}/meetings/${meetingId}`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to get meeting details: ${response.status} ${errorText}`);
      }

      const data = await response.json();
      return {
        uuid: data.uuid,
        id: data.id,
        topic: data.topic,
        join_url: data.join_url,
      };
    } catch (error: any) {
      log(`[ZoomAPI] Error getting meeting details: ${error.message}`);
      throw error;
    }
  }

  /**
   * Request RTMS connection details for a meeting
   * Note: This may require the meeting to be active and RTMS to be enabled
   */
  async requestRTMSConnection(meetingUuid: string): Promise<{
    stream_id: string;
    server_urls: string;
    access_token: string;
  }> {
    const accessToken = await this.getAccessToken();

    try {
      // Note: The actual endpoint may vary - this is based on typical Zoom API patterns
      // You may need to check Zoom API docs for the exact endpoint
      const response = await fetch(`${this.baseUrl}/meetings/${meetingUuid}/rtms`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action: "start",
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to request RTMS connection: ${response.status} ${errorText}`);
      }

      const data = await response.json();
      return {
        stream_id: data.stream_id,
        server_urls: data.server_urls,
        access_token: data.access_token,
      };
    } catch (error: any) {
      log(`[ZoomAPI] Error requesting RTMS connection: ${error.message}`);
      log(`[ZoomAPI] Note: RTMS connection details are typically provided via webhook events, not direct API calls`);
      throw error;
    }
  }

  /**
   * Convert meeting URL or numeric ID to meeting UUID
   */
  async getMeetingUuid(meetingIdentifier: string): Promise<string> {
    // If it's already a UUID format, return it
    if (meetingIdentifier.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i)) {
      return meetingIdentifier;
    }

    // Extract numeric meeting ID from URL if provided
    let meetingId: string = meetingIdentifier;
    const urlMatch = meetingIdentifier.match(/\/j\/(\d+)/);
    if (urlMatch) {
      meetingId = urlMatch[1];
    }

    // Get meeting details to retrieve UUID
    const meetingDetails = await this.getMeetingDetails(meetingId);
    return meetingDetails.uuid;
  }
}

/**
 * Helper function to update BotConfig with RTMS details from API
 */
export async function updateBotConfigFromAPI(
  botConfig: BotConfig,
  meetingIdentifier: string // Can be meeting URL, numeric ID, or UUID
): Promise<BotConfig> {
  const clientId = botConfig.zoomClientId || process.env.ZOOM_CLIENT_ID;
  const clientSecret = botConfig.zoomClientSecret || process.env.ZOOM_CLIENT_SECRET;

  if (!clientId || !clientSecret) {
    throw new Error("Zoom Client ID and Client Secret are required for API access");
  }

  const apiClient = new ZoomAPIClient(clientId, clientSecret);

  try {
    // Get meeting UUID
    const meetingUuid = await apiClient.getMeetingUuid(meetingIdentifier);
    log(`[ZoomAPI] Resolved meeting UUID: ${meetingUuid}`);

    // Try to get RTMS connection details
    // Note: This may fail if RTMS hasn't started yet - webhooks are the recommended approach
    try {
      const rtmsDetails = await apiClient.requestRTMSConnection(meetingUuid);
      
      return {
        ...botConfig,
        nativeMeetingId: meetingUuid,
        zoomRtmsStreamId: rtmsDetails.stream_id,
        zoomServerUrls: rtmsDetails.server_urls,
        zoomAccessToken: rtmsDetails.access_token,
      };
    } catch (rtmsError: any) {
      log(`[ZoomAPI] Could not get RTMS details via API: ${rtmsError.message}`);
      log(`[ZoomAPI] RTMS details are typically provided via webhook events when RTMS starts`);
      
      // Return config with UUID but without RTMS details
      // User will need to provide RTMS details via webhook or environment variables
      return {
        ...botConfig,
        nativeMeetingId: meetingUuid,
      };
    }
  } catch (error: any) {
    log(`[ZoomAPI] Error updating bot config: ${error.message}`);
    throw error;
  }
}

