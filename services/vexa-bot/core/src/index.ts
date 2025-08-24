import StealthPlugin from "puppeteer-extra-plugin-stealth";
import { log } from "./utils";
import { chromium } from "playwright-extra";
import { handleGoogleMeet, leaveGoogleMeet } from "./platforms/google";
import { browserArgs, userAgent } from "./constans";
import { BotConfig } from "./types";
import { createClient, RedisClientType } from 'redis';
import { Page, Browser } from 'playwright-core';
import * as http from 'http';
import * as https from 'https';

// Module-level variables to store current configuration
let currentLanguage: string | null | undefined = null;
let currentTask: string | null | undefined = 'transcribe';
let currentRedisUrl: string | null = null;
let currentConnectionId: string | null = null;
let currentMeetingId: number | null = null;
let botManagerCallbackUrl: string | null = null;
let botManagerStartedCallbackUrl: string | null = null;
let currentPlatform: "google_meet" | "zoom" | "teams" | undefined;
let page: Page | null = null;

// Flag to prevent multiple shutdowns
let isShuttingDown = false;

// Redis subscriber client
let redisSubscriber: RedisClientType | null = null;

// Browser instance
let browserInstance: Browser | null = null;

// Heartbeat interval
let heartbeatInterval: NodeJS.Timeout | null = null;

// Message Handler
const handleRedisMessage = async (message: string, channel: string, page: Page | null) => {
  log(`[DEBUG] handleRedisMessage entered for channel ${channel}. Message: ${message.substring(0, 100)}...`);
  log(`Received command on ${channel}: ${message}`);
  
  try {
      const command = JSON.parse(message);
      if (command.action === 'reconfigure') {
          log(`Processing reconfigure command: Lang=${command.language}, Task=${command.task}`);

          // Update Node.js state
          currentLanguage = command.language;
          currentTask = command.task;

          // Trigger browser-side reconfiguration via the exposed function
          if (page && !page.isClosed()) {
              try {
                  await page.evaluate(
                      ([lang, task]) => {
                          if (typeof (window as any).triggerWebSocketReconfigure === 'function') {
                              (window as any).triggerWebSocketReconfigure(lang, task);
                          } else {
                              console.error('[Node Eval Error] triggerWebSocketReconfigure not found on window.');
                              (window as any).logBot?.('[Node Eval Error] triggerWebSocketReconfigure not found on window.');
                          }
                      },
                      [currentLanguage, currentTask]
                  );
                  log("Sent reconfigure command to browser context via page.evaluate.");
              } catch (evalError: any) {
                  log(`Error evaluating reconfiguration script in browser: ${evalError.message}`);
              }
          } else {
               log("Page not available or closed, cannot send reconfigure command to browser.");
          }
      } else if (command.action === 'leave') {
        log("Received leave command");
        if (!isShuttingDown && page && !page.isClosed()) {
          // Set status to stopping before leaving
          await sendBotStatusUpdate('stopping');
          // A command-initiated leave is a successful completion, not an error.
          await performGracefulLeave(page, 0, "self_initiated_leave");
        } else {
           log("Ignoring leave command: Already shutting down or page unavailable.")
        }
      }
  } catch (e: any) {
      log(`Error processing Redis message: ${e.message}`);
  }
};

