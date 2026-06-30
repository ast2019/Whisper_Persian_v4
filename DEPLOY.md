# راهنمای استقرار کامل خط لولهٔ تحلیل صوتی (روی Coolify)

این سند نحوهٔ بالا آوردن **هر ۴ سرویس** را روی Coolify توضیح می‌دهد. هر سرویس یک
**Resource جداگانه** از **گیت مخصوص خودش** است (بدون docker-compose).

| # | سرویس | گیت | نقش | پورت |
|---|---|---|---|---|
| ① | **Whisper Persian v4** | `ast2019/Whisper_Persian_v4` | موتور صوت→متن (CPU) | 3000 |
| ② | **STT worker + api** | `ast2019/bihotel_voip_stt` | کشف تماس، ترنسکریپشن، API خام | 8080 (api) |
| ③ | **Backend** | `ast2019/bihotel-backend-izadshahr` | تحلیل + داشبورد API + /status | (وب) |
| ④ | **Frontend** | `ast2019/hotelbi` | داشبورد React | (وب) |
| — | **stt-db** | (Coolify MySQL Service) | دیتابیس نتایج + صف STT | 3306 |

> سرویس ② در واقع **دو Resource از یک گیت** است (worker و api) که یک stt-db مشترک دارند.

---

## نقشهٔ اتصال‌ها (مهم‌ترین بخش)

```
Asterisk (192.168.10.70)  ──MySQL CDR + SSH/SFTP──►  ② worker
② worker  ──HTTP /v1/audio/transcriptions──►  ① Whisper :3000
② worker/api  ──►  stt-db (voice_analysis + stt_queue)
② api  ──exposes /bi/calls (X-API-Key)──►  ③ Backend
③ Backend  ──serves /api/v1/*──►  ④ Frontend
```

🔑 **قانون طلایی هم‌بندی:** مقدار `STT_API_KEY` در بک‌اند (③) باید **دقیقاً برابر**
`API_KEY` در سرویس STT (②) باشد. در غیر این صورت `/bi/calls` با 401 رد می‌شود و
داشبورد تحلیل صوتی خالی می‌ماند.

---

## ترتیب استقرار

استقرار را به همین ترتیب انجام دهید: **stt-db → Whisper → worker → api → backend → frontend**

### پیش‌نیاز: یک Docker Network مشترک
Coolify → Settings → **Connect To Predefined Network**. سرویس‌های ①②④③ و stt-db را
به یک شبکه وصل کنید تا با **hostname داخلی** همدیگر را ببینند. همچنین مطمئن شوید
سرور Coolify به `192.168.10.70` (Asterisk) دسترسی شبکه‌ای دارد.

---

### ① stt-db (MySQL Database Service)
Coolify → **Add New Resource → Database → MySQL**.
- یک نام دیتابیس بسازید (مثلاً `default`).
- از بخش **Internal Connection** این مقادیر را بردارید (برای قدم بعد لازم‌اند):
  `DB_HOST` (مثل `coolify-db-xxxx`)، `DB_PORT`، `DB_USER`، `DB_PASSWORD`، `DB_NAME`.

---

### ② Whisper Persian v4  (موتور STT)
Coolify → **Add New Resource → Dockerfile-based** → گیت `ast2019/Whisper_Persian_v4`، برنچ `main`.

- **پورت:** `3000`
- ⚠️ **build سنگین است** (دانلود مدل + torch هنگام build). در تنظیمات Resource،
  **Build Timeout** را زیاد کنید (مثلاً ۳۰–۶۰ دقیقه).
- ⚠️ **RAM:** حداقل ~۳–۴GB بدهید (entrypoint زیر ۲GB هشدار می‌دهد). برای CPU با
  8GB RAM، مقدار `MAX_CONCURRENT=2` مناسب است.

**Environment Variables (مقادیر پیش‌فرض اکثراً کافی‌اند):**
```
STT_MODEL=nezamisafa/whisper-persian-v4
STT_LANGUAGE=fa
DEVICE=cpu
MAX_FILE_SIZE_MB=100
MAX_CONCURRENT=2
REQUEST_TIMEOUT=600
PORT=3000
LOG_LEVEL=INFO
```

**تأیید:**
```bash
curl http://<whisper-internal-host>:3000/health      # → {"status":"ok", ...}
```
(اولین بار تا مدل کاملاً لود شود کمی طول می‌کشد؛ `start-period` هلث‌چک ۱۲۰ ثانیه است.)

---

### ②‑a STT worker
Coolify → **Add New Resource → Dockerfile-based** → گیت `ast2019/bihotel_voip_stt`، برنچ `main`.
- **CMD:** پیش‌فرض Dockerfile (`python -u worker.py`) — نیازی به override نیست.
- entrypoint خودش اتصال DB را چک و migrationها (`voice_analysis` + `stt_queue`) را می‌سازد.

