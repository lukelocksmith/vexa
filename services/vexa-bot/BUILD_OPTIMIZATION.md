# Docker Build Optimization Guide

## Current Optimizations

### 1. Layer Caching Strategy
- **TypeScript installation** is in its own layer (changes rarely)
- **npm dependencies** (`npm ci`) are cached separately from source code
- **Playwright browsers** are installed before copying source code
- **Source code** is copied last to maximize cache hits

### 2. Build Time Improvements
- Using `npm ci` instead of `npm install` (faster, more reliable)
- Using `--prefer-offline` to use cached packages
- Using `--no-audit` to skip security audit during build
- Installing Playwright browsers in base stage only (not duplicated in runtime)

### 3. Expected Build Times
- **First build**: ~10-15 minutes (downloads everything)
- **Subsequent builds** (no changes): ~30 seconds (all cached)
- **Source code changes only**: ~2-3 minutes (rebuilds TypeScript)
- **Dependency changes**: ~5-8 minutes (reinstalls npm packages)

## Further Optimization Options

### Option 1: Use BuildKit Cache Mounts (Recommended)
Add to your build command:
```bash
DOCKER_BUILDKIT=1 docker build --build-arg BUILDKIT_INLINE_CACHE=1 -t vexa-bot:test .
```

### Option 2: Multi-stage Build with Shared Cache
The current Dockerfile already uses multi-stage builds, but you can add:
```dockerfile
# Cache npm packages
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline --no-audit
```

### Option 3: Pre-build Base Image
Create a base image with all dependencies pre-installed:
```bash
docker build -t vexa-bot-base:latest -f Dockerfile.base .
```

## Meeting SDK Binary Rebuild

The `rebuild-for-jammy.sh` script has been optimized:
- Cleans build directory to force fresh build
- Verifies GLIBC compatibility after build
- Uses parallel compilation (`-j$(nproc)`)
- Suppresses verbose output for faster execution

**To rebuild the binary:**
```bash
cd /Users/dmitriygrankin/dev/meetingsdk-headless-linux-sample
./rebuild-for-jammy.sh
```

**Expected rebuild time**: ~5-10 minutes (first time), ~3-5 minutes (subsequent)





