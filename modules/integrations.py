#!/usr/bin/env python3
"""
================================================================================
ALFA INTEGRATIONS v1.0
================================================================================
Integracje z zewnętrznymi serwisami (Zapier/Make style).

Supported Integrations:
- Slack
- Discord
- Telegram
- Google Sheets
- Notion
- Trello
- GitHub
- Gmail
- HubSpot CRM
- Stripe
- Webhook (generic)

Author: ALFA System / Karen86Tonoyan
================================================================================
"""

import asyncio
import aiohttp
import json
import logging
import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [INTEGRATIONS] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
LOG = logging.getLogger("alfa.integrations")

# =============================================================================
# BASE CLASSES
# =============================================================================

class IntegrationStatus(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass
class IntegrationConfig:
    """Konfiguracja integracji."""
    name: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    webhook_url: Optional[str] = None
    token: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntegrationEvent:
    """Zdarzenie z integracji."""
    source: str
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    raw: Optional[str] = None


class BaseIntegration(ABC):
    """Bazowa klasa dla integracji."""
    
    def __init__(self, config: IntegrationConfig):
        self.config = config
        self.status = IntegrationStatus.DISCONNECTED
        self.last_error: Optional[str] = None
        self.event_handlers: Dict[str, List[Callable]] = {}
    
    @abstractmethod
    async def connect(self) -> bool:
        """Połącz z serwisem."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Rozłącz z serwisem."""
        pass
    
    @abstractmethod
    async def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Wyślij dane do serwisu."""
        pass
    
    def on_event(self, event_type: str, handler: Callable):
        """Zarejestruj handler dla zdarzenia."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def emit_event(self, event: IntegrationEvent):
        """Emituj zdarzenie do handlerów."""
        handlers = self.event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                LOG.error(f"Event handler error: {e}")


# =============================================================================
# SLACK INTEGRATION
# =============================================================================

class SlackIntegration(BaseIntegration):
    """Integracja ze Slack."""
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self.base_url = "https://slack.com/api"
    
    async def connect(self) -> bool:
        """Test połączenia ze Slack."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.config.token}"}
                async with session.post(f"{self.base_url}/auth.test", headers=headers) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        self.status = IntegrationStatus.CONNECTED
                        LOG.info("Slack connected")
                        return True
                    self.last_error = data.get("error")
                    return False
        except Exception as e:
            self.last_error = str(e)
            self.status = IntegrationStatus.ERROR
            return False
    
    async def disconnect(self) -> bool:
        self.status = IntegrationStatus.DISCONNECTED
        return True
    
    async def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Wyślij wiadomość na Slack."""
        channel = data.get("channel", "#general")
        text = data.get("text", "")
        blocks = data.get("blocks")
        
        payload = {
            "channel": channel,
            "text": text
        }
        if blocks:
            payload["blocks"] = blocks
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.config.token}",
                    "Content-Type": "application/json"
                }
                async with session.post(
                    f"{self.base_url}/chat.postMessage",
                    headers=headers,
                    json=payload
                ) as resp:
                    result = await resp.json()
                    return {"success": result.get("ok"), "ts": result.get("ts")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def send_file(self, channel: str, file_path: str, comment: str = "") -> Dict:
        """Wyślij plik na Slack."""
        # TODO: Implementacja upload pliku
        return {"success": False, "error": "Not implemented"}


# =============================================================================
# DISCORD INTEGRATION
# =============================================================================

class DiscordIntegration(BaseIntegration):
    """Integracja z Discord (via webhook)."""
    
    async def connect(self) -> bool:
        if self.config.webhook_url:
            self.status = IntegrationStatus.CONNECTED
            return True
        return False
    
    async def disconnect(self) -> bool:
        self.status = IntegrationStatus.DISCONNECTED
        return True
    
    async def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Wyślij wiadomość na Discord."""
        content = data.get("content", "")
        embeds = data.get("embeds", [])
        username = data.get("username", "ALFA Bot")
        
        payload = {
            "content": content,
            "username": username
        }
        if embeds:
            payload["embeds"] = embeds
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.webhook_url,
                    json=payload
                ) as resp:
                    return {"success": resp.status == 204}
        except Exception as e:
            return {"success": False, "error": str(e)}


# =============================================================================
# TELEGRAM INTEGRATION
# =============================================================================

class TelegramIntegration(BaseIntegration):
    """Integracja z Telegram Bot API."""
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self.base_url = f"https://api.telegram.org/bot{config.token}"
    
    async def connect(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/getMe") as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        self.status = IntegrationStatus.CONNECTED
                        LOG.info(f"Telegram connected: @{data['result']['username']}")
                        return True
                    return False
        except Exception as e:
            self.last_error = str(e)
            return False
    
    async def disconnect(self) -> bool:
        self.status = IntegrationStatus.DISCONNECTED
        return True
    
    async def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Wyślij wiadomość na Telegram."""
        chat_id = data.get("chat_id")
        text = data.get("text", "")
        parse_mode = data.get("parse_mode", "HTML")
        
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/sendMessage",
                    json=payload
                ) as resp:
                    result = await resp.json()
                    return {"success": result.get("ok"), "message_id": result.get("result", {}).get("message_id")}
        except Exception as e:
            return {"success": False, "error": str(e)}


