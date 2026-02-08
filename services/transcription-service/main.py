"""
Vexa-Compatible Transcription Service (PoC)
Implements OpenAI Whisper API format for seamless integration with Vexa
"""
import os
import io
import time
import logging
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
import uvicorn
from faster_whisper import WhisperModel
# faster-whisper uses CTranslate2 internally (no PyTorch needed)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
WORKER_ID = os.getenv("WORKER_ID", "1")
MODEL_SIZE = os.getenv("MODEL_SIZE", "large-v3-turbo")

# Device detection: Use environment variable or default to cuda for GPU containers
# CTranslate2 (used by faster-whisper) will automatically detect and use CUDA if available
DEVICE = os.getenv("DEVICE", "cuda")

# Compute type optimization: Use INT8 for optimal VRAM efficiency
# Research shows: large-v3-turbo + INT8 = ~2.1 GB VRAM (validated)
# Provides 50-60% VRAM reduction with minimal accuracy loss (~1-2% WER increase)
COMPUTE_TYPE_ENV = os.getenv("COMPUTE_TYPE", "").strip().lower()
if COMPUTE_TYPE_ENV:
    COMPUTE_TYPE = COMPUTE_TYPE_ENV
else:
    # Default to INT8 for both GPU and CPU (optimal balance of speed, memory, and accuracy)
    COMPUTE_TYPE = "int8"

# CPU threads configuration (for CPU mode optimization)
CPU_THREADS = int(os.getenv("CPU_THREADS", "0"))  # 0 = auto-detect

# Quality / decoding parameters (optional)
def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, None)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")

def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, None)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"Invalid int env {name}={raw!r}, using default {default}")
        return default

def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, None)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning(f"Invalid float env {name}={raw!r}, using default {default}")
        return default

# WhisperLive-inspired defaults (can be overridden via env)
BEAM_SIZE = _env_int("BEAM_SIZE", 5)
BEST_OF = _env_int("BEST_OF", 5)
COMPRESSION_RATIO_THRESHOLD = _env_float("COMPRESSION_RATIO_THRESHOLD", 2.4)
LOG_PROB_THRESHOLD = _env_float("LOG_PROB_THRESHOLD", -1.0)
NO_SPEECH_THRESHOLD = _env_float("NO_SPEECH_THRESHOLD", 0.6)
CONDITION_ON_PREVIOUS_TEXT = _env_bool("CONDITION_ON_PREVIOUS_TEXT", True)
PROMPT_RESET_ON_TEMPERATURE = _env_float("PROMPT_RESET_ON_TEMPERATURE", 0.5)

# VAD parameters
VAD_FILTER = _env_bool("VAD_FILTER", True)
VAD_FILTER_THRESHOLD = _env_float("VAD_FILTER_THRESHOLD", 0.5)
VAD_MIN_SILENCE_DURATION_MS = _env_int("VAD_MIN_SILENCE_DURATION_MS", 160)

# Language detection (improved algorithm: segment-level aggregation, weighted scoring, early stopping)
# Used only when language is not provided (auto-detect). See _detect_language_improved().
SAMPLE_RATE_WHISPER = 16000  # Whisper/faster-whisper expect 16 kHz
LANGUAGE_DETECTION_THRESHOLD = _env_float("LANGUAGE_DETECTION_THRESHOLD", 0.5)
LANGUAGE_DETECTION_SEGMENTS = _env_int("LANGUAGE_DETECTION_SEGMENTS", 10)
# Duration per segment for language detection (seconds). We run detect_language on each segment then aggregate.
LANGUAGE_DETECTION_SEGMENT_DURATION_S = 10
LANGUAGE_DETECTION_SEGMENT_SAMPLES = SAMPLE_RATE_WHISPER * LANGUAGE_DETECTION_SEGMENT_DURATION_S

# Temperature fallback chain
USE_TEMPERATURE_FALLBACK = _env_bool("USE_TEMPERATURE_FALLBACK", False)
TEMPERATURE_FALLBACK_CHAIN = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

