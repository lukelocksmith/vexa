# Comprehensive Whisper Model Optimization Research
**Date:** November 2025  
**Objective:** Find all optimization options for Whisper models - multilingual, capable, optimized for lower GPU footprint or CPU

## Executive Summary

Based on comprehensive research, here are **multiple optimization strategies** to reduce GPU VRAM and CPU memory usage while maintaining multilingual capabilities and acceptable accuracy. The research covers model selection, quantization, compression techniques, and alternative implementations.

---

## 1. Model Selection (Multilingual Options)

### Current Supported Models in Your Codebase:

**Standard Models (Multilingual):**
- `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`
- All support 99+ languages
- No `.en` suffix = multilingual

**Distilled Models (Available but Limited):**
- `distil-small.en` - English only
- `distil-medium.en` - English only
- `distil-large-v2` - Multilingual ✅
- `distil-large-v3` - Multilingual ✅

**Optimized Models:**
- `large-v3-turbo` - Multilingual, 8x faster than large-v3 ✅
- `turbo` - Same as large-v3-turbo

### Model Size & VRAM Comparison

| Model | Parameters | GPU VRAM (Float16) | GPU VRAM (INT8) | CPU RAM (INT8) | Multilingual | Accuracy |
|-------|------------|-------------------|-----------------|----------------|--------------|----------|
| **tiny** | ~39M | ~150 MB | ~75 MB | ~150-300 MB | ✅ Yes | Basic |
| **base** | ~74M | ~300 MB | ~150 MB | ~300-600 MB | ✅ Yes | Good |
| **small** | ~244M | ~1 GB | ~500 MB | ~1-2 GB | ✅ Yes | Very Good |
| **medium** | ~769M | ~2-3 GB | ~1-1.5 GB | ~2-4 GB | ✅ Yes | Excellent |
| **large-v3** | ~1550M | ~6-8 GB | ~3-4 GB | ~6-8 GB | ✅ Yes | Outstanding |
| **large-v3-turbo** | ~809M | ~6-8 GB | ~2-3 GB | ~6-8 GB | ✅ Yes | Excellent* |
| **distil-large-v2** | ~756M | ~3-4 GB | ~1.5-2 GB | ~3-4 GB | ✅ Yes | Very Good |
| **distil-large-v3** | ~756M | ~3-4 GB | ~1.5-2 GB | ~3-4 GB | ✅ Yes | Very Good |

*Turbo models are optimized for speed, slightly lower accuracy than full large-v3

---

## 2. Optimization Strategies

### Strategy 1: INT8 Quantization (Already Implemented ✅)

**Status:** ✅ **Fully working** (validated at 2.1 GB VRAM)

**Benefits:**
- ✅ **50-75% VRAM reduction**
- ✅ Works on both GPU and CPU
- ✅ **2-4x speedup** on CPU
- ✅ Minimal accuracy loss (~1-2% WER increase)

**Configuration:**
```env
WL_COMPUTE_TYPE=int8
```

**Results:**
- `large-v3-turbo` + INT8: **~2.1 GB VRAM** (measured)
- `medium` + INT8: ~1-1.5 GB VRAM
- `small` + INT8: ~500 MB VRAM

---

### Strategy 2: Use Smaller Multilingual Models

#### Option A: Medium Model + INT8
```env
WHISPER_MODEL_SIZE=medium
DEVICE_TYPE=cuda  # or cpu
WL_COMPUTE_TYPE=int8
```

**Footprint:**
- **GPU VRAM**: ~1-1.5 GB
- **CPU RAM**: ~2-4 GB
- **Accuracy**: Excellent (95-98% of large-v3)
- **Speed**: Very fast

**Best for:** 4GB GPUs, need more headroom

#### Option B: Small Model + INT8
```env
WHISPER_MODEL_SIZE=small
DEVICE_TYPE=cuda  # or cpu
WL_COMPUTE_TYPE=int8
```

