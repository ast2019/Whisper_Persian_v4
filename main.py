from fastapi import FastAPI, File, UploadFile
from transformers import pipeline
import tempfile
import os

app = FastAPI()

# بارگذاری مدل Whisper Persian v4
pipe = pipeline(
    "automatic-speech-recognition",
    model="nezamisafa/whisper-persian-v4",
    device="cpu"  # چون GPU ندارید
)

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    
    # تبدیل صدا به متن
    result = pipe(tmp_path)
    os.unlink(tmp_path)
    
    return {"text": result["text"]}

@app.get("/health")
async def health():
    return {"status": "ok", "model": "whisper-persian-v4"}