def _looks_like_silence(segments: List[Dict[str, Any]]) -> bool:
    """Heuristic: treat as silence if all segments look like no-speech."""
    if not segments:
        return True
    for s in segments:
        if not (
            float(s.get("no_speech_prob", 0.0)) > NO_SPEECH_THRESHOLD
            and float(s.get("avg_logprob", 0.0)) < LOG_PROB_THRESHOLD
        ):
            return False
    return True

def _looks_like_hallucination(segments: List[Dict[str, Any]]) -> bool:
    """Heuristic: reject segments that look like hallucinations / low-confidence."""
    for s in segments:
        if float(s.get("compression_ratio", 0.0)) > COMPRESSION_RATIO_THRESHOLD:
            return True
        if float(s.get("avg_logprob", 0.0)) < LOG_PROB_THRESHOLD:
            return True
    return False


def _resample_to_16k(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Resample audio to 16 kHz (float32) for Whisper/faster-whisper language detection."""
    if sample_rate == SAMPLE_RATE_WHISPER:
        return np.ascontiguousarray(audio, dtype=np.float32)
    n = len(audio)
    duration_s = n / sample_rate
    n_16k = int(duration_s * SAMPLE_RATE_WHISPER)
    indices = np.linspace(0, n - 1, n_16k, dtype=np.float64)
    resampled = np.interp(indices, np.arange(n, dtype=np.float64), audio.astype(np.float64))
    return resampled.astype(np.float32)


def _detect_language_improved(
    whisper_model: WhisperModel,
    audio: np.ndarray,
    sample_rate: int,
    language_detection_threshold: float = LANGUAGE_DETECTION_THRESHOLD,
    language_detection_segments: int = LANGUAGE_DETECTION_SEGMENTS,
) -> Tuple[str, float]:
    """
    Improved language detection: aggregate probabilities across segments, weighted scoring,
    early stopping, and robust handling of noisy/silent audio (aligned with WhisperLive PR #77).

    - Filters out segments with low confidence (max_prob < 0.4, or uncertain top vs second).
    - Aggregates per-language probabilities across valid segments.
    - Uses weighted score (avg prob + consistency) and early stopping when confident.
    - Returns ("en", 0.0) when confidence < 0.5 to avoid false positives from silence/noise.

    Returns:
        (language, language_probability). probability is 0.0 when detection is not trusted.
    """
    audio_16k = _resample_to_16k(audio, sample_rate)
    n_samples = len(audio_16k)
    vad_params = {
        "threshold": VAD_FILTER_THRESHOLD,
        "min_silence_duration_ms": VAD_MIN_SILENCE_DURATION_MS,
    }

    language_prob_aggregator: Dict[str, List[float]] = {}
    segments_processed = 0
    language = None
    language_probability = None
    all_language_probs: Optional[List[Tuple[str, float]]] = None
    min_segment_confidence = 0.4

    num_segments = min(
        language_detection_segments,
        max(1, (n_samples + LANGUAGE_DETECTION_SEGMENT_SAMPLES - 1) // LANGUAGE_DETECTION_SEGMENT_SAMPLES),
    )

    for seg_idx in range(num_segments):
        start = seg_idx * LANGUAGE_DETECTION_SEGMENT_SAMPLES
        end = min(start + LANGUAGE_DETECTION_SEGMENT_SAMPLES, n_samples)
        segment_audio = audio_16k[start:end]
        if len(segment_audio) < SAMPLE_RATE_WHISPER * 0.5:
            continue

        seg_lang, seg_prob, all_probs = whisper_model.detect_language(
            segment_audio,
            vad_filter=VAD_FILTER,
            vad_parameters=vad_params,
            language_detection_segments=1,
            language_detection_threshold=language_detection_threshold,
        )
        # Strip token format e.g. "<|en|>" -> "en"
        segment_language_probs = [
            (t[2:-2] if (t.startswith("<|") and t.endswith("|>")) else t, p)
            for t, p in (all_probs or [])
        ]
        all_language_probs = segment_language_probs

        if not segment_language_probs:
            continue
        max_prob = max(p for _, p in segment_language_probs)
        if max_prob < min_segment_confidence:
            logger.debug(
                "Skipping segment with low confidence (max_prob=%.3f < %.3f)",
                max_prob, min_segment_confidence,
            )
            continue
        if len(segment_language_probs) >= 2:
            top_prob = segment_language_probs[0][1]
            second_prob = segment_language_probs[1][1]
            prob_diff = top_prob - second_prob
            # Slightly relaxed so valid non-English segments are not discarded (was 0.35 / 0.5)
            if (prob_diff < 0.12 and top_prob < 0.45) or top_prob < 0.3:
                logger.debug(
                    "Skipping uncertain/low-confidence segment (top_prob=%.3f, diff=%.3f)",
                    top_prob, prob_diff,
                )
                continue

        for lang, prob in segment_language_probs:
            if prob >= 0.1:
                language_prob_aggregator.setdefault(lang, []).append(prob)
        segments_processed += 1

        if language_prob_aggregator:
            lang_avg_probs = {
                lang: sum(probs) / len(probs)
                for lang, probs in language_prob_aggregator.items()
            }
            top_lang = max(lang_avg_probs, key=lang_avg_probs.get)
            top_lang_avg_prob = lang_avg_probs[top_lang]
            early_stop_threshold = language_detection_threshold
            if segments_processed >= 3:
                early_stop_threshold = max(0.4, language_detection_threshold - 0.1)
            if top_lang_avg_prob > early_stop_threshold and segments_processed >= 2:
                top_lang_count = len(language_prob_aggregator[top_lang])
                if top_lang_count >= 2 and top_lang_avg_prob > early_stop_threshold:
                    language = top_lang
                    language_probability = top_lang_avg_prob
                    break

    if language is None:
        if not language_prob_aggregator:
            if all_language_probs:
                top_lang, top_prob = all_language_probs[0]
                if top_prob >= 0.5:
                    language, language_probability = top_lang, top_prob
                else:
                    logger.info(
                        "All segments filtered out, last segment has low confidence (%.3f < 0.5). Returning 'en' with probability 0.0",
                        top_prob,
                    )
                    language, language_probability = "en", 0.0
            else:
                language, language_probability = "en", 0.0
        else:
            lang_scores = {}
            for lang, probs in language_prob_aggregator.items():
                avg_prob = sum(probs) / len(probs)
                consistency_weight = min(1.0, len(probs) / 3.0)
                lang_scores[lang] = avg_prob * (0.7 + 0.3 * consistency_weight)
            language = max(lang_scores, key=lang_scores.get)
            language_probability = sum(language_prob_aggregator[language]) / len(language_prob_aggregator[language])
            if language_probability < 0.5:
                logger.info(
                    "Language detection confidence too low (%.3f < 0.5), likely noise/silence. Returning 'en' with probability 0.0",
                    language_probability,
                )
                language, language_probability = "en", 0.0

    return language, language_probability


# API Token Authentication
API_TOKEN = os.getenv("API_TOKEN", "").strip()
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_token(
    request: Request,
    api_key: Optional[str] = Depends(API_KEY_HEADER)
) -> bool:
    """Verify API token - supports both X-API-Key and Authorization Bearer"""
    if not API_TOKEN:
        # If no token configured, allow all requests (backward compatibility)
        logger.warning("API_TOKEN not configured - allowing all requests")
        return True
    
    # Try X-API-Key header first
    if api_key and api_key == API_TOKEN:
        return True
    
    # Try Authorization Bearer header (for compatibility)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        if token == API_TOKEN:
            return True
    
    logger.warning(f"Invalid or missing API token - X-API-Key: {api_key is not None}, Authorization: {bool(auth_header)}")
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API token"
    )

app = FastAPI(
    title="Vexa Transcription Service",
    description="OpenAI Whisper API compatible transcription service",
    version="1.0.0"
)

# Global model instance
model: Optional[WhisperModel] = None

# Load management: Global concurrency limit and bounded queue
# These settings control how many transcription requests can be processed concurrently
MAX_CONCURRENT_TRANSCRIPTIONS = _env_int("MAX_CONCURRENT_TRANSCRIPTIONS", 2)  # Max concurrent model calls
MAX_QUEUE_SIZE = _env_int("MAX_QUEUE_SIZE", 10)  # Max requests waiting in queue

# Backpressure strategy:
# - If FAIL_FAST_WHEN_BUSY=true, we do NOT wait in a queue; we immediately return 503 so callers
#   (e.g. WhisperLive) can keep buffering and submit a newer/larger window later.
FAIL_FAST_WHEN_BUSY = _env_bool("FAIL_FAST_WHEN_BUSY", True)
BUSY_RETRY_AFTER_S = _env_int("BUSY_RETRY_AFTER_S", 1)

# Semaphore to limit concurrent transcriptions (protects GPU/CPU from overload)
transcription_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSCRIPTIONS)

# Thread pool for running blocking transcription calls
transcription_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TRANSCRIPTIONS)

# Queue to track waiting requests (for 429/503 responses when full)
# We use a simple counter since FastAPI doesn't have a built-in queue
waiting_requests = 0
waiting_requests_lock = asyncio.Lock()


@app.on_event("startup")
async def startup_event():
    """Initialize Whisper model on startup"""
    global model
    logger.info(f"Worker {WORKER_ID} starting up...")
    logger.info(f"Device: {DEVICE}, Model: {MODEL_SIZE}, Compute: {COMPUTE_TYPE}")
    logger.info(
        "Quality params - "
        f"beam_size={BEAM_SIZE}, best_of={BEST_OF}, "
        f"cond_prev_text={CONDITION_ON_PREVIOUS_TEXT}, "
        f"compression_ratio_threshold={COMPRESSION_RATIO_THRESHOLD}, "
        f"log_prob_threshold={LOG_PROB_THRESHOLD}, "
        f"no_speech_threshold={NO_SPEECH_THRESHOLD}, "
        f"vad_filter={VAD_FILTER}"
    )
    
    try:
        # Build model initialization parameters
        model_kwargs = {
            "model_size_or_path": MODEL_SIZE,
            "device": DEVICE,
            "compute_type": COMPUTE_TYPE,
            "download_root": "/app/models"
        }
        
        # Add CPU threads for CPU mode (optimization from research)
        if DEVICE == "cpu" and CPU_THREADS > 0:
            model_kwargs["cpu_threads"] = CPU_THREADS
            logger.info(f"Worker {WORKER_ID} using {CPU_THREADS} CPU threads")
        
        model = WhisperModel(**model_kwargs)
        logger.info(f"Worker {WORKER_ID} ready - Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer"""
    health_status = {
        "status": "healthy" if model is not None else "unhealthy",
        "worker_id": WORKER_ID,
        "timestamp": datetime.utcnow().isoformat(),
        "model": MODEL_SIZE,
        "device": DEVICE,
        "gpu_available": DEVICE == "cuda",
    }
    
    if DEVICE == "cuda":
        # CTranslate2 (via faster-whisper) handles GPU automatically
        health_status["compute_type"] = COMPUTE_TYPE
    
    if model is None:
        return JSONResponse(content=health_status, status_code=503)
    
    return health_status


@app.post("/v1/audio/transcriptions")
async def transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
    requested_model: str = Form(..., alias="model"),
    temperature: str = Form("0"),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: str = Form("verbose_json"),
    timestamp_granularities: str = Form("segment"),
    task: str = Form("transcribe"),
    _: bool = Depends(verify_api_token)
):
    """
    OpenAI Whisper API compatible transcription endpoint
    
    Required by Vexa's RemoteTranscriber:
    - Accepts multipart/form-data with audio file
    - Returns verbose_json format with segments
    - Includes timing, language, and segment details
    
    Load management:
    - Limits concurrent transcriptions to prevent GPU/CPU overload
    - Returns 429/503 when queue is full to signal backpressure
    """
    if not requested_model:
        raise HTTPException(status_code=400, detail="Model parameter is required")
    
    # Load management: Check queue size before accepting request
    async with waiting_requests_lock:
        global waiting_requests
        # Fail-fast mode: don't accept work we can't start immediately.
        # This avoids "processing the first chunk" (small/old) and lets upstream buffer/coalesce.
        if FAIL_FAST_WHEN_BUSY and (transcription_semaphore.locked() or waiting_requests > 0):
            raise HTTPException(
                status_code=503,
                detail="Service busy. Please retry later.",
                headers={"Retry-After": str(max(1, BUSY_RETRY_AFTER_S))},
            )
        if waiting_requests >= MAX_QUEUE_SIZE:
            logger.warning(
                f"Worker {WORKER_ID} queue full ({waiting_requests}/{MAX_QUEUE_SIZE}). "
                f"Rejecting request with 503."
            )
            raise HTTPException(
                status_code=503,
                detail="Service temporarily overloaded. Please retry later.",
                headers={"Retry-After": str(max(1, BUSY_RETRY_AFTER_S))}
            )
        waiting_requests += 1
    
    try:
        # Acquire semaphore (blocks if MAX_CONCURRENT_TRANSCRIPTIONS is reached)
        await transcription_semaphore.acquire()
        
        async with waiting_requests_lock:
            waiting_requests -= 1
        
        start_time = time.time()
        logger.info(f"Worker {WORKER_ID} received transcription request - filename: {file.filename}, content_type: {file.content_type}")
        # Read audio file
        audio_bytes = await file.read()
        logger.info(f"Worker {WORKER_ID} read {len(audio_bytes)} bytes of audio data")
        
        # Convert to format suitable for faster-whisper
        # Use soundfile to properly decode audio formats (WAV, MP3, etc.)
        audio_io = io.BytesIO(audio_bytes)
        try:
            audio_array, sample_rate = sf.read(audio_io, dtype=np.float32)
            logger.info(f"Worker {WORKER_ID} decoded audio - shape: {audio_array.shape}, sample_rate: {sample_rate}")
        except Exception as e:
            logger.error(f"Worker {WORKER_ID} failed to decode audio with soundfile: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to decode audio file: {e}")
        
        # Ensure mono audio (convert stereo to mono if needed)
        if len(audio_array.shape) > 1:
            audio_array = np.mean(audio_array, axis=1)
            logger.info(f"Worker {WORKER_ID} converted to mono - shape: {audio_array.shape}")
        
        # Ensure audio is contiguous array
        audio_array = np.ascontiguousarray(audio_array, dtype=np.float32)
        
        # When language is not provided, use improved language detection (segment-level aggregation,
        # weighted scoring, early stopping, noise/silence filtering) before transcribing.
        auto_detect_low_confidence = False  # True when we ran detector but rejected (prob 0)
        if language is None and model is not None:
            def _detect_sync():
                return _detect_language_improved(
                    model,
                    audio_array,
                    sample_rate,
                    language_detection_threshold=LANGUAGE_DETECTION_THRESHOLD,
                    language_detection_segments=LANGUAGE_DETECTION_SEGMENTS,
                )
            detected_lang, detected_prob = await asyncio.get_event_loop().run_in_executor(
                transcription_executor, _detect_sync
            )
            # Whisper has a known bias toward English; require higher confidence for "en" before locking.
            MIN_CONFIDENCE_FOR_EN = 0.65
            if detected_prob > 0:
                if detected_lang == "en" and detected_prob < MIN_CONFIDENCE_FOR_EN:
                    auto_detect_low_confidence = True
                    logger.info(
                        f"Worker {WORKER_ID} English detection borderline (prob={detected_prob:.3f} < {MIN_CONFIDENCE_FOR_EN}), not locking"
                    )
                else:
                    language = detected_lang
                    logger.info(
                        f"Worker {WORKER_ID} auto-detected language: {language} (confidence={detected_prob:.3f})"
                    )
            else:
                auto_detect_low_confidence = True
                logger.info(
                    f"Worker {WORKER_ID} language detection low confidence, transcribe will use default"
                )

        # Transcribe (with optional temperature fallback)
        requested_temp = float(temperature) if temperature else 0.0
        temps = TEMPERATURE_FALLBACK_CHAIN if USE_TEMPERATURE_FALLBACK else [requested_temp]

        logger.info(
            f"Worker {WORKER_ID} starting transcription - requested_temp: {requested_temp}, "
            f"temps: {temps}, language: {language}, task: {task}, vad_filter: {VAD_FILTER}"
        )

        best: Optional[Tuple[str, str, float, List[Dict[str, Any]]]] = None
        last_info = None
        last_segments: List[Dict[str, Any]] = []

        for t in temps:
            # Run blocking transcription in thread pool to avoid blocking event loop
            def _transcribe_sync():
                return model.transcribe(
                    audio_array,
                    language=language,
                    task=task,
                    initial_prompt=prompt,
                    temperature=t,
                    beam_size=BEAM_SIZE,
                    best_of=BEST_OF,
                    compression_ratio_threshold=COMPRESSION_RATIO_THRESHOLD,
                    log_prob_threshold=LOG_PROB_THRESHOLD,
                    no_speech_threshold=NO_SPEECH_THRESHOLD,
                    condition_on_previous_text=CONDITION_ON_PREVIOUS_TEXT,
                    prompt_reset_on_temperature=PROMPT_RESET_ON_TEMPERATURE,
                    vad_filter=VAD_FILTER,
                    vad_parameters={
                        "threshold": VAD_FILTER_THRESHOLD,
                        "min_silence_duration_ms": VAD_MIN_SILENCE_DURATION_MS,
                    },
                    word_timestamps=False,
                )
            
            segments_list, info = await asyncio.get_event_loop().run_in_executor(
                transcription_executor, _transcribe_sync
            )
            last_info = info

            # Convert segments to list (faster-whisper returns generator)
            segments: List[Dict[str, Any]] = []
            for idx, segment in enumerate(segments_list):
                segments.append({
                    "id": idx,
                    "seek": 0,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "tokens": [],  # Not needed for PoC
                    "temperature": t,
                    "avg_logprob": segment.avg_logprob,
                    "compression_ratio": segment.compression_ratio,
                    "no_speech_prob": segment.no_speech_prob,
                    # Add audio_ fields that RemoteTranscriber looks for
                    "audio_start": segment.start,
                    "audio_end": segment.end,
                })
            last_segments = segments

            if _looks_like_silence(segments):
                best = ("", info.language, 0.0, [])
                logger.info(f"Worker {WORKER_ID} detected silence (temp={t})")
                break

            is_hallucination = _looks_like_hallucination(segments)

            if not is_hallucination:
                full_text = " ".join([s["text"].strip() for s in segments]).strip()
                duration = segments[-1]["end"] if segments else 0.0
                best = (full_text, info.language, duration, segments)
                logger.info(f"Worker {WORKER_ID} accepted transcription (temp={t})")
                break
            else:
                logger.info(f"Worker {WORKER_ID} rejected transcription as hallucination/low-confidence (temp={t})")

        if best is None:
            # Fall back to last attempt (even if it looks low-quality) to preserve backward behavior.
            info = last_info
            segments = last_segments
            full_text = " ".join([s["text"].strip() for s in segments]).strip()
            duration = segments[-1]["end"] if segments else 0.0
            best = (full_text, info.language if info else (language or "unknown"), duration, segments)

        full_text, detected_language, duration, segments = best
        # When we had low-confidence auto-detect and model returned "en", don't report "en" so
        # clients don't lock to English; report "unknown" and probability 0 so they can keep detecting.
        if auto_detect_low_confidence and detected_language == "en":
            reported_language = "unknown"
            language_probability = 0.0
        else:
            reported_language = detected_language
            language_probability = 1.0
        logger.info(f"Worker {WORKER_ID} transcription completed - language: {reported_language}")
        
        processing_time = time.time() - start_time
        logger.info(
            f"Worker {WORKER_ID} completed in {processing_time:.2f}s - "
            f"Duration: {duration:.2f}s, Segments: {len(segments)}, Language: {reported_language}"
        )
        
        # Return format expected by Vexa RemoteTranscriber
        response = {
            "text": full_text,
            "language": reported_language,
            "language_probability": language_probability,
            "duration": duration,
            "segments": segments,
        }
        
        # CTranslate2 handles memory management automatically
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions (429, 503, etc.)
        raise
    except Exception as e:
        logger.error(f"Worker {WORKER_ID} transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Always release semaphore, even on error
        transcription_semaphore.release()


@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": "Vexa Transcription Service",
        "worker_id": WORKER_ID,
        "model": MODEL_SIZE,
        "device": DEVICE,
        "status": "ready" if model is not None else "initializing",
        "endpoints": {
            "transcribe": "/v1/audio/transcriptions",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

