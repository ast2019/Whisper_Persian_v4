"""
دانلود و کش مدل Whisper هنگام build (نه runtime).

این اسکریپت عمداً جداست تا از دستور چندخطی `RUN python -c "..."` داخل Dockerfile
پرهیز شود؛ آن دستور چندخطی هنگام تزریق خودکار ARGهای Coolify (مثل
COOLIFY_RESOURCE_UUID) می‌شکست و خطای «unknown instruction: import» می‌داد.
"""
import os

import torch
from transformers import pipeline

model_name = os.environ.get("MODEL_NAME", "nezamisafa/whisper-persian-v4")

print(f"Downloading model: {model_name}", flush=True)
pipeline(
    "automatic-speech-recognition",
    model=model_name,
    device="cpu",
    torch_dtype=torch.float32,
)
print("Model downloaded and cached successfully", flush=True)
