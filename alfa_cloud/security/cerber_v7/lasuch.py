# ═══════════════════════════════════════════════════════════════════════════
# ŁASUCH - Honeypot & Deception Layer
# ═══════════════════════════════════════════════════════════════════════════
"""
Łasuch: Reverse Antivirus / Deception System

Features:
- Honeypot file/folder creation
- Decoy service exposure
- Payload capture and analysis
- Evidence packaging
- Attacker behavior tracking
"""

from __future__ import annotations

import json
import logging
import os
import socketserver
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import base64
import hashlib

logger = logging.getLogger("cerber.lasuch")


@dataclass
class CapturedPayload:
    """Captured malicious payload."""
    timestamp: datetime
    source: str  # IP:port or file path
    payload_type: str  # "network", "file", "process"
    data: bytes
    hash_sha256: str
    size: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "payload_type": self.payload_type,
            "hash_sha256": self.hash_sha256,
            "size": self.size,
            "data_b64": base64.b64encode(self.data[:4096]).decode("ascii"),  # Limit size
            "metadata": self.metadata,
        }


@dataclass
class DecoyAsset:
    """Honeypot decoy asset."""
    path: Path
    asset_type: str  # "file", "directory", "service"
    description: str
    created_at: datetime
    accessed: bool = False
    access_count: int = 0
    last_access: Optional[datetime] = None


