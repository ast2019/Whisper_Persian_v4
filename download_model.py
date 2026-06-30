"""
دانلود مدل Whisper در runtime — با مانیتورینگ کامل.
توسط entrypoint.sh فراخوانی می‌شود.
"""
import os
import sys
import time
import threading

from transformers import pipeline
import torch
from huggingface_hub import snapshot_download

model_name = os.environ.get("MODEL_NAME", "nezamisafa/whisper-persian-v4")
hf_token   = os.environ.get("HF_TOKEN", None)
cache_dir  = os.environ.get("HF_HOME", "/app/models")

print(f"[DOWNLOAD] Model  : {model_name}", flush=True)
print(f"[DOWNLOAD] Cache  : {cache_dir}", flush=True)
print(f"[DOWNLOAD] Started: {time.strftime('%H:%M:%S')}", flush=True)
print(f"[DOWNLOAD] -----------------------------------------------", flush=True)

# تایمر برای نشان دادن حجم فایل‌های دانلود شده هر 30 ثانیه
_stop_monitor = threading.Event()

def _monitor_progress():
    import os as _os
    interval = 30
    while not _stop_monitor.wait(interval):
        try:
            total = 0
            for root, dirs, files in _os.walk(cache_dir):
                for f in files:
                    try:
                        total += _os.path.getsize(_os.path.join(root, f))
                    except OSError:
                        pass
            mb = total / (1024 * 1024)
            elapsed = time.strftime('%H:%M:%S')
            print(f"[DOWNLOAD] Progress: {mb:.0f} MB downloaded so far... ({elapsed})", flush=True)
        except Exception:
            pass

monitor_thread = threading.Thread(target=_monitor_progress, daemon=True)
monitor_thread.start()

t0 = time.time()
try:
    # snapshot_download تمام فایل‌ها را یکجا دانلود می‌کند
    snapshot_download(
        repo_id=model_name,
        cache_dir=cache_dir,
        token=hf_token,
    )
    elapsed = time.time() - t0
    _stop_monitor.set()

    # حجم نهایی
    total = 0
    for root, dirs, files in os.walk(cache_dir):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    mb = total / (1024 * 1024)

    print(f"[DOWNLOAD] -----------------------------------------------", flush=True)
    print(f"[DOWNLOAD] DONE in {elapsed/60:.1f} min | Total size: {mb:.0f} MB", flush=True)
    print(f"[DOWNLOAD] Finished: {time.strftime('%H:%M:%S')}", flush=True)

except Exception as e:
    _stop_monitor.set()
    print(f"[DOWNLOAD] ERROR: {e}", file=sys.stderr, flush=True)
    sys.exit(1)
