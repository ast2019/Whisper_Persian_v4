# ──────────────────────────────────────────────────────────────
#  Whisper Persian v4 — STT Service (CPU-only)
#  مدل در runtime دانلود می‌شود — نه build time
#  Volume را در Coolify روی /app/models ست کن!
# ──────────────────────────────────────────────────────────────

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # CPU-only — GPU لازم نیست
    CUDA_VISIBLE_DEVICES="" \
    HF_HOME=/app/models \
    TRANSFORMERS_CACHE=/app/models \
    MODEL_NAME=nezamisafa/whisper-persian-v4

WORKDIR /app

# فقط ffmpeg و curl — بدون هیچ چیز اضافه
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# pip با no-cache و verbose تا لاگ کامل ببینیم
RUN pip install --no-cache-dir --progress-bar off -r requirements.txt

COPY main.py download_model.py entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh && mkdir -p /app/models

# ── Volume باید در Coolify روی /app/models mount شود ──────────
VOLUME ["/app/models"]

# start-period=3600s — صبر کامل برای دانلود مدل
HEALTHCHECK --interval=30s --timeout=10s --start-period=3600s --retries=3 \
    CMD curl -fsS http://localhost:3000/health || exit 1

EXPOSE 3000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-u", "main.py"]