class EvidenceWriter:
    """Writes captured evidence to disk."""
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.home() / ".cerber" / "evidence" / "lasuch"
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def write(self, peername: str, payload: bytes) -> Path:
        """Write captured payload to evidence file."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        hash_short = hashlib.sha256(payload).hexdigest()[:12]
        out_file = self.base_dir / f"capture_{timestamp}_{hash_short}.json"
        
        content = {
            "timestamp": datetime.now().isoformat(),
            "peer": peername,
            "bytes": len(payload),
            "hash_sha256": hashlib.sha256(payload).hexdigest(),
            "payload_b64": base64.b64encode(payload).decode("ascii"),
        }
        out_file.write_text(json.dumps(content, indent=2))
        return out_file


class HoneypotHandler(socketserver.BaseRequestHandler):
    """TCP handler for honeypot connections."""
    
    writer: EvidenceWriter
    capture_callback: Optional[Callable[[CapturedPayload], None]] = None
    
    def handle(self) -> None:
        """Handle incoming connection."""
        try:
            data = self.request.recv(4096)
            peer = f"{self.client_address[0]}:{self.client_address[1]}"
            
            # Log capture
            logger.warning(f"🍯 Honeypot capture from {peer}: {len(data)} bytes")
            
            # Save evidence
            saved = self.writer.write(peer, data)
            
            # Create payload object
            payload = CapturedPayload(
                timestamp=datetime.now(),
                source=peer,
                payload_type="network",
                data=data,
                hash_sha256=hashlib.sha256(data).hexdigest(),
                size=len(data),
                metadata={"saved_to": str(saved)},
            )
            
            # Callback
            if self.capture_callback:
                try:
                    self.capture_callback(payload)
                except Exception as e:
                    logger.error(f"Capture callback failed: {e}")
            
            # Send fake response to keep attacker engaged
            self.request.sendall(f"captured:{saved.name}\n".encode())
            
        except Exception as e:
            logger.error(f"Honeypot handler error: {e}")


class HoneypotServer(socketserver.ThreadingTCPServer):
    """Threaded TCP honeypot server."""
    allow_reuse_address = True

    def __init__(self, server_address, writer: EvidenceWriter):
        super().__init__(server_address, HoneypotHandler)
        HoneypotHandler.writer = writer


class Lasuch:
    """
    Łasuch - Deception & Honeypot System.
    
    Creates decoy assets to attract and capture malware:
    - Fake credential files
    - Decoy databases
    - Honeypot network services
    """
    
    # Decoy file templates
    DECOY_TEMPLATES = {
        "passwords.txt": "admin:admin123\nroot:password\nuser:12345678\n",
        "credentials.json": '{"api_key": "sk-fake-1234567890", "secret": "hunter2"}',
        "wallet.dat": b"\x00FAKE_WALLET_DATA\x00" * 100,
        "backup.sql": "-- MySQL dump\nINSERT INTO users VALUES (1, 'admin', 'password');",
        "id_rsa": "-----BEGIN FAKE RSA PRIVATE KEY-----\nNOT_A_REAL_KEY\n-----END FAKE RSA PRIVATE KEY-----",
        ".env": "DATABASE_URL=postgres://admin:password@localhost/db\nSECRET_KEY=fake_secret",
    }
    
    def __init__(
        self,
        decoy_dir: Optional[Path] = None,
        evidence_dir: Optional[Path] = None,
        capture_callback: Optional[Callable[[CapturedPayload], None]] = None,
    ):
        self.decoy_dir = decoy_dir or Path.home() / ".cerber" / "decoys"
        self.evidence_dir = evidence_dir or Path.home() / ".cerber" / "evidence" / "lasuch"
        self.capture_callback = capture_callback
        
        self.decoy_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        
        self._decoys: Dict[str, DecoyAsset] = {}
        self._honeypots: List[HoneypotServer] = []
        self._captures: List[CapturedPayload] = []
        self._lock = threading.Lock()
        self._running = False
        self._watcher_thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start Łasuch deception system."""
        if self._running:
            return
        
        logger.info("🍯 Łasuch starting...")
        self._running = True
        
        # Create default decoys
        self.create_decoys()
        
        # Start file watcher
        self._watcher_thread = threading.Thread(target=self._watch_decoys, daemon=True)
        self._watcher_thread.start()
        
        logger.info(f"🍯 Łasuch active - {len(self._decoys)} decoys deployed")
    
    def stop(self) -> None:
        """Stop Łasuch system."""
        self._running = False
        
        # Stop honeypot servers
        for server in self._honeypots:
            try:
                server.shutdown()
            except Exception:
                pass
        
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5.0)
        
        logger.info("🍯 Łasuch stopped")
    
    def create_decoys(self) -> None:
        """Create decoy files."""
        for filename, content in self.DECOY_TEMPLATES.items():
            self.create_decoy_file(filename, content)
    
    def create_decoy_file(self, filename: str, content: str | bytes) -> DecoyAsset:
        """Create a single decoy file."""
        filepath = self.decoy_dir / filename
        
        if isinstance(content, str):
            filepath.write_text(content)
        else:
            filepath.write_bytes(content)
        
        decoy = DecoyAsset(
            path=filepath,
            asset_type="file",
            description=f"Decoy: {filename}",
            created_at=datetime.now(),
        )
        
        self._decoys[str(filepath)] = decoy
        logger.debug(f"🍯 Created decoy: {filepath}")
        
        return decoy
    
    def create_decoy_directory(self, name: str = "backup") -> DecoyAsset:
        """Create a decoy directory with fake files."""
        dirpath = self.decoy_dir / name
        dirpath.mkdir(parents=True, exist_ok=True)
        
        # Add some fake files
        (dirpath / "database.bak").write_bytes(b"\x00" * 1024)
        (dirpath / "config.old").write_text("password=secret123")
        
        decoy = DecoyAsset(
            path=dirpath,
            asset_type="directory",
            description=f"Decoy directory: {name}",
            created_at=datetime.now(),
        )
        
        self._decoys[str(dirpath)] = decoy
        return decoy
    
    def start_honeypot(self, host: str = "0.0.0.0", port: int = 4040) -> HoneypotServer:
        """Start a honeypot TCP listener."""
        writer = EvidenceWriter(self.evidence_dir)
        server = HoneypotServer((host, port), writer)
        
        if self.capture_callback:
            HoneypotHandler.capture_callback = self.capture_callback
        
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        
        self._honeypots.append(server)
        logger.info(f"🍯 Honeypot listening on {host}:{port}")
        
        return server
    
    def _watch_decoys(self) -> None:
        """Watch decoy files for access."""
        # Track modification times
        mtimes: Dict[str, float] = {}
        
        for path in self._decoys:
            try:
                mtimes[path] = os.stat(path).st_mtime
            except Exception:
                pass
        
        while self._running:
            for path, decoy in list(self._decoys.items()):
                try:
                    current_mtime = os.stat(path).st_mtime
                    
                    if path in mtimes and current_mtime != mtimes[path]:
                        # File was accessed/modified!
                        self._handle_decoy_access(decoy)
                        mtimes[path] = current_mtime
                        
                except FileNotFoundError:
                    # File was deleted - also suspicious!
                    self._handle_decoy_access(decoy, deleted=True)
                except Exception:
                    pass
            
            time.sleep(1.0)
    
    def _handle_decoy_access(self, decoy: DecoyAsset, deleted: bool = False) -> None:
        """Handle when a decoy is accessed."""
        decoy.accessed = True
        decoy.access_count += 1
        decoy.last_access = datetime.now()
        
        action = "DELETED" if deleted else "ACCESSED"
        logger.warning(f"🚨 Decoy {action}: {decoy.path}")
        
        # Create capture record
        try:
            data = decoy.path.read_bytes() if not deleted and decoy.path.exists() else b""
        except Exception:
            data = b""
        
        payload = CapturedPayload(
            timestamp=datetime.now(),
            source=str(decoy.path),
            payload_type="file",
            data=data,
            hash_sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),
            metadata={"action": action, "access_count": decoy.access_count},
        )
        
        with self._lock:
            self._captures.append(payload)
        
        # Save evidence
        self._save_evidence(payload)
        
        # Callback
        if self.capture_callback:
            try:
                self.capture_callback(payload)
            except Exception as e:
                logger.error(f"Capture callback failed: {e}")
    
    def _save_evidence(self, payload: CapturedPayload) -> None:
        """Save capture evidence to disk."""
        timestamp = payload.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"capture_{timestamp}_{payload.hash_sha256[:12]}.json"
        filepath = self.evidence_dir / filename
        
        try:
            filepath.write_text(json.dumps(payload.to_dict(), indent=2))
        except Exception as e:
            logger.error(f"Failed to save evidence: {e}")
    
    def get_captures(self) -> List[CapturedPayload]:
        """Get all captures."""
        with self._lock:
            return list(self._captures)
    
    def get_decoy_status(self) -> List[Dict[str, Any]]:
        """Get status of all decoys."""
        return [
            {
                "path": str(d.path),
                "type": d.asset_type,
                "accessed": d.accessed,
                "access_count": d.access_count,
                "last_access": d.last_access.isoformat() if d.last_access else None,
            }
            for d in self._decoys.values()
        ]
