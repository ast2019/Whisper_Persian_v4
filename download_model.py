"""
دانلود و کش مدل Whisper — در runtime (نه build time).

این اسکریپت توسط entrypoint.sh فراخوانی می‌شود.
اگه مدل قبلاً کش شده باشد، entrypoint.sh اصلاً این اسکریپت را صدا نمی‌زند.
"""
import os
import sys

from transformers import pipeline
import torch

model_name = os.environ.get("MODEL_NAME", "nezamisafa/whisper-persian-v4")
hf_token   = os.environ.get("HF_TOKEN", None)   # اگه مدل private باشه

print(f"Downloading model: {model_name}", flush=True)

try:
    pipeline(
        "automatic-speech-recognition",
        model=model_name,
        device="cpu",
        torch_dtype=torch.float32,
        token=hf_token,
    )
    print("Model downloaded and cached successfully.", flush=True)
except Exception as e:
    print(f"ERROR: Failed to download model: {e}", file=sys.stderr, flush=True)
    sys.exit(1)
