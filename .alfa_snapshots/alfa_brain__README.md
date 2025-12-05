# ALFA_BRAIN v2.0 — PRIVATE AI CLOUD RUNTIME

> **Single Source of Truth** — Jedno repozytorium, jedna architektura, jeden system.

## 🌐 ALFA ECOSYSTEM (Jeden Projekt!)

```
ALFA_CORE/                          ← ROOT (jeden projekt)
│
├── alfa_master.py                  ← 👑 MASTER CONTROLLER
│
├── alfa_brain/                     ← 🧠 MÓZG (CLI/REPL)
│   ├── brain.py                    
│   └── core/                       
│
├── alfa_cloud/                     ← ☁️ CHMURA (API, AI, Dashboard)
│   ├── run_cloud.py                
│   ├── api/                        
│   └── ai/                         
│
├── alfa_keyvault/                  ← 🔐 KRYPTOGRAFIA (Rust, PQC)
│   ├── Cargo.toml                  
│   └── src/                        
│
├── alfa_photos_vault/              ← 📷 VAULT ZDJĘĆ (Rust + Android)
│   ├── Cargo.toml                  
│   └── android/                    
│
├── ALFA_Mail/                      ← 📧 POCZTA (Python + Android)
│   ├── core/                       
│   └── app/                        
│
├── core/                           ← ⚙️ WSPÓLNE MODUŁY
│   ├── cerber.py                   
│   ├── event_bus.py                
│   └── mcp_dispatcher.py           
│
├── modules/                        ← 📦 MODUŁY DODATKOWE
│   ├── mirror_*.py                 
│   └── watchdog/                   
│
└── plugins/                        ← 🔌 PLUGINY
    ├── voice/                      
    ├── bridge/                     
    └── mail/                       
```

## 👑 HIERARCHIA

```
                    ┌─────────────────┐
                    │  ALFA_MASTER    │  ← Król (Centralny kontroler)
                    │  alfa_master.py │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
        │   BRAIN   │  │   CLOUD   │  │   MAIL    │
        │  (Mózg)   │  │ (Chmura)  │  │ (Poczta)  │
        └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
              │              │              │
        ┌─────▼──────────────▼──────────────▼─────┐
        │              CORE (Silnik)              │
        │  cerber · event_bus · mcp_dispatcher    │
        └─────────────────┬───────────────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
        ┌─────▼─────┐           ┌─────▼─────┐
        │ KEYVAULT  │           │  PHOTOS   │
        │  (Rust)   │           │  VAULT    │
        └───────────┘           └───────────┘
```

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