**Environment Variables:**
```
# موتور STT → لوکال (Whisper)
STT_PROVIDER=local
STT_LANGUAGE=fa
LOCAL_STT_URL=http://<whisper-internal-host>:3000
LOCAL_STT_MODEL=large-v3-turbo        # نادیده گرفته می‌شود؛ Whisper همیشه v4 است
LOCAL_STT_TIMEOUT=600

# Asterisk — فقط خواندن
ASTERISK_DB_HOST=192.168.10.70
ASTERISK_DB_PORT=3306
ASTERISK_DB_USER=asterisk_readonly
ASTERISK_DB_PASSWORD=<رمز واقعی>
ASTERISK_DB_NAME=asterisk
ASTERISK_SSH_HOST=192.168.10.70
ASTERISK_SSH_PORT=22
ASTERISK_SSH_USER=root
ASTERISK_SSH_PASSWORD=<رمز واقعی>
ASTERISK_RECORDING_PATH=/var/spool/asterisk/monitor

# stt-db (از Internal Connection قدم ①)
DB_HOST=<coolify-internal-db-host>
DB_PORT=3306
DB_USER=<از Coolify>
DB_PASSWORD=<از Coolify>
DB_NAME=default

# رفتار worker (پیش‌فرض‌ها معمولاً خوب‌اند)
POLL_INTERVAL_SECONDS=120
BATCH_SIZE=10
MIN_DURATION_SECONDS=30
PROCESS_CALL_TYPES=incoming
QUEUE_ORDER=asc
MAX_ATTEMPTS=3
STALE_LOCK_MINUTES=15

# 🔑 کلید API خروجی — باید قوی و تصادفی باشد (در قدم api و backend هم همین)
API_KEY=<یک کلید قوی و تصادفی>
```

---

### ②‑b STT api
Coolify → **Add New Resource → Dockerfile-based** → **همان گیت** `ast2019/bihotel_voip_stt`.
- **CMD override:** `uvicorn api:app --host 0.0.0.0 --port 8080`
- **پورت:** `8080`
- **Environment Variables:** **دقیقاً همان** متغیرهای worker (مخصوصاً همان `DB_*`
  و همان `API_KEY`). فقط CMD و پورت فرق دارد.

**تأیید:**
```bash
curl http://<stt-api-host>:8080/health
curl -H "X-API-Key: <API_KEY>" http://<stt-api-host>:8080/status
curl -H "X-API-Key: <API_KEY>" "http://<stt-api-host>:8080/bi/calls?page=1"
```

---

### ③ Backend (Laravel)
Resource موجود است؛ فقط دو متغیر **جدید** را اضافه کنید و با برنچ **`reborn-voice`** ری‌دیپلوی کنید:
```
STT_API_BASE_URL=http://<stt-api-internal-host>:8080
STT_API_KEY=<همان API_KEY سرویس STT>

# اختیاری (پیش‌فرض دارند):
STT_API_TIMEOUT=30
STT_API_PAGE_SIZE=200
VOICE_ANALYSIS_CONNECTION=mysql
VOICE_INGEST_LOOKBACK_DAYS=2
VOICE_INGEST_MAX_PAGES=50
VOICE_INGEST_MIN_CHARS=10
```
- migration جدول `call_voice_analysis` با دیپلوی اجرا می‌شود (روی کانکشن `mysql`).
- زمان‌بند `callanalytics:analyze-voice` هر ۱۵ دقیقه خودکار اجرا می‌شود و جدول را پر می‌کند
  (نیازمند فعال بودن Laravel scheduler / `schedule:run`).

**اجرای دستی برای پرکردن اولیه (اختیاری):**
```bash
php artisan callanalytics:analyze-voice --from=2026-06-01 --to=2026-06-30
```

---

### ④ Frontend (React)
Resource موجود است؛ مطمئن شوید این متغیر به بک‌اند اشاره می‌کند و با `reborn-voice` بیلد/دیپلوی کنید:
```
VITE_API_BASE_URL=https://<backend-host>
```

---

## تأیید سرتاسری (End‑to‑End)

1. `curl http://<whisper>:3000/health` → `ok`
2. `curl -H "X-API-Key: KEY" http://<stt-api>:8080/status` → اتصال‌های DB/Asterisk/STT سبز
3. در لاگ worker باید `Enqueued ... / Done ... / Saved: uniqueid=...` ببینید.
4. `curl -H "X-API-Key: KEY" http://<stt-api>:8080/bi/calls?page=1` → آیتم‌های دارای `transcript`
5. در بک‌اند: `GET /api/v1/status` → کارت «سرویس تحلیل صوتی (STT)» و «تازگی دادهٔ تحلیل صوتی» باید سبز شوند.
6. در داشبورد: صفحهٔ «تحلیل عمیق تماس» → پنل تحلیل صوتی با توزیع احساس/موضوع پر شود.

---

## عیب‌یابی سریع

| نشانه | علت محتمل | راه‌حل |
|---|---|---|
| داشبورد تحلیل صوتی خالی / «فعال نشده» | `STT_API_KEY` ≠ `API_KEY` | یکسان‌سازی کلید در ② و ③ |
| `/bi/calls` خطای 401 | کلید نادرست در هدر | بررسی `STT_API_KEY` بک‌اند |
| worker در STT تایم‌اوت | Whisper کند/کم‌RAM | افزایش RAM، `MAX_CONCURRENT=2`، `LOCAL_STT_TIMEOUT` بالاتر |
| build Whisper شکست می‌خورد | Build Timeout کم | افزایش Build Timeout در Coolify |
| worker به Asterisk وصل نمی‌شود | روتینگ/فایروال به 192.168.10.70 | باز کردن دسترسی شبکه از سرور Coolify |
| `/status` کارت STT قرمز | `STT_API_BASE_URL` غلط یا api پایین | بررسی hostname داخلی و بالا بودن api |

---

## یادداشت معماری

- سرویس STT (②) فقط **متن خام** تولید می‌کند؛ **تحلیل** (احساس/موضوع/امتیاز/خلاصه)
  در بک‌اند (③) انجام می‌شود — این تفکیک عمدی است (گزینهٔ A).
- بک‌اند داده را از **API سرویس STT** (`/bi/calls`) می‌خواند، نه مستقیم از stt-db؛
  پس بین بک‌اند و stt-db هیچ کوپلینگ دیتابیسی لازم نیست — فقط شبکه به `:8080` و کلید API.