// Graceful Leave Function
async function performGracefulLeave(
  page: Page | null,
  exitCode: number = 1,
  reason: string = "self_initiated_leave"
): Promise<void> {
  if (isShuttingDown) {
    log("[Graceful Leave] Already in progress, ignoring duplicate call.");
    return;
  }
  isShuttingDown = true;
  log(`[Graceful Leave] Initiating graceful shutdown sequence... Reason: ${reason}, Exit Code: ${exitCode}`);

  let platformLeaveSuccess = false;
  if (page && !page.isClosed()) {
    try {
      log("[Graceful Leave] Attempting platform-specific leave...");
      if (currentPlatform === "google_meet") {
         platformLeaveSuccess = await leaveGoogleMeet(page);
      } else {
         log(`[Graceful Leave] No platform-specific leave defined for ${currentPlatform}. Page will be closed.`);
         platformLeaveSuccess = true;
      }
      log(`[Graceful Leave] Platform leave/close attempt result: ${platformLeaveSuccess}`);
    } catch (leaveError: any) {
      log(`[Graceful Leave] Error during platform leave/close attempt: ${leaveError.message}`);
      platformLeaveSuccess = false;
    }
  } else {
    log("[Graceful Leave] Page not available or already closed. Skipping platform-specific leave attempt.");
  }

  // Determine final exit code
  const finalCallbackExitCode = (exitCode === 0) ? 0 : exitCode;
  const finalCallbackReason = reason;

  // Send exit callback to bot-manager
  if (botManagerCallbackUrl && currentConnectionId) {
    const payload = JSON.stringify({
      connection_id: currentConnectionId,
      exit_code: finalCallbackExitCode,
      reason: finalCallbackReason
    });

    try {
      log(`[Graceful Leave] Sending exit callback to ${botManagerCallbackUrl} with payload: ${payload}`);
      const url = new URL(botManagerCallbackUrl);
      const options: https.RequestOptions = {
        method: 'POST',
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? '443' : '80'),
        path: url.pathname,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload)
        }
      };

      const req = (url.protocol === 'https:' ? https : http).request(options, (res: http.IncomingMessage) => {
        log(`[Graceful Leave] Bot-manager callback response status: ${res.statusCode}`);
        res.on('data', () => { /* consume data */ });
      });

      req.on('error', (err: Error) => {
        log(`[Graceful Leave] Error sending bot-manager callback: ${err.message}`);
      });

      req.write(payload);
      req.end();
      await new Promise(resolve => setTimeout(resolve, 500));
    } catch (callbackError: any) {
      log(`[Graceful Leave] Exception during bot-manager callback preparation: ${callbackError.message}`);
    }
  } else {
    log("[Graceful Leave] Bot manager callback URL or Connection ID not configured. Cannot send exit status.");
  }

  // Clean up Redis connection
  if (redisSubscriber && redisSubscriber.isOpen) {
    log("[Graceful Leave] Disconnecting Redis subscriber...");
    try {
        await redisSubscriber.unsubscribe();
        await redisSubscriber.quit();
        log("[Graceful Leave] Redis subscriber disconnected.");
    } catch (err) {
        log(`[Graceful Leave] Error closing Redis connection: ${err}`);
    }
  }

  // Stop heartbeat
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }

  // Close the browser page if it's still open
  if (page && !page.isClosed()) {
    log("[Graceful Leave] Ensuring page is closed.");
    try {
      await page.close();
      log("[Graceful Leave] Page closed.");
    } catch (pageCloseError: any) {
      log(`[Graceful Leave] Error closing page: ${pageCloseError.message}`);
    }
  }

  // Close the browser instance
  log("[Graceful Leave] Closing browser instance...");
  try {
    if (browserInstance && browserInstance.isConnected()) {
       await browserInstance.close();
       log("[Graceful Leave] Browser instance closed.");
    } else {
       log("[Graceful Leave] Browser instance already closed or not available.");
    }
  } catch (browserCloseError: any) {
    log(`[Graceful Leave] Error closing browser: ${browserCloseError.message}`);
  }

  // Exit the process
  log(`[Graceful Leave] Exiting process with code ${finalCallbackExitCode} (Reason: ${finalCallbackReason}).`);
  process.exit(finalCallbackExitCode);
}

