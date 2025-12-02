# GPU VRAM Optimization - Drastic Footprint Reduction

## Current vs Optimized Configuration

### Current Setup:
- **Model**: `large-v3-turbo`
- **Compute Type**: `float16` (auto-selected)
- **GPU VRAM**: ~6-8 GB

### Optimized Setup Options:

## Strategy 1: INT8 Quantization on GPU (RECOMMENDED - Best Balance)

**VRAM Reduction: ~50-60%** (from 6-8GB to **~3-4GB**)

### Configuration:
```env
WHISPER_MODEL_SIZE=large-v3-turbo
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8  # Force INT8 on GPU for VRAM optimization
```

### Expected Results:
| Metric | Float16 (Current) | INT8 (Optimized) | Reduction |
|--------|------------------|------------------|-----------|
| **GPU VRAM** | ~6-8 GB | **~3-4 GB** | **50-60%** ↓ |
| **Disk Size** | ~1.6-2 GB | ~0.8-1 GB | ~50% ↓ |
| **Speed** | Very Fast | Fast (still GPU accelerated) | Slight decrease |
| **Accuracy** | 100% | ~95-98% | Minimal loss |

### Benefits:
✅ **Drastically reduced VRAM** (~50-60% reduction)  
✅ **Still uses GPU** (faster than CPU)  
✅ **Maintains high accuracy** (~95-98%)  
✅ **Can fit on 4GB GPUs**  
✅ **Same model quality** (multilingual, real-time ready)

## Strategy 2: Use Smaller Model + Float16

**VRAM Reduction: ~60-70%** (to **~2-3GB**)

### Option A: Medium Model
```env
WHISPER_MODEL_SIZE=medium
DEVICE_TYPE=cuda
# Uses float16 automatically
```

**VRAM**: ~2-3 GB  
**Trade-off**: Lower accuracy, still multilingual

### Option B: Small Model
```env
WHISPER_MODEL_SIZE=small
DEVICE_TYPE=cuda
```

**VRAM**: ~1-2 GB  
**Trade-off**: Lower accuracy, still multilingual

## Strategy 3: Medium Model + INT8 (Ultra Low VRAM)

**VRAM Reduction: ~75-80%** (to **~1-1.5GB**)

```env
WHISPER_MODEL_SIZE=medium
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
```

**VRAM**: ~1-1.5 GB  
**Best for**: GPUs with limited VRAM (4GB or less)

## VRAM Comparison Table

| Model | Float16 VRAM | INT8 VRAM | Disk Size |
|-------|-------------|-----------|-----------|
| **large-v3-turbo** | ~6-8 GB | **~3-4 GB** | ~0.8-1 GB |
| **medium** | ~2-3 GB | **~1-1.5 GB** | ~0.4-0.5 GB |
| **small** | ~1-2 GB | **~0.5-1 GB** | ~0.2-0.3 GB |

## Recommended Approach

### For Maximum VRAM Reduction While Keeping Quality:

**Use `large-v3-turbo` + INT8 on GPU**

This gives you:
- ✅ **~3-4 GB VRAM** (50-60% reduction)
- ✅ **High quality** (95-98% accuracy)
- ✅ **Multilingual** (99+ languages)
- ✅ **GPU acceleration** (faster than CPU)

## Implementation

### Step 1: Enable INT8 on GPU
Update `.env`:
```env
WHISPER_MODEL_SIZE=large-v3-turbo
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8  # Force INT8 quantization on GPU
```

### Step 2: Code Already Supports This!
The code in `server.py` already reads `WL_COMPUTE_TYPE` from environment, so setting it to `int8` will work on GPU.

### Step 3: Rebuild and Test
```bash
docker compose --profile gpu build whisperlive
docker compose --profile gpu up -d whisperlive
```

## Verification

After starting, check logs for:
```
INFO:root:Using Device=cuda with precision int8
```

Check GPU memory:
```bash
nvidia-smi
```

Should show **~3-4 GB** VRAM usage instead of 6-8 GB!

## Alternative: Ultra-Low VRAM Setup

If you need even less VRAM:

```env
WHISPER_MODEL_SIZE=medium
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
```

This will use **~1-1.5 GB VRAM** but with lower accuracy.

## Performance Impact

### Large v3 Turbo + INT8 on GPU:
- **VRAM**: ~3-4 GB (vs 6-8 GB)
- **Speed**: Still fast (GPU accelerated)
- **Accuracy**: ~95-98% (vs 100%)
- **Best for**: GPUs with 4-6 GB VRAM

### Trade-offs Summary:
- ✅ **VRAM**: Drastically reduced
- ✅ **Speed**: Still much faster than CPU
- ⚠️ **Accuracy**: Slight reduction (usually acceptable)
- ✅ **Cost**: Can use smaller/cheaper GPUs