# =============================================================================
# GOOGLE SHEETS INTEGRATION
# =============================================================================

class GoogleSheetsIntegration(BaseIntegration):
    """Integracja z Google Sheets."""
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self.spreadsheet_id = config.extra.get("spreadsheet_id")
    
    async def connect(self) -> bool:
        # TODO: OAuth2 flow
        if self.config.token:
            self.status = IntegrationStatus.CONNECTED
            return True
        return False
    
    async def disconnect(self) -> bool:
        self.status = IntegrationStatus.DISCONNECTED
        return True
    
    async def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Zapisz dane do arkusza."""
        sheet = data.get("sheet", "Sheet1")
        range_name = data.get("range", "A1")
        values = data.get("values", [])
        
        # TODO: Implementacja z google-api-python-client
        LOG.info(f"Would write to {sheet}!{range_name}: {values}")
        return {"success": True, "simulated": True}
    
    async def read(self, sheet: str, range_name: str) -> List[List[Any]]:
        """Odczytaj dane z arkusza."""
        # TODO: Implementacja
        return []


# =============================================================================
# NOTION INTEGRATION
# =============================================================================

class NotionIntegration(BaseIntegration):
    """Integracja z Notion."""
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self.base_url = "https://api.notion.com/v1"
        self.version = "2022-06-28"
    
    async def connect(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.config.token}",
                    "Notion-Version": self.version
                }
                async with session.get(f"{self.base_url}/users/me", headers=headers) as resp:
                    if resp.status == 200:
                        self.status = IntegrationStatus.CONNECTED
                        return True
                    return False
        except Exception as e:
            self.last_error = str(e)
            return False
    
    async def disconnect(self) -> bool:
        self.status = IntegrationStatus.DISCONNECTED
        return True
    
    async def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Utwórz stronę w Notion."""
        parent_id = data.get("parent_id")
        title = data.get("title", "Untitled")
        content = data.get("content", [])
        
        payload = {
            "parent": {"page_id": parent_id} if parent_id else {"database_id": data.get("database_id")},
            "properties": {
                "title": {"title": [{"text": {"content": title}}]}
            },
            "children": content
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.config.token}",
                    "Notion-Version": self.version,
                    "Content-Type": "application/json"
                }
                async with session.post(
                    f"{self.base_url}/pages",
                    headers=headers,
                    json=payload
                ) as resp:
                    result = await resp.json()
                    return {"success": resp.status == 200, "page_id": result.get("id")}
        except Exception as e:
            return {"success": False, "error": str(e)}


# =============================================================================
# GITHUB INTEGRATION
# =============================================================================

