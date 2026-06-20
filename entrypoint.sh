#!/bin/sh
set -e

echo "========================================"
echo " Whisper Persian v4 — STT Service"
echo "   Model: ${STT_MODEL:-nezamisafa/whisper-persian-v4}"
echo "   Device: ${DEVICE:-cpu}"
echo "   Port: ${PORT:-8000}"
echo "   Max Concurrent: ${MAX_CONCURRENT:-2}"
echo "========================================"

# بررسی وجود مدل کش شده
MODEL_DIR="${HF_HOME:-/app/models}"
if [ -d "$MODEL_DIR" ] && [ "$(ls -A $MODEL_DIR 2>/dev/null)" ]; then
    echo "Model cache found at $MODEL_DIR"
else
    echo "WARNING: Model cache not found at $MODEL_DIR"
    echo "  Model will be downloaded at startup (slow first start)"
fi

# بررسی ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ERROR: ffmpeg not found! Audio processing will fail."
    exit 1
fi
echo "ffmpeg: $(ffmpeg -version 2>&1 | head -1)"

# بررسی حافظه
if [ -f /proc/meminfo ]; then
    total_mem=$(grep MemTotal /proc/meminfo | awk '{print int($2/1024)}')
    avail_mem=$(grep MemAvailable /proc/meminfo | awk '{print int($2/1024)}')
    echo "Memory: ${avail_mem}MB available / ${total_mem}MB total"
    if [ "$avail_mem" -lt 2048 ]; then
        echo "WARNING: Less than 2GB RAM available. Model loading may fail."
    fi
fi

echo "Starting service..."
exec "$@"
