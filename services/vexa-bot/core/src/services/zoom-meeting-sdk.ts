import { spawn, ChildProcess } from "child_process";
import { log } from "../utils";
import * as path from "path";
import * as fs from "fs";

export interface ZoomMeetingSDKConfig {
  clientId: string;
  clientSecret: string;
  sdkPath?: string; // Optional path to SDK binary, defaults to ./zoomsdk
}

export class ZoomMeetingSDKService {
  private config: ZoomMeetingSDKConfig;
  private process: ChildProcess | null = null;
  private isInitialized: boolean = false;
  private isConnected: boolean = false;

  constructor(config: ZoomMeetingSDKConfig) {
    this.config = config;
  }

  /**
   * Validate credentials and SDK binary path
   */
  async initialize(): Promise<void> {
    if (!this.config.clientId || !this.config.clientSecret) {
      throw new Error("Zoom Client ID and Client Secret are required");
    }

    // Determine SDK binary path
    const sdkPath = this.config.sdkPath || process.env.ZOOM_MEETING_SDK_PATH || "./zoomsdk";
    
    // Check if binary exists (if relative path)
    if (!path.isAbsolute(sdkPath)) {
      const fullPath = path.resolve(process.cwd(), sdkPath);
      if (!fs.existsSync(fullPath)) {
        log(`[ZoomMeetingSDK] Warning: SDK binary not found at ${fullPath}, will try to use ${sdkPath} directly`);
      }
    }

    this.isInitialized = true;
    log(`[ZoomMeetingSDK] Initialized with client ID: ${this.config.clientId.substring(0, 10)}...`);
  }

  /**
   * Parse meeting URL to extract meeting ID and password
   */
  private parseMeetingUrl(meetingUrl: string): { meetingId: string; password: string } {
    try {
      const url = new URL(meetingUrl);
      const pathParts = url.pathname.split("/").filter(p => p);
      
      // Zoom URL format: https://zoom.us/j/{meetingId}?pwd={password}
      // or: https://us05web.zoom.us/j/{meetingId}?pwd={password}
      const meetingIdIndex = pathParts.indexOf("j");
      if (meetingIdIndex === -1 || meetingIdIndex === pathParts.length - 1) {
        throw new Error("Invalid Zoom meeting URL format: missing meeting ID");
      }

      const meetingId = pathParts[meetingIdIndex + 1];
      const password = url.searchParams.get("pwd");

      if (!meetingId) {
        throw new Error("Invalid Zoom meeting URL: meeting ID not found");
      }

      if (!password) {
        throw new Error("Invalid Zoom meeting URL: password not found");
      }

      return { meetingId, password };
    } catch (error: any) {
      throw new Error(`Failed to parse meeting URL: ${error.message}`);
    }
  }