// Bot Started Callback Function
async function sendBotStartedCallback(
  status: string,
  details?: string
): Promise<void> {
  if (botManagerStartedCallbackUrl && currentConnectionId) {
    const payload = JSON.stringify({
      connection_id: currentConnectionId,
      status: status,
      details: details
    });

    try {
      log(`[Bot Started] Sending started callback to ${botManagerStartedCallbackUrl} with payload: ${payload}`);
      
      const url = new URL(botManagerStartedCallbackUrl);
      const options: https.RequestOptions = {
        method: 'POST',
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? '443' : '80'),
        path: url.pathname,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload)
        }
      };

      const req = (url.protocol === 'https:' ? https : http).request(options, (res: http.IncomingMessage) => {
        log(`[Bot Started] Bot-manager started callback response status: ${res.statusCode}`);
        if (res.statusCode === 200) {
          log(`[Bot Started] Successfully sent '${status}' callback to bot-manager`);
        } else {
          log(`[Bot Started] Warning: Bot-manager returned status ${res.statusCode} for '${status}' callback`);
        }
        res.on('data', () => { /* consume data */ });
      });

      req.on('error', (err: Error) => {
        log(`[Bot Started] Error sending bot-manager started callback: ${err.message}`);
      });

      req.write(payload);
      req.end();
      await new Promise(resolve => setTimeout(resolve, 500));
    } catch (callbackError: any) {
      log(`[Bot Started] Exception during bot-manager started callback preparation: ${callbackError.message}`);
    }
  } else {
    log(`[Bot Started] Cannot send callback: URL=${botManagerStartedCallbackUrl}, ConnectionID=${currentConnectionId}`);
  }
}

// Bot Joined Callback Function
async function sendBotJoinedCallback(): Promise<void> {
  if (botManagerCallbackUrl && currentConnectionId) {
    const payload = JSON.stringify({
      connection_id: currentConnectionId
    });

    try {
      const url = new URL(botManagerCallbackUrl.replace('/exited', '/joined'));
      const options: https.RequestOptions = {
        method: 'POST',
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? '443' : '80'),
        path: url.pathname,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload)
        }
      };

      const req = (url.protocol === 'https:' ? https : http).request(options, (res: http.IncomingMessage) => {
        log(`[Bot Joined] Bot-manager joined callback response status: ${res.statusCode}`);
        if (res.statusCode === 200) {
          log(`[Bot Joined] Successfully sent joined callback to bot-manager`);
        }
        res.on('data', () => { /* consume data */ });
      });

      req.on('error', (err: Error) => {
        log(`[Bot Joined] Error sending bot-manager joined callback: ${err.message}`);
      });

      req.write(payload);
      req.end();
      await new Promise(resolve => setTimeout(resolve, 500));
    } catch (callbackError: any) {
      log(`[Bot Joined] Exception during bot-manager joined callback preparation: ${callbackError.message}`);
    }
  } else {
    log(`[Bot Joined] Cannot send callback: URL=${botManagerCallbackUrl}, ConnectionID=${currentConnectionId}`);
  }
}

// Bot Heartbeat Function
async function sendBotHeartbeat(): Promise<void> {
  if (botManagerCallbackUrl && currentConnectionId) {
    const payload = JSON.stringify({
      connection_id: currentConnectionId
    });

    try {
      const url = new URL(botManagerCallbackUrl.replace('/exited', '/heartbeat'));
      const options: https.RequestOptions = {
        method: 'POST',
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? '443' : '80'),
        path: url.pathname,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload)
        }
      };

      const req = (url.protocol === 'https:' ? https : http).request(options, (res: http.IncomingMessage) => {
        if (res.statusCode === 200) {
          log(`[Bot Heartbeat] Successfully sent heartbeat to bot-manager`);
        }
        res.on('data', () => { /* consume data */ });
      });

      req.on('error', (err: Error) => {
        log(`[Bot Heartbeat] Error sending heartbeat: ${err.message}`);
      });

      req.write(payload);
      req.end();
    } catch (callbackError: any) {
      log(`[Bot Heartbeat] Exception during heartbeat preparation: ${callbackError.message}`);
    }
  }
}

