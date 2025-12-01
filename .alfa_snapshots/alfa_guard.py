import os
import time
import hashlib
import shutil

WATCH_DIR = os.getcwd()
SNAPSHOT_DIR = os.path.join(WATCH_DIR, ".alfa_snapshots")
LOG_FILE = os.path.join(WATCH_DIR, "alfa_guard.log")

EXTENSIONS = (".py", ".html", ".js", ".css")
MAX_SIZE = 500_000
MAX_LINE = 400

FORBIDDEN = [
    r"cleaned\s*=\s*\[",
    r"requested\s*=",
    r"nonlocal",
    r"def __init__",
    r"<<AudioTranscription",
    r"copilot",
    r"gemini",
]

def log(msg: str):
    stamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{stamp} {msg}\n")
    print(msg)

def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def snapshot(path):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    snap = os.path.join(SNAPSHOT_DIR, os.path.basename(path))
    shutil.copy2(path, snap)
    return snap

def rollback(path):
    snap = os.path.join(SNAPSHOT_DIR, os.path.basename(path))
    if os.path.exists(snap):
        shutil.copy2(snap, path)
        log(f"[ROLLBACK] Przywrócono plik: {path}")

def clean_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except:
        return

    original = lines
    cleaned = []
    removed = 0

    import re

    for line in lines:
        if len(line) > MAX_LINE:
            removed += 1
            continue

        skip = False
        for pattern in FORBIDDEN:
            if re.search(pattern, line, re.IGNORECASE):
                removed += 1
                skip = True
                break

        if skip:
            continue

        cleaned.append(line)

    if removed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(cleaned)
        log(f"[CLEAN] Usunięto {removed} linii z {os.path.basename(path)}")

def guard():
    log("[ALFA_GUARD] ACTIVE — monitoring zmian…")
    hashes = {}

    while True:
        for root, dirs, files in os.walk(WATCH_DIR):
            for name in files:
                if not name.endswith(EXTENSIONS):
                    continue

                path = os.path.join(root, name)
                try:
                    h = file_hash(path)
                except:
                    continue

                if path not in hashes:
                    snapshot(path)
                    hashes[path] = h
                    continue

                if h != hashes[path]:
                    log(f"[DETECT] Wykryto zmianę: {path}")

                    clean_file(path)

                    # Sprawdzamy po czyszczeniu
                    new_h = file_hash(path)
                    if new_h != h:
                        hashes[path] = new_h
                        snapshot(path)
                    else:
                        rollback(path)

                    hashes[path] = file_hash(path)

        time.sleep(1)

if __name__ == "__main__":
    guard()