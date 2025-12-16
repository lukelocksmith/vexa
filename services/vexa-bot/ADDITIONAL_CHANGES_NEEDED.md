# Additional Changes Needed for Meeting SDK Integration

## Critical Changes

### 1. ✅ GLIBC Version Mismatch - REBUILD BINARY
**Status**: Script created (`rebuild-for-jammy.sh`)
**Action**: Rebuild Meeting SDK binary on Ubuntu 22.04 to match Playwright image

### 2. ⚠️ PulseAudio and DBus Setup
**Status**: NOT IMPLEMENTED
**Issue**: Meeting SDK requires PulseAudio and DBus to be running
**Location**: `core/entrypoint.sh`
**Required**: 
- Start DBus daemon
- Set up PulseAudio with null sink
- Create zoomus.conf config file
- Add user to pulse-access and audio groups

### 3. ⚠️ Environment Variables for Meeting SDK Process
**Status**: PARTIALLY IMPLEMENTED
**Issue**: Meeting SDK may need additional environment variables
**Location**: `core/src/services/zoom-meeting-sdk.ts` (spawn env)
**Required**:
- `QT_LOGGING_RULES` (already in entry.sh, but not passed to process)
- `DISPLAY` (for X11, though headless)
- Audio-related env vars

### 4. ⚠️ Socket Permissions
**Status**: NEEDS VERIFICATION
**Issue**: Unix socket `/tmp/meeting.sock` needs proper permissions
**Location**: Socket is created by Meeting SDK, but we should ensure /tmp is writable

### 5. ⚠️ Audio Group Permissions
**Status**: NOT IMPLEMENTED
**Issue**: Process needs to be in pulse-access and audio groups
**Location**: Dockerfile or entrypoint.sh

## Nice-to-Have Improvements

### 6. Better Error Handling
- Check if binary exists before spawning
- Better error messages for missing dependencies
- Validate meeting URL format before joining

### 7. Process Health Monitoring
- Monitor Meeting SDK process health
- Auto-restart on crashes (if needed)
- Better logging of process output

### 8. Configuration
- Make Meeting SDK path configurable
- Support for different audio output formats
- Configurable socket path

### 9. Cleanup
- Remove old RTMS code references (optional, for backward compat)
- Update documentation
- Remove unused imports

## Implementation Priority

1. **HIGH**: Rebuild binary for Ubuntu 22.04
2. **HIGH**: Add PulseAudio/DBus setup to entrypoint.sh
3. **MEDIUM**: Add environment variables to spawn process
4. **MEDIUM**: Verify socket permissions
5. **LOW**: Error handling improvements
6. **LOW**: Process monitoring





