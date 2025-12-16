import { Page } from "playwright";
import { BotConfig } from "../../types";
import { log } from "../../utils";
import { ZoomMeetingSDKService } from "../../services/zoom-meeting-sdk";

// Store Meeting SDK service instance globally for this session
let meetingSDKService: ZoomMeetingSDKService | null = null;

export function getMeetingSDKService(): ZoomMeetingSDKService | null {
  return meetingSDKService;
}

export function setMeetingSDKService(service: ZoomMeetingSDKService | null): void {
  meetingSDKService = service;
}

export async function joinZoomMeeting(
  page: Page | null,
  botConfig: BotConfig
): Promise<void> {
  try {
    log(`[Zoom] Joining meeting: ${botConfig.meetingUrl || botConfig.nativeMeetingId}`);

    // Get Zoom credentials from config or environment
    const clientId = botConfig.zoomClientId || process.env.ZOOM_CLIENT_ID;
    const clientSecret = botConfig.zoomClientSecret || process.env.ZOOM_CLIENT_SECRET;

    if (!clientId || !clientSecret) {
      throw new Error("Zoom Client ID and Client Secret are required");
    }

    // Get meeting URL - required for Meeting SDK
    const meetingUrl = botConfig.meetingUrl;
    if (!meetingUrl) {
      throw new Error("Meeting URL is required for Meeting SDK");
    }

    // Initialize Meeting SDK service
    const service = new ZoomMeetingSDKService({
      clientId,
      clientSecret,
      sdkPath: process.env.ZOOM_MEETING_SDK_PATH,
    });

    await service.initialize();
    setMeetingSDKService(service);

    // Join meeting with URL
    await service.join(meetingUrl, botConfig.botName || "Vexa Bot");

    log(`[Zoom] Successfully initiated join to meeting: ${meetingUrl}`);
  } catch (error: any) {
    log(`[Zoom] Error joining meeting: ${error.message}`);
    if (meetingSDKService) {
      try {
        await meetingSDKService.cleanup();
      } catch (cleanupError: any) {
        log(`[Zoom] Error during cleanup: ${cleanupError.message}`);
      }
      setMeetingSDKService(null);
    }
    throw error;
  }
}

