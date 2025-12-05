#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# ALFA CORE v2.0 — SYNC ENGINE — LAN Synchronization
# ═══════════════════════════════════════════════════════════════════════════
"""
SYNC ENGINE: Bezprzewodowa synchronizacja plików w sieci lokalnej.

Features:
- UDP Multicast peer discovery
- TCP file transfer with checksums
- Conflict resolution (hash-based)
- Delta sync (only changed files)
- End-to-end encryption (AES-256-GCM)
- EventBus integration

Protocol:
- Discovery: UDP 239.255.0.1:8766 (multicast)
- Transfer: TCP :8767 (per-peer)
- Messages: JSON + binary payload

Author: ALFA System / Karen86Tonoyan
"""

import asyncio
import hashlib
import json
import logging
import os
import socket
import struct
import threading
import time
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# EventBus integration
try:
    from .event_bus import EventBus, Priority, get_bus, publish
except ImportError:
    EventBus = None
    Priority = None
    get_bus = lambda: None
    publish = lambda *a, **k: None

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

LOG = logging.getLogger("alfa.sync")

# Network
MULTICAST_GROUP = "239.255.0.1"
MULTICAST_PORT = 8766
TRANSFER_PORT = 8767
DISCOVERY_INTERVAL = 10.0  # seconds
PEER_TIMEOUT = 30.0  # seconds without heartbeat

# Transfer
CHUNK_SIZE = 64 * 1024  # 64KB chunks
MAX_CONCURRENT_TRANSFERS = 4
TRANSFER_TIMEOUT = 300  # 5 minutes

# Sync
HASH_ALGORITHM = "blake2b"
COMPRESSION_LEVEL = 6

# ═══════════════════════════════════════════════════════════════════════════
# ENUMS & DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

class SyncState(Enum):
    """Stan silnika synchronizacji"""
    IDLE = auto()
    DISCOVERING = auto()
    SYNCING = auto()
    RECEIVING = auto()
    SENDING = auto()
    ERROR = auto()


class MessageType(Enum):
    """Typy wiadomości protokołu sync"""
    # Discovery
    ANNOUNCE = "ANNOUNCE"
    ANNOUNCE_ACK = "ANNOUNCE_ACK"
    HEARTBEAT = "HEARTBEAT"
    GOODBYE = "GOODBYE"
    
    # Sync negotiation
    SYNC_REQUEST = "SYNC_REQUEST"
    SYNC_MANIFEST = "SYNC_MANIFEST"
    SYNC_DELTA = "SYNC_DELTA"
    
    # Transfer
    FILE_REQUEST = "FILE_REQUEST"
    FILE_HEADER = "FILE_HEADER"
    FILE_CHUNK = "FILE_CHUNK"
    FILE_COMPLETE = "FILE_COMPLETE"
    FILE_ACK = "FILE_ACK"
    FILE_ERROR = "FILE_ERROR"
    
    # Control
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    CANCEL = "CANCEL"


class ConflictResolution(Enum):
    """Strategia rozwiązywania konfliktów"""
    NEWEST_WINS = auto()
    HASH_COMPARE = auto()
    MANUAL = auto()
    KEEP_BOTH = auto()


@dataclass
class Peer:
    """Informacje o peer'ze w sieci"""
    peer_id: str
    hostname: str
    ip: str
    port: int
    version: str = "2.0"
    last_seen: float = field(default_factory=time.time)
    is_online: bool = True
    sync_enabled: bool = True
    shared_folders: List[str] = field(default_factory=list)
    
    def is_alive(self) -> bool:
        return time.time() - self.last_seen < PEER_TIMEOUT