  /**
   * Spawn Meeting SDK process with parsed URL
   */
  async join(meetingUrl: string, displayName: string = "Vexa Bot"): Promise<void> {
    if (!this.isInitialized) {
      throw new Error("Service not initialized. Call initialize() first.");
    }

    if (this.process) {
      throw new Error("Already connected to a meeting. Call leave() first.");
    }

    try {
      const { meetingId, password } = this.parseMeetingUrl(meetingUrl);
      log(`[ZoomMeetingSDK] Joining meeting: ${meetingId}`);

      // Determine SDK binary path
      const sdkPath = this.config.sdkPath || process.env.ZOOM_MEETING_SDK_PATH || "./zoomsdk";

      // Build command arguments
      // Note: --file is required for RawAudio subcommand even when using --transcribe
      const args = [
        "--client-id", this.config.clientId,
        "--client-secret", this.config.clientSecret,
        "--join-url", meetingUrl,
        "--display-name", displayName,
        "RawAudio", // Enable raw audio recording subcommand
        "--file", "meeting-audio.pcm", // Required filename (not used when --transcribe is enabled)
        "--transcribe", // Enable transcription mode (sends to socket instead of file)
      ];

      log(`[ZoomMeetingSDK] Spawning process: ${sdkPath} ${args.join(" ")}`);

      // Spawn the Meeting SDK process
      this.process = spawn(sdkPath, args, {
        stdio: ["ignore", "pipe", "pipe"], // Ignore stdin, capture stdout/stderr
        env: {
          ...process.env,
          // Ensure socket path is accessible
          TMPDIR: process.env.TMPDIR || "/tmp",
          // Meeting SDK environment variables
          DISPLAY: process.env.DISPLAY || ":99",
          QT_LOGGING_RULES: "*.debug=false;*.warning=false",
          // Audio configuration
          PULSE_RUNTIME_PATH: process.env.PULSE_RUNTIME_PATH || "/var/run/pulse",
        },
      });

      // Handle stdout
      this.process.stdout?.on("data", (data: Buffer) => {
        const output = data.toString().trim();
        if (output) {
          log(`[ZoomMeetingSDK] ${output}`);
        }
      });

      // Handle stderr
      this.process.stderr?.on("data", (data: Buffer) => {
        const output = data.toString().trim();
        if (output) {
          log(`[ZoomMeetingSDK] ${output}`);
        }
      });

      // Handle process exit
      this.process.on("exit", (code: number | null, signal: string | null) => {
        log(`[ZoomMeetingSDK] Process exited with code ${code}, signal ${signal}`);
        this.isConnected = false;
        this.process = null;
      });

      // Handle process error
      this.process.on("error", (error: Error) => {
        log(`[ZoomMeetingSDK] Process error: ${error.message}`);
        this.isConnected = false;
        this.process = null;
        throw error;
      });

      // Wait a bit for the process to start and initialize
      await new Promise(resolve => setTimeout(resolve, 2000));

      // Check if process is still running
      if (!this.process || this.process.killed) {
        throw new Error("Meeting SDK process failed to start");
      }

      this.isConnected = true;
      log(`[ZoomMeetingSDK] Successfully started Meeting SDK process`);
    } catch (error: any) {
      log(`[ZoomMeetingSDK] Error joining meeting: ${error.message}`);
      if (this.process) {
        this.process.kill();
        this.process = null;
      }
      this.isConnected = false;
      throw error;
    }
  }

  /**
   * Gracefully stop the Meeting SDK process
   */
  async leave(): Promise<void> {
    if (!this.process) {
      log("[ZoomMeetingSDK] No process to stop");
      return;
    }

    try {
      log("[ZoomMeetingSDK] Stopping Meeting SDK process...");
      
      // Send SIGTERM for graceful shutdown
      this.process.kill("SIGTERM");

      // Wait for process to exit (with timeout)
      await new Promise<void>((resolve, reject) => {
        if (!this.process) {
          resolve();
          return;
        }

        const timeout = setTimeout(() => {
          if (this.process && !this.process.killed) {
            log("[ZoomMeetingSDK] Process did not exit gracefully, forcing kill");
            this.process.kill("SIGKILL");
          }
          resolve();
        }, 5000);

        this.process.once("exit", () => {
          clearTimeout(timeout);
          resolve();
        });
      });

      this.process = null;
      this.isConnected = false;
      log("[ZoomMeetingSDK] Successfully stopped Meeting SDK process");
    } catch (error: any) {
      log(`[ZoomMeetingSDK] Error stopping process: ${error.message}`);
      if (this.process) {
        this.process.kill("SIGKILL");
        this.process = null;
      }
      this.isConnected = false;
    }
  }

  /**
   * Clean up process and resources
   */
  async cleanup(): Promise<void> {
    await this.leave();
    this.isInitialized = false;
  }

  /**
   * Check if connected to meeting
   */
  getConnected(): boolean {
    return this.isConnected && this.process !== null && !this.process.killed;
  }

  /**
   * Get the process instance (for monitoring)
   */
  getProcess(): ChildProcess | null {
    return this.process;
  }
}

