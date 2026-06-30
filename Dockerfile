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
    HF_HOME=/app/models \
    HUGGINGFACE_HUB_CACHE=/app/models \
    TRANSFORMERS_CACHE=/app/models \
    MODEL_NAME=nezamisafa/whisper-persian-v4

WORKDIR /app

# فقط curl, ca-certificates, xz-utils — بدون ffmpeg سنگین از Debian
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg static binary — 1 فایل، بدون dependency، ~80MB به جای 470MB
RUN mkdir -p /tmp/ffmpeg-src /tmp/ffmpeg-extract \
    && curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
       -o /tmp/ffmpeg-src/ffmpeg.tar.xz \
    && tar -xJf /tmp/ffmpeg-src/ffmpeg.tar.xz -C /tmp/ffmpeg-extract \
    && cp /tmp/ffmpeg-extract/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg \
    && cp /tmp/ffmpeg-extract/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
    && rm -rf /tmp/ffmpeg-src /tmp/ffmpeg-extract

COPY requirements.txt .
RUN pip install --no-cache-dir --progress-bar off -r requirements.txt

COPY main.py download_model.py entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh && mkdir -p /app/models

VOLUME ["/app/models"]

# start-period=900s (15 دقیقه) — مدل cache شده، فقط 3-4 ثانیه لود می‌شه
HEALTHCHECK --interval=30s --timeout=10s --start-period=900s --retries=3 \
    CMD curl -fsS http://localhost:3000/health || exit 1

EXPOSE 3000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-u", "main.py"]
