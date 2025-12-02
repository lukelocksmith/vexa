# Large v3 Turbo CPU Setup

## Configuration Updated

Changed from `medium` model to `large-v3-turbo` for CPU testing.

### Changes Made:
1. ✅ Updated `.env`: `WHISPER_MODEL_SIZE=large-v3-turbo`
2. ✅ Updated `download_model.py`: Added `large-v3-turbo` and `turbo` to supported model types
3. ✅ CPU optimizations already configured:
   - `DEVICE_TYPE=cpu`
   - `WL_COMPUTE_TYPE=int8`
   - `WL_CPU_THREADS=4`

## About Large v3 Turbo

**Key Features:**
- 🚀 **8x faster** than standard Large v3
- 🌍 **99+ languages** supported (multilingual)
- ✅ **Production-ready**
- 📊 **High accuracy** maintained despite speed gains

**Trade-offs:**
- Slightly lower accuracy than full Large v3 (~95-97% vs 98-99%)
- Much faster inference on CPU
- Still excellent quality for real-time transcription

## Performance Expectations on CPU

With `large-v3-turbo` + INT8 quantization:
- **Speed**: ~5-8x real-time (vs ~2-4x for standard large-v3)
- **Memory**: ~6-8GB (similar to large-v3)
- **Accuracy**: High quality, production-ready

## Next Steps

### 1. Download the Model
```bash
make download-model
```

This will download `large-v3-turbo` model optimized for CPU with INT8 quantization.

### 2. Rebuild Container (if needed)
```bash
docker compose --profile cpu build whisperlive-cpu
```

### 3. Start Services
```bash
make up TARGET=cpu
# or just
docker compose --profile cpu up -d
```

### 4. Verify Configuration
Check logs to confirm:
```
INFO:root:Using Device=cpu with precision int8
```

And that it loads the turbo model correctly.

## Notes

- The model will be downloaded to `./hub` directory
- First load may take longer as it downloads the model
- INT8 quantization will be applied automatically for CPU
- The model supports multilingual transcription out of the box

