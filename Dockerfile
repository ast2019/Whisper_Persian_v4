# ─────────────────────────────────────────────────────────────
#  Whisper Persian v4 — STT Service for Coolify
#  CPU-only | Model pre-downloaded at build time
#  API: OpenAI-compatible /v1/audio/transcriptions
# ─────────────────────────────────────────────────────────────

FROM python:3.11-slim AS base

# ── متغیرهای build ──────────────────────────────────────────
ARG MODEL_NAME=nezamisafa/whisper-persian-v4
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/models \
    TRANSFORMERS_CACHE=/app/models \
    MODEL_NAME=${MODEL_NAME}

WORKDIR /app

# ── نصب وابستگی‌های سیستمی ──────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── نصب وابستگی‌های Python ──────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── دانلود مدل هنگام build (نه runtime) ─────────────────────
# این باعث میشه container سریع بالا بیاد و نیازی به اینترنت نداشته باشه
RUN python -c "\
from transformers import pipeline; \
import torch; \
print(f'Downloading model: ${MODEL_NAME}'); \
p = pipeline('automatic-speech-recognition', model='${MODEL_NAME}', device='cpu', torch_dtype=torch.float32); \
print('Model downloaded and cached successfully')"

# ── کپی سورس ────────────────────────────────────────────────
COPY main.py .
COPY entrypoint.sh .
RUN chmod +x /app/entrypoint.sh

# ── کاربر غیر root ──────────────────────────────────────────
RUN useradd -r -s /bin/false -d /app sttuser \
    && chown -R sttuser:sttuser /app
USER sttuser

# ── Health check ─────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -fsS http://localhost:3000/health || exit 1

EXPOSE 3000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-u", "main.py"]
