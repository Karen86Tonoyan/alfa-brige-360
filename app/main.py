"""
ALFA MAIN v2.0
Punkt wejścia do aplikacji.
"""

import sys
from pathlib import Path

# Dodaj root do ścieżki
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core_manager import CoreManager


def main():
    """Główna pętla ALFA."""
    cm = CoreManager()
    cm.start()
    
    print("\nWpisz prompt (Ctrl+C aby wyjść):\n")
    
    while True:
        try:
            prompt = input("👑 Król: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n[ALFA] Zamykam system. Do zobaczenia, Królu.")
            break
        
        if not prompt:
            continue
        
        if prompt.lower() in ("exit", "quit", "q"):
            print("[ALFA] Zamykam.")
            break
        
        if prompt.lower() == "status":
            print(cm.status())
            continue
        
        response = cm.dispatch(prompt)
        print(f"\n🤖 ALFA:\n{response}\n")
        print("-" * 50)


if __name__ == "__main__":
    main()