// Bot Status Update Function
async function sendBotStatusUpdate(newStatus: string): Promise<void> {
  if (botManagerCallbackUrl && currentConnectionId) {
    const payload = JSON.stringify({
      connection_id: currentConnectionId,
      status: newStatus
    });

    try {
      const url = new URL(botManagerCallbackUrl.replace('/exited', '/status'));
      const options: https.RequestOptions = {
        method: 'PATCH',
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? '443' : '80'),
        path: url.pathname,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload)
        }
      };

      const req = (url.protocol === 'https:' ? https : http).request(options, (res: http.IncomingMessage) => {
        log(`[Bot Status Update] Bot-manager status update response: ${res.statusCode}`);
        res.on('data', () => { /* consume data */ });
      });

      req.on('error', (err: Error) => {
        log(`[Bot Status Update] Error sending status update: ${err.message}`);
      });

      req.write(payload);
      req.end();
      await new Promise(resolve => setTimeout(resolve, 500));
    } catch (callbackError: any) {
      log(`[Bot Status Update] Exception during status update preparation: ${callbackError.message}`);
    }
  }
}

// Start heartbeat interval
function startHeartbeat(): void {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
  }
  
  heartbeatInterval = setInterval(async () => {
    await sendBotHeartbeat();
  }, 30000); // Every 30 seconds
  
  log("[Bot Heartbeat] Started heartbeat interval (30 seconds)");
}

