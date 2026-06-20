"""
Whisper Persian v4 — سرویس تبدیل گفتار به متن فارسی

API سازگار با OpenAI Audio Transcription:
  POST /v1/audio/transcriptions  (multipart/form-data)

طراحی شده برای:
  • استقرار روی Coolify (Dockerfile-based)
  • اتصال از bihotel_voip_stt (حالت STT_PROVIDER=local)
  • پایداری بالا: health check، graceful shutdown، concurrency control
  • CPU-only (بدون GPU)

مدل: nezamisafa/whisper-persian-v4 (HuggingFace)
"""
import os
import sys
import time
import signal
import asyncio
import tempfile
import logging
import threading
from pathlib import Path
from contextlib import asynccontextmanager

import torch
import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from transformers import pipeline

# ─── تنظیمات ──────────────────────────────────────────────────────

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("whisper-stt")

# مدل و زبان
MODEL_NAME = os.environ.get("STT_MODEL", "nezamisafa/whisper-persian-v4")
DEFAULT_LANGUAGE = os.environ.get("STT_LANGUAGE", "fa")
DEVICE = os.environ.get("DEVICE", "cpu")

# محدودیت‌ها
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", 100))
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", 2))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 600))  # ثانیه

# پورت
PORT = int(os.environ.get("PORT", 3000))

# ─── State ────────────────────────────────────────────────────────

_model_ready = False
_model_lock = threading.Semaphore(MAX_CONCURRENT)
_pipe = None
_start_time = time.time()
_total_requests = 0
_total_errors = 0
_total_processed = 0


# ─── Model Loading ────────────────────────────────────────────────

def load_model():
    """بارگذاری مدل Whisper — یک‌بار هنگام استارت."""
    global _pipe, _model_ready
    logger.info(f"Loading model: {MODEL_NAME} on device: {DEVICE}")
    t0 = time.time()
    try:
        _pipe = pipeline(
            "automatic-speech-recognition",
            model=MODEL_NAME,
            device=DEVICE,
            torch_dtype=torch.float32,
        )
        elapsed = time.time() - t0
        _model_ready = True
        logger.info(f"Model loaded successfully in {elapsed:.1f}s")
    except Exception as e:
        logger.critical(f"FATAL: Failed to load model: {e}")
        sys.exit(1)


# ─── Lifespan (startup / shutdown) ───────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """مدیریت چرخه حیات: بارگذاری مدل + graceful shutdown."""
    load_model()
    logger.info(f"Service ready on port {PORT} | max_concurrent={MAX_CONCURRENT}")
    yield
    logger.info("Shutting down gracefully...")


# ─── FastAPI App ──────────────────────────────────────────────────

app = FastAPI(
    title="Whisper Persian STT",
    version="4.0.0",
    description="سرویس تبدیل گفتار فارسی به متن — API سازگار با OpenAI",
    lifespan=lifespan,
)


# ─── Middleware: request timeout ─────────────────────────────────

@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """تایم‌اوت برای جلوگیری از هنگ کردن روی فایل‌های بزرگ."""
    try:
        return await asyncio.wait_for(
            call_next(request),
            timeout=REQUEST_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"error": f"Request timeout ({REQUEST_TIMEOUT}s)"},
        )


# ─── Endpoints ───────────────────────────────────────────────────

@app.get("/")
async def root():
    """ریشه — برای health check ساده."""
    return {
        "service": "whisper-persian-stt",
        "version": "4.0.0",
        "model": MODEL_NAME,
        "status": "ready" if _model_ready else "loading",
    }


@app.get("/health")
async def health():
    """
    Health check — Coolify و bihotel_voip_stt از این استفاده می‌کنن.
    اگه مدل آماده نباشه 503 برمی‌گردونه.
    """
    if not _model_ready:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "device": DEVICE,
        "uptime_seconds": int(time.time() - _start_time),
        "stats": {
            "total_requests": _total_requests,
            "total_processed": _total_processed,
            "total_errors": _total_errors,
        },
    }


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default=None),
    language: str = Form(default=None),
    response_format: str = Form(default="json"),
):
    """
    API سازگار با OpenAI Audio Transcription.
    
    bihotel_voip_stt این پارامترها رو می‌فرسته:
      - file: فایل صوتی (wav/ogg/mp3/flac)
      - model: نادیده گرفته می‌شه (همیشه whisper-persian-v4)
      - language: زبان (پیش‌فرض fa)
      - response_format: json
    
    Returns:
      {"text": "متن ترنسکریپت شده"}
    """
    global _total_requests, _total_errors, _total_processed
    _total_requests += 1

    # ── بررسی آمادگی مدل ────────────────────────────────────────
    if not _model_ready:
        _total_errors += 1
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    # ── بررسی اندازه فایل ───────────────────────────────────────
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        _total_errors += 1
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {file_size_mb:.1f}MB (max: {MAX_FILE_SIZE_MB}MB)",
        )

    if len(content) == 0:
        _total_errors += 1
        raise HTTPException(status_code=400, detail="Empty file")

    # ── تشخیص پسوند فایل ────────────────────────────────────────
    original_name = file.filename or "audio.wav"
    suffix = Path(original_name).suffix or ".wav"
    if suffix not in (".wav", ".ogg", ".mp3", ".flac", ".webm", ".m4a", ".mp4"):
        suffix = ".wav"

    # ── ذخیره موقت و پردازش ──────────────────────────────────────
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Concurrency control — فقط MAX_CONCURRENT درخواست همزمان
        acquired = _model_lock.acquire(timeout=30)
        if not acquired:
            _total_errors += 1
            raise HTTPException(
                status_code=429,
                detail=f"Server busy — max {MAX_CONCURRENT} concurrent requests",
            )

        try:
            lang = language or DEFAULT_LANGUAGE
            t0 = time.time()

            # اجرای inference در thread pool (برای async)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: _pipe(
                    tmp_path,
                    generate_kwargs={"language": lang, "task": "transcribe"},
                ),
            )

            elapsed = time.time() - t0
            text = (result.get("text") or "").strip()

            logger.info(
                f"Transcribed: {file_size_mb:.1f}MB | "
                f"{elapsed:.1f}s | {len(text)} chars | lang={lang}"
            )

            _total_processed += 1

            # ── فرمت خروجی ──────────────────────────────────────
            if response_format == "text":
                return text
            elif response_format == "verbose_json":
                return {
                    "text": text,
                    "language": lang,
                    "duration": elapsed,
                    "model": MODEL_NAME,
                }
            else:
                # json (default) — همون که bihotel_voip_stt انتظار داره
                return {"text": text}

        finally:
            _model_lock.release()

    except HTTPException:
        raise
    except Exception as e:
        _total_errors += 1
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ─── Graceful Shutdown ────────────────────────────────────────────

def _shutdown_handler(signum, frame):
    """سیگنال SIGTERM — Coolify هنگام restart/redeploy می‌فرسته."""
    logger.info(f"Received signal {signum}. Shutting down...")
    sys.exit(0)


signal.signal(signal.SIGTERM, _shutdown_handler)
signal.signal(signal.SIGINT, _shutdown_handler)


# ─── Direct Run ──────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        workers=1,  # فقط ۱ worker — مدل سنگینه و RAM محدوده
        log_level=LOG_LEVEL.lower(),
        timeout_keep_alive=30,
    )
