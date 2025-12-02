# Quick Optimization Reference Guide

## 🎯 Quick Model Selection by VRAM

| Your GPU VRAM | Recommended Model | Config | Expected VRAM |
|---------------|-------------------|--------|---------------|
| **4 GB** (A16 1/4) | `large-v3-turbo` | INT8 | **~2.1 GB** ✅ |
| **4 GB** (More headroom) | `medium` | INT8 | ~1-1.5 GB |
| **2 GB** | `small` | INT8 | ~500 MB |
| **1 GB or less** | `base` | INT8 | ~150 MB |

## 🔧 Quick Configuration Templates

### 1. 4GB GPU - Balanced (Current Best ✅)
```env
WHISPER_MODEL_SIZE=large-v3-turbo
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
WL_MAX_CLIENTS=5-8
```
**Result:** ~2.1 GB VRAM (validated)

### 2. 4GB GPU - More Headroom
```env
WHISPER_MODEL_SIZE=medium
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
WL_MAX_CLIENTS=10+
```
**Result:** ~1-1.5 GB VRAM

### 3. 2GB GPU - Minimal
```env
WHISPER_MODEL_SIZE=small
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
WL_MAX_CLIENTS=5-8
```
**Result:** ~500 MB VRAM

### 4. CPU-Only - Balanced
```env
WHISPER_MODEL_SIZE=medium
DEVICE_TYPE=cpu
WL_COMPUTE_TYPE=int8
WL_CPU_THREADS=4
```
**Result:** ~2-4 GB RAM

### 5. CPU-Only - Minimal
```env
WHISPER_MODEL_SIZE=small
DEVICE_TYPE=cpu
WL_COMPUTE_TYPE=int8
WL_CPU_THREADS=4
```
**Result:** ~1-2 GB RAM

## 📊 All Multilingual Models Comparison

| Model | GPU VRAM (INT8) | CPU RAM (INT8) | Quality | Speed |
|-------|-----------------|----------------|---------|-------|
| **large-v3-turbo** | ~2.1 GB ✅ | ~6-8 GB | Excellent | Very Fast |
| **medium** | ~1-1.5 GB | ~2-4 GB | Excellent | Fast |
| **small** | ~500 MB | ~1-2 GB | Very Good | Very Fast |
| **base** | ~150 MB | ~300-600 MB | Good | Extremely Fast |
| **tiny** | ~75 MB | ~150-300 MB | Basic | Extremely Fast |

**All models above are multilingual (99+ languages)** ✅

## ⚡ Quick Optimization Tips

### Reduce VRAM Further:
1. ✅ Use INT8 quantization (already done)
2. ✅ Use smaller model (`medium` → `small`)
3. ✅ Reduce `WL_MAX_CLIENTS`
4. ✅ Use greedy decoding (`beam_size=1`)

### Reduce CPU RAM:
1. ✅ Use INT8 quantization
2. ✅ Use smaller model
3. ✅ Configure `WL_CPU_THREADS` appropriately

### Improve Speed:
1. ✅ Use GPU (vs CPU)
2. ✅ Use INT8 quantization
3. ✅ Use `large-v3-turbo` (faster than large-v3)
4. ✅ Reduce `beam_size` to 1 (greedy)

## 🚀 Quick Test Commands

### Test Medium Model:
```bash
# Update .env
WHISPER_MODEL_SIZE=medium
WL_COMPUTE_TYPE=int8

# Rebuild and test
docker compose --profile gpu build whisperlive
docker compose --profile gpu up -d whisperlive

# Check VRAM
nvidia-smi
```

### Test Small Model:
```bash
# Update .env
WHISPER_MODEL_SIZE=small
WL_COMPUTE_TYPE=int8

# Rebuild and test
docker compose --profile gpu build whisperlive
docker compose --profile gpu up -d whisperlive

# Check VRAM
nvidia-smi
```

## 📋 Validation Checklist

After changing model, verify:
- [ ] Model loads successfully
- [ ] Check VRAM usage: `nvidia-smi`
- [ ] Check logs for correct model/precision
- [ ] Test transcription quality
- [ ] Test latency/performance
- [ ] Monitor for memory issues

## 🔍 Current Status

✅ **Currently Using:**
- Model: `large-v3-turbo`
- Device: `cuda` (GPU)
- Compute: `int8`
- VRAM: **~2.1 GB** (validated)

✅ **Ready to Test:**
- `medium` + INT8 → ~1-1.5 GB VRAM
- `small` + INT8 → ~500 MB VRAM

---

**See `COMPREHENSIVE_OPTIMIZATION_RESEARCH.md` for full details.**

