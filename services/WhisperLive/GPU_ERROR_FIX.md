# GPU Model Loading Error Fix

## Issue

When trying to load `large-v3-turbo` on GPU, the following error occurred:

```
ERROR:root:Failed to load model: __init__(): incompatible constructor arguments. The following argument types are supported:
    1. ctranslate2._ext.Whisper(model_path: str, device: str = 'cpu', *, device_index: Union[int, List[int]] = 0, compute_type: Union[str, Dict[str, str]] = 'default', inter_threads: int = 1, intra_threads: int = 0, max_queued_batches: int = 0, flash_attention: bool = False, tensor_parallel: bool = False, files: object = None)

Invoked with: '...'; kwargs: device='cuda', device_index=0, compute_type='float16', intra_threads=None, inter_threads=1, files=None
```

**Root Cause:** The code was passing `cpu_threads=None` when not explicitly set, which got converted to `intra_threads=None` in the underlying CTranslate2 library. CTranslate2 expects an integer (default is 0 for auto-detect), not None.

## Fix Applied

**File:** `whisper_live/server.py` - `create_model` method

**Changed from:**
```python
cpu_threads = cpu_threads if cpu_threads > 0 else None

self.transcriber = WhisperModel(
    self.model_size_or_path,
    device=device,
    compute_type=self.compute_type,
    cpu_threads=cpu_threads,  # Could be None - causes error
    local_files_only=False,
)
```

**Changed to:**
```python
# Build kwargs - only include cpu_threads if it's explicitly set (> 0)
model_kwargs = {
    "device": device,
    "compute_type": self.compute_type,
    "local_files_only": False,
}
# Only pass cpu_threads if explicitly set (0 means auto-detect in WhisperModel)
if cpu_threads > 0:
    model_kwargs["cpu_threads"] = cpu_threads

self.transcriber = WhisperModel(
    self.model_size_or_path,
    **model_kwargs
)
```

## How It Works Now

- **If `WL_CPU_THREADS` is set and > 0:** Passes `cpu_threads` explicitly
- **If `WL_CPU_THREADS` is 0 or not set:** Doesn't pass `cpu_threads` parameter, allowing WhisperModel to use its default (0 = auto-detect)

This prevents passing `None` which causes the CTranslate2 error.

## Next Steps

Rebuild the container for the fix to take effect:

```bash
docker compose --profile gpu build whisperlive
docker compose --profile gpu up -d whisperlive
```

After rebuilding, the model should load successfully with GPU.

