#!/bin/sh
set -e

echo "========================================"
echo " Whisper Persian v4 — STT Service"
echo "   Model : ${MODEL_NAME:-nezamisafa/whisper-persian-v4}"
echo "   Device: ${DEVICE:-cpu}"
echo "   Port  : ${PORT:-3000}"
echo "   Concur: ${MAX_CONCURRENT:-2}"
echo "========================================"

# ── بررسی ffmpeg ────────────────────────────────────────────
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "[ERROR] ffmpeg not found — cannot process audio. Aborting."
    exit 1
fi
echo "[OK] ffmpeg: $(ffmpeg -version 2>&1 | head -1)"

# ── بررسی حافظه ─────────────────────────────────────────────
if [ -f /proc/meminfo ]; then
    total_mem=$(grep MemTotal    /proc/meminfo | awk '{print int($2/1024)}')
    avail_mem=$(grep MemAvailable /proc/meminfo | awk '{print int($2/1024)}')
    echo "[INFO] Memory: ${avail_mem}MB available / ${total_mem}MB total"
    if [ "$avail_mem" -lt 2048 ]; then
        echo "[WARN] Less than 2GB RAM available. Model loading may fail."
    fi
fi

# ── دانلود مدل (فقط اگه کش نشده باشه) ──────────────────────
MODEL_DIR="${HF_HOME:-/app/models}"
MARKER_FILE="${MODEL_DIR}/.download_complete"

if [ -f "$MARKER_FILE" ]; then
    echo "[OK] Model already downloaded (marker found). Skipping download."
else
    echo "[INFO] Model not cached. Starting download..."
    echo "[INFO] This may take 3-5 minutes on first run."

    # دانلود با python — اگه fail شد container نمی‌توند کار کند
    if python /app/download_model.py; then
        # marker بنویس تا دفعه بعد دانلود نشه
        touch "$MARKER_FILE"
        echo "[OK] Model downloaded and cached successfully."
    else
        echo "[ERROR] Model download failed! Check network or HF_TOKEN."
        exit 1
    fi
fi

# ── تأیید نهایی که فایل‌های مدل واقعاً وجود دارند ────────────
MODEL_FILES=$(find "$MODEL_DIR" -name "*.safetensors" -o -name "*.bin" 2>/dev/null | wc -l)
if [ "$MODEL_FILES" -eq 0 ]; then
    echo "[ERROR] No model weight files found in $MODEL_DIR — download may be incomplete!"
    # marker را پاک کن تا دفعه بعد دوباره تلاش کند
    rm -f "$MARKER_FILE"
    exit 1
fi
echo "[OK] Model weights verified: $MODEL_FILES file(s) found in $MODEL_DIR"

echo "[INFO] Starting service..."
exec "$@"
