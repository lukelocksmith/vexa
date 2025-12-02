# Model Footprint Summary - Large v3 Turbo

## Current Configuration

- **Model**: `large-v3-turbo`
- **Device**: `cuda` (GPU)
- **Compute Type**: `float16` (auto-selected for modern GPUs)
- **Parameters**: ~809 million

## Expected Model Footprint

### 1. Disk Storage Size (Model Files)

**Location**: `./hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/`

| Format | Disk Size | Notes |
|--------|-----------|-------|
| **Float16** (GPU default) | **~1.6-2 GB** | Pre-converted CTranslate2 format |
| Float32 | ~3-4 GB | Full precision (rarely used on GPU) |
| INT8 | ~0.8-1 GB | CPU-optimized version |

**For your GPU setup**: Expect **~1.6-2 GB** on disk

### 2. GPU VRAM Usage (When Loaded)

| Compute Type | VRAM Usage | Notes |
|--------------|------------|-------|
| **Float16** (your config) | **~6-8 GB** | Optimal for modern GPUs (Compute Capability >= 7) |
| Float32 | ~12 GB | Full precision, only for older GPUs |
| INT8 | N/A | CPU-only format |

**For your GPU setup**: Expect **~6-8 GB GPU VRAM** when model is loaded

### 3. System RAM Usage

| Component | RAM Usage | Notes |
|-----------|-----------|-------|
| Model overhead | ~1-2 GB | Python/runtime overhead |
| Audio buffers | Variable | Depends on concurrent clients |
| Total (idle) | **~1-2 GB** | Minimal system RAM needed |
| Total (active) | **~2-4 GB** | With active transcription sessions |

**Note**: GPU models use system RAM only for runtime overhead, not for model storage.

## Full Resource Requirements

### Minimum Recommended GPU:
- **VRAM**: 8 GB minimum (for float16)
- **VRAM**: 12 GB minimum (for float32, older GPUs)

### Disk Space:
- **Model files**: ~2 GB (initial download)
- **Cache/overhead**: +0.5-1 GB
- **Total**: ~3 GB per model

### System RAM:
- **Container base**: ~1-2 GB
- **Per client session**: +50-100 MB
- **Total**: ~2-4 GB for normal operation

## Comparison: GPU vs CPU Footprint

### GPU (Float16) - Your Current Setup:
- **Disk**: ~1.6-2 GB
- **VRAM**: ~6-8 GB
- **System RAM**: ~2-4 GB
- **Speed**: Very fast (>10x real-time)

### CPU (INT8) - Alternative:
- **Disk**: ~0.8-1 GB
- **VRAM**: N/A
- **System RAM**: ~6-8 GB
- **Speed**: ~2-5x real-time

## Download Size

When running `make download-model`:
- **Initial download**: ~1.6-2 GB (CTranslate2 format, float16)
- **Processing time**: Minimal (already converted format)
- **Total download time**: Depends on connection speed
  - Fast connection (100 Mbps): ~2-3 minutes
  - Slower connection (10 Mbps): ~20-30 minutes

## Storage Location

Models are stored in:
```
./hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/
```

This directory is mounted as a volume in Docker, so:
- Models persist between container restarts
- Shared across CPU and GPU containers
- Can be manually backed up/restored

## Memory Management Notes

1. **Single Model Mode**: If `single_model=True` (default), one model instance is shared across all clients - **most memory efficient**
2. **Per-Client Models**: If disabled, each client gets its own model instance - uses ~6-8 GB VRAM per client (not recommended)
3. **Model Caching**: Models are kept in GPU memory once loaded for fast subsequent requests

## Recommendations

### For Production GPU Deployment:
- ✅ **GPU with 8+ GB VRAM** (for float16)
- ✅ **Single model mode** (share model across clients)
- ✅ **Monitor GPU memory** with `nvidia-smi`
- ✅ **Plan for ~2 GB disk space** per model version

### If VRAM is Limited (< 8 GB):
- Consider using `large-v3` instead (slightly smaller)
- Or use CPU with INT8 quantization (trades speed for memory)

## Quick Check Commands

**Check disk usage:**
```bash
du -sh ./hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/
```

**Check GPU memory usage:**
```bash
nvidia-smi
```

**Monitor in real-time:**
```bash
watch -n 1 nvidia-smi
```