**Footprint:**
- **GPU VRAM**: ~500 MB
- **CPU RAM**: ~1-2 GB
- **Accuracy**: Very Good (90-95% of large-v3)
- **Speed**: Very fast

**Best for:** Extremely limited VRAM (2GB GPUs), CPU-only systems

#### Option C: Base Model + INT8
```env
WHISPER_MODEL_SIZE=base
DEVICE_TYPE=cuda  # or cpu
WL_COMPUTE_TYPE=int8
```

**Footprint:**
- **GPU VRAM**: ~150 MB
- **CPU RAM**: ~300-600 MB
- **Accuracy**: Good (85-90% of large-v3)
- **Speed**: Extremely fast

**Best for:** Embedded systems, edge devices, minimal resources

---

### Strategy 3: Distilled Models (If Available)

#### distil-large-v3 (Multilingual ✅)
```env
WHISPER_MODEL_SIZE=distil-large-v3
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
```

**Expected Footprint:**
- **GPU VRAM**: ~1.5-2 GB (INT8)
- **CPU RAM**: ~3-4 GB (INT8)
- **Accuracy**: Very Good (90-95% of large-v3)
- **Parameters**: ~756M (half of large-v3)

**Status:** ⚠️ **Need to verify availability** in faster-whisper repository

**Advantages:**
- ✅ Smaller than full large-v3
- ✅ Multilingual support
- ✅ Good accuracy/quality trade-off

---

### Strategy 4: Advanced Quantization Techniques

#### 4-bit Quantization (Whisper.cpp)
**Status:** ⚠️ **Requires whisper.cpp backend** (not currently integrated)

**Benefits:**
- **75% VRAM reduction** vs INT8
- **50% VRAM reduction** vs INT8 (4-bit = 0.5 bytes vs 1 byte)
- Very low memory footprint

**Trade-offs:**
- ⚠️ Requires separate backend implementation
- ⚠️ May have accuracy impact

**Potential Footprint:**
- `large-v3-turbo` + 4-bit: ~1 GB VRAM
- `medium` + 4-bit: ~500-750 MB VRAM

---

### Strategy 5: Model Compression Techniques

#### Pruning (Research Stage)
**Status:** ⚠️ **Research/Experimental**

**Benefits:**
- Up to **35.4% parameter reduction**
- **14.25% memory reduction** (demonstrated on Whisper-small)
- Maintains accuracy

**Implementation:**
- Structured Sparsity
- Weight-Adaptive Pruning
- Requires custom model conversion

**Note:** Not directly available in faster-whisper, would need custom implementation

---

### Strategy 6: CPU Optimization Strategies

#### CPU-Specific Optimizations

**Already Implemented:**
- ✅ INT8 quantization
- ✅ CPU thread configuration (`WL_CPU_THREADS`)

**Additional Optimizations:**

1. **Batch Size Tuning:**
   ```python
   # Smaller batches use less memory
   batch_size=1  # Minimal memory
   ```

2. **Beam Size Reduction:**
   ```python
   # Greedy decoding (beam_size=1) uses less memory
   beam_size=1  # Fastest, lower memory
   ```

3. **VAD Optimization:**
   ```python
   # Skip non-speech segments
   use_vad=True  # Reduces processing
   ```

---

## 3. Comprehensive Footprint Comparison

### GPU VRAM Requirements (All Multilingual Models)

| Model | Float16 | INT8 | 4-bit (if available) |
|-------|---------|------|---------------------|
| **large-v3-turbo** | ~6-8 GB | **~2.1 GB** ✅ | ~1 GB* |
| **large-v3** | ~6-8 GB | ~3-4 GB | ~1.5 GB* |
| **distil-large-v3** | ~3-4 GB | ~1.5-2 GB | ~750 MB* |
| **medium** | ~2-3 GB | **~1-1.5 GB** | ~500 MB* |
| **small** | ~1 GB | **~500 MB** | ~250 MB* |
| **base** | ~300 MB | **~150 MB** | ~75 MB* |
| **tiny** | ~150 MB | **~75 MB** | ~40 MB* |

