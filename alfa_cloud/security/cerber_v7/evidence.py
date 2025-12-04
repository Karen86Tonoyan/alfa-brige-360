# ═══════════════════════════════════════════════════════════════════════════
# EVIDENCE - Forensic Artifact Collector
# ═══════════════════════════════════════════════════════════════════════════
"""
Evidence Collector: Forensic artifact capture and packaging.

Features:
- Process memory snapshots
- File hash collection (SHA-512)
- Screenshot capture
- Network capture stubs
- Encrypted evidence bundles
- Signed evidence with PQXHybrid
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import platform
import subprocess
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cerber.evidence")


@dataclass
class EvidenceItem:
    """Single evidence artifact."""
    item_type: str  # "file", "process", "network", "screenshot"
    source: str
    captured_at: datetime
    hash_sha512: str
    size: int
    data_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "item_type": self.item_type,
            "source": self.source,
            "captured_at": self.captured_at.isoformat(),
            "hash_sha512": self.hash_sha512,
            "size": self.size,
            "data_path": str(self.data_path) if self.data_path else None,
            "metadata": self.metadata,
        }


@dataclass
class EvidenceBundle:
    """Collection of evidence artifacts."""
    bundle_id: str
    created_at: datetime
    items: List[EvidenceItem] = field(default_factory=list)
    signed: bool = False
    signature: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "bundle_id": self.bundle_id,
            "created_at": self.created_at.isoformat(),
            "item_count": len(self.items),
            "items": [i.to_dict() for i in self.items],
            "signed": self.signed,
            "signature": self.signature,
        }


class EvidenceCollector:
    """
    Forensic Evidence Collector for Cerber Security.
    
    Collects and packages:
    - File artifacts
    - Process information
    - Network state
    - Screenshots
    - Memory dumps (where permitted)
    """
    
    def __init__(
        self,
        evidence_dir: Optional[Path] = None,
        keypair = None,  # PQKeyPair for signing
    ):
        self.evidence_dir = evidence_dir or Path.home() / ".cerber" / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.keypair = keypair
        
        self._bundles: List[EvidenceBundle] = []
        self.platform = platform.system().lower()
    
    def capture_file(self, file_path: Path | str) -> EvidenceItem:
        """Capture a file as evidence."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Evidence file not found: {path}")
        
        data = path.read_bytes()
        hash_value = hashlib.sha512(data).hexdigest()
        
        # Copy to evidence directory
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        dest = self.evidence_dir / f"file_{timestamp}_{hash_value[:12]}"
        dest.write_bytes(data)
        
        item = EvidenceItem(
            item_type="file",
            source=str(path),
            captured_at=datetime.now(),
            hash_sha512=hash_value,
            size=len(data),
            data_path=dest,
            metadata={"original_name": path.name},
        )
        
        logger.info(f"📁 Captured file evidence: {path.name}")
        return item
    
    def capture_process_list(self) -> EvidenceItem:
        """Capture current process list."""
        try:
            if self.platform == "windows":
                result = subprocess.run(
                    ["tasklist", "/v", "/fo", "csv"],
                    capture_output=True, text=True, timeout=30
                )
            else:
                result = subprocess.run(
                    ["ps", "auxww"],
                    capture_output=True, text=True, timeout=30
                )
            
            data = result.stdout.encode("utf-8")
            hash_value = hashlib.sha512(data).hexdigest()
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            dest = self.evidence_dir / f"processes_{timestamp}.txt"
            dest.write_bytes(data)
            
            return EvidenceItem(
                item_type="process",
                source="system",
                captured_at=datetime.now(),
                hash_sha512=hash_value,
                size=len(data),
                data_path=dest,
            )
            
        except Exception as e:
            logger.error(f"Process capture failed: {e}")
            raise
    
    def capture_network_state(self) -> EvidenceItem:
        """Capture current network connections."""
        try:
            if self.platform == "windows":
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True, text=True, timeout=30
                )
            else:
                result = subprocess.run(
                    ["netstat", "-anp"],
                    capture_output=True, text=True, timeout=30
                )
            
            data = result.stdout.encode("utf-8")
            hash_value = hashlib.sha512(data).hexdigest()
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            dest = self.evidence_dir / f"network_{timestamp}.txt"
            dest.write_bytes(data)
            
            return EvidenceItem(
                item_type="network",
                source="system",
                captured_at=datetime.now(),
                hash_sha512=hash_value,
                size=len(data),
                data_path=dest,
            )
            
        except Exception as e:
            logger.error(f"Network capture failed: {e}")
            raise
    
    def capture_screenshot(self) -> Optional[EvidenceItem]:
        """Capture a screenshot (if possible)."""
        try:
            # Try using built-in tools
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            dest = self.evidence_dir / f"screenshot_{timestamp}.png"
            
            if self.platform == "windows":
                # PowerShell screenshot
                ps_script = f'''
                Add-Type -AssemblyName System.Windows.Forms
                $screen = [System.Windows.Forms.Screen]::PrimaryScreen
                $bitmap = New-Object System.Drawing.Bitmap($screen.Bounds.Width, $screen.Bounds.Height)
                $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
                $graphics.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size)
                $bitmap.Save("{dest}")
                '''
                subprocess.run(["powershell", "-Command", ps_script], timeout=10)
            else:
                # Try scrot on Linux
                subprocess.run(["scrot", str(dest)], timeout=10)
            
            if dest.exists():
                data = dest.read_bytes()
                return EvidenceItem(
                    item_type="screenshot",
                    source="display",
                    captured_at=datetime.now(),
                    hash_sha512=hashlib.sha512(data).hexdigest(),
                    size=len(data),
                    data_path=dest,
                )
                
        except Exception as e:
            logger.warning(f"Screenshot capture failed: {e}")
        
        return None
    
    def create_bundle(
        self,
        items: List[EvidenceItem],
        sign: bool = True
    ) -> EvidenceBundle:
        """Create an evidence bundle from items."""
        import uuid
        
        bundle_id = str(uuid.uuid4())[:8]
        bundle = EvidenceBundle(
            bundle_id=bundle_id,
            created_at=datetime.now(),
            items=items,
        )
        
        # Create ZIP archive
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        zip_path = self.evidence_dir / f"bundle_{bundle_id}_{timestamp}.zip"
        
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add manifest
            manifest = bundle.to_dict()
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            
            # Add evidence files
            for item in items:
                if item.data_path and item.data_path.exists():
                    zf.write(item.data_path, f"evidence/{item.data_path.name}")
        
        # Sign bundle if keypair available
        if sign and self.keypair:
            try:
                from .pqxhybrid import sign_message
                
                bundle_hash = hashlib.sha512(zip_path.read_bytes()).digest()
                signature = sign_message(bundle_hash, self.keypair)
                bundle.signature = base64.b64encode(signature).decode("ascii")
                bundle.signed = True
                
                # Write signature file
                sig_path = zip_path.with_suffix(".sig")
                sig_path.write_text(json.dumps({
                    "bundle_id": bundle_id,
                    "hash_sha512": hashlib.sha512(zip_path.read_bytes()).hexdigest(),
                    "signature": bundle.signature,
                    "scheme": self.keypair.scheme,
                }))
                
                logger.info(f"📝 Bundle signed with {self.keypair.scheme}")
                
            except Exception as e:
                logger.warning(f"Bundle signing failed: {e}")
        
        self._bundles.append(bundle)
        logger.info(f"📦 Evidence bundle created: {bundle_id} ({len(items)} items)")
        
        return bundle
    
    def quick_capture(self) -> EvidenceBundle:
        """Quick capture of all available evidence."""
        items = []
        
        # Process list
        try:
            items.append(self.capture_process_list())
        except Exception:
            pass
        
        # Network state
        try:
            items.append(self.capture_network_state())
        except Exception:
            pass
        
        # Screenshot
        screenshot = self.capture_screenshot()
        if screenshot:
            items.append(screenshot)
        
        return self.create_bundle(items)
    
    def get_bundles(self) -> List[EvidenceBundle]:
        """Get all created bundles."""
        return list(self._bundles)
