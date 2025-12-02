import os
from typing import Literal
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure a local cache dir exists and point HF_HOME to ./hub so it aligns with docker-compose bind mounts
hub_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'hub'))
os.makedirs(hub_dir, exist_ok=True)
os.environ['HF_HOME'] = hub_dir

from faster_whisper import WhisperModel

# Get model configuration from environment variables with fallbacks
model_size: Literal["tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3", "large", "distil-small", "distil-medium", "distil-large", "large-v3-turbo", "turbo"] = os.getenv('WHISPER_MODEL_SIZE', 'tiny')
device_env = os.getenv('DEVICE_TYPE', 'cuda')
# Normalize device type: map 'groq' or other non-standard values to 'cpu' for local CPU inference
if device_env not in ["cpu", "cuda", "auto"]:
    device_env = "cpu"
device: Literal["cpu", "cuda", "auto"] = device_env
# Use int8 for CPU, default for others
compute_type: Literal["int8", "float16", "default"] = "int8" if device == "cpu" else "default"

print(f"Downloading Whisper model with configuration:")
print(f"Model Size: {model_size}")
print(f"Device: {device}")
print(f"Compute Type: {compute_type}")

model = WhisperModel(model_size, device=device, compute_type=compute_type)

print(f"\nSuccessfully downloaded {model_size} model for {device} device.")

# segments, _ = model.transcribe("input.mp3", language="en", task="transcribe")

# for segment in segments:
#     print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))