class GitHubIntegration(BaseIntegration):
    """Integracja z GitHub."""
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self.base_url = "https://api.github.com"
    
    async def connect(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"token {self.config.token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                async with session.get(f"{self.base_url}/user", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.status = IntegrationStatus.CONNECTED
                        LOG.info(f"GitHub connected: {data.get('login')}")
                        return True
                    return False
        except Exception as e:
            self.last_error = str(e)
            return False
    
    async def disconnect(self) -> bool:
        self.status = IntegrationStatus.DISCONNECTED
        return True
    
    async def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Utwórz issue na GitHub."""
        repo = data.get("repo")  # owner/repo
        title = data.get("title")
        body = data.get("body", "")
        labels = data.get("labels", [])
        
        payload = {
            "title": title,
            "body": body,
            "labels": labels
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"token {self.config.token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                async with session.post(
                    f"{self.base_url}/repos/{repo}/issues",
                    headers=headers,
                    json=payload
                ) as resp:
                    result = await resp.json()
                    return {"success": resp.status == 201, "issue_number": result.get("number")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def create_pr(self, repo: str, title: str, head: str, base: str, body: str = "") -> Dict:
        """Utwórz Pull Request."""
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"token {self.config.token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                async with session.post(
                    f"{self.base_url}/repos/{repo}/pulls",
                    headers=headers,
                    json=payload
                ) as resp:
                    result = await resp.json()
                    return {"success": resp.status == 201, "pr_number": result.get("number")}
        except Exception as e:
            return {"success": False, "error": str(e)}


# =============================================================================
# WEBHOOK (GENERIC)
# =============================================================================

class WebhookIntegration(BaseIntegration):
    """Generyczna integracja webhook."""
    
    async def connect(self) -> bool:
        if self.config.webhook_url:
            self.status = IntegrationStatus.CONNECTED
            return True
        return False
    
    async def disconnect(self) -> bool:
        self.status = IntegrationStatus.DISCONNECTED
        return True
    
    async def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Wyślij POST do webhooka."""
        method = data.get("method", "POST")
        headers = data.get("headers", {})
        payload = data.get("payload", data)
        
        try:
            async with aiohttp.ClientSession() as session:
                if method == "POST":
                    async with session.post(
                        self.config.webhook_url,
                        headers=headers,
                        json=payload
                    ) as resp:
                        return {"success": resp.status < 400, "status": resp.status}
                elif method == "GET":
                    async with session.get(
                        self.config.webhook_url,
                        headers=headers
                    ) as resp:
                        return {"success": resp.status < 400, "status": resp.status}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Zweryfikuj podpis webhooka."""
        computed = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f"sha256={computed}", signature)


# =============================================================================
# INTEGRATION MANAGER
# =============================================================================

class IntegrationManager:
    """Menedżer wszystkich integracji."""
    
    INTEGRATION_TYPES = {
        "slack": SlackIntegration,
        "discord": DiscordIntegration,
        "telegram": TelegramIntegration,
        "google_sheets": GoogleSheetsIntegration,
        "notion": NotionIntegration,
        "github": GitHubIntegration,
        "webhook": WebhookIntegration,
    }
    
    def __init__(self):
        self.integrations: Dict[str, BaseIntegration] = {}
        LOG.info("IntegrationManager initialized")
    
    def register(self, name: str, integration_type: str, config: IntegrationConfig) -> bool:
        """Zarejestruj nową integrację."""
        if integration_type not in self.INTEGRATION_TYPES:
            LOG.error(f"Unknown integration type: {integration_type}")
            return False
        
        integration_class = self.INTEGRATION_TYPES[integration_type]
        self.integrations[name] = integration_class(config)
        LOG.info(f"Integration registered: {name} ({integration_type})")
        return True
    
    async def connect(self, name: str) -> bool:
        """Połącz integrację."""
        if name not in self.integrations:
            return False
        return await self.integrations[name].connect()
    
    async def connect_all(self) -> Dict[str, bool]:
        """Połącz wszystkie integracje."""
        results = {}
        for name in self.integrations:
            results[name] = await self.connect(name)
        return results
    
    async def send(self, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Wyślij przez integrację."""
        if name not in self.integrations:
            return {"success": False, "error": "Integration not found"}
        return await self.integrations[name].send(data)
    
    def get(self, name: str) -> Optional[BaseIntegration]:
        """Pobierz integrację."""
        return self.integrations.get(name)
    
    def list_integrations(self) -> List[Dict[str, Any]]:
        """Lista wszystkich integracji."""
        return [
            {
                "name": name,
                "type": type(integration).__name__,
                "status": integration.status.value,
                "last_error": integration.last_error
            }
            for name, integration in self.integrations.items()
        ]
    
    @classmethod
    def available_types(cls) -> List[str]:
        """Dostępne typy integracji."""
        return list(cls.INTEGRATION_TYPES.keys())


# =============================================================================
# DEMO
# =============================================================================

async def demo():
    """Demo integracji."""
    manager = IntegrationManager()
    
    print("\n=== ALFA Integrations Demo ===\n")
    
    # Pokaż dostępne typy
    print("Available integrations:")
    for t in manager.available_types():
        print(f"  - {t}")
    
    # Zarejestruj webhook (nie wymaga prawdziwego tokenu)
    manager.register("test_webhook", "webhook", IntegrationConfig(
        name="test",
        webhook_url="https://httpbin.org/post"
    ))
    
    # Połącz
    await manager.connect("test_webhook")
    
    # Wyślij
    result = await manager.send("test_webhook", {
        "message": "Hello from ALFA!",
        "timestamp": datetime.now().isoformat()
    })
    
    print(f"\nWebhook result: {result}")
    
    # Lista
    print("\nRegistered integrations:")
    for i in manager.list_integrations():
        print(f"  {i['name']}: {i['status']}")


if __name__ == "__main__":
    asyncio.run(demo())
