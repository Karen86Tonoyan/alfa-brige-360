"""
ALFA SECRET LOADER v2.0
Ładuje klucze z plików .key.enc lub zmiennych środowiskowych.
"""

import os
import base64
from pathlib import Path


def load_key(path: str) -> str:
    """
    Ładuje klucz z pliku.
    Obsługuje zarówno base64 jak i plain text.
    """
    file_path = Path(path)
    if not file_path.exists():
        # Fallback: sprawdź env
        env_name = file_path.stem.upper().replace(".", "_") + "_KEY"
        env_val = os.environ.get(env_name)
        if env_val:
            return env_val.strip()
        raise FileNotFoundError(f"Brak pliku klucza: {path}")
    
    raw = file_path.read_bytes()
    
    # Próbuj base64
    try:
        decoded = base64.b64decode(raw).decode("utf-8").strip()
        if decoded.startswith("AIza"):  # Gemini key format
            return decoded
        return decoded
    except Exception:
        pass
    
    # Plain text
    return raw.decode("utf-8").strip()


def load_gemini_key() -> str:
    """Ładuje klucz Gemini z różnych lokalizacji."""
    # 1. Zmienna środowiskowa
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        return env_key.strip()
    
    # 2. Pliki w różnych lokalizacjach
    base = Path(__file__).parent.parent
    candidates = [
        base / "config" / "gemini.key.enc",
        base / "config" / "gemini.key",
        base / "src" / "modules" / "config" / "secrets" / "gemini.key.py",
    ]
    
    for path in candidates:
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            # Wyciągnij klucz (może być w pliku .py jako string)
            import re
            match = re.search(r'AIza[A-Za-z0-9_-]+', content)
            if match:
                return match.group(0)
    
    raise RuntimeError("Brak klucza GEMINI_API_KEY")
