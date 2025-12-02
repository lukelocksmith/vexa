# Large v3 Turbo GPU Setup

## Configuration Updated for GPU

Changed from CPU to GPU while keeping `large-v3-turbo` model.

### Changes Made:
1. ✅ Updated `.env`: `DEVICE_TYPE=cuda`
2. ✅ Removed CPU-specific settings (WL_CPU_THREADS, WL_COMPUTE_TYPE=int8)
3. ✅ Model remains: `WHISPER_MODEL_SIZE=large-v3-turbo`

### GPU Compute Type Auto-Selection:
The code automatically selects the best compute type for your GPU:
- **Compute Capability >= 7** (Volta/Turing/Ampere/Ada): Uses `float16` (faster, lower memory)
- **Compute Capability < 7** (older GPUs): Uses `float32` (more compatible)

You can override this by setting `WL_COMPUTE_TYPE` explicitly if needed.

## GPU vs CPU Performance

### GPU Advantages:
- 🚀 **Much faster inference** (often 10-50x faster than CPU)
- ✅ **Higher accuracy** (no quantization needed)
- 📊 **Better real-time performance**
- 🔄 **Can handle more concurrent connections**

### Model: Large v3 Turbo on GPU
- **Speed**: Very fast (often >10x real-time)
- **Memory**: ~6-8 GB GPU VRAM (with float16)
- **Accuracy**: Excellent (no quantization loss)

## Configuration Summary

```env
WHISPER_MODEL_SIZE=large-v3-turbo
DEVICE_TYPE=cuda
```

The code will automatically:
- Detect GPU availability
- Select optimal compute type (float16/float32)
- Use GPU acceleration

## Next Steps

### 1. Run with GPU Target
```bash
make all TARGET=gpu
```

This will:
- Build the GPU version of WhisperLive
- Download the model if needed
- Start all services with GPU support

### 2. Verify GPU Setup
Check logs to confirm:
```
INFO:root:Using Device=cuda with precision float16
```
(or `float32` for older GPUs)

### 3. Check GPU Utilization
```bash
nvidia-smi
```

You should see the WhisperLive container using GPU memory.

## Notes

- **GPU Required**: Make sure you have NVIDIA GPU with CUDA support
- **Docker GPU Access**: Requires `nvidia-container-toolkit` installed
- **Model Download**: Will download the appropriate GPU-optimized version
- **Memory**: Ensure GPU has enough VRAM (6-8GB recommended for large-v3-turbo)

## Comparison: CPU vs GPU

| Metric | CPU (int8) | GPU (float16) |
|--------|-----------|---------------|
| Speed | ~2-4x RT | ~10-50x RT |
| Memory | ~6-8 GB RAM | ~6-8 GB VRAM |
| Accuracy | ~98% | ~100% |
| Best for | Testing/Dev | Production |

**RT = Real-time (1.0x = processes audio in real-time)**

