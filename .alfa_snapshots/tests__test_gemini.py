#!/usr/bin/env python3
"""
ALFA GEMINI TEST v2.0
Prosty test połączenia z Gemini.
"""

import sys
from pathlib import Path

# Dodaj root do ścieżki
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from providers.gemini_provider import GeminiProvider


def main():
    print("=" * 50)
    print("🧪 ALFA GEMINI TEST v2.0")
    print("=" * 50)
    
    try:
        provider = GeminiProvider("config/gemini.yaml")
        print(f"[OK] Provider załadowany")
        print(f"[MODEL] {provider.model}")
        
        # Maskuj klucz
        key = provider.key
        masked = key[:8] + "****" + key[-4:] if len(key) > 12 else "****"
        print(f"[KEY] {masked}")
        
    except Exception as e:
        print(f"[ERROR] Nie można załadować providera: {e}")
        return False
    
    print("\n[TEST] Wysyłam zapytanie...")
    response = provider.generate("Powiedz krótko: ALFA działa.")
    
    print(f"\n[ODPOWIEDŹ]\n{response}")
    
    if "[ERROR]" in response or "[GEMINI ERROR]" in response:
        print("\n❌ TEST NIEUDANY")
        return False
    else:
        print("\n✅ TEST UDANY - Gemini działa!")
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
