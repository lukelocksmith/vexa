import { log } from '../utils';
// @ts-ignore - RTMS SDK types may be incomplete
import rtms from '@zoom/rtms';
// @ts-ignore - RTMS SDK types may be incomplete
const Client = (rtms as any).Client;
type JoinParams = any;
type AudioDataCallback = any;
type UserUpdateCallback = any;

export interface RTMSConfig {
  clientId: string;
  clientSecret: string;
}

export interface ParticipantEvent {
  type: 'participant_joined' | 'participant_left' | 'participant_speaking' | 'audio_source_changed';
  participantId: string;
  participantName?: string;
  timestamp?: number;
}

export interface SessionEvent {
  type: 'session_started' | 'session_ended' | 'session_error' | 'connection_established' | 'connection_lost';
  data?: any;
}

export class ZoomRTMSService {
  private client: any = null; // @ts-ignore - RTMS Client type
  private config: RTMSConfig;
  private isConnected: boolean = false;
  private audioCallbacks: Array<(audioData: Buffer) => void> = [];
  private sessionEventCallbacks: Array<(event: SessionEvent) => void> = [];
  private participantEventCallbacks: Array<(event: ParticipantEvent) => void> = [];

  constructor(config: RTMSConfig) {
    this.config = config;
  }

  /**
   * Initialize RTMS SDK with credentials
   */
  async initialize(): Promise<void> {
    try {
      // Debug: Check what we imported
      const rtmsClient = (rtms as any).Client;
      log(`[ZoomRTMS] Debug - rtms: ${rtms ? 'defined' : 'undefined'}, rtms.Client: ${rtmsClient ? 'defined' : 'undefined'}, Client const: ${Client ? 'defined' : 'undefined'}`);
      
      const ActualClient = Client || rtmsClient;
      if (!ActualClient) {
        log(`[ZoomRTMS] Debug - rtms object keys: ${rtms ? Object.keys(rtms).join(', ') : 'N/A'}`);
        throw new Error('RTMS Client class not found. Check @zoom/rtms package installation and ensure it is compiled for the target platform.');
      }
      
      // Initialize RTMS SDK (static method)
      // @ts-ignore - RTMS SDK API
      if (rtms && typeof rtms.isInitialized === 'function' && !rtms.isInitialized()) {
        // @ts-ignore - RTMS SDK API
        if (typeof ActualClient.initialize === 'function') {
          // @ts-ignore - RTMS SDK API
          ActualClient.initialize();
        } else {
          log('[ZoomRTMS] Warning: Client.initialize() not available, skipping initialization');
        }
      }

      // Create client instance
      // @ts-ignore - RTMS SDK API
      this.client = new ActualClient();

      // Set up event handlers
      this.setupEventHandlers();

      log('[ZoomRTMS] SDK initialized successfully');
    } catch (error: any) {
      log(`[ZoomRTMS] Error initializing SDK: ${error.message}`);
      throw error;
    }
  }

  /**
   * Connect to a Zoom meeting
   * Note: Requires rtms_stream_id and server_urls which should be obtained from Zoom API or webhook
   */
  async connect(meetingUuid: string, rtmsStreamId: string, serverUrls: string, accessToken?: string): Promise<void> {
    if (!this.client) {
      await this.initialize();
    }

    if (!this.client) {
      throw new Error('Failed to initialize RTMS client');
    }

    try {
      log(`[ZoomRTMS] Connecting to meeting: ${meetingUuid}`);

      // Generate signature if client/secret provided, otherwise use accessToken
      let signature: string | undefined;
      if (this.config.clientId && this.config.clientSecret) {
        // @ts-ignore - RTMS SDK API
        signature = rtms.generateSignature?.({
          client: this.config.clientId,
          secret: this.config.clientSecret,
          uuid: meetingUuid,
          streamId: rtmsStreamId,
        });
      }

      // Join parameters
      const joinParams: JoinParams = {
        meeting_uuid: meetingUuid,
        rtms_stream_id: rtmsStreamId,
        server_urls: serverUrls,
        client: this.config.clientId,
        secret: this.config.clientSecret,
        signature: signature,
        pollInterval: 10, // milliseconds
      };

      const success = this.client.join(joinParams);
      if (!success) {
        throw new Error('Failed to join RTMS session');
      }

      this.isConnected = true;
      log('[ZoomRTMS] Successfully initiated join to meeting');
    } catch (error: any) {
      log(`[ZoomRTMS] Error connecting to meeting: ${error.message}`);
      this.isConnected = false;
      throw error;
    }
  }

  /**
   * Disconnect from the meeting
   */
  async disconnect(): Promise<void> {
    if (!this.client || !this.isConnected) {
      return;
    }

    try {
      log('[ZoomRTMS] Disconnecting from meeting');
      const success = this.client.leave();
      if (!success) {
        log('[ZoomRTMS] Warning: leave() returned false');
      }
      this.isConnected = false;
      log('[ZoomRTMS] Disconnected successfully');
    } catch (error: any) {
      log(`[ZoomRTMS] Error disconnecting: ${error.message}`);
      throw error;
    }
  }

  /**
   * Register callback for audio data
   */
  onAudio(callback: (audioData: Buffer) => void): void {
    this.audioCallbacks.push(callback);
  }

  /**
   * Register callback for session events
   */
  onSessionEvent(callback: (event: SessionEvent) => void): void {
    this.sessionEventCallbacks.push(callback);
  }

  /**
   * Register callback for participant events
   */
  onParticipantEvent(callback: (event: ParticipantEvent) => void): void {
    this.participantEventCallbacks.push(callback);
  }

