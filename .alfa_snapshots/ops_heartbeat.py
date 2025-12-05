import time
import requests
from datetime import datetime

URL = "http://127.0.0.1:8000/health"
LOG = "ops_heartbeat.log"

if __name__ == "__main__":
    while True:
        try:
            r = requests.get(URL, timeout=3)
            ok = r.status_code == 200
        except Exception as e:
            ok = False

        line = f"{datetime.utcnow().isoformat()}Z | {'OK' if ok else 'FAIL'}\n"
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line)

        time.sleep(60)
