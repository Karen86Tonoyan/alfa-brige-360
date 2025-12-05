"""
ALFA / DEEPSEEK API CLIENT v1.0
Twardy klient do DeepSeek Chat API.
Zero dekoracji. Sama stal.
"""

import os
import requests
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "deepseek.yaml"

def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Brak configu: {CONFIG_PATH}")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)

CFG = load_config()

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


def deepseek_query(prompt: str, system_prompt: str = None) -> str:
    """
    Wysyła prompt do DeepSeek i zwraca odpowiedź.
    Rzuca wyjątek przy błędzie.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": CFG.get("engine", "deepseek-chat"),
        "messages": messages,
        "temperature": CFG.get("temperature", 0.6),
        "max_tokens": CFG.get("max_tokens", 4096),
    }

    headers = {
        "Authorization": f"Bearer {CFG['api_key']}",
        "Content-Type": "application/json",
    }

    timeout = CFG.get("timeout", 60)

    r = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()

    data = r.json()
    return data["choices"][0]["message"]["content"].strip()


def deepseek_health() -> bool:
    """Sprawdza czy API działa (lekki prompt)."""
    try:
        resp = deepseek_query("ping", system_prompt="Odpowiedz jednym słowem: pong")
        return "pong" in resp.lower()
    except Exception:
        return False


if __name__ == "__main__":
    # Quick test
    print("[ALFA/DeepSeek] Test połączenia...")
    if deepseek_health():
        print("[OK] DeepSeek ONLINE")
    else:
        print("[BŁĄD] DeepSeek OFFLINE lub zły klucz API")
