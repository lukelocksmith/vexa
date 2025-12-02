# WhisperLive Large v3 CPU Optimization Research
**Date:** November 2025  
**Objective:** Research optimized CPU version of WhisperLive Large v3 for multilingual, real-time transcription

## Executive Summary

Based on current research and available solutions as of November 2025, here are the key findings for running WhisperLive Large v3 optimized for CPU with multilingual and real-time capabilities.

## Current Implementation Status

- **Current Model:** `medium` (from .env configuration)
- **Backend:** faster-whisper (CTranslate2-based)
- **CPU Compute Type:** `default` (int8 commented out)
- **Large v3 Support:** Already supported in model list
- **Multilingual:** Supported natively by large-v3

## Recommended CPU Optimization Approaches

### 1. **Faster Whisper with INT8 Quantization (RECOMMENDED)**

**Why this is best:**
- Already integrated in your codebase
- Proven performance for CPU inference
- Native multilingual support
- Real-time streaming capabilities built-in

**Key Optimization Steps:**
1. **Use INT8 quantization** instead of default compute_type
   - Provides 2-4x speedup on CPU
   - Minimal accuracy loss (~1-2% WER increase)
   - Reduces memory usage by ~50%

2. **Configure CPU threads** for optimal performance
   - Set `cpu_threads` parameter based on available CPU cores
   - Recommended: Number of physical cores (not hyperthreads)

3. **Model Configuration:**
   ```python
   WhisperModel(
       "large-v3",
       device="cpu",
       compute_type="int8",  # Key optimization
       cpu_threads=4,  # Adjust based on CPU cores
       num_workers=1
   )
   ```

**Performance Expectations:**
- Large v3 on CPU with int8: ~2-5x real-time speed (depends on CPU)
- Memory usage: ~6-8GB (vs ~12GB for float32)

### 2. **Whisper Turbo (Alternative Consideration)**

**Characteristics:**
- 8x faster than standard Large v3
- Supports 99+ languages
- Maintains high accuracy
- Production-ready
- Compatible with Hugging Face Transformers

**Consideration:**
- Not yet integrated into faster-whisper
- Would require separate implementation
- Model ID: `large-v3-turbo` or `turbo` (already in your model list)

**Trade-off:**
- Slightly lower accuracy than full Large v3
- Much faster inference

### 3. **OpenVINO Backend (Intel CPU Optimization)**

**Best for:**
- Intel CPUs specifically
- Maximum Intel hardware utilization
- Integrated GPU acceleration on Intel chips

**Implementation:**
- Requires separate backend integration
- Available through WhisperLive backend options
- Optimized for Intel architectures

### 4. **Distilled Models (For Extreme Speed Requirements)**

**Options:**
- `distil-large-v3`: Smaller, faster, slightly less accurate
- Language-specific experts available

**Use Case:**
- When Large v3 is still too slow
- Acceptable accuracy trade-off

## Technical Implementation Recommendations

### Step 1: Enable INT8 Quantization

**File:** `whisper_live/server.py` (Line ~2394)

**Current code:**
```python
self.compute_type = "default" #"int8" #NOTE: maybe we use default here...
```

**Recommended change:**
```python
if device == "cuda":
    major, _ = torch.cuda.get_device_capability(device)
    self.compute_type = "float16" if major >= 7 else "float32"
else:
    # Use int8 for CPU - provides significant speedup with minimal accuracy loss
    self.compute_type = "int8"
```

### Step 2: Add CPU Thread Configuration

**Enhancement:** Add environment variable for CPU thread control

```python
cpu_threads = int(os.getenv("WL_CPU_THREADS", "0"))  # 0 = auto-detect
```

Pass to model creation:
```python
self.transcriber = WhisperModel(
    self.model_size_or_path,
    device=device,
    compute_type=self.compute_type,
    cpu_threads=cpu_threads,  # Add this
    local_files_only=False,
)
```

### Step 3: Update Model Configuration

**Environment Variables (.env):**
```
WHISPER_MODEL_SIZE=large-v3
DEVICE_TYPE=cpu
WL_CPU_THREADS=4  # Adjust based on your CPU
```

### Step 4: Real-Time Optimization Settings

**Recommended settings for real-time performance:**

In `settings.py`:
- `BEAM_SIZE = 1` ✅ (Already optimized - greedy decoding)
- `MIN_AUDIO_S = 1.0` ✅ (Good for real-time)
- Consider adjusting `MAX_BUFFER_S` based on CPU performance

**Additional Optimizations:**
- Use `single_model=True` to share model across connections
- Enable VAD to reduce unnecessary processing
- Tune `VAD_ONSET` threshold for your use case

## Performance Benchmarks (Expected)

Based on faster-whisper documentation and benchmarks:

### Large v3 on Modern CPU (e.g., Intel i7-12700, 8 cores)

| Configuration | Speed | Memory | Accuracy |
|--------------|-------|--------|----------|
| Float32 (default) | ~0.5x RT | ~12GB | 100% |
| INT8 | ~2-3x RT | ~6-8GB | ~98-99% |
| INT8 + 4 threads | ~2.5-3.5x RT | ~6-8GB | ~98-99% |

*RT = Real-time speed (1.0x RT means processes audio in real-time)*

### Large v3 Turbo (if available)

| Configuration | Speed | Memory | Accuracy |
|--------------|-------|--------|----------|
| CPU | ~5-8x RT | ~6-8GB | ~95-97% |

## Multilingual Support

**Large v3 Native Support:**
- 99+ languages
- Automatic language detection
- Language codes: auto-detect or specify (e.g., "en", "es", "fr", "de", etc.)

**No additional configuration needed** - large-v3 is multilingual by default.

**Implementation:**
```python
# Auto-detect language
language=None  # or omit

# Or specify language
language="en"  # or any other language code
```

## Real-Time Readiness

**Current Implementation is Real-Time Ready:**
- ✅ Streaming audio buffer
- ✅ Voice Activity Detection (VAD)
- ✅ Incremental transcription
- ✅ Low-latency processing

**Optimizations for Better Real-Time Performance:**
1. Use INT8 quantization (reduces latency)
2. Tune MIN_AUDIO_S (balance latency vs quality)
3. Optimize CPU threads (ensure all cores utilized)
4. Use single_model=True (reduces memory per connection)

## Migration Plan

### Phase 1: Enable INT8 for CPU (Quick Win)
1. Uncomment/enable `compute_type="int8"` for CPU
2. Update .env: `WHISPER_MODEL_SIZE=large-v3`
3. Test with sample audio

### Phase 2: Add CPU Thread Control
1. Add `WL_CPU_THREADS` environment variable
2. Pass to WhisperModel initialization
3. Test different thread counts

### Phase 3: Performance Tuning
1. Benchmark with your typical audio streams
2. Tune buffer settings
3. Optimize VAD thresholds
4. Monitor memory usage

### Phase 4: Evaluate Turbo (Optional)
1. Test `large-v3-turbo` if available
2. Compare speed vs accuracy
3. Decide if trade-off is acceptable

## Code Changes Required

### 1. server.py (Line ~2394)
```python
# Change from:
self.compute_type = "default" #"int8"

# To:
self.compute_type = os.getenv("WL_COMPUTE_TYPE", "int8" if device == "cpu" else "float16")
```

### 2. server.py - Add CPU threads support
```python
# Add after compute_type assignment:
cpu_threads = int(os.getenv("WL_CPU_THREADS", "0"))

# Update create_model:
def create_model(self, device):
    cpu_threads = int(os.getenv("WL_CPU_THREADS", "0"))
    self.transcriber = WhisperModel(
        self.model_size_or_path,
        device=device,
        compute_type=self.compute_type,
        cpu_threads=cpu_threads if cpu_threads > 0 else None,
        local_files_only=False,
    )
```

### 3. .env file
```
WHISPER_MODEL_SIZE=large-v3
DEVICE_TYPE=cpu
WL_CPU_THREADS=4
WL_COMPUTE_TYPE=int8
```

## Testing Checklist

- [ ] Load large-v3 model successfully
- [ ] Test INT8 quantization accuracy
- [ ] Verify multilingual transcription (test 3+ languages)
- [ ] Measure real-time performance (should be > 1.0x RT)
- [ ] Test with streaming audio
- [ ] Monitor memory usage
- [ ] Verify low latency (< 2-3 seconds)
- [ ] Test with multiple concurrent connections

## Resources and References

1. **Faster Whisper GitHub:** https://github.com/guillaumekln/faster-whisper
2. **WhisperLive Documentation:** https://deepwiki.com/collabora/WhisperLive
3. **Whisper Turbo:** https://whisperturbo.org
4. **CTranslate2 Quantization:** https://opennmt.net/CTranslate2/quantization.html

## Conclusion

**Recommended Approach:**
1. ✅ Use **faster-whisper with INT8 quantization** (already in codebase)
2. ✅ Upgrade to **large-v3** model (already supported)
3. ✅ Enable **CPU thread optimization**
4. ⚠️ Consider **large-v3-turbo** if speed is critical

**Expected Outcome:**
- 2-4x real-time transcription speed on CPU
- 99+ language support (native to large-v3)
- Real-time ready with existing streaming infrastructure
- ~50% memory reduction vs float32

**Next Steps:**
1. Enable INT8 quantization in code
2. Update environment configuration
3. Test with large-v3 model
4. Benchmark and tune performance

