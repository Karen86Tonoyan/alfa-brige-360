#!/usr/bin/env python3
"""
Test ALFA Kernel v1.2 + Security Watchdog

Testuje:
1. Start kernela
2. Rejestracja modułów
3. Dispatch komend
4. Heartbeat
5. Predator Mode (blokowanie modułów)
"""

import sys
sys.path.insert(0, r"c:\Users\ktono\alfa_core")

from alfa_core.kernel import AlfaKernel
from alfa_core.kernel_contract import ExampleEchoModule, ExampleEchoConfig, BaseModule, CommandResult
from modules.security_watchdog import SecurityWatchdog, SecurityWatchdogConfig


# === BROKEN MODULE (do testów Predator Mode) ===

class BrokenModule(BaseModule):
    """Moduł który zawsze się wywala - do testów watchdog'a."""
    id = "test.broken"
    version = "1.0.0"

    def execute(self, command: str, **kwargs):
        raise RuntimeError("Simulated crash!")


def main():
    print("=" * 60)
    print("ALFA KERNEL v1.2 + SECURITY WATCHDOG TEST")
    print("=" * 60)
    
    # 1. Tworzymy kernel z konfiguracją
    config_map = {
        "example.echo": ExampleEchoConfig(prefix="[ALFA]"),
        "security.watchdog": SecurityWatchdogConfig(
            predator_mode=True,
            restart_limit=2,
        ),
    }
    
    kernel = AlfaKernel(config_map=config_map)
    print("\n[OK] Kernel utworzony")
    
    # 2. Rejestrujemy moduły
    kernel.register_module(ExampleEchoModule)
    kernel.register_module(SecurityWatchdog)
    kernel.register_module(BrokenModule)
    print("[OK] Moduły zarejestrowane")
    
    # 3. Start kernela
    kernel.start()
    print("[OK] Kernel wystartowany")
    
    # 4. Info o kernelu
    print("\n--- KERNEL INFO ---")
    print(kernel.info())
    
    # 5. Test dispatch - echo
    print("\n--- TEST ECHO MODULE ---")
    result = kernel.dispatch("example.echo", "echo", msg="Król wrócił!")
    print(f"Echo result: {result}")
    
    result = kernel.dispatch("example.echo", "ping")
    print(f"Ping result: {result}")
    
    # 6. Test watchdog status
    print("\n--- WATCHDOG STATUS ---")
    result = kernel.dispatch("security.watchdog", "status")
    print(f"Status: {result}")
    
    # 7. Test heartbeat
    print("\n--- HEARTBEAT ---")
    kernel.heartbeat()
    print("[OK] Heartbeat wysłany")
    
    # 8. Watchdog policy
    print("\n--- WATCHDOG POLICY ---")
    result = kernel.dispatch("security.watchdog", "policy")
    print(f"Policy: {result}")
    
    # 9. Test PREDATOR MODE - próba wywołania broken module
    print("\n--- PREDATOR MODE TEST ---")
    print("Wywołuję broken module 5 razy...")
    
    for i in range(5):
        result = kernel.dispatch("test.broken", "anything")
        print(f"  Call {i+1}: ok={result.ok}, error={result.error[:50] if result.error else 'none'}...")
    
    # 10. Sprawdź policy po crashach
    print("\n--- POLICY AFTER CRASHES ---")
    result = kernel.dispatch("security.watchdog", "policy")
    print(f"Policy: {result}")
    
    # 11. Sprawdź anomalie
    print("\n--- ANOMALIES ---")
    result = kernel.dispatch("security.watchdog", "anomalies", limit=5)
    if result.ok:
        print(f"Total anomalies: {result.data.get('total', 0)}")
        for anomaly in result.data.get('anomalies', [])[-3:]:
            print(f"  - {anomaly.get('module')}: {anomaly.get('type')}")
    
    # 12. Health check
    print("\n--- KERNEL HEALTH ---")
    print(kernel.health())
    
    # 13. Unblock module
    print("\n--- UNBLOCK TEST ---")
    result = kernel.dispatch("security.watchdog", "unblock", target_module_id="test.broken")
    print(f"Unblock result: {result}")
    
    # 14. Stop kernel
    kernel.stop()
    print("\n[OK] Kernel zatrzymany")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
