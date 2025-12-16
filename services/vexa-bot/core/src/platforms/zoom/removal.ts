import { Page } from "playwright";
import { log } from "../../utils";
import { getMeetingSDKService } from "./join";

export function startZoomRemovalMonitor(
  page: Page | null,
  onRemoval?: () => void | Promise<void>
): () => void {
  const meetingSDKService = getMeetingSDKService();

  if (!meetingSDKService) {
    log("[Zoom] Cannot start removal monitor: Meeting SDK service not initialized");
    return () => {}; // Return no-op cleanup function
  }

  let isMonitoring = true;

  // Monitor Meeting SDK process status
  const checkInterval = setInterval(() => {
    if (!isMonitoring) {
      clearInterval(checkInterval);
      return;
    }

    // Check if process is still running and connected
    if (!meetingSDKService.getConnected()) {
      log(`[Zoom] Detected removal: Meeting SDK process disconnected`);
      if (onRemoval) {
        try {
          Promise.resolve(onRemoval()).catch((error: any) => {
            log(`[Zoom] Error in removal callback: ${error.message}`);
          });
        } catch (error: any) {
          log(`[Zoom] Error in removal callback: ${error.message}`);
        }
      }
      isMonitoring = false;
      clearInterval(checkInterval);
    }
  }, 1000); // Check every second

  log("[Zoom] Removal monitor started");

  // Return cleanup function
  return () => {
    isMonitoring = false;
    clearInterval(checkInterval);
    log("[Zoom] Removal monitor stopped");
  };
}

