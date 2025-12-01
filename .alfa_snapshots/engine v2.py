from fastapi import FastAPI
import sqlite3
import time

app = FastAPI()

@app.get("/")
def root():
    return {
        "status": "OK",
        "message": "ALFA backend działa poprawnie.",
        "timestamp": time.time()
    }

@app.get("/health")
def health():
    return {"alive": True}

@app.get("/guard/status")
def guard_status():
    try:
        conn = sqlite3.connect("alfa_guard.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM guard_events")
        count = cursor.fetchone()[0]
        conn.close()
        return {"db_status": "OK", "events_logged": count}
    except:
        return {"db_status": "NOT_READY"}