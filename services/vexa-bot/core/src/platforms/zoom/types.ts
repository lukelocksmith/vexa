export interface ZoomMeetingConfig {
  meetingId: string;
  accessToken: string;
}

export interface ZoomParticipant {
  id: string;
  name?: string;
  isSpeaking?: boolean;
}

