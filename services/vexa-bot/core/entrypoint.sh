#!/bin/bash
# Start a virtual framebuffer in the background
Xvfb :99 -screen 0 1920x1080x24 &

# Set up DBus for Meeting SDK (if not already running)
if [ ! -d /var/run/dbus ]; then
  mkdir -p /var/run/dbus
  dbus-uuidgen > /var/lib/dbus/machine-id 2>/dev/null || true
  dbus-daemon --config-file=/usr/share/dbus-1/system.conf --print-address > /dev/null 2>&1 &
fi

# Set up PulseAudio for Meeting SDK
# Add user to audio groups (if running as root, this is already done in Dockerfile)
usermod -G pulse-access,audio root 2>/dev/null || true

# Cleanup PulseAudio state (required for stateless containers)
rm -rf /var/run/pulse /var/lib/pulse /root/.config/pulse/ 2>/dev/null || true
mkdir -p ~/.config/pulse/ && cp -r /etc/pulse/* ~/.config/pulse/ 2>/dev/null || true

# Start PulseAudio with null sink for Meeting SDK
pulseaudio -D --exit-idle-time=-1 --system --disallow-exit 2>/dev/null || true

# Create virtual audio sink for Meeting SDK
pactl load-module module-null-sink sink_name=SpeakerOutput 2>/dev/null || true
pactl set-default-sink SpeakerOutput 2>/dev/null || true
pactl set-default-source SpeakerOutput.monitor 2>/dev/null || true

# Create Zoom config file for Meeting SDK
mkdir -p ~/.config
echo -e "[General]\nsystem.audio.type=default" > ~/.config/zoomus.conf 2>/dev/null || true

# Ensure browser utils bundle exists (defensive in case of stale layer pulls)
if [ ! -f "/app/dist/browser-utils.global.js" ]; then
  echo "[Entrypoint] browser-utils.global.js missing; regenerating..."
  node /app/build-browser-utils.js || echo "[Entrypoint] Failed to regenerate browser-utils.global.js"
fi

# Finally, run the bot using the built production wrapper
# This wrapper (e.g., docker.js generated from docker.ts) will read the BOT_CONFIG env variable.
node dist/docker.js
