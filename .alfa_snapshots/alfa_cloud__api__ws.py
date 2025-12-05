"""
🔌 ALFA CLOUD WEBSOCKET
Real-time komunikacja dla ALFA CLOUD OFFLINE
"""

from __future__ import annotations
import json
import asyncio
from datetime import datetime
from typing import Dict, Set, Any, Optional
from dataclasses import dataclass, asdict

from fastapi import WebSocket, WebSocketDisconnect

from alfa_cloud.core.cloud_engine import CloudEngine

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONNECTION MANAGER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class WSClient:
    """Klient WebSocket"""
    id: str
    websocket: WebSocket
    connected_at: datetime
    subscriptions: Set[str]


class ConnectionManager:
    """Menedżer połączeń WebSocket"""
    
    def __init__(self):
        self.active_connections: Dict[str, WSClient] = {}
        self._client_counter = 0
    
    async def connect(self, websocket: WebSocket) -> str:
        """Akceptuje nowe połączenie"""
        await websocket.accept()
        
        self._client_counter += 1
        client_id = f"client_{self._client_counter}"
        
        self.active_connections[client_id] = WSClient(
            id=client_id,
            websocket=websocket,
            connected_at=datetime.now(),
            subscriptions=set()
        )
        
        return client_id
    
    def disconnect(self, client_id: str):
        """Usuwa połączenie"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
    
    async def send_to(self, client_id: str, message: dict):
        """Wysyła do konkretnego klienta"""
        if client_id in self.active_connections:
            ws = self.active_connections[client_id].websocket
            await ws.send_json(message)
    
    async def broadcast(self, message: dict, channel: Optional[str] = None):
        """Broadcast do wszystkich (lub tylko subskrybentów kanału)"""
        for client in self.active_connections.values():
            if channel is None or channel in client.subscriptions:
                try:
                    await client.websocket.send_json(message)
                except:
                    pass  # Klient mógł się rozłączyć
    
    def subscribe(self, client_id: str, channel: str):
        """Subskrybuje klienta do kanału"""
        if client_id in self.active_connections:
            self.active_connections[client_id].subscriptions.add(channel)
    
    def unsubscribe(self, client_id: str, channel: str):
        """Wypisuje klienta z kanału"""
        if client_id in self.active_connections:
            self.active_connections[client_id].subscriptions.discard(channel)


# Globalny manager
manager = ConnectionManager()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MESSAGE TYPES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MessageType:
    # System
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PONG = "pong"
    
    # Commands
    AI_REQUEST = "ai_request"
    AI_RESPONSE = "ai_response"
    AI_STREAM = "ai_stream"
    
    # Events
    FILE_UPLOADED = "file_uploaded"
    FILE_DELETED = "file_deleted"
    SYNC_STARTED = "sync_started"
    SYNC_COMPLETED = "sync_completed"
    BACKUP_COMPLETED = "backup_completed"
    
    # Subscriptions
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def ws_handler(websocket: WebSocket, cloud: CloudEngine):
    """
    Główny handler WebSocket
    
    Protokół wiadomości:
    {
        "type": "message_type",
        "data": { ... },
        "timestamp": "ISO datetime"
    }
    """
    client_id = await manager.connect(websocket)
    
    # Wyślij potwierdzenie połączenia
    await manager.send_to(client_id, {
        "type": MessageType.CONNECTED,
        "data": {
            "client_id": client_id,
            "cloud": cloud.config.get("cloud_name", "ALFA_CLOUD_OFFLINE"),
            "version": cloud.config.get("version", "1.0.0")
        },
        "timestamp": datetime.now().isoformat()
    })
    
    # Zarejestruj event handlers
    def on_file_uploaded(data):
        asyncio.create_task(manager.broadcast({
            "type": MessageType.FILE_UPLOADED,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }, channel="files"))
    
    def on_sync_completed(data):
        asyncio.create_task(manager.broadcast({
            "type": MessageType.SYNC_COMPLETED,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }, channel="sync"))
    
    cloud.on("file:uploaded", on_file_uploaded)
    cloud.on("sync:completed", on_sync_completed)
    
    try:
        while True:
            # Odbierz wiadomość
            raw_data = await websocket.receive_text()
            
            try:
                message = json.loads(raw_data)
            except json.JSONDecodeError:
                # Jeśli nie JSON - traktuj jako prosty tekst
                message = {"type": "text", "data": {"text": raw_data}}
            
            msg_type = message.get("type", "text")
            msg_data = message.get("data", {})
            
            # Obsłuż wiadomość
            await handle_message(client_id, msg_type, msg_data, cloud)
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast({
            "type": MessageType.DISCONNECTED,
            "data": {"client_id": client_id},
            "timestamp": datetime.now().isoformat()
        })


async def handle_message(client_id: str, msg_type: str, data: dict, cloud: CloudEngine):
    """Obsługuje różne typy wiadomości"""
    
    # Ping/Pong
    if msg_type == "ping":
        await manager.send_to(client_id, {
            "type": MessageType.PONG,
            "data": {},
            "timestamp": datetime.now().isoformat()
        })
    
    # Subskrypcje
    elif msg_type == MessageType.SUBSCRIBE:
        channel = data.get("channel")
        if channel:
            manager.subscribe(client_id, channel)
            await manager.send_to(client_id, {
                "type": "subscribed",
                "data": {"channel": channel},
                "timestamp": datetime.now().isoformat()
            })
    
    elif msg_type == MessageType.UNSUBSCRIBE:
        channel = data.get("channel")
        if channel:
            manager.unsubscribe(client_id, channel)
    
    # AI Request
    elif msg_type == MessageType.AI_REQUEST:
        prompt = data.get("prompt", "")
        task = data.get("task", "analysis")
        stream = data.get("stream", False)
        
        if stream:
            await handle_ai_stream(client_id, prompt, task, cloud)
        else:
            await handle_ai_request(client_id, prompt, task, cloud)
    
    # Echo (dla testów)
    elif msg_type == "text":
        text = data.get("text", "")
        
        # Prosty AI echo
        if text.startswith("/ai "):
            prompt = text[4:]
            await handle_ai_request(client_id, prompt, "analysis", cloud)
        else:
            await manager.send_to(client_id, {
                "type": "echo",
                "data": {"text": f"ECHO: {text}"},
                "timestamp": datetime.now().isoformat()
            })
    
    # Status
    elif msg_type == "status":
        status = cloud.status()
        await manager.send_to(client_id, {
            "type": "status",
            "data": status,
            "timestamp": datetime.now().isoformat()
        })
    
    # Nieznany typ
    else:
        await manager.send_to(client_id, {
            "type": MessageType.ERROR,
            "data": {"error": f"Unknown message type: {msg_type}"},
            "timestamp": datetime.now().isoformat()
        })


async def handle_ai_request(client_id: str, prompt: str, task: str, cloud: CloudEngine):
    """Obsługuje request do AI (non-streaming)"""
    ai_config = cloud.config.get("ai_local", {})
    
    if not ai_config.get("enabled"):
        await manager.send_to(client_id, {
            "type": MessageType.ERROR,
            "data": {"error": "AI jest wyłączone"},
            "timestamp": datetime.now().isoformat()
        })
        return
    
    try:
        import httpx
        
        model = ai_config.get("models", {}).get(task, ai_config.get("default_model", "llama3"))
        endpoint = ai_config.get("endpoint", "http://127.0.0.1:11434")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{endpoint}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False}
            )
            response.raise_for_status()
            data = response.json()
        
        await manager.send_to(client_id, {
            "type": MessageType.AI_RESPONSE,
            "data": {
                "response": data.get("response", ""),
                "model": model,
                "task": task
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        await manager.send_to(client_id, {
            "type": MessageType.ERROR,
            "data": {"error": f"AI error: {str(e)}"},
            "timestamp": datetime.now().isoformat()
        })


async def handle_ai_stream(client_id: str, prompt: str, task: str, cloud: CloudEngine):
    """Obsługuje streaming AI response"""
    ai_config = cloud.config.get("ai_local", {})
    
    if not ai_config.get("enabled"):
        await manager.send_to(client_id, {
            "type": MessageType.ERROR,
            "data": {"error": "AI jest wyłączone"},
            "timestamp": datetime.now().isoformat()
        })
        return
    
    try:
        import httpx
        
        model = ai_config.get("models", {}).get(task, ai_config.get("default_model", "llama3"))
        endpoint = ai_config.get("endpoint", "http://127.0.0.1:11434")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{endpoint}/api/generate",
                json={"model": model, "prompt": prompt, "stream": True}
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            text = chunk.get("response", "")
                            done = chunk.get("done", False)
                            
                            await manager.send_to(client_id, {
                                "type": MessageType.AI_STREAM,
                                "data": {
                                    "chunk": text,
                                    "done": done,
                                    "model": model
                                },
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            if done:
                                break
                        except json.JSONDecodeError:
                            pass
        
    except Exception as e:
        await manager.send_to(client_id, {
            "type": MessageType.ERROR,
            "data": {"error": f"AI stream error: {str(e)}"},
            "timestamp": datetime.now().isoformat()
        })