*Requires whisper.cpp backend

### CPU RAM Requirements (All Multilingual Models)

| Model | Float32 | INT8 |
|-------|---------|------|
| **large-v3-turbo** | ~12 GB | **~6-8 GB** |
| **medium** | ~6 GB | **~2-4 GB** |
| **small** | ~3 GB | **~1-2 GB** |
| **base** | ~1 GB | **~300-600 MB** |
| **tiny** | ~400 MB | **~150-300 MB** |

---

## 4. Recommended Configurations by Use Case

### Use Case 1: 1/4 A16 (4GB VRAM) - Current Target ✅

**Best Option:**
```env
WHISPER_MODEL_SIZE=large-v3-turbo
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
WL_MAX_CLIENTS=5-8
```

**Result:** ~2.1 GB VRAM (measured) ✅

**Alternative (More Headroom):**
```env
WHISPER_MODEL_SIZE=medium
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
WL_MAX_CLIENTS=10+
```

**Result:** ~1-1.5 GB VRAM

---

### Use Case 2: 2GB GPU or Less

**Recommended:**
```env
WHISPER_MODEL_SIZE=small
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
```

**Result:** ~500 MB VRAM

**Or:**
```env
WHISPER_MODEL_SIZE=medium
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
```

**Result:** ~1-1.5 GB VRAM (tight but workable)

---

### Use Case 3: CPU-Only System

**Recommended:**
```env
WHISPER_MODEL_SIZE=medium
DEVICE_TYPE=cpu
WL_COMPUTE_TYPE=int8
WL_CPU_THREADS=4  # Adjust to your CPU cores
```

**Result:** ~2-4 GB RAM, ~2-5x real-time speed

**For Lower Memory:**
```env
WHISPER_MODEL_SIZE=small
DEVICE_TYPE=cpu
WL_COMPUTE_TYPE=int8
WL_CPU_THREADS=4
```

**Result:** ~1-2 GB RAM, very fast

---

### Use Case 4: Maximum Quality (Quality > Memory)

**Recommended:**
```env
WHISPER_MODEL_SIZE=large-v3
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
```

**Result:** ~3-4 GB VRAM (INT8) or ~6-8 GB (Float16)

---

### Use Case 5: Maximum Efficiency (Memory > Quality)

**Recommended:**
```env
WHISPER_MODEL_SIZE=small
DEVICE_TYPE=cuda
WL_COMPUTE_TYPE=int8
```

**Result:** ~500 MB VRAM, still multilingual and good quality

---

## 5. Alternative Backends (Future Considerations)

### Whisper.cpp (C++ Implementation)

**Benefits:**
- ✅ 4-bit, 5-bit, 8-bit quantization
- ✅ Lower memory footprint
- ✅ Faster inference
- ✅ CPU optimized

**Drawbacks:**
- ⚠️ Not currently integrated
- ⚠️ Would require backend implementation

**Potential VRAM:**
- `large-v3-turbo` + 4-bit: ~1 GB
- `medium` + 4-bit: ~500 MB

---

### OpenVINO (Intel CPU Optimization)

**Benefits:**
- ✅ Optimized for Intel CPUs
- ✅ Can use Intel integrated GPU
- ✅ Lower memory usage

**Drawbacks:**
- ⚠️ Intel-specific
- ⚠️ Would require backend implementation

---

## 6. Quick Reference: Optimization Matrix

| Goal | Model | Device | Compute | VRAM/RAM | Quality |
|------|-------|--------|---------|----------|---------|
| **Best Quality** | large-v3 | GPU | int8 | ~3-4 GB | 98-99% |
| **Balanced** | large-v3-turbo | GPU | int8 | **~2.1 GB** ✅ | 95-98% |
| **Low VRAM** | medium | GPU | int8 | ~1-1.5 GB | 95-97% |
| **Ultra Low VRAM** | small | GPU | int8 | ~500 MB | 90-95% |
| **CPU Efficient** | medium | CPU | int8 | ~2-4 GB | 95-97% |
| **CPU Minimal** | small | CPU | int8 | ~1-2 GB | 90-95% |

