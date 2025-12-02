# CPU Setup Configuration Summary

## Changes Made for CPU Setup

### 1. Updated `.env` file
- **DEVICE_TYPE**: Changed from `groq` to `cpu`
- **WHISPER_MODEL_SIZE**: Kept as `medium` (current model)
- **Added CPU optimizations**:
  - `WL_CPU_THREADS=4` - Number of CPU threads for inference
  - `WL_COMPUTE_TYPE=int8` - INT8 quantization for faster CPU inference

### 2. Updated `docker-compose.yml`
- Added CPU optimization environment variables to `whisperlive-cpu` service:
  - `WL_CPU_THREADS=${WL_CPU_THREADS:-4}` (defaults to 4)
  - `WL_COMPUTE_TYPE=${WL_COMPUTE_TYPE:-int8}` (defaults to int8)

### 3. Updated `download_model.py`
- Enhanced device type handling: automatically maps non-standard values (like "groq") to "cpu"
- Enabled INT8 quantization for CPU by default: `compute_type = "int8" if device == "cpu" else "default"`

## Current Configuration

```env
WHISPER_MODEL_SIZE=medium
DEVICE_TYPE=cpu
WL_CPU_THREADS=4
WL_COMPUTE_TYPE=int8
```

## How to Use

### Option 1: Run with existing .env (recommended)
Since `.env` already exists and is configured for CPU:
```bash
make all
```

This will:
- Preserve your existing `.env` file
- Use CPU profile automatically (defaults to CPU when TARGET not set)
- Download the medium model with CPU optimizations
- Build and start all services including whisperlive-cpu

### Option 2: Explicitly set TARGET (optional)
```bash
make all TARGET=cpu
```

## Next Steps

1. Run `make all` to set up and test
2. The system will:
   - Download the `medium` model optimized for CPU with INT8 quantization
   - Start whisperlive-cpu service
   - Run migrations and tests

## Expected Performance

With `medium` model on CPU with INT8:
- **Speed**: Faster than default float32
- **Memory**: Lower memory usage
- **Suitable for**: Development and testing

## Note

After testing with `medium`, you can upgrade to `large-v3` by changing:
```env
WHISPER_MODEL_SIZE=large-v3
```

And running `make download-model` to download the new model.