  /**
   * Remove audio callback
   */
  offAudio(callback: (audioData: Buffer) => void): void {
    this.audioCallbacks = this.audioCallbacks.filter(cb => cb !== callback);
  }

  /**
   * Remove session event callback
   */
  offSessionEvent(callback: (event: SessionEvent) => void): void {
    this.sessionEventCallbacks = this.sessionEventCallbacks.filter(cb => cb !== callback);
  }

  /**
   * Remove participant event callback
   */
  offParticipantEvent(callback: (event: ParticipantEvent) => void): void {
    this.participantEventCallbacks = this.participantEventCallbacks.filter(cb => cb !== callback);
  }

  /**
   * Check if connected
   */
  getConnected(): boolean {
    return this.isConnected;
  }

  /**
   * Set up event handlers for RTMS SDK
   */
  private setupEventHandlers(): void {
    if (!this.client) return;

    // Set up join confirmation handler
    // @ts-ignore - RTMS SDK types
    const joinConfirmHandler: any = (reason: number) => {
      // @ts-ignore - RTMS SDK constants
      if (reason === rtms.RTMS_SDK_OK || reason === 0) {
        log('[ZoomRTMS] Join confirmed successfully');
        this.isConnected = true;
        this.sessionEventCallbacks.forEach(callback => {
          try {
            callback({
              type: 'connection_established',
            });
          } catch (error: any) {
            log(`[ZoomRTMS] Error in join confirm callback: ${error.message}`);
          }
        });
      } else {
        log(`[ZoomRTMS] Join failed with reason: ${reason}`);
        this.isConnected = false;
        this.sessionEventCallbacks.forEach(callback => {
          try {
            callback({
              type: 'session_error',
              data: { reason },
            });
          } catch (error: any) {
            log(`[ZoomRTMS] Error in join confirm callback: ${error.message}`);
          }
        });
      }
    };
    // @ts-ignore - RTMS SDK API
    this.client.onJoinConfirm?.(joinConfirmHandler);

    // Set up audio data handler
    // @ts-ignore - RTMS SDK types
    const audioHandler: any = (buffer: Buffer, size: number, timestamp: number, metadata: any) => {
      this.audioCallbacks.forEach(callback => {
        try {
          callback(buffer);
        } catch (error: any) {
          log(`[ZoomRTMS] Error in audio callback: ${error.message}`);
        }
      });
    };
    // @ts-ignore - RTMS SDK API
    this.client.onAudioData?.(audioHandler);

    // Set up session update handler
    // @ts-ignore - RTMS SDK types
    const sessionHandler: any = (op: number, sessionInfo: any) => {
      let eventType: SessionEvent['type'] = 'session_error';
      // @ts-ignore - RTMS SDK constants
      if (op === rtms.SESSION_EVENT_ADD || op === 1) {
        eventType = 'session_started';
      // @ts-ignore - RTMS SDK constants
      } else if (op === rtms.SESSION_EVENT_STOP || op === 2) {
        eventType = 'session_ended';
      }

      const sessionEvent: SessionEvent = {
        type: eventType,
        data: sessionInfo,
      };
      this.sessionEventCallbacks.forEach(callback => {
        try {
          callback(sessionEvent);
        } catch (error: any) {
          log(`[ZoomRTMS] Error in session event callback: ${error.message}`);
        }
      });
    };
    // @ts-ignore - RTMS SDK API
    this.client.onSessionUpdate?.(sessionHandler);

    // Set up user update handler (participant events)
    // @ts-ignore - RTMS SDK types
    const userHandler: any = (op: number, participantInfo: any) => {
      let eventType: ParticipantEvent['type'] = 'audio_source_changed';
      // @ts-ignore - RTMS SDK constants
      if (op === rtms.USER_EVENT_JOIN || op === 1) {
        eventType = 'participant_joined';
      // @ts-ignore - RTMS SDK constants
      } else if (op === rtms.USER_EVENT_LEAVE || op === 2) {
        eventType = 'participant_left';
      }

      const participantEvent: ParticipantEvent = {
        type: eventType,
        participantId: participantInfo.id || participantInfo.userId || '',
        participantName: participantInfo.name || participantInfo.userName,
        timestamp: Date.now(),
      };
      this.participantEventCallbacks.forEach(callback => {
        try {
          callback(participantEvent);
        } catch (error: any) {
          log(`[ZoomRTMS] Error in participant event callback: ${error.message}`);
        }
      });
    };
    // @ts-ignore - RTMS SDK API
    this.client.onUserUpdate?.(userHandler);

    // Set up leave handler
    // @ts-ignore - RTMS SDK types
    const leaveHandler: any = (reason: number) => {
      log(`[ZoomRTMS] Left meeting with reason: ${reason}`);
      this.isConnected = false;
      this.sessionEventCallbacks.forEach(callback => {
        try {
          callback({
            type: 'session_ended',
            data: { reason },
          });
        } catch (error: any) {
          log(`[ZoomRTMS] Error in leave callback: ${error.message}`);
        }
      });
    };
    // @ts-ignore - RTMS SDK API
    this.client.onLeave?.(leaveHandler);
  }

  /**
   * Cleanup resources
   */
  async cleanup(): Promise<void> {
    this.audioCallbacks = [];
    this.sessionEventCallbacks = [];
    this.participantEventCallbacks = [];
    
    if (this.isConnected) {
      await this.disconnect();
    }
    
    if (this.client) {
      this.client.release();
      this.client = null;
    }
  }
}

