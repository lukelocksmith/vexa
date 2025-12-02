# CPU Optimization Fixes Applied

## Issue Found
From the logs, the system was using `precision default` instead of `int8`:
```
INFO:root:Using Device=cpu with precision default
```

This means the INT8 quantization wasn't being applied even though it was configured in `.env`.

## Fixes Applied

### 1. Updated `server.py` - Compute Type Logic (Line ~2389-2399)
**Changed from:**
```python
self.compute_type = "default" #"int8" #NOTE: maybe we use default here...
```

**Changed to:**
```python
# Check for explicit compute type from environment variable
env_compute_type = os.getenv("WL_COMPUTE_TYPE")
if env_compute_type:
    self.compute_type = env_compute_type
elif device == "cuda":
    major, _ = torch.cuda.get_device_capability(device)
    self.compute_type = "float16" if major >= 7 else "float32"
else:
    # Default to int8 for CPU (faster and lower memory)
    self.compute_type = "int8"
```

### 2. Updated `server.py` - CPU Threads Support (Line ~2439-2453)
**Added CPU threads configuration:**
```python
# Get CPU threads from environment variable (0 = auto-detect)
cpu_threads_env = os.getenv("WL_CPU_THREADS", "0")
cpu_threads = int(cpu_threads_env) if cpu_threads_env.isdigit() else 0
cpu_threads = cpu_threads if cpu_threads > 0 else None

self.transcriber = WhisperModel(
    self.model_size_or_path,
    device=device,
    compute_type=self.compute_type,
    cpu_threads=cpu_threads,  # NEW: Pass CPU threads
    local_files_only=False,
)
```

## Next Steps

**You need to rebuild the WhisperLive container for changes to take effect:**

```bash
# Option 1: Rebuild just the whisperlive-cpu service
docker compose --profile cpu build whisperlive-cpu

# Option 2: Rebuild everything
make build TARGET=cpu

# Then restart
docker compose --profile cpu up -d whisperlive-cpu
```

## Expected Result After Rebuild

The logs should now show:
```
INFO:root:Using Device=cpu with precision int8
```

Instead of:
```
INFO:root:Using Device=cpu with precision default
```

## Configuration Summary

Current `.env` settings:
- `DEVICE_TYPE=cpu`
- `WHISPER_MODEL_SIZE=medium`
- `WL_CPU_THREADS=4`
- `WL_COMPUTE_TYPE=int8`

These will now be properly applied when the container is rebuilt!

