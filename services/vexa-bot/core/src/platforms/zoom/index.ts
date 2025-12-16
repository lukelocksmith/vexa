import { Page } from "playwright";
import { BotConfig } from "../../types";
import { runMeetingFlow, PlatformStrategies } from "../shared/meetingFlow";
import { joinZoomMeeting } from "./join";
import { waitForZoomAdmission } from "./admission";
import { startZoomRecording } from "./recording";
import { leaveZoomMeeting } from "./leave";
import { startZoomRemovalMonitor } from "./removal";

// --- Zoom Main Handler ---

export async function handleZoom(
  botConfig: BotConfig,
  page: Page | null,
  gracefulLeaveFunction: (page: Page | null, exitCode: number, reason: string, errorDetails?: any) => Promise<void>
): Promise<void> {
  
  const strategies: PlatformStrategies = {
    join: async (page: Page | null, botConfig: BotConfig) => {
      await joinZoomMeeting(page, botConfig);
    },
    waitForAdmission: waitForZoomAdmission,
    prepare: async (page: Page | null, botConfig: BotConfig) => {
      // No browser prep needed for Zoom
      return;
    },
    startRecording: startZoomRecording,
    startRemovalMonitor: startZoomRemovalMonitor,
    leave: leaveZoomMeeting
  };

  await runMeetingFlow(
    "zoom",
    botConfig,
    page,
    gracefulLeaveFunction,
    strategies
  );
}

// Export the leave function for external use
export { leaveZoomMeeting };