export async function runBot(botConfig: BotConfig): Promise<void> {
  // Parse and store config values
  currentLanguage = botConfig.language;
  currentTask = botConfig.task || 'transcribe';
  currentRedisUrl = botConfig.redisUrl;
  currentConnectionId = botConfig.connectionId;
  currentMeetingId = botConfig.meeting_id || null;
  botManagerCallbackUrl = botConfig.botManagerCallbackUrl || null;
  botManagerStartedCallbackUrl = botConfig.botManagerStartedCallbackUrl || null;
  currentPlatform = botConfig.platform;

  const { meetingUrl, platform, botName } = botConfig;

  log(`Starting bot for ${platform} with URL: ${meetingUrl}, name: ${botName}, language: ${currentLanguage}, task: ${currentTask}, connectionId: ${currentConnectionId}`);

  // Redis Client Setup and Subscription
  if (currentRedisUrl && currentConnectionId) {
    log("Setting up Redis subscriber...");
    try {
      redisSubscriber = createClient({ url: currentRedisUrl });

      redisSubscriber.on('error', (err) => log(`Redis Client Error: ${err}`));
      redisSubscriber.on('connect', () => log('[DEBUG] Redis client connecting...'));
      redisSubscriber.on('ready', () => log('[DEBUG] Redis client ready.'));
      redisSubscriber.on('reconnecting', () => log('[DEBUG] Redis client reconnecting...'));
      redisSubscriber.on('end', () => log('[DEBUG] Redis client connection ended.'));

      await redisSubscriber.connect();
      log(`Connected to Redis at ${currentRedisUrl}`);

      const commandChannel = `bot_commands:${currentConnectionId}`;
      await redisSubscriber.subscribe(commandChannel, (message, channel) => {
          log(`[DEBUG] Redis subscribe callback fired for channel ${channel}.`);
          handleRedisMessage(message, channel, page)
      });
      log(`Subscribed to Redis channel: ${commandChannel}`);

    } catch (err) {
      log(`*** Failed to connect or subscribe to Redis: ${err} ***`);
      redisSubscriber = null;
    }
  } else {
    log("Redis URL or Connection ID missing, skipping Redis setup.");
  }

  // Use Stealth Plugin to avoid detection
  const stealthPlugin = StealthPlugin();
  stealthPlugin.enabledEvasions.delete("iframe.contentWindow");
  stealthPlugin.enabledEvasions.delete("media.codecs");
  chromium.use(stealthPlugin);

  // Launch browser with stealth configuration
  browserInstance = await chromium.launch({
    headless: false,
    args: browserArgs,
  });

  // Create a new page with permissions and viewport
  const context = await browserInstance.newContext({
    permissions: ["camera", "microphone"],
    userAgent: userAgent,
    viewport: {
      width: 1280,
      height: 720
    }
  })
  page = await context.newPage();

  // Expose function for browser to trigger Node.js graceful leave
  await page.exposeFunction("triggerNodeGracefulLeave", async () => {
    log("[Node.js] Received triggerNodeGracefulLeave from browser context.");
    if (!isShuttingDown) {
      await performGracefulLeave(page, 0, "self_initiated_leave_from_browser");
    } else {
      log("[Node.js] Ignoring triggerNodeGracefulLeave as shutdown is already in progress.");
    }
  });

  // Expose function for browser to send bot started callback
  await page.exposeFunction("sendBotStartedCallback", async (status: string, details?: string) => {
    log(`[Node.js] Received sendBotStartedCallback from browser context: status=${status}, details=${details}`);
    await sendBotStartedCallback(status, details);
  });

  // Expose function for browser to send bot joined callback
  await page.exposeFunction("sendBotJoinedCallback", async () => {
    log(`[Node.js] Received sendBotJoinedCallback from browser context`);
    await sendBotJoinedCallback();
  });

  // Setup anti-detection measures
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => undefined });
    Object.defineProperty(navigator, "plugins", {
      get: () => [{ name: "Chrome PDF Plugin" }, { name: "Chrome PDF Viewer" }],
    });
    Object.defineProperty(navigator, "languages", {
      get: () => ["en-US", "en"],
    });
  });

  try {
    // Navigate to the meeting URL
    if (!meetingUrl) {
      throw new Error("Meeting URL is required but not provided");
    }
    
    log(`Navigating to meeting URL: ${meetingUrl}`);
    await page.goto(meetingUrl, { waitUntil: 'networkidle' });

    // Send bot started callback
    log("[Bot Started] Sending started callback to bot-manager");
    await sendBotStartedCallback("bot_started", "Bot container started and navigated to meeting URL");

    // Start heartbeat
    startHeartbeat();

    // Handle the meeting based on platform
    if (platform === "google_meet") {
      log("Handling Google Meet...");
      
      // Create a BotConfig object for the handleGoogleMeet function
      const botConfigForHandler = {
        platform: platform,
        meetingUrl: meetingUrl,
        botName: botName,
        token: botConfig.token,
        connectionId: currentConnectionId || '',
        nativeMeetingId: botConfig.nativeMeetingId,
        language: currentLanguage || 'en',
        task: currentTask || 'transcribe',
        redisUrl: currentRedisUrl || '',
        automaticLeave: {
          waitingRoomTimeout: 300000, // 5 minutes
          noOneJoinedTimeout: 300000, // 5 minutes
          everyoneLeftTimeout: 300000  // 5 minutes
        },
        meeting_id: currentMeetingId || undefined,
        botManagerCallbackUrl: botManagerCallbackUrl || undefined,
        botManagerStartedCallbackUrl: botManagerStartedCallbackUrl || undefined
      };
      
      await handleGoogleMeet(botConfigForHandler, page, performGracefulLeave);
      
      // Send bot joined callback
      log("[Bot Joined] Sending joined callback to bot-manager");
      await sendBotJoinedCallback();
      
    } else {
      log(`Platform ${platform} not implemented yet. Waiting for manual intervention...`);
      // Keep the bot running for other platforms
      await new Promise(() => {}); // Never resolves
    }

  } catch (error) {
    log(`Error during bot execution: ${error}`);
    await performGracefulLeave(page, 1, "execution_error");
  }
}

// Basic Signal Handling (for future Phase 5)
// Setup signal handling to also trigger graceful leave
const gracefulShutdown = async (signal: string) => {
    log(`Received signal: ${signal}. Triggering graceful shutdown.`);
    if (!isShuttingDown) {
        // Determine the correct page instance if multiple are possible, or use a global 'currentPage'
        // For now, assuming 'page' (if defined globally/module-scoped) or null
        const pageToClose = typeof page !== 'undefined' ? page : null;
        await performGracefulLeave(pageToClose, signal === 'SIGINT' ? 130 : 143, `signal_${signal.toLowerCase()}`);
    } else {
         log("[Signal Shutdown] Shutdown already in progress.");
    }
};

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