---

## 7. Implementation Priority

### Already Implemented ✅
1. ✅ INT8 quantization (GPU & CPU)
2. ✅ CPU thread configuration
3. ✅ Multiple model sizes support
4. ✅ Multilingual models available

### Recommended Next Steps

1. **Test smaller models:**
   - Validate `medium` + INT8 on GPU (~1-1.5 GB VRAM)
   - Validate `small` + INT8 on GPU (~500 MB VRAM)

2. **Verify distilled models:**
   - Test `distil-large-v3` availability
   - Benchmark footprint vs accuracy

3. **Optimize batch/beam settings:**
   - Reduce `beam_size` to 1 (greedy) for lower memory
   - Adjust `batch_size` based on VRAM

4. **Monitor and tune:**
   - Track actual VRAM usage per model
   - Optimize `WL_MAX_CLIENTS` based on measurements

---

## 8. Summary & Recommendations

### Current State ✅
- **Best option currently:** `large-v3-turbo` + INT8 on GPU
- **Actual VRAM:** ~2.1 GB (validated)
- **Fits on:** 4GB GPUs (like 1/4 A16)

### Additional Options Available:

1. **For More Headroom:**
   - Switch to `medium` + INT8 → ~1-1.5 GB VRAM

2. **For Lower Quality Needs:**
   - Use `small` + INT8 → ~500 MB VRAM

3. **For CPU Deployment:**
   - `medium` + INT8 on CPU → ~2-4 GB RAM

4. **Future Options:**
   - Distilled models (if verified)
   - Whisper.cpp backend (4-bit quantization)
   - Model pruning (experimental)

### Key Findings:

✅ **All standard Whisper models are multilingual** (except `.en` variants)  
✅ **INT8 quantization works on both GPU and CPU**  
✅ **Medium model + INT8 provides excellent quality/VRAM trade-off**  
✅ **Small model + INT8 fits on minimal hardware**  
⚠️ **Distilled models need verification** in faster-whisper  
⚠️ **4-bit quantization requires whisper.cpp backend** (not integrated)

---

## 9. Next Actions

1. **Test `medium` model:**
   ```bash
   WHISPER_MODEL_SIZE=medium
   WL_COMPUTE_TYPE=int8
   # Measure actual VRAM usage
   ```

2. **Test `small` model:**
   ```bash
   WHISPER_MODEL_SIZE=small
   WL_COMPUTE_TYPE=int8
   # Measure actual VRAM usage
   ```

3. **Compare quality:**
   - Run same audio through different models
   - Compare transcription accuracy
   - Measure latency

4. **Document findings:**
   - Create model comparison matrix
   - Document actual footprints
   - Recommend per use case

---

## Appendix: Model Details

### Standard Whisper Models (All Multilingual ✅)

- **tiny**: 39M params, basic quality, fastest
- **base**: 74M params, good quality, very fast
- **small**: 244M params, very good quality, fast
- **medium**: 769M params, excellent quality, good speed
- **large-v2**: 1550M params, outstanding quality
- **large-v3**: 1550M params, outstanding quality (latest)

### Optimized Variants

- **large-v3-turbo**: ~809M params, 8x faster, excellent quality
- **distil-large-v2**: ~756M params, distilled from large-v2
- **distil-large-v3**: ~756M params, distilled from large-v3

### Language-Specific (English Only)

- **tiny.en, base.en, small.en, medium.en**: English-only versions
- **distil-small.en, distil-medium.en**: Distilled English-only

**Note:** Models without `.en` suffix are all multilingual (99+ languages) ✅

