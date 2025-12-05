# 🔥 ALFA_CORE v2.0

<div align="center">

![ALFA System](https://img.shields.io/badge/ALFA-CORE-red?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyTDEgMjFoMjJMMTIgMnptMCAzLjk5TDE5LjUzIDE5SDQuNDdMMTIgNS45OXoiLz48L3N2Zz4=)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)
![Rust](https://img.shields.io/badge/Rust-1.75+-orange?style=for-the-badge&logo=rust)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge)

**Autonomiczny system AI z własnym ekosystemem bezpieczeństwa**

[Instalacja](#-instalacja) • [Architektura](#-architektura) • [Moduły](#-moduły) • [API](#-api) • [Bezpieczeństwo](#-bezpieczeństwo) • [Roadmapa](#-roadmapa)

</div>

---

## 🎯 O Projekcie

**ALFA_CORE** to zaawansowany, modułowy system backendowy łączący lokalne AI (Ollama), zewnętrzne API (DeepSeek), oraz własne moduły bezpieczeństwa w jedną, spójną platformę.

### Kluczowe cechy:
- 🧠 **Multi-AI** — integracja z Ollama (lokalne) + DeepSeek API (chmura)
- 🔒 **Cerber Security** — wielowarstwowe zabezpieczenia i monitoring
- 🔌 **Modułowość** — dynamiczne ładowanie rozszerzeń/pluginów
- 📡 **MCP Support** — Model Context Protocol dla integracji zewnętrznych
- 🛡️ **ALFA Guard** — automatyczny watchdog z rollbackiem plików
- 🔑 **ALFA KeyVault** — kryptograficzny sejf (Rust, PQX-ready)
- 📧 **ALFA Mail** — szyfrowana komunikacja email (IMAP/SMTP)

---

## ⚡ Instalacja

### Wymagania
- Python 3.11+
- Rust 1.75+ (dla ALFA KeyVault)
- Ollama (opcjonalne, dla lokalnych modeli AI)

### Szybki start

```bash
# 1. Klonuj repozytorium
git clone https://github.com/Karen86Tonoyan/ALFA__CORE.git
cd ALFA__CORE

# 2. Utwórz środowisko wirtualne
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# 3. Zainstaluj zależności
pip install -r requirements.txt

# 4. Skonfiguruj (opcjonalne)
copy config\deepseek.yaml.example config\deepseek.yaml

# 5. Uruchom serwer
python app.py
```

### Docker

```bash
docker-compose up -d
```

---

## 🏗 Architektura

```
ALFA_CORE/
├── app.py                 # 🚀 FastAPI REST API
├── core_manager.py        # 🎛️ Centralny dispatcher
├── alfa_cli.py            # 💻 CLI interface
├── alfa_guard.py          # 🛡️ Watchdog + rollback
├── config.py              # ⚙️ Konfiguracja globalna
│
├── core/                  # 🧠 Rdzeń systemu
│   ├── sync_engine.py     # Synchronizacja
│   ├── secure_executor.py # Bezpieczne wykonanie kodu
│   ├── plugin_engine.py   # Silnik pluginów
│   ├── extensions_loader.py
│   ├── event_bus.py       # Magistrala zdarzeń
│   ├── cerber.py          # 🔒 Security layer
│   ├── mcp_dispatcher.py  # MCP routing
│   ├── api_deepseek.py    # DeepSeek integration
│   └── voice_deepseek.py  # Voice AI
│
├── modules/               # 📦 Moduły funkcjonalne
│   ├── automation/        # Automatyzacja zadań
│   ├── creative/          # Generowanie treści
│   ├── dev/               # Narzędzia developerskie
│   └── knowledge/         # Baza wiedzy
│
├── plugins/               # 🔌 Pluginy zewnętrzne
│   ├── bridge/            # ALFA Bridge
│   ├── mail/              # Email integration
│   └── voice/             # Voice processing
│
├── extensions/            # 🧩 Rozszerzenia
│   └── coding/            # Code execution
│
├── alfa_keyvault/         # 🔐 Kryptograficzny sejf (Rust)
│   ├── src/
│   │   ├── crypto/        # Argon2, AES-GCM, HKDF
│   │   ├── vault.rs       # Główny vault
│   │   ├── brain.rs       # Self-learning AI
│   │   ├── policy.rs      # Auto-policies
│   │   └── snapshot.rs    # PQX snapshots
│   └── Cargo.toml
│
├── ALFA_Mail/             # 📧 Email system
└── config/                # ⚙️ Pliki konfiguracyjne
```

---

## 🧩 Moduły

### Core Manager
Centralny dispatcher zarządzający wszystkimi modułami:

```python
from core_manager import CoreManager, get_manager

manager = get_manager()
await manager.load_module("chat")
result = await manager.dispatch("chat", {"prompt": "Hello"})
```

### Cerber (Security Layer)
Wielowarstwowe zabezpieczenia:

```python
from core import get_cerber

cerber = get_cerber()
cerber.validate_request(request)
cerber.log_access(user_id, action)
```

### Event Bus
Asynchroniczna magistrala zdarzeń:

```python
from core import get_bus, publish, Priority

# Publikuj zdarzenie
await publish("user.login", {"user_id": 123}, priority=Priority.HIGH)

# Subskrybuj
@bus.subscribe("user.*")
async def on_user_event(event):
    print(f"User event: {event}")
```

---

## 📡 API

### Endpointy REST

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/health` | GET | Health check |
| `/status` | GET | Status systemu |
| `/api/v1/chat` | POST | Chat z AI |
| `/api/v1/modules` | GET | Lista modułów |
| `/api/v1/modules/{name}` | POST | Zarządzanie modułem |
| `/api/v1/cerber/status` | GET | Status bezpieczeństwa |
| `/api/v1/events` | WS | EventBus WebSocket |

### Przykład użycia

```bash
# Health check
curl http://localhost:8000/health

# Chat z AI
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Wyjaśnij kryptografię", "profile": "balanced"}'

# Status modułów
curl http://localhost:8000/api/v1/modules
```

### Profile AI

| Profil | Opis | Użycie |
|--------|------|--------|
| `fast` | Szybkie odpowiedzi | Proste pytania |
| `balanced` | Zbalansowany | Ogólne użycie |
| `creative` | Kreatywny | Generowanie treści |
| `security` | Bezpieczny | Analiza zagrożeń |

---

## 🔒 Bezpieczeństwo

### ALFA Guard
Automatyczny watchdog monitorujący zmiany w plikach:

```bash
python alfa_guard.py
```

Funkcje:
- 📸 Snapshoty plików przed zmianami
- 🔄 Automatyczny rollback przy wykryciu problemów
- 🚫 Blokowanie podejrzanych wzorców (conflict markers, itp.)
- 📊 Logowanie incydentów do SQLite

### ALFA KeyVault (Rust)
Kryptograficzny sejf z:
- **Argon2id** — KDF (64 MiB memory)
- **AES-256-GCM / XChaCha20-Poly1305** — AEAD
- **HKDF-SHA256** — Derywacja subkluczy
- **PQX Snapshots** — Post-quantum ready
- **Self-learning Brain** — Automatyczna detekcja zagrożeń

```bash
cd alfa_keyvault
cargo build --release
./target/release/alfa-vault create --name "main"
```

---

## 💻 CLI

```bash
# Sprawdź health
python alfa_cli.py health

# Status systemu
python alfa_cli.py status

# Uruchom w trybie dev
python app.py --dev

# Uruchom w trybie produkcyjnym
python app.py --prod --port 8080
```

---

## 🐳 Docker

```yaml
# docker-compose.yml
version: '3.8'
services:
  alfa-core:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
```

```bash
docker-compose up -d
docker-compose logs -f alfa-core
```

---

## 🛠 Rozwój

### Struktura pluginu

```python
# plugins/my_plugin/__init__.py

class MyPlugin:
    name = "my_plugin"
    version = "1.0.0"
    
    async def initialize(self, manager):
        self.manager = manager
        
    async def handle(self, command: str, params: dict):
        if command == "hello":
            return {"message": "Hello from plugin!"}
        return None
```

### Dodawanie modułu

```python
# modules/my_module/__init__.py

from core import register_module

@register_module("my_module")
class MyModule:
    async def execute(self, params):
        return {"result": "success"}
```

---

## 🗺 Roadmapa

### v2.0 (Current) ✅
- [x] FastAPI REST backend
- [x] CoreManager z hot-reload
- [x] Cerber security layer
- [x] Event Bus
- [x] ALFA Guard watchdog
- [x] Ollama + DeepSeek integration

### v2.5 (In Progress) 🔄
- [x] ALFA KeyVault (Rust)
- [ ] PQX Hybrid encryption
- [ ] ALFA Mobile bridge
- [ ] Voice commands

### v3.0 (Planned) 📋
- [ ] Multi-node clustering
- [ ] Federated AI
- [ ] Hardware security module (HSM)
- [ ] ALFA Cloud sync

---

## 🤝 Integracje

### Claude Code (Anthropic)
ALFA wspiera Claude Code jako zewnętrznego agenta AI:

```bash
# Instalacja Claude Code
npm install -g @anthropic-ai/claude-code

# Windows PowerShell
irm https://claude.ai/install.ps1 | iex

# Użycie z ALFA
claude-code --context ./alfa_core
```

### Ollama (Local AI)
```bash
# Instalacja Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pobierz model
ollama pull deepseek-r1:7b

# Sprawdź połączenie
curl http://localhost:11434/api/tags
```

### DeepSeek API
```bash
# Ustaw klucz API
export DEEPSEEK_API_KEY="your-api-key"

# Lub w config/deepseek.yaml
api_key: "your-api-key"
```

---

## 📄 Licencja

MIT License - zobacz [LICENSE](LICENSE)

---

## 👤 Autor

**Karen86Tonoyan** — [GitHub](https://github.com/Karen86Tonoyan)

---

<div align="center">

**🔥 ALFA — Twoja cyfrowa twierdza 🔥**

</div>
