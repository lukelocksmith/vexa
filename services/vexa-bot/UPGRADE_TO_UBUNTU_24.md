# Upgrade to Ubuntu 24.04 (Noble)

## Why This Change?

Instead of rebuilding the Meeting SDK binary for Ubuntu 22.04 (which takes 30+ minutes), we upgraded the Docker container to Ubuntu 24.04 to match the existing binary.

**Benefits:**
- ✅ **Much faster** - No binary rebuild needed (~10 min Docker build vs 30+ min binary rebuild)
- ✅ **Uses existing binary** - The Meeting SDK binary was already built on Ubuntu 24.04
- ✅ **Simpler** - No need for OpenCV symlink workarounds
- ✅ **Better compatibility** - Container matches binary's build environment

## Changes Made

1. **Updated Dockerfile base images:**
   - Changed from `mcr.microsoft.com/playwright:v1.56.0-jammy` (Ubuntu 22.04)
   - To `mcr.microsoft.com/playwright:v1.56.0-noble` (Ubuntu 24.04)

2. **Removed OpenCV symlink workaround:**
   - Ubuntu 24.04 has the correct OpenCV version, so symlinks are no longer needed

3. **Cancelled binary rebuild:**
   - The existing binary built on Ubuntu 24.04 will work with the new container

## Next Steps

1. **Rebuild Docker image:**
   ```bash
   cd /Users/dmitriygrankin/dev/vexa/services/vexa-bot
   make build
   ```

2. **Test:**
   ```bash
   make test-zoom MEETING_URL="https://us05web.zoom.us/j/82491759979?pwd=..."
   ```

## Verification

The existing Meeting SDK binary at:
```
/Users/dmitriygrankin/dev/meetingsdk-headless-linux-sample/build/zoomsdk
```

Should now work without GLIBC errors since the container matches its build environment (Ubuntu 24.04).





