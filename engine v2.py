from fastapi import FastAPI
import time
import socket
from pathlib import Path

app = FastAPI()

START_TIME = time.time()

def read_version_safe() -> str:
    try:
        vf = Path("VERSION")
        if vf.exists():
            return vf.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "unknown"

@app.get("/")
def root():
    return {"status": "ALFA_CORE_OK"}

@app.get("/health")
def health():
    return {"status": "ok", "service": "ALFA_CORE"}

@app.get("/status")
def status():
    uptime = time.time() - START_TIME
    return {
        "service": "ALFA_CORE",
        "uptime_seconds": int(uptime),
        "host": socket.gethostname(),
        "version": read_version_safe(),
    }