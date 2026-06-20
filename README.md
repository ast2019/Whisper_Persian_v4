# Whisper Persian v4 — STT Service

سرویس تبدیل گفتار فارسی به متن (Speech-to-Text) بر پایه مدل [nezamisafa/whisper-persian-v4](https://huggingface.co/nezamisafa/whisper-persian-v4).

طراحی شده برای استقرار روی **Coolify** و اتصال داخلی به سرویس `bihotel_voip_stt`.

---

## فهرست

- [معماری](#معماری)
- [API Reference](#api-reference)
- [استقرار روی Coolify](#استقرار-روی-coolify)
- [اتصال به bihotel_voip_stt](#اتصال-به-bihotel_voip_stt)
- [تنظیمات (Environment Variables)](#تنظیمات)
- [ساختار فایل‌ها](#ساختار-فایلها)
- [عملکرد و محدودیت‌ها](#عملکرد-و-محدودیتها)
- [مانیتورینگ و سلامت](#مانیتورینگ-و-سلامت)
- [توسعه و گسترش](#توسعه-و-گسترش)
- [عیب‌یابی](#عیبیابی)

---

## معماری

```
┌───────────────────────────────────────────────────────────────┐
│                        Coolify Server                          │
│                                                               │
│  ┌─────────────────────┐      ┌─────────────────────────┐    │
│  │  bihotel_voip_stt   │      │  Whisper Persian v4     │    │
│  │  (STT Worker)       │──────│  (This Service)         │    │
│  │                     │ HTTP │                         │    │
│  │  POST /v1/audio/    │◄─────│  Port: 3000            │    │
│  │  transcriptions     │      │  Model: whisper-v4     │    │
│  └─────────────────────┘      └─────────────────────────┘    │
│           │                              │                    │
│           ▼                              ▼                    │
│  ┌─────────────────────┐      ┌─────────────────────────┐    │
│  │  MySQL Database     │      │  HuggingFace Model      │    │
│  │  (Coolify DB)       │      │  (cached at build)      │    │
│  └─────────────────────┘      └─────────────────────────┘    │
└───────────────────────────────────────────────────────────────┘
```

### جریان داده:

```
فایل صوتی (WAV/OGG/MP3)
    │
    ▼
bihotel_voip_stt (worker)
    │  POST /v1/audio/transcriptions
    │  multipart/form-data: file + model + language
    ▼
Whisper Persian v4 (این سرویس)
    │  1. دریافت فایل
    │  2. بررسی اندازه و فرمت
    │  3. Semaphore (concurrency control)
    │  4. Inference با مدل Whisper
    │  5. بازگشت متن
    ▼
{"text": "متن فارسی ترنسکریپت شده"}
```

---

## API Reference

### `POST /v1/audio/transcriptions`

ترنسکریپشن فایل صوتی به متن فارسی. **سازگار با OpenAI Audio API**.

**Request:**
```
Content-Type: multipart/form-data
```

| پارامتر | نوع | اجباری | توضیح |
|---------|------|--------|-------|
| `file` | File | ✅ | فایل صوتی (wav, ogg, mp3, flac, webm, m4a) |
| `model` | string | ❌ | نام مدل (نادیده گرفته می‌شود — همیشه whisper-persian-v4) |
| `language` | string | ❌ | زبان ترنسکریپشن. پیش‌فرض: `fa` |
| `response_format` | string | ❌ | فرمت خروجی: `json` (پیش‌فرض), `text`, `verbose_json` |

**Response (json):**
```json
{"text": "سلام خوش آمدید به هتل ایزدشهر"}
```

**Response (verbose_json):**
```json
{
  "text": "سلام خوش آمدید به هتل ایزدشهر",
  "language": "fa",
  "duration": 12.3,
  "model": "nezamisafa/whisper-persian-v4"
}
```

**خطاها:**
| Status | دلیل |
|--------|-------|
| 400 | فایل خالی |
| 413 | فایل بیش از حد بزرگ (پیش‌فرض: 100MB) |
| 429 | سرور مشغول (تعداد درخواست همزمان پر شده) |
| 503 | مدل هنوز لود نشده |
| 504 | تایم‌اوت (پیش‌فرض: 600 ثانیه) |

**مثال با curl:**
```bash
curl -X POST http://localhost:3000/v1/audio/transcriptions \
  -F "file=@/path/to/audio.wav" \
  -F "language=fa" \
  -F "response_format=json"
```

**مثال با Python:**
```python
import requests

resp = requests.post(
    "http://localhost:3000/v1/audio/transcriptions",
    files={"file": ("audio.wav", open("audio.wav", "rb"), "audio/wav")},
    data={"language": "fa", "response_format": "json"},
    timeout=600,
)
print(resp.json()["text"])
```

---

### `GET /health`

بررسی سلامت سرویس. استفاده‌کنندگان:
- **Coolify** (HEALTHCHECK داخل Dockerfile)
- **bihotel_voip_stt** (بررسی اتصال قبل از شروع پردازش)
- **سیستم مانیتورینگ** (Prometheus / UptimeKuma / ...)

**Response (200 OK):**
```json
{
  "status": "ok",
  "model": "nezamisafa/whisper-persian-v4",
  "device": "cpu",
  "uptime_seconds": 3600,
  "stats": {
    "total_requests": 150,
    "total_processed": 145,
    "total_errors": 5
  }
}
```

**Response (503 — مدل لود نشده):**
```json
{"detail": "Model not loaded yet"}
```

---

### `GET /`

اطلاعات پایه سرویس.

```json
{
  "service": "whisper-persian-stt",
  "version": "4.0.0",
  "model": "nezamisafa/whisper-persian-v4",
  "status": "ready"
}
```

---

## استقرار روی Coolify

### ۱. ساخت سرویس

1. در Coolify → **Add New Resource** → **Dockerfile-based**
2. ریپو: `ast2019/Whisper_Persian_v4`
3. Branch: `main`
4. Port: **3000**

### ۲. تنظیم شبکه داخلی (مهم!)

چون `bihotel_voip_stt` باید به این سرویس از داخل Docker network وصل بشه:

**روش ۱ — Connect To Predefined Network (ساده‌ترین):**
1. هر دو سرویس (`bihotel_voip_stt` و `Whisper_Persian_v4`) رو از بخش Settings → Network → **Connect To Predefined Network** فعال کنید
2. هر دو باید در شبکه `coolify` باشن

**روش ۲ — Custom Docker Network:**
1. در Coolify یه Custom Network بسازید (مثلاً `stt-network`)
2. هر دو سرویس رو بهش اضافه کنید

**بعد از تنظیم شبکه:**
- Hostname داخلی این سرویس رو از پنل Coolify بگیرید (مثل `b3xxx...`)
- اون رو توی `LOCAL_STT_URL` سرویس `bihotel_voip_stt` بذارید

### ۳. متغیرهای محیطی (اختیاری)

| متغیر | پیش‌فرض | توضیح |
|--------|---------|-------|
| `STT_MODEL` | `nezamisafa/whisper-persian-v4` | نام مدل HuggingFace |
| `STT_LANGUAGE` | `fa` | زبان پیش‌فرض |
| `DEVICE` | `cpu` | دستگاه (cpu/cuda) |
| `MAX_FILE_SIZE_MB` | `100` | حداکثر اندازه فایل |
| `MAX_CONCURRENT` | `2` | حداکثر درخواست همزمان |
| `REQUEST_TIMEOUT` | `600` | تایم‌اوت ثانیه |
| `PORT` | `3000` | پورت سرویس |
| `LOG_LEVEL` | `INFO` | سطح لاگ |

### ۴. نیازمندی سخت‌افزاری

| منبع | حداقل | پیشنهادی |
|------|--------|----------|
| RAM | 4 GB | 8 GB |
| CPU | 2 core | 4+ core |
| Disk | 5 GB (مدل + image) | 10 GB |
| GPU | ❌ نیازی نیست | اختیاری (CUDA) |

> ⚠️ مدل هنگام Docker build دانلود می‌شه (~3GB). Build اول کند خواهد بود.

---

## اتصال به bihotel_voip_stt

در `.env` پروژه `bihotel_voip_stt`:

```env
# حالت لوکال
STT_PROVIDER=local

# آدرس داخلی این سرویس در Coolify
# hostname رو از پنل Coolify → سرویس Whisper → Internal URL بگیرید
LOCAL_STT_URL=http://<coolify-internal-hostname>:3000

# مدل (اختیاری — سرور نادیده می‌گیره ولی لاگ می‌شه)
LOCAL_STT_MODEL=nezamisafa/whisper-persian-v4

# تایم‌اوت (CPU کُنده — ۶۰۰ ثانیه کافیه)
LOCAL_STT_TIMEOUT=600
```

### بررسی اتصال:

Worker هنگام استارت، `/health` رو صدا می‌زنه. اگه 200 برگرده شروع به کار می‌کنه.

---

## ساختار فایل‌ها

```
Whisper_Persian_v4/
│
├── main.py              # سرویس اصلی FastAPI
│   ├── /v1/audio/transcriptions  (POST)  — ترنسکریپشن
│   ├── /health                   (GET)   — سلامت‌سنجی
│   └── /                         (GET)   — اطلاعات پایه
│
├── Dockerfile           # ساخت image + دانلود مدل
├── entrypoint.sh        # بررسی پیش‌شرط‌ها (RAM, ffmpeg, model)
├── requirements.txt     # وابستگی‌های Python (CPU-only)
├── .env.example         # نمونه تنظیمات
├── .gitignore
└── .dockerignore
```

### main.py — ساختار داخلی:

```python
# ─── تنظیمات ─────────── خواندن env vars
# ─── State ────────────── متغیرهای global (model, counters, semaphore)
# ─── Model Loading ────── load_model() — یکبار هنگام startup
# ─── Lifespan ─────────── مدیریت startup/shutdown
# ─── Middleware ────────── timeout middleware
# ─── Endpoints ─────────── /, /health, /v1/audio/transcriptions
# ─── Graceful Shutdown ── signal handlers (SIGTERM/SIGINT)
# ─── Direct Run ────────── uvicorn.run()
```

---

## عملکرد و محدودیت‌ها

### سرعت پردازش (تخمینی، CPU):

| مدت فایل صوتی | زمان پردازش (4-core CPU) |
|----------------|--------------------------|
| 30 ثانیه | ~15-25 ثانیه |
| 1 دقیقه | ~30-50 ثانیه |
| 5 دقیقه | ~2-4 دقیقه |
| 10 دقیقه | ~5-8 دقیقه |

### Concurrency:

- `MAX_CONCURRENT=2` یعنی حداکثر ۲ فایل همزمان پردازش می‌شن
- درخواست سوم ۳۰ ثانیه منتظر می‌مونه، بعد 429 برمی‌گردونه
- افزایش `MAX_CONCURRENT` → نیاز به RAM بیشتر (هر درخواست ~2GB)

### محدودیت اندازه فایل:

- پیش‌فرض: 100MB
- فایل‌های WAV ضبط هتل معمولاً 5-30MB هستن
- OGG (بعد پیش‌پردازش bihotel_voip_stt): معمولاً 1-5MB

---

## مانیتورینگ و سلامت

### Health Check داخلی (Dockerfile):

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -fsS http://localhost:3000/health || exit 1
```

- `start-period=120s`: مدل سنگینه، ۲ دقیقه صبر می‌کنه تا لود بشه
- `interval=30s`: هر ۳۰ ثانیه بررسی
- `retries=3`: بعد ۳ بار fail → container unhealthy

### مانیتورینگ خارجی:

**UptimeKuma / Prometheus / هر سیستم مانیتورینگ:**

```
GET http://<host>:3000/health
Expected: 200 OK + JSON with status="ok"
```

**متریک‌های موجود در `/health`:**

| متریک | توضیح |
|--------|--------|
| `stats.total_requests` | کل درخواست‌های دریافتی |
| `stats.total_processed` | موفق‌ها |
| `stats.total_errors` | خطاها (4xx + 5xx) |
| `uptime_seconds` | مدت آپتایم |

### لاگ‌ها:

لاگ‌ها به `stdout` می‌رن (مناسب Docker/Coolify):

```
2025-01-15 10:30:00 [INFO] whisper-stt — Model loaded successfully in 45.2s
2025-01-15 10:30:05 [INFO] whisper-stt — Service ready on port 3000 | max_concurrent=2
2025-01-15 10:31:12 [INFO] whisper-stt — Transcribed: 3.2MB | 18.5s | 245 chars | lang=fa
2025-01-15 10:31:45 [WARNING] whisper-stt — Request timeout (600s)
2025-01-15 10:32:00 [ERROR] whisper-stt — Transcription error: ...
```

### Alert های پیشنهادی:

| وضعیت | شرط | اقدام |
|--------|-----|-------|
| 🔴 Down | `/health` → timeout یا non-200 | restart container |
| 🟡 Slow | `total_errors / total_requests > 10%` | بررسی RAM / CPU |
| 🟡 Busy | 429 زیاد | افزایش `MAX_CONCURRENT` یا اضافه کردن replica |
| 🟢 OK | 200 + error rate < 5% | عادی |

---

## توسعه و گسترش

### اضافه کردن مدل جدید:

```python
# در main.py — load_model() رو عوض کن:
MODEL_NAME = os.environ.get("STT_MODEL", "your-new-model")
```

یا فقط env var عوض کن:
```env
STT_MODEL=openai/whisper-large-v3
```

### اضافه کردن GPU (CUDA):

1. `requirements.txt` — PyTorch GPU:
```
torch==2.3.1+cu121
--extra-index-url https://download.pytorch.org/whl/cu121
```

2. `.env`:
```env
DEVICE=cuda
```

3. Dockerfile — base image عوض کن:
```dockerfile
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04
```

### اضافه کردن endpoint جدید:

مثلاً endpoint تحلیل احساسات:

```python
@app.post("/v1/audio/analyze")
async def analyze(file: UploadFile = File(...)):
    # ۱. ترنسکریپشن
    text = await _transcribe_internal(file)
    # ۲. تحلیل با LLM
    sentiment = await _analyze_sentiment(text)
    return {"text": text, "sentiment": sentiment}
```

### اضافه کردن Prometheus metrics:

```bash
pip install prometheus-fastapi-instrumentator
```

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

بعد Prometheus رو به `http://<host>:3000/metrics` وصل کن.

### Scale کردن (چند replica):

اگه حجم درخواست‌ها زیاد شد:

1. **Load balancer جلوش بذار** (Coolify خودش handle می‌کنه)
2. **هر replica مدل رو خودش لود می‌کنه** → RAM × تعداد replica
3. **پیشنهاد:** بجای replica، `MAX_CONCURRENT` رو زیاد کن (اگه RAM داری)

### اضافه کردن cache (برای فایل‌های تکراری):

```python
import hashlib

_cache = {}  # یا Redis

@app.post("/v1/audio/transcriptions")
async def transcribe(file: UploadFile):
    content = await file.read()
    file_hash = hashlib.md5(content).hexdigest()
    
    if file_hash in _cache:
        return _cache[file_hash]
    
    result = _do_transcription(content)
    _cache[file_hash] = result
    return result
```

### اضافه کردن Authentication:

```python
from fastapi import Header, HTTPException

API_KEY = os.environ.get("STT_API_KEY", "")

def _auth(x_api_key: str = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, "invalid API key")
```

---

## عیب‌یابی

### مدل لود نمی‌شه:

```
FATAL: Failed to load model: ...
```

**دلایل:**
- RAM کم (حداقل 4GB لازمه)
- مدل هنگام build دانلود نشده
- مسیر cache خراب شده

**راه‌حل:**
```bash
# Rebuild image
docker build --no-cache -t whisper-stt .
```

### خطای 429 (Server Busy):

```json
{"detail": "Server busy — max 2 concurrent requests"}
```

**راه‌حل:** `MAX_CONCURRENT` رو زیاد کن (اگه RAM کافی داری):
```env
MAX_CONCURRENT=4
```

### خطای 504 (Timeout):

```json
{"error": "Request timeout (600s)"}
```

**دلایل:**
- فایل صوتی خیلی بلنده
- CPU ضعیفه

**راه‌حل:**
```env
REQUEST_TIMEOUT=900  # ۱۵ دقیقه
```

### خطای OOM (Out of Memory):

Container کرش می‌کنه بدون لاگ.

**راه‌حل:**
- RAM سرور رو زیاد کن (8GB+)
- `MAX_CONCURRENT=1` بذار
- فایل‌های بزرگ‌تر از 50MB رو قبول نکن: `MAX_FILE_SIZE_MB=50`

### اتصال از bihotel_voip_stt fail می‌شه:

```
Local STT connection error: ...
```

**بررسی:**
1. هر دو سرویس در یک Docker network هستن؟
2. Hostname درسته؟ `curl http://<hostname>:3000/health`
3. سرویس Whisper بالاست؟ لاگ Coolify رو چک کن

---

## لایسنس

MIT — استفاده آزاد.

## مدل

[nezamisafa/whisper-persian-v4](https://huggingface.co/nezamisafa/whisper-persian-v4) — مدل fine-tune شده Whisper برای زبان فارسی.
