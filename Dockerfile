# ──────────────────────────────────────────────────────────────
#  Whisper Persian v4 — STT Service (CPU-only)
#  مدل در runtime دانلود می‌شود — نه build time
#  Volume را در Coolify روی /app/models ست کن!
# ──────────────────────────────────────────────────────────────

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CUDA_VISIBLE_DEVICES="" \
    # هر سه متغیر یکسان — جلوگیری از دانلود دوباره
    HF_HOME=/app/models \
    HUGGINGFACE_HUB_CACHE=/app/models \
    TRANSFORMERS_CACHE=/app/models \
    MODEL_NAME=nezamisafa/whisper-persian-v4

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --progress-bar off -r requirements.txt

COPY main.py download_model.py entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh && mkdir -p /app/models

VOLUME ["/app/models"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=3600s --retries=3 \
    CMD curl -fsS http://localhost:3000/health || exit 1

EXPOSE 3000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-u", "main.py"]
