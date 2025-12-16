export type BotConfig = {
  platform: "google_meet" | "zoom" | "teams",
  meetingUrl: string | null,
  botName: string,
  token: string,  // MeetingToken (HS256 JWT)
  connectionId: string,
  nativeMeetingId: string,
  language?: string | null,
  task?: string | null,
  redisUrl: string,
  container_name?: string,
  automaticLeave: {
    waitingRoomTimeout: number,
    noOneJoinedTimeout: number,
    everyoneLeftTimeout: number
  },
  reconnectionIntervalMs?: number,
  meeting_id: number,  // Required, not optional
  botManagerCallbackUrl?: string;
  // Zoom-specific (optional, only for zoom platform)
  zoomClientId?: string;
  zoomClientSecret?: string;
  zoomAccessToken?: string; // Meeting access token (JWT or OAuth)
  zoomRtmsStreamId?: string; // RTMS stream ID (from webhook or API)
  zoomServerUrls?: string; // RTMS server URLs (from webhook or API)
}
