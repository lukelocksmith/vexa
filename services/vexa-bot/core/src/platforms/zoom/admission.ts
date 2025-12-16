import { Page } from "playwright";
import { BotConfig } from "../../types";
import { AdmissionResult, AdmissionDecision } from "../shared/meetingFlow";
import { log } from "../../utils";
import { getMeetingSDKService } from "./join";

export async function waitForZoomAdmission(
  page: Page | null,
  timeoutMs: number,
  botConfig: BotConfig
): Promise<AdmissionResult> {
  const startTime = Date.now();
  const meetingSDKService = getMeetingSDKService();

  if (!meetingSDKService) {
    log("[Zoom] Meeting SDK service not initialized");
    return { admitted: false, reason: "meeting_sdk_service_not_initialized" } as AdmissionDecision;
  }

  return new Promise<AdmissionResult>((resolve) => {
    let resolved = false;
    let timeoutId: NodeJS.Timeout | null = null;

    const checkConnection = () => {
      if (meetingSDKService.getConnected()) {
        if (!resolved) {
          resolved = true;
          if (timeoutId) clearTimeout(timeoutId);
          log("[Zoom] Successfully admitted to meeting");
          resolve(true);
        }
        return;
      }

      // Check if timeout exceeded
      if (Date.now() - startTime >= timeoutMs) {
        if (!resolved) {
          resolved = true;
          if (timeoutId) clearTimeout(timeoutId);
          log(`[Zoom] Admission timeout after ${timeoutMs}ms`);
          resolve({ admitted: false, reason: "admission_timeout" } as AdmissionDecision);
        }
        return;
      }
    };

    // Check connection status immediately
    checkConnection();

    // Set up periodic checks
    const checkInterval = setInterval(() => {
      if (resolved) {
        clearInterval(checkInterval);
        return;
      }
      checkConnection();
    }, 500); // Check every 500ms

    // Set timeout
    timeoutId = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        clearInterval(checkInterval);
        log(`[Zoom] Admission timeout after ${timeoutMs}ms`);
        resolve({ admitted: false, reason: "admission_timeout" } as AdmissionDecision);
      }
    }, timeoutMs);
  });
}

