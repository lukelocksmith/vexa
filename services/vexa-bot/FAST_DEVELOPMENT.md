# Fast Development Workflow (No Docker Rebuilds!)

## One-Time Setup (Only When Dependencies Change)

```bash
# Build Docker image once (takes ~10-15 min first time, ~30 sec if cached)
make build
```

## Daily Development Workflow

### 1. Make Code Changes
Edit TypeScript files in `core/src/`

### 2. Fast Rebuild (30 seconds)
```bash
# Rebuilds only TypeScript → dist/ (no Docker rebuild!)
make rebuild
```

### 3. Test Immediately
```bash
# Uses bind mounts - picks up changes from dist/ instantly
make test-zoom MEETING_URL="https://us05web.zoom.us/j/..."
```

## When Do You Need to Rebuild Docker?

**Only rebuild Docker image (`make build`) when:**
- ✅ First time setup
- ✅ `package.json` changes (new npm dependencies)
- ✅ Dockerfile changes
- ✅ System dependencies change (apt packages in Dockerfile)

**You DON'T need to rebuild Docker for:**
- ❌ TypeScript code changes → use `make rebuild`
- ❌ Configuration changes → just restart container
- ❌ Meeting SDK binary updates → just remount it

## Quick Development Cycle

```bash
# Terminal 1: Watch for changes and auto-rebuild
cd core && npm run watch  # or use your IDE's watch mode

# Terminal 2: Test loop
make rebuild && make test-zoom MEETING_URL="..."
```

## Even Faster: Auto-Rebuild on Save

Add to your IDE or use a file watcher:

```bash
# Watch TypeScript files and auto-rebuild
cd core
npm run watch  # if you have a watch script, or:
npx tsc --watch
```

Then in another terminal:
```bash
# Just restart the container (dist/ is already updated)
make test-zoom MEETING_URL="..."
```

## Troubleshooting

### "dist/ not found" error
```bash
make rebuild  # Builds dist/ directory
```

### "Image not found" error
```bash
make build  # One-time Docker image build
```

### Changes not picked up?
1. Check that `make rebuild` completed successfully
2. Restart the container (it uses bind mounts, so changes should be instant)
3. Check that you're editing files in `core/src/` (not `core/dist/`)

## Performance Comparison

| Action | Time | When Needed |
|--------|------|-------------|
| `make build` | 10-15 min (first) / 30 sec (cached) | Dependencies change |
| `make rebuild` | ~30 seconds | Code changes |
| `make test-zoom` | ~5 seconds | Every test |

**Total development cycle: ~35 seconds per iteration!** 🚀





