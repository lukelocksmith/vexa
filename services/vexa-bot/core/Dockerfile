# --- Meeting SDK Build Stage ---
FROM mcr.microsoft.com/playwright:v1.56.0-noble AS meetingsdk-builder

ARG DEBIAN_FRONTEND=noninteractive
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install build dependencies for Meeting SDK
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    gfortran \
    libopencv-dev \
    libglib2.0-dev \
    libssl-dev \
    libx11-dev \
    pkgconf \
    && rm -rf /var/lib/apt/lists/*

# Install vcpkg for dependencies
WORKDIR /opt
RUN git clone --depth 1 https://github.com/Microsoft/vcpkg.git \
    && ./vcpkg/bootstrap-vcpkg.sh -disableMetrics \
    && ln -s /opt/vcpkg/vcpkg /usr/local/bin/vcpkg \
    && vcpkg install vcpkg-cmake

# Build Meeting SDK
# Note: This assumes the Meeting SDK source is available at build time
# For now, we'll copy from the mounted volume approach, but this stage
# can be used if we want to build from source in the image
WORKDIR /tmp/meetingsdk

# --- Build Stage ---
FROM mcr.microsoft.com/playwright:v1.56.0-noble AS base

# Install required OS dependencies (e.g., for Xvfb and other utilities)
RUN apt-get update && apt-get install -y \
    xvfb \
    ffmpeg \
    x11-utils \
    pulseaudio \
    x11-xserver-utils \
    fluxbox \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install TypeScript globally first (changes rarely)
RUN npm install -g typescript

# Copy package files and install dependencies with npm
# This layer will be cached if package.json doesn't change
COPY package.json package-lock.json ./
RUN npm ci --prefer-offline --no-audit

# Install Playwright browsers (cached if versions don't change)
# Do this before copying source to maximize cache hits
RUN npx playwright install-deps && npx playwright install --with-deps msedge

# Copy the rest of the application source code
# This should be last to maximize cache hits for dependencies
COPY . .

# Build the TypeScript code and browser utilities bundle
RUN npm run build

# --- Runtime Stage ---
FROM mcr.microsoft.com/playwright:v1.56.0-noble AS runtime

# Set working directory
WORKDIR /app

# Install runtime dependencies for Xvfb and others (if needed)
# Also install OpenCV for Meeting SDK binary
# Note: Ubuntu 24.04 (noble) has compatible OpenCV version, no symlinks needed
ARG DEBIAN_FRONTEND=noninteractive
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    xvfb \
    pulseaudio \
    pulseaudio-utils \
    dbus \
    dbus-x11 \
    xserver-xephyr \
    libopencv-dev \
    libxcb-xtest0 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-shape0 \
    libxcb-shm0 \
    libxcb-xfixes0 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the built application and node_modules from the base stage
# This includes Playwright browsers already installed in base stage
COPY --from=base /app /app

# Ensure the Playwright cache directory has proper permissions
# Playwright browsers are already installed in base stage, just need permissions
RUN mkdir -p /root/.cache/ms-playwright /root/ms-playwright && \
    chmod -R 777 /root/.cache/ms-playwright /root/ms-playwright 2>/dev/null || true

# Create storage directory structure for bot data (screenshots, logs, etc.)
RUN mkdir -p /app/storage/screenshots /app/storage/logs /app/storage/temp && chmod -R 777 /app/storage

# Copy an entrypoint script that will start Xvfb and run our bot
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose DISPLAY port for headful browser operations (adjust as needed)
ENV DISPLAY=:99

# Set the command to run our entrypoint script
CMD ["/app/entrypoint.sh"]
