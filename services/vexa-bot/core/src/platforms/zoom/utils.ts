import { BotConfig } from "../../types";
import { updateBotConfigWithRTMSDetails, parseRTMSWebhook } from "./webhook";
import { updateBotConfigFromAPI } from "./api";
import { log } from "../../utils";

/**
 * Helper to prepare BotConfig for Zoom RTMS connection
 * 
 * This function handles multiple input formats:
 * 1. Webhook payload (recommended) - extracts RTMS details from webhook
 * 2. Meeting URL/ID - attempts to fetch UUID and RTMS details from API
 * 3. Direct configuration - uses provided values
 */
export async function prepareZoomBotConfig(
  botConfig: BotConfig,
  options?: {
    webhookPayload?: string | object; // RTMS webhook event payload
    meetingIdentifier?: string; // Meeting URL, numeric ID, or UUID
  }
): Promise<BotConfig> {
  let config = botConfig;

  // Option 1: Process webhook payload (highest priority)
  if (options?.webhookPayload) {
    try {
      const webhook = parseRTMSWebhook(options.webhookPayload);
      config = updateBotConfigWithRTMSDetails(config, webhook);
      log(`[Zoom] Updated config from webhook: UUID=${config.nativeMeetingId}, StreamID=${config.zoomRtmsStreamId}`);
      return config;
    } catch (error: any) {
      log(`[Zoom] Failed to process webhook payload: ${error.message}`);
      // Fall through to other options
    }
  }

  // Option 2: Fetch from API using meeting identifier
  if (options?.meetingIdentifier) {
    try {
      config = await updateBotConfigFromAPI(config, options.meetingIdentifier);
      log(`[Zoom] Updated config from API: UUID=${config.nativeMeetingId}`);
      // Note: RTMS details may not be available via API - webhook is recommended
    } catch (error: any) {
      log(`[Zoom] Failed to fetch from API: ${error.message}`);
      // Fall through to use existing config
    }
  }

  // Option 3: Use existing config values (from BotConfig or environment variables)
  // Validate required fields
  const hasRequiredFields = 
    config.nativeMeetingId &&
    (config.zoomRtmsStreamId || process.env.ZOOM_RTMS_STREAM_ID) &&
    (config.zoomClientId || process.env.ZOOM_CLIENT_ID) &&
    (config.zoomClientSecret || process.env.ZOOM_CLIENT_SECRET);

  if (!hasRequiredFields) {
    const missing: string[] = [];
    if (!config.nativeMeetingId) missing.push("nativeMeetingId (meeting UUID)");
    if (!config.zoomRtmsStreamId && !process.env.ZOOM_RTMS_STREAM_ID) missing.push("zoomRtmsStreamId");
    if (!config.zoomClientId && !process.env.ZOOM_CLIENT_ID) missing.push("zoomClientId");
    if (!config.zoomClientSecret && !process.env.ZOOM_CLIENT_SECRET) missing.push("zoomClientSecret");

    throw new Error(
      `Missing required Zoom configuration: ${missing.join(", ")}\n` +
      `Provide via:\n` +
      `  1. Webhook payload (recommended)\n` +
      `  2. BotConfig fields\n` +
      `  3. Environment variables\n` +
      `  4. API fetch (for UUID only)`
    );
  }

  return config;
}

/**
 * Extract meeting ID from Zoom meeting URL
 */
export function extractMeetingIdFromUrl(url: string): string | null {
  // Match patterns like:
  // https://us05web.zoom.us/j/83307709878?pwd=...
  // https://zoom.us/j/83307709878
  // zoom.us/j/83307709878
  const match = url.match(/\/j\/(\d+)/);
  return match ? match[1] : null;
}

/**
 * Check if a string is a Zoom meeting UUID
 */
export function isMeetingUuid(identifier: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(identifier);
}

/**
 * Check if a string is a Zoom meeting URL
 */
export function isMeetingUrl(url: string): boolean {
  return /zoom\.us\/j\/\d+/.test(url);
}

