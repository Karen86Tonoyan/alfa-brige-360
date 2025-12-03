# ALFA_BRAIN v2.0 — PRIVATE AI CLOUD RUNTIME

> **Single Source of Truth** — Jedno repozytorium, jedna architektura, jeden system.

## 🏛️ Architektura

```
alfa_brain/
├── brain.py                # Mózg (CLI/REPL, routing komend)
├── core/                   # ALFA_CORE v2.0 (SILNIK)
│   ├── __init__.py
│   ├── engine.py           # AlfaEngine - boot, lifecycle, plugins
│   ├── plugin_engine.py    # Dynamiczne ładowanie pluginów
│   ├── event_bus.py        # Magistrala zdarzeń (pub/sub)
│   ├── cerber.py           # Security Guardian (fingerprint, integrity)
│   └── secure_exec.py      # Sandbox execution
├── plugins/                # Jednostki wykonawcze
│   ├── __init__.py
│   ├── mail/               # IMAP sync + PQXHybrid
│   ├── voice/              # STT/TTS daemon
│   └── bridge/             # Multi-AI router
├── config/
│   ├── system.json         # Konfiguracja systemowa
│   ├── plugins.json        # Lista pluginów
│   └── signatures.json     # Cerber fingerprints
└── README.md
```

## 🔱 Hierarchia

| Komponent | Rola |
|-----------|------|
| **BRAIN** | Kapitan — interfejs użytkownika, CLI/REPL |
| **CORE/ENGINE** | Silnik — boot, lifecycle, heartbeat |
| **CERBER** | Policja — integralność, fingerprinting |
| **EVENT_BUS** | Magistrala — komunikacja między modułami |
| **PLUGINS** | Oddziały specjalne — mail, voice, bridge |

## 🚀 Uruchomienie

```bash
# REPL interaktywny
python brain.py

# Status systemu
python brain.py --status

# Health check
python brain.py --health

# Jedna komenda
python brain.py --cmd "chat Hello"
```

## 🔥 ALFA CLOUD

Ten system to **Private AI Cloud Runtime**:
- 100% lokalny
- 100% prywatny
- 100% modularny
- Zero zależności od zewnętrznych chmur

## 📦 Zależności

```bash
pip install -r requirements.txt
```

## 🔐 Cerber

Cerber weryfikuje integralność przy każdym starcie:
- SHA256 fingerprinting
- Snapshot & rollback
- Incident logging
- IP whitelist

## 🧩 Plugins

Każdy plugin ma:
- `manifest.yaml` z metadanymi
- `__init__.py` z klasą `Plugin`
- Integrację z EventBus

---

**ALFA System v2.0** — *The King's Private Cloud*
