import { Page } from "playwright";
import { BotConfig } from "../../types";
import { LeaveReason } from "../shared/meetingFlow";
import { log } from "../../utils";
import { getMeetingSDKService, setMeetingSDKService } from "./join";

export async function leaveZoomMeeting(
  page: Page | null,
  botConfig?: BotConfig,
  reason?: LeaveReason
): Promise<boolean> {
  const meetingSDKService = getMeetingSDKService();

  if (!meetingSDKService) {
    log("[Zoom] No Meeting SDK service to disconnect");
    return true; // Already disconnected
  }

  try {
    log(`[Zoom] Leaving meeting${reason ? ` (reason: ${reason})` : ''}`);

    // Cleanup recording if active
    if ((globalThis as any).__zoomRecordingCleanup) {
      try {
        (globalThis as any).__zoomRecordingCleanup();
        delete (globalThis as any).__zoomRecordingCleanup;
      } catch (error: any) {
        log(`[Zoom] Error during recording cleanup: ${error.message}`);
      }
    }

    // Leave Meeting SDK
    await meetingSDKService.leave();
    await meetingSDKService.cleanup();
    setMeetingSDKService(null);

    log("[Zoom] Successfully left meeting");
    return true;
  } catch (error: any) {
    log(`[Zoom] Error leaving meeting: ${error.message}`);
    // Try to cleanup anyway
    try {
      await meetingSDKService.cleanup();
      setMeetingSDKService(null);
    } catch (cleanupError: any) {
      log(`[Zoom] Error during cleanup: ${cleanupError.message}`);
    }
    return false;
  }
}

