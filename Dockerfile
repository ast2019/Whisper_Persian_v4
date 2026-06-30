# ─────────────────────────────────────────────────────────────
#  Whisper Persian v4 — STT Service for Coolify
#  CPU-only | Model downloaded at first runtime (NOT build time)
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

# ── کپی سورس ────────────────────────────────────────────────
COPY main.py .
COPY download_model.py .
COPY entrypoint.sh .
RUN chmod +x /app/entrypoint.sh

# ── کاربر غیر root ──────────────────────────────────────────
RUN useradd -r -s /bin/false -d /app sttuser \
    && mkdir -p /app/models \
    && chown -R sttuser:sttuser /app
USER sttuser

# ── Health check ─────────────────────────────────────────────
# start-period=300s چون دانلود مدل در اولین اجرا تا 5 دقیقه طول می‌کشد
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=5 \
    CMD curl -fsS http://localhost:3000/health || exit 1

EXPOSE 3000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-u", "main.py"]