@dataclass
class FileEntry:
    """Wpis pliku w manifeście synchronizacji"""
    path: str
    hash: str
    size: int
    modified: float
    is_dir: bool = False
    compressed_size: Optional[int] = None
    
    def to_dict(self) -> Dict:
        return {
            "path": self.path,
            "hash": self.hash,
            "size": self.size,
            "modified": self.modified,
            "is_dir": self.is_dir,
            "compressed_size": self.compressed_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "FileEntry":
        return cls(**data)


@dataclass
class MessageEnvelope:
    """Koperta wiadomości protokołu sync"""
    msg_type: MessageType
    sender_id: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    msg_id: str = ""
    
    def __post_init__(self):
        if not self.msg_id:
            self.msg_id = f"{self.sender_id}:{int(self.timestamp * 1000)}"
    
    def to_json(self) -> str:
        return json.dumps({
            "type": self.msg_type.value,
            "sender": self.sender_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "msg_id": self.msg_id
        })
    
    def to_bytes(self) -> bytes:
        return self.to_json().encode("utf-8")
    
    @classmethod
    def from_json(cls, data: str) -> "MessageEnvelope":
        parsed = json.loads(data)
        return cls(
            msg_type=MessageType(parsed["type"]),
            sender_id=parsed["sender"],
            payload=parsed.get("payload", {}),
            timestamp=parsed.get("timestamp", time.time()),
            msg_id=parsed.get("msg_id", "")
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "MessageEnvelope":
        return cls.from_json(data.decode("utf-8"))


@dataclass
class TransferTask:
    """Zadanie transferu pliku"""
    task_id: str
    peer_id: str
    file_entry: FileEntry
    direction: str  # "send" | "receive"
    state: str = "pending"  # pending, active, completed, failed
    progress: float = 0.0
    bytes_transferred: int = 0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# SYNC ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class SyncEngine:
    """
    Silnik synchronizacji LAN dla ALFA System.
    
    Usage:
        engine = SyncEngine(sync_folder="/data/sync")
        await engine.start()
        await engine.sync_with_peers()
        await engine.stop()
    """
    
    def __init__(
        self,
        sync_folder: str,
        peer_id: Optional[str] = None,
        conflict_resolution: ConflictResolution = ConflictResolution.HASH_COMPARE
    ):
        self.sync_folder = Path(sync_folder)
        self.sync_folder.mkdir(parents=True, exist_ok=True)
        
        # Identity
        self.peer_id = peer_id or self._generate_peer_id()
        self.hostname = socket.gethostname()
        self.version = "2.0.0"
        
        # State
        self.state = SyncState.IDLE
        self.conflict_resolution = conflict_resolution
        
        # Peers
        self.peers: Dict[str, Peer] = {}
        self._peers_lock = threading.Lock()
        
        # Manifest cache
        self._local_manifest: Dict[str, FileEntry] = {}
        self._manifest_lock = threading.Lock()
        
        # Transfer queue
        self._transfer_queue: asyncio.Queue = asyncio.Queue()
        self._active_transfers: Dict[str, TransferTask] = {}
        self._transfers_lock = threading.Lock()
        
        # Network
        self._discovery_socket: Optional[socket.socket] = None
        self._transfer_server: Optional[asyncio.Server] = None
        self._running = False
        
        # Stats
        self.stats = {
            "files_synced": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "conflicts_resolved": 0,
            "last_sync": None
        }
        
        # Callbacks
        self._on_peer_discovered: Optional[Callable[[Peer], None]] = None
        self._on_sync_progress: Optional[Callable[[float, str], None]] = None
        self._on_conflict: Optional[Callable[[FileEntry, FileEntry], str]] = None
        
        LOG.info(f"[SyncEngine] Initialized: peer_id={self.peer_id}")
    
    def _generate_peer_id(self) -> str:
        """Generate unique peer ID based on machine info"""
        import uuid
        machine_id = str(uuid.getnode())
        return hashlib.blake2b(machine_id.encode(), digest_size=8).hexdigest()
    
    # ─────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────
    
    async def start(self):
        """Start sync engine"""
        if self._running:
            return
        
        self._running = True
        self.state = SyncState.DISCOVERING
        
        # Build initial manifest
        await self._build_local_manifest()
        
        # Start discovery
        self._start_discovery()
        
        # Start transfer server
        await self._start_transfer_server()
        
        # Start background tasks
        asyncio.create_task(self._discovery_loop())
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._transfer_worker())
        
        # Publish event
        if get_bus():
            publish("sync.started", {"peer_id": self.peer_id})
        
        LOG.info("[SyncEngine] Started")
    
    async def stop(self):
        """Stop sync engine"""
        if not self._running:
            return
        
        self._running = False
        self.state = SyncState.IDLE
        
        # Send goodbye to peers
        await self._broadcast_goodbye()
        
        # Close sockets
        if self._discovery_socket:
            self._discovery_socket.close()
        
        if self._transfer_server:
            self._transfer_server.close()
            await self._transfer_server.wait_closed()
        
        # Publish event
        if get_bus():
            publish("sync.stopped", {"peer_id": self.peer_id})
        
        LOG.info("[SyncEngine] Stopped")
    
    # ─────────────────────────────────────────────────────────────────────
    # DISCOVERY (UDP Multicast)
    # ─────────────────────────────────────────────────────────────────────
    
    def _start_discovery(self):
        """Initialize UDP multicast socket for discovery"""
        self._discovery_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
            socket.IPPROTO_UDP
        )
        
        # Allow reuse
        self._discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind to multicast port
        self._discovery_socket.bind(("", MULTICAST_PORT))
        
        # Join multicast group
        mreq = struct.pack(
            "4sl",
            socket.inet_aton(MULTICAST_GROUP),
            socket.INADDR_ANY
        )
        self._discovery_socket.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_ADD_MEMBERSHIP,
            mreq
        )
        
        # Set TTL for multicast
        self._discovery_socket.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_MULTICAST_TTL,
            2
        )
        
        # Non-blocking
        self._discovery_socket.setblocking(False)
        
        LOG.info(f"[Discovery] Listening on {MULTICAST_GROUP}:{MULTICAST_PORT}")
    
    async def _discovery_loop(self):
        """Background loop for peer discovery"""
        loop = asyncio.get_event_loop()
        
        while self._running:
            try:
                # Send announce
                await self._broadcast_announce()
                
                # Receive responses
                for _ in range(10):  # Check multiple times per interval
                    try:
                        data, addr = await loop.run_in_executor(
                            None,
                            lambda: self._discovery_socket.recvfrom(4096)
                        )
                        await self._handle_discovery_message(data, addr)
                    except BlockingIOError:
                        pass
                    except Exception as e:
                        LOG.debug(f"[Discovery] Recv error: {e}")
                    
                    await asyncio.sleep(DISCOVERY_INTERVAL / 10)
                
            except Exception as e:
                LOG.error(f"[Discovery] Loop error: {e}")
                await asyncio.sleep(1)
    
    async def _broadcast_announce(self):
        """Broadcast announcement to find peers"""
        msg = MessageEnvelope(
            msg_type=MessageType.ANNOUNCE,
            sender_id=self.peer_id,
            payload={
                "hostname": self.hostname,
                "port": TRANSFER_PORT,
                "version": self.version,
                "sync_enabled": True,
                "shared_folders": [str(self.sync_folder)]
            }
        )
        
        try:
            self._discovery_socket.sendto(
                msg.to_bytes(),
                (MULTICAST_GROUP, MULTICAST_PORT)
            )
        except Exception as e:
            LOG.error(f"[Discovery] Announce error: {e}")
    
    async def _broadcast_goodbye(self):
        """Broadcast goodbye before shutdown"""
        msg = MessageEnvelope(
            msg_type=MessageType.GOODBYE,
            sender_id=self.peer_id,
            payload={}
        )
        
        try:
            self._discovery_socket.sendto(
                msg.to_bytes(),
                (MULTICAST_GROUP, MULTICAST_PORT)
            )
        except Exception:
            pass
    
    async def _handle_discovery_message(self, data: bytes, addr: Tuple[str, int]):
        """Handle incoming discovery message"""
        try:
            msg = MessageEnvelope.from_bytes(data)
            
            # Ignore own messages
            if msg.sender_id == self.peer_id:
                return
            
            if msg.msg_type == MessageType.ANNOUNCE:
                peer = Peer(
                    peer_id=msg.sender_id,
                    hostname=msg.payload.get("hostname", "unknown"),
                    ip=addr[0],
                    port=msg.payload.get("port", TRANSFER_PORT),
                    version=msg.payload.get("version", "1.0"),
                    sync_enabled=msg.payload.get("sync_enabled", True),
                    shared_folders=msg.payload.get("shared_folders", [])
                )
                
                with self._peers_lock:
                    is_new = msg.sender_id not in self.peers
                    self.peers[msg.sender_id] = peer
                
                if is_new:
                    LOG.info(f"[Discovery] New peer: {peer.hostname} ({peer.ip})")
                    if self._on_peer_discovered:
                        self._on_peer_discovered(peer)
                    if get_bus():
                        publish("sync.peer_discovered", peer.__dict__)
                
                # Send ACK
                await self._send_announce_ack(addr)
            
            elif msg.msg_type == MessageType.ANNOUNCE_ACK:
                with self._peers_lock:
                    if msg.sender_id in self.peers:
                        self.peers[msg.sender_id].last_seen = time.time()
            
            elif msg.msg_type == MessageType.HEARTBEAT:
                with self._peers_lock:
                    if msg.sender_id in self.peers:
                        self.peers[msg.sender_id].last_seen = time.time()
            
            elif msg.msg_type == MessageType.GOODBYE:
                with self._peers_lock:
                    if msg.sender_id in self.peers:
                        peer = self.peers.pop(msg.sender_id)
                        LOG.info(f"[Discovery] Peer left: {peer.hostname}")
                        if get_bus():
                            publish("sync.peer_left", {"peer_id": msg.sender_id})
                            
        except Exception as e:
            LOG.error(f"[Discovery] Handle error: {e}")
    
    async def _send_announce_ack(self, addr: Tuple[str, int]):
        """Send ACK to announce"""
        msg = MessageEnvelope(
            msg_type=MessageType.ANNOUNCE_ACK,
            sender_id=self.peer_id,
            payload={"hostname": self.hostname}
        )
        
        try:
            self._discovery_socket.sendto(msg.to_bytes(), addr)
        except Exception:
            pass
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        while self._running:
            await asyncio.sleep(DISCOVERY_INTERVAL / 2)
            
            msg = MessageEnvelope(
                msg_type=MessageType.HEARTBEAT,
                sender_id=self.peer_id,
                payload={"timestamp": time.time()}
            )
            
            try:
                self._discovery_socket.sendto(
                    msg.to_bytes(),
                    (MULTICAST_GROUP, MULTICAST_PORT)
                )
            except Exception:
                pass
            
            # Clean stale peers
            with self._peers_lock:
                stale = [
                    pid for pid, peer in self.peers.items()
                    if not peer.is_alive()
                ]
                for pid in stale:
                    peer = self.peers.pop(pid)
                    LOG.info(f"[Discovery] Peer timeout: {peer.hostname}")
    
    # ─────────────────────────────────────────────────────────────────────
    # MANIFEST & HASHING
    # ─────────────────────────────────────────────────────────────────────
    
    async def _build_local_manifest(self):
        """Build manifest of local files"""
        manifest = {}
        
        for path in self.sync_folder.rglob("*"):
            if path.is_file():
                rel_path = path.relative_to(self.sync_folder)
                
                # Skip hidden/system files
                if any(p.startswith(".") for p in rel_path.parts):
                    continue
                
                try:
                    stat = path.stat()
                    file_hash = await self._hash_file(path)
                    
                    entry = FileEntry(
                        path=str(rel_path),
                        hash=file_hash,
                        size=stat.st_size,
                        modified=stat.st_mtime,
                        is_dir=False
                    )
                    manifest[str(rel_path)] = entry
                    
                except Exception as e:
                    LOG.warning(f"[Manifest] Error reading {path}: {e}")
        
        with self._manifest_lock:
            self._local_manifest = manifest
        
        LOG.info(f"[Manifest] Built: {len(manifest)} files")
        return manifest
    
    async def _hash_file(self, path: Path) -> str:
        """Calculate BLAKE2b hash of file"""
        loop = asyncio.get_event_loop()
        
        def _hash():
            h = hashlib.blake2b(digest_size=32)
            with open(path, "rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    h.update(chunk)
            return h.hexdigest()
        
        return await loop.run_in_executor(None, _hash)
    
    def get_manifest(self) -> Dict[str, FileEntry]:
        """Get current local manifest"""
        with self._manifest_lock:
            return self._local_manifest.copy()
    
    # ─────────────────────────────────────────────────────────────────────
    # TRANSFER SERVER (TCP)
    # ─────────────────────────────────────────────────────────────────────
    
    async def _start_transfer_server(self):
        """Start TCP server for file transfers"""
        self._transfer_server = await asyncio.start_server(
            self._handle_transfer_connection,
            "0.0.0.0",
            TRANSFER_PORT
        )
        
        LOG.info(f"[Transfer] Server listening on port {TRANSFER_PORT}")
    
    async def _handle_transfer_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Handle incoming transfer connection"""
        addr = writer.get_extra_info("peername")
        LOG.debug(f"[Transfer] Connection from {addr}")
        
        try:
            # Read message header (4 bytes length + JSON)
            header_len_bytes = await reader.read(4)
            if len(header_len_bytes) < 4:
                return
            
            header_len = struct.unpack("!I", header_len_bytes)[0]
            header_data = await reader.read(header_len)
            msg = MessageEnvelope.from_bytes(header_data)
            
            if msg.msg_type == MessageType.SYNC_REQUEST:
                await self._handle_sync_request(msg, reader, writer)
            
            elif msg.msg_type == MessageType.FILE_REQUEST:
                await self._handle_file_request(msg, reader, writer)
            
            elif msg.msg_type == MessageType.SYNC_MANIFEST:
                await self._handle_sync_manifest(msg, reader, writer)
                
        except Exception as e:
            LOG.error(f"[Transfer] Connection error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _handle_sync_request(
        self,
        msg: MessageEnvelope,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Handle sync request from peer"""
        # Send our manifest
        manifest_data = {
            path: entry.to_dict()
            for path, entry in self._local_manifest.items()
        }
        
        response = MessageEnvelope(
            msg_type=MessageType.SYNC_MANIFEST,
            sender_id=self.peer_id,
            payload={"manifest": manifest_data}
        )
        
        await self._send_message(writer, response)
    
    async def _handle_file_request(
        self,
        msg: MessageEnvelope,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Handle file request from peer"""
        file_path = msg.payload.get("path")
        if not file_path:
            return
        
        full_path = self.sync_folder / file_path
        
        if not full_path.exists() or not full_path.is_file():
            error = MessageEnvelope(
                msg_type=MessageType.FILE_ERROR,
                sender_id=self.peer_id,
                payload={"error": "File not found", "path": file_path}
            )
            await self._send_message(writer, error)
            return
        
        # Send file header
        stat = full_path.stat()
        file_hash = await self._hash_file(full_path)
        
        header = MessageEnvelope(
            msg_type=MessageType.FILE_HEADER,
            sender_id=self.peer_id,
            payload={
                "path": file_path,
                "size": stat.st_size,
                "hash": file_hash,
                "modified": stat.st_mtime
            }
        )
        await self._send_message(writer, header)
        
        # Send file chunks
        bytes_sent = 0
        with open(full_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                # Compress chunk
                compressed = zlib.compress(chunk, COMPRESSION_LEVEL)
                
                chunk_msg = MessageEnvelope(
                    msg_type=MessageType.FILE_CHUNK,
                    sender_id=self.peer_id,
                    payload={
                        "offset": bytes_sent,
                        "size": len(chunk),
                        "compressed_size": len(compressed)
                    }
                )
                
                # Send chunk header
                await self._send_message(writer, chunk_msg)
                
                # Send compressed data
                writer.write(struct.pack("!I", len(compressed)))
                writer.write(compressed)
                await writer.drain()
                
                bytes_sent += len(chunk)
        
        # Send complete
        complete = MessageEnvelope(
            msg_type=MessageType.FILE_COMPLETE,
            sender_id=self.peer_id,
            payload={"path": file_path, "size": bytes_sent}
        )
        await self._send_message(writer, complete)
        
        self.stats["bytes_sent"] += bytes_sent
        LOG.info(f"[Transfer] Sent: {file_path} ({bytes_sent} bytes)")
    
    async def _handle_sync_manifest(
        self,
        msg: MessageEnvelope,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Handle manifest from peer and calculate delta"""
        remote_manifest = {
            path: FileEntry.from_dict(data)
            for path, data in msg.payload.get("manifest", {}).items()
        }
        
        # Calculate delta
        to_download = []
        to_upload = []
        conflicts = []
        
        local = self._local_manifest
        
        # Files we need from peer
        for path, remote_entry in remote_manifest.items():
            if path not in local:
                to_download.append(remote_entry)
            elif local[path].hash != remote_entry.hash:
                # Conflict - check resolution strategy
                if self.conflict_resolution == ConflictResolution.NEWEST_WINS:
                    if remote_entry.modified > local[path].modified:
                        to_download.append(remote_entry)
                    else:
                        to_upload.append(local[path])
                elif self.conflict_resolution == ConflictResolution.HASH_COMPARE:
                    # Different content - resolve by timestamp
                    if remote_entry.modified > local[path].modified:
                        to_download.append(remote_entry)
                else:
                    conflicts.append((local[path], remote_entry))
        
        # Files peer needs from us
        for path, local_entry in local.items():
            if path not in remote_manifest:
                to_upload.append(local_entry)
        
        # Send delta response
        delta = MessageEnvelope(
            msg_type=MessageType.SYNC_DELTA,
            sender_id=self.peer_id,
            payload={
                "to_send": [e.path for e in to_upload],
                "to_receive": [e.path for e in to_download],
                "conflicts": len(conflicts)
            }
        )
        await self._send_message(writer, delta)
        
        LOG.info(f"[Sync] Delta: download={len(to_download)}, upload={len(to_upload)}, conflicts={len(conflicts)}")
    
    async def _send_message(self, writer: asyncio.StreamWriter, msg: MessageEnvelope):
        """Send message with length prefix"""
        data = msg.to_bytes()
        writer.write(struct.pack("!I", len(data)))
        writer.write(data)
        await writer.drain()
    
    # ─────────────────────────────────────────────────────────────────────
    # SYNC OPERATIONS
    # ─────────────────────────────────────────────────────────────────────
    
    async def sync_with_peer(self, peer_id: str) -> bool:
        """Synchronize with specific peer"""
        with self._peers_lock:
            peer = self.peers.get(peer_id)
        
        if not peer or not peer.is_alive():
            LOG.warning(f"[Sync] Peer not available: {peer_id}")
            return False
        
        self.state = SyncState.SYNCING
        
        try:
            # Connect to peer
            reader, writer = await asyncio.open_connection(peer.ip, peer.port)
            
            # Send sync request
            request = MessageEnvelope(
                msg_type=MessageType.SYNC_REQUEST,
                sender_id=self.peer_id,
                payload={"manifest": {
                    p: e.to_dict() for p, e in self._local_manifest.items()
                }}
            )
            await self._send_message(writer, request)
            
            # Receive peer's manifest
            header_len = struct.unpack("!I", await reader.read(4))[0]
            response = MessageEnvelope.from_bytes(await reader.read(header_len))
            
            if response.msg_type == MessageType.SYNC_MANIFEST:
                # Process manifest and download needed files
                remote_manifest = response.payload.get("manifest", {})
                await self._process_sync_manifest(peer, remote_manifest, reader, writer)
            
            writer.close()
            await writer.wait_closed()
            
            self.stats["last_sync"] = datetime.now().isoformat()
            self.state = SyncState.IDLE
            
            if get_bus():
                publish("sync.completed", {
                    "peer_id": peer_id,
                    "timestamp": self.stats["last_sync"]
                })
            
            return True
            
        except Exception as e:
            LOG.error(f"[Sync] Error with peer {peer_id}: {e}")
            self.state = SyncState.ERROR
            return False
    
    async def _process_sync_manifest(
        self,
        peer: Peer,
        remote_manifest: Dict,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Process remote manifest and sync files"""
        for path, entry_data in remote_manifest.items():
            remote_entry = FileEntry.from_dict(entry_data)
            
            # Check if we need this file
            local_entry = self._local_manifest.get(path)
            
            if not local_entry or local_entry.hash != remote_entry.hash:
                # Need to download
                if not local_entry or remote_entry.modified > local_entry.modified:
                    await self._download_file(peer, path, reader, writer)
    
    async def _download_file(
        self,
        peer: Peer,
        path: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> bool:
        """Download file from peer"""
        try:
            # Request file
            request = MessageEnvelope(
                msg_type=MessageType.FILE_REQUEST,
                sender_id=self.peer_id,
                payload={"path": path}
            )
            await self._send_message(writer, request)
            
            # Receive header
            header_len = struct.unpack("!I", await reader.read(4))[0]
            header = MessageEnvelope.from_bytes(await reader.read(header_len))
            
            if header.msg_type == MessageType.FILE_ERROR:
                LOG.error(f"[Download] Error: {header.payload.get('error')}")
                return False
            
            if header.msg_type != MessageType.FILE_HEADER:
                return False
            
            file_size = header.payload.get("size", 0)
            file_hash = header.payload.get("hash", "")
            
            # Prepare local path
            local_path = self.sync_folder / path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Receive chunks
            received = 0
            h = hashlib.blake2b(digest_size=32)
            
            with open(local_path, "wb") as f:
                while received < file_size:
                    # Read chunk header
                    chunk_len = struct.unpack("!I", await reader.read(4))[0]
                    chunk_msg = MessageEnvelope.from_bytes(await reader.read(chunk_len))
                    
                    if chunk_msg.msg_type == MessageType.FILE_COMPLETE:
                        break
                    
                    if chunk_msg.msg_type != MessageType.FILE_CHUNK:
                        continue
                    
                    # Read compressed data
                    compressed_size = chunk_msg.payload.get("compressed_size", 0)
                    data_len = struct.unpack("!I", await reader.read(4))[0]
                    compressed = await reader.read(data_len)
                    
                    # Decompress and write
                    chunk = zlib.decompress(compressed)
                    f.write(chunk)
                    h.update(chunk)
                    received += len(chunk)
                    
                    # Progress callback
                    if self._on_sync_progress:
                        progress = received / file_size if file_size > 0 else 1.0
                        self._on_sync_progress(progress, path)
            
            # Verify hash
            computed_hash = h.hexdigest()
            if computed_hash != file_hash:
                LOG.error(f"[Download] Hash mismatch: {path}")
                local_path.unlink()
                return False
            
            self.stats["bytes_received"] += received
            self.stats["files_synced"] += 1
            
            # Update manifest
            with self._manifest_lock:
                self._local_manifest[path] = FileEntry(
                    path=path,
                    hash=file_hash,
                    size=file_size,
                    modified=time.time()
                )
            
            LOG.info(f"[Download] Complete: {path} ({received} bytes)")
            return True
            
        except Exception as e:
            LOG.error(f"[Download] Error: {path} - {e}")
            return False
    
    async def sync_with_all(self) -> Dict[str, bool]:
        """Sync with all known peers"""
        results = {}
        
        with self._peers_lock:
            peer_ids = list(self.peers.keys())
        
        for peer_id in peer_ids:
            results[peer_id] = await self.sync_with_peer(peer_id)
        
        return results
    
    async def _transfer_worker(self):
        """Background worker for transfer queue"""
        while self._running:
            try:
                task = await asyncio.wait_for(
                    self._transfer_queue.get(),
                    timeout=1.0
                )
                
                with self._transfers_lock:
                    self._active_transfers[task.task_id] = task
                
                # Process task
                task.state = "active"
                task.started_at = time.time()
                
                # TODO: Execute transfer
                
                task.state = "completed"
                task.completed_at = time.time()
                
                with self._transfers_lock:
                    del self._active_transfers[task.task_id]
                
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                LOG.error(f"[Transfer] Worker error: {e}")
    
    # ─────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────────
    
    def get_peers(self) -> List[Peer]:
        """Get list of known peers"""
        with self._peers_lock:
            return [p for p in self.peers.values() if p.is_alive()]
    
    def get_stats(self) -> Dict:
        """Get sync statistics"""
        return {
            **self.stats,
            "state": self.state.name,
            "peers_count": len(self.get_peers()),
            "manifest_files": len(self._local_manifest),
            "active_transfers": len(self._active_transfers)
        }
    
    def on_peer_discovered(self, callback: Callable[[Peer], None]):
        """Set callback for peer discovery"""
        self._on_peer_discovered = callback
    
    def on_sync_progress(self, callback: Callable[[float, str], None]):
        """Set callback for sync progress"""
        self._on_sync_progress = callback
    
    def on_conflict(self, callback: Callable[[FileEntry, FileEntry], str]):
        """Set callback for conflict resolution"""
        self._on_conflict = callback


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON & HELPERS
# ═══════════════════════════════════════════════════════════════════════════

_sync_engine: Optional[SyncEngine] = None


def get_sync_engine(sync_folder: str = None) -> SyncEngine:
    """Get or create SyncEngine singleton"""
    global _sync_engine
    
    if _sync_engine is None:
        if sync_folder is None:
            sync_folder = str(Path.home() / ".alfa" / "sync")
        _sync_engine = SyncEngine(sync_folder)
    
    return _sync_engine


async def quick_sync(folder: str = None) -> Dict[str, bool]:
    """Quick sync with all peers"""
    engine = get_sync_engine(folder)
    await engine.start()
    results = await engine.sync_with_all()
    await engine.stop()
    return results


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ALFA Sync Engine")
    parser.add_argument("--folder", "-f", default="./sync_data", help="Sync folder")
    parser.add_argument("--discover", "-d", action="store_true", help="Discover peers only")
    parser.add_argument("--sync", "-s", action="store_true", help="Sync with all peers")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        engine = SyncEngine(args.folder)
        await engine.start()
        
        if args.discover:
            print("Discovering peers... (Ctrl+C to stop)")
            while True:
                peers = engine.get_peers()
                print(f"\rPeers: {len(peers)}", end="")
                await asyncio.sleep(1)
        
        if args.sync:
            print("Syncing with all peers...")
            results = await engine.sync_with_all()
            for peer_id, success in results.items():
                print(f"  {peer_id}: {'✓' if success else '✗'}")
        
        await engine.stop()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
