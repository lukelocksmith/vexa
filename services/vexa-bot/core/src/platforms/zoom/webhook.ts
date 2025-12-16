import { log } from "../../utils";
import { BotConfig } from "../../types";

/**
 * RTMS webhook event payload structure
 */
export interface RTMSStartedWebhook {
  event: "meeting.rtms_started";
  payload: {
    account_id: string;
    object: {
      uuid: string; // Meeting UUID
      id: number; // Meeting ID
      host_id: string;
      topic: string;
      type: number;
      start_time: string;
      timezone: string;
      duration: number;
      join_url: string;
      rtms: {
        stream_id: string; // RTMS stream ID
        server_urls: string; // RTMS server URLs (comma-separated)
        access_token: string; // Access token for RTMS
      };
    };
  };
  event_ts: number;
}

export interface RTMSStoppedWebhook {
  event: "meeting.rtms_stopped";
  payload: {
    account_id: string;
    object: {
      uuid: string;
      id: number;
      rtms: {
        stream_id: string;
      };
    };
  };
  event_ts: number;
}

/**
 * Extract RTMS connection details from webhook event
 */
export function extractRTMSDetailsFromWebhook(
  webhookPayload: RTMSStartedWebhook
): {
  meetingUuid: string;
  rtmsStreamId: string;
  serverUrls: string;
  accessToken: string;
} {
  if (webhookPayload.event !== "meeting.rtms_started") {
    throw new Error(`Expected meeting.rtms_started event, got: ${webhookPayload.event}`);
  }

  const rtms = webhookPayload.payload.object.rtms;
  if (!rtms) {
    throw new Error("RTMS details not found in webhook payload");
  }

  return {
    meetingUuid: webhookPayload.payload.object.uuid,
    rtmsStreamId: rtms.stream_id,
    serverUrls: rtms.server_urls,
    accessToken: rtms.access_token,
  };
}

/**
 * Update BotConfig with RTMS details from webhook
 */
export function updateBotConfigWithRTMSDetails(
  botConfig: BotConfig,
  webhookPayload: RTMSStartedWebhook
): BotConfig {
  const rtmsDetails = extractRTMSDetailsFromWebhook(webhookPayload);

  return {
    ...botConfig,
    nativeMeetingId: rtmsDetails.meetingUuid,
    zoomRtmsStreamId: rtmsDetails.rtmsStreamId,
    zoomServerUrls: rtmsDetails.serverUrls,
    zoomAccessToken: rtmsDetails.accessToken,
    meetingUrl: webhookPayload.payload.object.join_url || botConfig.meetingUrl,
  };
}

/**
 * Validate webhook payload structure
 */
export function isValidRTMSWebhook(payload: any): payload is RTMSStartedWebhook {
  return (
    payload &&
    payload.event === "meeting.rtms_started" &&
    payload.payload &&
    payload.payload.object &&
    payload.payload.object.uuid &&
    payload.payload.object.rtms &&
    payload.payload.object.rtms.stream_id &&
    payload.payload.object.rtms.server_urls &&
    payload.payload.object.rtms.access_token
  );
}

/**
 * Parse webhook payload (handles both raw JSON and parsed objects)
 */
export function parseRTMSWebhook(payload: string | object): RTMSStartedWebhook {
  let parsed: any;
  
  if (typeof payload === "string") {
    try {
      parsed = JSON.parse(payload);
    } catch (error: any) {
      throw new Error(`Failed to parse webhook payload: ${error.message}`);
    }
  } else {
    parsed = payload;
  }

  if (!isValidRTMSWebhook(parsed)) {
    throw new Error("Invalid RTMS webhook payload structure");
  }

  return parsed;
}

