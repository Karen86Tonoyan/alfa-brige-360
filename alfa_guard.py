import os
import hashlib
import shutil
import sqlite3
import time
from datetime import datetime

# ============================
# KONFIG
# ============================

WATCH_EXT = (".py",)
SNAP_DIR = ".alfa_snapshots"
DB_FILE = "alfa_guard.db"

BLOCK_WRITE = False  # flaga – na razie OFF

# strażnik nie rusza samego siebie
IGNORE_FILES = ["alfa_guard.py"]

FORBIDDEN = [
    "<<<<<<<",
    ">>>>>>>",
    "copilot",
    "gemini",
    "tmp",
    "hallucination",
]

MAX_LINE = 300


# ============================
# LOGOWANIE DO SQLITE
# ============================

def db_init():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            level TEXT,
            msg TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_incident(level, msg):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute(
        "INSERT INTO incidents (ts, level, msg) VALUES (?, ?, ?)",
        (datetime.now().isoformat(), level, msg)
    )

    conn.commit()
    conn.close()
    print(f"[{level}] {msg}")


# ============================
# SNAPSHOT / ROLLBACK
# ============================

def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def snapshot(path):
    os.makedirs(SNAP_DIR, exist_ok=True)
    snap = os.path.join(SNAP_DIR, os.path.basename(path))

    # nie snapshotujemy samego siebie
    if os.path.abspath(path) == os.path.abspath(snap):
        return

    shutil.copy2(path, snap)
    return snap


def restore(path):
    snap = os.path.join(SNAP_DIR, os.path.basename(path))

    if os.path.exists(snap):
        shutil.copy2(snap, path)
        log_incident("ROLLBACK", f"Przywrócono snapshot dla {path}")
    else:
        log_incident("WARN", f"Brak snapshota dla {path}")


def needs_rollback(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if len(line) > MAX_LINE:
                    return True
                for s in FORBIDDEN:
                    if s.lower() in line.lower():
                        return True
    except:
        return False

    return False


def clean_file(path):
    cleaned = []
    removed = 0

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if len(line) > MAX_LINE:
                removed += 1
                continue

            skip = False
            for s in FORBIDDEN:
                if s.lower() in line.lower():
                    removed += 1
                    skip = True
                    break

            if skip:
                continue

            cleaned.append(line)

    if removed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(cleaned)

        log_incident("CLEAN", f"Oczyszczono {path} (usunięto {removed} linii)")


# ============================
# STRAŻNIK
# ============================

def guard():
    print("[ALFA_GUARD] ACTIVE — monitoring zmian…")

    db_init()
    tracked = {}

    while True:
        # sprawdzanie śledzonych plików
        for path in list(tracked.keys()):

            if not os.path.exists(path):
                continue

            # nigdy nie ruszamy strażnika
            if os.path.basename(path) in IGNORE_FILES:
                continue

            new_hash = file_hash(path)

            if new_hash != tracked[path]:
                clean_file(path)

                if needs_rollback(path):
                    restore(path)

                tracked[path] = file_hash(path)

        # skanuj folder
        for file in os.listdir("."):

            if file in IGNORE_FILES:
                continue

            if file.endswith(WATCH_EXT):

                path = os.path.abspath(file)

                if path not in tracked:
                    snapshot(path)
                    tracked[path] = file_hash(path)

        time.sleep(1)


# ============================
# START
# ============================

if __name__ == "__main__":
    guard()