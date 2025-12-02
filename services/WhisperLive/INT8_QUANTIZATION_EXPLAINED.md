# INT8 Quantization - Model Size Reduction

## ✅ Yes, INT8 Quantization Reduces Model Size

`WL_COMPUTE_TYPE=int8` reduces **both disk storage size and memory (RAM) usage** when the model is loaded.

## How INT8 Quantization Works

### Memory (RAM) Reduction:
- **Float32 (default)**: 4 bytes per parameter
- **INT8**: 1 byte per parameter
- **Theoretical reduction**: ~75% (4x smaller)
- **Actual reduction**: ~50-75% depending on implementation

### Disk Storage Reduction:
With faster-whisper and CTranslate2:
- Models can be stored as **pre-quantized INT8 versions** on disk
- This means the actual model files are smaller
- Faster download times
- Less disk space required

## Size Comparison Examples

### Large v3 Model:
| Format | Disk Size | Memory (RAM) | Speed |
|--------|-----------|--------------|-------|
| Float32 | ~3-4 GB | ~12 GB | Baseline |
| INT8 | ~1-1.5 GB | ~6-8 GB | 2-4x faster |

### Large v3 Turbo:
| Format | Disk Size | Memory (RAM) | Speed |
|--------|-----------|--------------|-------|
| Float32 | ~3-4 GB | ~12 GB | Baseline |
| INT8 | ~1-1.5 GB | ~6-8 GB | 2-4x faster |

*Note: Large v3 Turbo is already optimized, so sizes may vary slightly*

## How Faster-Whisper Handles This

When you specify `compute_type="int8"`:

1. **If pre-quantized model exists**: Downloads/caches the INT8 version directly
2. **If not available**: Downloads the standard model and quantizes it on first load
3. **Subsequent loads**: Uses the cached quantized version (faster)

The quantized model is stored in your `./hub` directory, so you get the size benefits permanently.

## Benefits Summary

✅ **Disk Space**: ~50-75% reduction in model file size  
✅ **Memory (RAM)**: ~50-75% reduction when loaded  
✅ **Download Speed**: Faster to download smaller files  
✅ **Inference Speed**: 2-4x faster on CPU  
✅ **Accuracy**: Minimal loss (~1-2% WER increase)

## Trade-offs

⚠️ **Accuracy**: Slight reduction (~95-98% of original accuracy)  
⚠️ **First Load**: May take time to quantize if pre-quantized version doesn't exist

## For Your Current Setup

With `WHISPER_MODEL_SIZE=large-v3-turbo` and `WL_COMPUTE_TYPE=int8`:

- **Expected disk size**: ~1-1.5 GB (instead of ~3-4 GB)
- **Expected RAM usage**: ~6-8 GB (instead of ~12 GB)
- **Download time**: Faster due to smaller file size
- **Inference speed**: Much faster on CPU

This is especially important for CPU inference where memory and speed are critical!

