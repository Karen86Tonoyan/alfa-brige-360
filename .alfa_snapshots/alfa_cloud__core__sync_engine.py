alfa_cloud/
├── config.py          # Podstawowy config (Ollama)
├── core/
│   ├── api_deepseek.py    # DeepSeek API client
│   └── voice_deepseek.py  # Voice module
├── ALFA_Mail/
│   └── core/
│       ├── database.py    # SQLCipher DB
│       └── imap_engine.py # IMAP client
├── ALFA_Mail_Project/     # Cerber spec
├── alfa_guard.py          # Security
├── engine_v2.py           # Engine
├── api/
│   └── main.py            # FastAPI main application
└── ai/
    └── bridge.py          # DeepSeek AI bridge
"""
🔄 ALFA CLOUD SYNC ENGINE
Synchronizacja LAN offline (bez internetu)
"""

import os
import json
import socket
import asyncio
import hashlib
import struct
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any, Callable, Set
from enum import Enum, auto
import threading
import queue
import httpx
from magestik_mail.core import Database, DatabaseConfig, MagestikIMAPEngine

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENUMS & CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SyncState(Enum):
    """Stan synchronizacji"""
    IDLE = auto()
    DISCOVERING = auto()
    SYNCING = auto()
    RECEIVING = auto()
    SENDING = auto()
    ERROR = auto()


class MessageType(Enum):
    """Typy wiadomości sync"""
    DISCOVER = "discover"       # Broadcast discovery
    ANNOUNCE = "announce"       # Odpowiedź na discover
    FILE_LIST = "file_list"     # Lista plików
    FILE_REQUEST = "file_req"   # Żądanie pliku
    FILE_DATA = "file_data"     # Dane pliku
    FILE_ACK = "file_ack"       # Potwierdzenie
    SYNC_COMPLETE = "sync_done" # Koniec synchronizacji


# Porty
DISCOVERY_PORT = 8766
SYNC_PORT = 8767

# Magic bytes dla protokołu
MAGIC = b"ALFA"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA CLASSES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class Peer:
    """Peer w sieci LAN"""
    id: str
    name: str
    ip: str
    port: int = SYNC_PORT
    last_seen: datetime = field(default_factory=datetime.now)
    is_online: bool = True
    files_count: int = 0
    storage_used: int = 0
    version: str = "1.0.0"


@dataclass
class FileInfo:
    """Informacja o pliku do synchronizacji"""
    id: str
    path: str
    name: str
    size: int
    hash: str
    modified_at: str
    encrypted: bool = False


@dataclass
class SyncMessage:
    """Wiadomość synchronizacji"""
    type: MessageType
    sender_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SyncStats:
    """Statystyki synchronizacji"""
    files_synced: int = 0
    bytes_transferred: int = 0
    peers_synced: int = 0
    last_sync: Optional[datetime] = None
    errors: int = 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYNC ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SyncEngine:
    """
    🔄 Silnik synchronizacji LAN dla ALFA CLOUD OFFLINE
    
    Protokół:
    1. UDP Broadcast Discovery (port 8766)
    2. TCP File Transfer (port 8767)
    3. Conflict Resolution: newest_wins / manual
    """
    
    def __init__(self, 
                 node_id: str,
                 node_name: str,
                 storage_path: str,
                 config: Optional[Dict] = None):
        
        self.node_id = node_id
        self.node_name = node_name
        self.storage_path = Path(storage_path)
        self.config = config or {}
        
        self.state = SyncState.IDLE
        self.logger = logging.getLogger("ALFA_CLOUD.Sync")
        
        # Peers
        self.peers: Dict[str, Peer] = {}
        self.known_files: Dict[str, FileInfo] = {}
        
        # Stats
        self.stats = SyncStats()
        
        # Network
        self._discovery_socket: Optional[socket.socket] = None
        self._sync_server: Optional[asyncio.Server] = None
        
        # Events
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        # Queue dla wiadomości
        self._message_queue: queue.Queue = queue.Queue()
        
        # Running flag
        self._running = False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # LIFECYCLE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def start(self):
        """Uruchamia silnik synchronizacji"""
        self.logger.info("🔄 Uruchamiam Sync Engine...")
        self._running = True
        
        try:
            # Uruchom discovery listener
            await self._start_discovery_listener()
            
            # Uruchom TCP server
            await self._start_sync_server()
            
            self.logger.info("✅ Sync Engine uruchomiony")
            self._emit("sync:started", {})
            
        except Exception as e:
            self.logger.error(f"❌ Błąd uruchamiania Sync Engine: {e}")
            self.state = SyncState.ERROR
            raise
    
    async def stop(self):
        """Zatrzymuje silnik synchronizacji"""
        self.logger.info("🛑 Zatrzymuję Sync Engine...")
        self._running = False
        
        if self._discovery_socket:
            self._discovery_socket.close()
        
        if self._sync_server:
            self._sync_server.close()
            await self._sync_server.wait_closed()
        
        self.state = SyncState.IDLE
        self.logger.info("⏹️ Sync Engine zatrzymany")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # DISCOVERY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _start_discovery_listener(self):
        """Uruchamia UDP listener dla discovery"""
        self._discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._discovery_socket.setblocking(False)
        
        try:
            self._discovery_socket.bind(('', DISCOVERY_PORT))
            self.logger.info(f"📡 Discovery listener na porcie {DISCOVERY_PORT}")
            
            # Uruchom background task
            asyncio.create_task(self._discovery_loop())
            
        except OSError as e:
            self.logger.warning(f"⚠️ Nie można bindować discovery port: {e}")
    
    async def _discovery_loop(self):
        """Background loop dla discovery"""
        while self._running:
            try:
                # Użyj asyncio do czekania na dane
                loop = asyncio.get_event_loop()
                data, addr = await loop.run_in_executor(
                    None, 
                    lambda: self._discovery_socket.recvfrom(1024)
                )
                
                await self._handle_discovery_message(data, addr)
                
            except BlockingIOError:
                await asyncio.sleep(0.1)
            except Exception as e:
                if self._running:
                    self.logger.error(f"Discovery error: {e}")
                await asyncio.sleep(1)
    
    async def discover_peers(self) -> List[Peer]:
        """
        Wysyła broadcast discovery i czeka na odpowiedzi
        """
        self.state = SyncState.DISCOVERING
        self.logger.info("🔍 Szukam peerów w sieci LAN...")
        
        # Przygotuj wiadomość discovery
        message = self._create_message(MessageType.DISCOVER, {
            "name": self.node_name,
            "port": SYNC_PORT,
            "version": "1.0.0"
        })
        
        # Wyślij broadcast
        broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        try:
            broadcast_socket.sendto(
                self._encode_message(message),
                ('<broadcast>', DISCOVERY_PORT)
            )
            self.logger.info("📤 Wysłano discovery broadcast")
            
            # Czekaj na odpowiedzi
            await asyncio.sleep(2)
            
        finally:
            broadcast_socket.close()
        
        self.state = SyncState.IDLE
        return list(self.peers.values())
    
    async def _handle_discovery_message(self, data: bytes, addr: tuple):
        """Obsługuje wiadomość discovery"""
        try:
            message = self._decode_message(data)
            sender_ip = addr[0]
            
            if message.type == MessageType.DISCOVER:
                # Odpowiedz announce
                if message.sender_id != self.node_id:
                    await self._send_announce(sender_ip)
                    
            elif message.type == MessageType.ANNOUNCE:
                # Dodaj peera
                peer = Peer(
                    id=message.sender_id,
                    name=message.data.get("name", "Unknown"),
                    ip=sender_ip,
                    port=message.data.get("port", SYNC_PORT),
                    last_seen=datetime.now(),
                    files_count=message.data.get("files_count", 0)
                )
                
                self.peers[peer.id] = peer
                self.logger.info(f"🔗 Znaleziono peer: {peer.name} ({peer.ip})")
                self._emit("peer:discovered", {"peer": asdict(peer)})
                
        except Exception as e:
            self.logger.error(f"Błąd discovery message: {e}")
    
    async def _send_announce(self, target_ip: str):
        """Wysyła announce do konkretnego IP"""
        message = self._create_message(MessageType.ANNOUNCE, {
            "name": self.node_name,
            "port": SYNC_PORT,
            "version": "1.0.0",
            "files_count": len(self.known_files)
        })
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(
                self._encode_message(message),
                (target_ip, DISCOVERY_PORT)
            )
        finally:
            sock.close()
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SYNC SERVER (TCP)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _start_sync_server(self):
        """Uruchamia TCP server do transferu plików"""
        self._sync_server = await asyncio.start_server(
            self._handle_sync_connection,
            '0.0.0.0',
            SYNC_PORT
        )
        self.logger.info(f"📡 Sync server na porcie {SYNC_PORT}")
    
    async def _handle_sync_connection(self, 
                                       reader: asyncio.StreamReader,
                                       writer: asyncio.StreamWriter):
        """Obsługuje połączenie sync"""
        addr = writer.get_extra_info('peername')
        self.logger.info(f"📥 Połączenie sync z {addr}")
        
        try:
            while True:
                # Czytaj header (4 bajty magic + 4 bajty długość)
                header = await reader.read(8)
                if not header:
                    break
                
                if header[:4] != MAGIC:
                    self.logger.warning("⚠️ Nieprawidłowy magic byte")
                    break
                
                length = struct.unpack("!I", header[4:8])[0]
                
                # Czytaj dane
                data = await reader.read(length)
                message = self._decode_message(data)
                
                # Obsłuż wiadomość
                response = await self._handle_sync_message(message)
                
                if response:
                    response_data = self._encode_message(response)
                    writer.write(MAGIC + struct.pack("!I", len(response_data)) + response_data)
                    await writer.drain()
                    
        except Exception as e:
            self.logger.error(f"Sync connection error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _handle_sync_message(self, message: SyncMessage) -> Optional[SyncMessage]:
        """Obsługuje wiadomość sync"""
        
        if message.type == MessageType.FILE_LIST:
            # Zwróć listę plików
            files_data = [asdict(f) for f in self.known_files.values()]
            return self._create_message(MessageType.FILE_LIST, {"files": files_data})
        
        elif message.type == MessageType.FILE_REQUEST:
            # Wyślij plik
            file_id = message.data.get("file_id")
            if file_id in self.known_files:
                file_info = self.known_files[file_id]
                file_path = self.storage_path / file_info.path
                
                if file_path.exists():
                    content = file_path.read_bytes()
                    return self._create_message(MessageType.FILE_DATA, {
                        "file_id": file_id,
                        "content": content.hex(),  # Hex dla JSON
                        "hash": file_info.hash
                    })
        
        elif message.type == MessageType.FILE_ACK:
            # Potwierdzenie
            self.stats.files_synced += 1
            self._emit("sync:file_synced", message.data)
        
        return None
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SYNC OPERATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def sync_with_peer(self, peer: Peer) -> SyncStats:
        """
        Synchronizuje z konkretnym peerem
        """
        self.state = SyncState.SYNCING
        self.logger.info(f"🔄 Synchronizacja z {peer.name} ({peer.ip})...")
        
        stats = SyncStats()
        
        try:
            # Połącz z peerem
            reader, writer = await asyncio.open_connection(peer.ip, peer.port)
            
            # Pobierz listę plików peera
            request = self._create_message(MessageType.FILE_LIST, {})
            await self._send_tcp_message(writer, request)
            
            response = await self._receive_tcp_message(reader)
            
            if response and response.type == MessageType.FILE_LIST:
                remote_files = response.data.get("files", [])
                
                # Porównaj i pobierz brakujące/nowsze pliki
                for file_data in remote_files:
                    file_info = FileInfo(**file_data)
                    
                    if self._should_sync_file(file_info):
                        await self._request_file(reader, writer, file_info)
                        stats.files_synced += 1
                        stats.bytes_transferred += file_info.size
            
            # Zamknij połączenie
            writer.close()
            await writer.wait_closed()
            
            stats.peers_synced = 1
            stats.last_sync = datetime.now()
            
            self.logger.info(f"✅ Sync zakończony: {stats.files_synced} plików")
            self._emit("sync:completed", {"peer": peer.id, "stats": asdict(stats)})
            
        except Exception as e:
            self.logger.error(f"❌ Błąd synchronizacji: {e}")
            stats.errors += 1
            self._emit("sync:failed", {"peer": peer.id, "error": str(e)})
        
        finally:
            self.state = SyncState.IDLE
        
        return stats
    
    async def sync_all(self) -> SyncStats:
        """Synchronizuje ze wszystkimi peerami"""
        total_stats = SyncStats()
        
        for peer in self.peers.values():
            if peer.is_online:
                stats = await self.sync_with_peer(peer)
                total_stats.files_synced += stats.files_synced
                total_stats.bytes_transferred += stats.bytes_transferred
                total_stats.peers_synced += stats.peers_synced
                total_stats.errors += stats.errors
        
        total_stats.last_sync = datetime.now()
        self.stats = total_stats
        
        return total_stats
    
    def _should_sync_file(self, remote_file: FileInfo) -> bool:
        """Sprawdza czy plik powinien być zsynchronizowany"""
        local_file = self.known_files.get(remote_file.id)
        
        if not local_file:
            return True  # Brak lokalnie
        
        if local_file.hash != remote_file.hash:
            # Konflikt - użyj strategii
            strategy = self.config.get("conflict_resolution", "newest_wins")
            
            if strategy == "newest_wins":
                remote_time = datetime.fromisoformat(remote_file.modified_at)
                local_time = datetime.fromisoformat(local_file.modified_at)
                return remote_time > local_time
            
        return False
    
    async def _request_file(self, 
                           reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter,
                           file_info: FileInfo):
        """Pobiera plik od peera"""
        self.state = SyncState.RECEIVING
        
        request = self._create_message(MessageType.FILE_REQUEST, {
            "file_id": file_info.id
        })
        
        await self._send_tcp_message(writer, request)
        response = await self._receive_tcp_message(reader)
        
        if response and response.type == MessageType.FILE_DATA:
            content = bytes.fromhex(response.data.get("content", ""))
            
            # Weryfikuj hash
            actual_hash = hashlib.blake2b(content).hexdigest()
            if actual_hash == response.data.get("hash"):
                # Zapisz plik
                file_path = self.storage_path / file_info.path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(content)
                
                # Aktualizuj known_files
                self.known_files[file_info.id] = file_info
                
                # Wyślij ACK
                ack = self._create_message(MessageType.FILE_ACK, {
                    "file_id": file_info.id,
                    "status": "ok"
                })
                await self._send_tcp_message(writer, ack)
                
                self.logger.info(f"📥 Pobrano: {file_info.name}")
            else:
                self.logger.error(f"❌ Hash mismatch dla {file_info.name}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # NETWORK HELPERS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _send_tcp_message(self, writer: asyncio.StreamWriter, message: SyncMessage):
        """Wysyła wiadomość TCP"""
        data = self._encode_message(message)
        writer.write(MAGIC + struct.pack("!I", len(data)) + data)
        await writer.drain()
    
    async def _receive_tcp_message(self, reader: asyncio.StreamReader) -> Optional[SyncMessage]:
        """Odbiera wiadomość TCP"""
        header = await reader.read(8)
        if not header or header[:4] != MAGIC:
            return None
        
        length = struct.unpack("!I", header[4:8])[0]
        data = await reader.read(length)
        
        return self._decode_message(data)
    
    def _create_message(self, msg_type: MessageType, data: Dict) -> SyncMessage:
        """Tworzy wiadomość sync"""
        return SyncMessage(
            type=msg_type,
            sender_id=self.node_id,
            data=data
        )
    
    def _encode_message(self, message: SyncMessage) -> bytes:
        """Koduje wiadomość do bytes"""
        data = {
            "type": message.type.value,
            "sender_id": message.sender_id,
            "data": message.data,
            "timestamp": message.timestamp
        }
        return json.dumps(data).encode('utf-8')
    
    def _decode_message(self, data: bytes) -> SyncMessage:
        """Dekoduje wiadomość z bytes"""
        parsed = json.loads(data.decode('utf-8'))
        return SyncMessage(
            type=MessageType(parsed["type"]),
            sender_id=parsed["sender_id"],
            data=parsed.get("data", {}),
            timestamp=parsed.get("timestamp", datetime.now().isoformat())
        )
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FILE REGISTRY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def register_file(self, file_info: FileInfo):
        """Rejestruje plik"""
        self.known_files[file_info.id] = file_info
    
    def unregister_file(self, file_id: str):
        """Wyrejestrowuje plik"""
        if file_id in self.known_files:
            del self.known_files[file_id]
    
    def scan_storage(self) -> int:
        """Skanuje storage i rejestruje pliki"""
        count = 0
        
        files_path = self.storage_path / "files"
        if files_path.exists():
            for file_path in files_path.rglob("*"):
                if file_path.is_file():
                    content = file_path.read_bytes()
                    file_id = hashlib.md5(str(file_path).encode()).hexdigest()[:16]
                    file_info = FileInfo(
                        id=file_id,
                        path=str(file_path.relative_to(self.storage_path)),
                        name=file_path.name,
                        size=len(content),
                        hash=hashlib.blake2b(content).hexdigest(),
                        modified_at=datetime.fromtimestamp(
                            file_path.stat().st_mtime
                        ).isoformat()
                    )
                    
                    self.register_file(file_info)
                    count += 1            
        
        self.logger.info(f"📂 Zarejestrowano {count} plików")
        return count    
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EVENTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def analyze_request(request):
    if "DROP" in request or "DELETE" in request:
        raise Exception("SECURITY BLOCKED")

    def on(self, event: str, handler: Callable):
        """Rejestruje event handler"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
    
    def _emit(self, event: str, data: Dict):
        """Emituje event"""
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    self.logger.error(f"Event handler error: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━# MAIN
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"ALFA_PC",
if __name__ == "__main__":"__main__":
    import uuidimport uuid   storage_path="./storage"
    )
    async def main():
        sync = SyncEngine()[:8],await sync.start()
            node_id=str(uuid.uuid4())[:8],   node_name="ALFA_PC",
            node_name="ALFA_PC",    storage_path="./storage"
            storage_path="./storage"sync.scan_storage()
        )
        rt()
        await sync.start()
        # Skanuj plikiprint(f"Znaleziono {len(peers)} peerów")
        # Skanuj plikige()
        sync.scan_storage() wszystkimi
        
        # Szukaj peerówpeers = await sync.discover_peers()
        peers = await sync.discover_peers()len(peers)} peerów")print(f"Zsynchronizowano: {stats.files_synced} plików")    
        print(f"Znaleziono {len(peers)} peerów")
        await sync.stop()    
        # Sync ze wszystkimi    
        if peers:    stats = await sync.sync_all()    asyncio.run(main())
            stats = await sync.sync_all()hronizowano: {stats.files_synced} plików")
            print(f"Zsynchronizowano: {stats.files_synced} plików")    # alfa_cloud/api/main.py
        ()
        await sync.stop()    from fastapi import FastAPI, WebSocket
from alfa_cloud.core.event_bus import EventBus

app = FastAPI()
bus = EventBus()

@app.get("/ping")

    return {"status": "ALFA CLOUD ONLINE"}


    return r.json().get("response", "NO RESPONSE")    )        json={"prompt": prompt, "model": "deepseek-chat"}        "https://api.deepseek.com/v1/chat",    r = httpx.post(async def ask(prompt: str):    asyncio.run(main())        asyncio.run(main())async def ask_ai(prompt: str):
loud.ai.bridge import ask
# alfa_cloud/api/main.pyit ask(prompt)
    await bus.publish("AI_RESPONSE", answer)
from fastapi import FastAPI, WebSocketer": answer}@app.get("/ping")
from alfa_cloud.core.event_bus import EventBus

app = FastAPI()async def ws_endpoint(ws: WebSocket):
bus = EventBus()ept()
TED TO ALFA CLOUD")async def ask_ai(prompt: str):
@app.get("/ping")
async def ping():import ask
    return {"status": "ALFA CLOUD ONLINE"}
PONSE", answer)
@app.post("/ai")    return {"answer": answer}
async def ask_ai(prompt: str):
    from alfa_cloud.ai.bridge import ask
    answer = await ask(prompt)(ws: WebSocket):
    await bus.publish("AI_RESPONSE", answer)
    return {"answer": answer}    await ws.send_text("CONNECTED TO ALFA CLOUD")






    await ws.send_text("CONNECTED TO ALFA CLOUD")    await ws.accept()async def ws_endpoint(ws: WebSocket):@app.websocket("/ws")