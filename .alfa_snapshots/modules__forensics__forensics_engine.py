#!/usr/bin/env python3
"""
ALFA Forensics Engine

Core forensics functionality:
- RecoverPy integration for Linux block scanning
- Pattern-based file recovery
- Encrypted results handling
- Audit logging

Author: ALFA System / Karen86Tonoyan
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

# ═══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════

class ScanStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BlockMatch:
    """Single block match from disk scan."""
    block_number: int
    offset: int
    content_preview: str  # First 256 bytes
    content_full: Optional[bytes] = None
    match_score: float = 0.0
    recovered: bool = False
    recovery_path: Optional[str] = None


@dataclass
class ForensicsScanResult:
    """Results from forensic scan operation."""
    scan_id: str
    partition: str
    search_pattern: str
    status: ScanStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    blocks_scanned: int = 0
    matches: List[BlockMatch] = field(default_factory=list)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "partition": self.partition,
            "search_pattern": self.search_pattern,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "blocks_scanned": self.blocks_scanned,
            "matches_count": len(self.matches),
            "matches": [
                {
                    "block": m.block_number,
                    "offset": m.offset,
                    "preview": m.content_preview[:100] + "..." if len(m.content_preview) > 100 else m.content_preview,
                    "score": m.match_score,
                    "recovered": m.recovered,
                }
                for m in self.matches
            ],
            "error": self.error_message,
        }


# ═══════════════════════════════════════════════════════════════════════════
# RECOVERPY WRAPPER
# ═══════════════════════════════════════════════════════════════════════════

class RecoverPyWrapper:
    """
    Wrapper for RecoverPy tool.
    
    RecoverPy scans raw disk blocks for deleted/overwritten files.
    Requires root privileges on Linux.
    """
    
    def __init__(self, output_dir: str = "/tmp/alfa_forensics"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._check_available()
    
    def _check_available(self) -> bool:
        """Check if RecoverPy is installed."""
        if sys.platform != "linux":
            self.available = False
            self.unavailable_reason = "RecoverPy requires Linux"
            return False
        
        try:
            result = subprocess.run(
                ["which", "recoverpy"],
                capture_output=True,
                text=True,
            )
            self.available = result.returncode == 0
            if not self.available:
                self.unavailable_reason = "RecoverPy not installed. Run: pip install recoverpy"
        except Exception as e:
            self.available = False
            self.unavailable_reason = str(e)
        
        return self.available
    
    def list_partitions(self) -> List[Dict[str, str]]:
        """List available partitions."""
        if sys.platform != "linux":
            return []
        
        try:
            result = subprocess.run(
                ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                partitions = []
                for device in data.get("blockdevices", []):
                    if device.get("type") == "part":
                        partitions.append({
                            "name": f"/dev/{device['name']}",
                            "size": device.get("size", "unknown"),
                            "mountpoint": device.get("mountpoint", ""),
                        })
                    for child in device.get("children", []):
                        if child.get("type") == "part":
                            partitions.append({
                                "name": f"/dev/{child['name']}",
                                "size": child.get("size", "unknown"),
                                "mountpoint": child.get("mountpoint", ""),
                            })
                return partitions
        except Exception:
            pass
        return []
    
    async def scan_partition(
        self,
        partition: str,
        search_string: str,
        block_size: int = 512,
        max_results: int = 100,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> ForensicsScanResult:
        """
        Scan partition for string pattern.
        
        NOTE: This is a simplified implementation. 
        For production, use the actual RecoverPy tool interactively.
        """
        import uuid
        
        scan_id = str(uuid.uuid4())[:8]
        result = ForensicsScanResult(
            scan_id=scan_id,
            partition=partition,
            search_pattern=search_string,
            status=ScanStatus.RUNNING,
            started_at=datetime.now(),
        )
        
        if not self.available:
            result.status = ScanStatus.FAILED
            result.error_message = self.unavailable_reason
            result.completed_at = datetime.now()
            return result
        
        # Check if we have root privileges
        if os.geteuid() != 0:
            result.status = ScanStatus.FAILED
            result.error_message = "Root privileges required for disk scanning"
            result.completed_at = datetime.now()
            return result
        
        try:
            # Use grep for raw block scanning (simplified)
            # Real implementation should use RecoverPy's block scanner
            cmd = [
                "grep", "-a", "-b", "-o",
                "-P", f".{{0,50}}{search_string}.{{0,50}}",
                partition
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if stdout:
                lines = stdout.decode("utf-8", errors="replace").split("\n")
                for line in lines[:max_results]:
                    if ":" in line:
                        offset_str, content = line.split(":", 1)
                        try:
                            offset = int(offset_str)
                            block_num = offset // block_size
                            
                            result.matches.append(BlockMatch(
                                block_number=block_num,
                                offset=offset,
                                content_preview=content[:256],
                                match_score=1.0 if search_string in content else 0.5,
                            ))
                        except ValueError:
                            continue
            
            result.status = ScanStatus.COMPLETED
            result.blocks_scanned = result.matches[-1].block_number if result.matches else 0
            
        except Exception as e:
            result.status = ScanStatus.FAILED
            result.error_message = str(e)
        
        result.completed_at = datetime.now()
        return result
    
    def recover_block(
        self,
        partition: str,
        block_number: int,
        block_size: int = 4096,
        output_file: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Recover specific block from partition.
        """
        if not self.available or os.geteuid() != 0:
            return None
        
        try:
            with open(partition, "rb") as f:
                f.seek(block_number * block_size)
                data = f.read(block_size)
            
            if output_file:
                output_path = self.output_dir / output_file
                with open(output_path, "wb") as f:
                    f.write(data)
            
            return data
            
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════════════════
# FORENSICS ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class ForensicsEngine:
    """
    Main forensics engine for ALFA.
    
    Provides:
    - Disk block scanning
    - Pattern-based file recovery
    - Secure logging of all operations
    - Integration with ALFA encryption
    """
    
    # Known patterns for ALFA recovery
    ALFA_PATTERNS = {
        "seed": [
            "ALFA:SEED",
            "ALFA_SEED=",
            "seed_encrypted",
            '"version": "4.0-ARMORED"',
        ],
        "config": [
            "alfa_bridge.toml",
            "[agents.alfa]",
            "ALFA_CONFIG",
        ],
        "keys": [
            "-----BEGIN",
            "kdf:",
            "nonce:",
            "ct:",
        ],
    }
    
    def __init__(
        self,
        output_dir: str = "/tmp/alfa_forensics",
        log_callback: Optional[Callable[[str, Dict], None]] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_callback = log_callback
        self.recoverpy = RecoverPyWrapper(output_dir)
        self.scan_history: List[ForensicsScanResult] = []
    
    def _log(self, action: str, data: Dict[str, Any]) -> None:
        """Log forensics operation."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            **data,
        }
        
        # Write to local log
        log_file = self.output_dir / "forensics.log"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        # Callback for ALFA integration
        if self.log_callback:
            self.log_callback(action, data)
    
    def check_system(self) -> Dict[str, Any]:
        """Check system readiness for forensics."""
        return {
            "platform": sys.platform,
            "is_linux": sys.platform == "linux",
            "is_root": os.geteuid() == 0 if sys.platform != "win32" else False,
            "recoverpy_available": self.recoverpy.available,
            "recoverpy_reason": getattr(self.recoverpy, "unavailable_reason", None),
            "partitions": self.recoverpy.list_partitions(),
            "output_dir": str(self.output_dir),
        }
    
    async def scan_for_alfa_seed(
        self,
        partition: str,
        custom_patterns: Optional[List[str]] = None,
    ) -> ForensicsScanResult:
        """
        Scan for ALFA seed patterns on partition.
        """
        patterns = custom_patterns or self.ALFA_PATTERNS["seed"]
        
        self._log("scan_start", {
            "partition": partition,
            "type": "alfa_seed",
            "patterns": patterns,
        })
        
        # Scan for first matching pattern
        for pattern in patterns:
            result = await self.recoverpy.scan_partition(
                partition=partition,
                search_string=pattern,
                max_results=50,
            )
            
            if result.matches:
                self._log("scan_matches", {
                    "scan_id": result.scan_id,
                    "pattern": pattern,
                    "matches_count": len(result.matches),
                })
                self.scan_history.append(result)
                return result
        
        # No matches found
        result = ForensicsScanResult(
            scan_id="no-match",
            partition=partition,
            search_pattern=str(patterns),
            status=ScanStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )
        self.scan_history.append(result)
        return result
    
    async def scan_custom(
        self,
        partition: str,
        search_string: str,
    ) -> ForensicsScanResult:
        """Scan for custom string pattern."""
        self._log("scan_custom", {
            "partition": partition,
            "pattern": search_string,
        })
        
        result = await self.recoverpy.scan_partition(
            partition=partition,
            search_string=search_string,
        )
        
        self.scan_history.append(result)
        return result
    
    def recover_match(
        self,
        result: ForensicsScanResult,
        match_index: int,
        output_name: Optional[str] = None,
    ) -> Optional[bytes]:
        """Recover block from scan match."""
        if match_index >= len(result.matches):
            return None
        
        match = result.matches[match_index]
        
        output_file = output_name or f"recovered_{result.scan_id}_{match_index}.bin"
        
        data = self.recoverpy.recover_block(
            partition=result.partition,
            block_number=match.block_number,
            output_file=output_file,
        )
        
        if data:
            match.recovered = True
            match.recovery_path = str(self.output_dir / output_file)
            
            self._log("recovery_success", {
                "scan_id": result.scan_id,
                "block": match.block_number,
                "output": match.recovery_path,
            })
        
        return data
    
    def get_scan_history(self) -> List[Dict[str, Any]]:
        """Get history of all scans."""
        return [r.to_dict() for r in self.scan_history]
    
    def clear_history(self) -> None:
        """Clear scan history and recovered files."""
        self.scan_history.clear()
        
        for f in self.output_dir.glob("recovered_*"):
            f.unlink()
        
        self._log("history_cleared", {})


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS ALTERNATIVE
# ═══════════════════════════════════════════════════════════════════════════

class WindowsForensics:
    """
    Windows alternative for forensics operations.
    Uses different tools available on Windows.
    """
    
    @staticmethod
    def check_available_tools() -> Dict[str, bool]:
        """Check which forensics tools are available on Windows."""
        tools = {
            "vss": False,  # Volume Shadow Copy
            "recuva": False,
            "testdisk": False,
        }
        
        # Check for Volume Shadow Copy service
        try:
            result = subprocess.run(
                ["vssadmin", "list", "shadows"],
                capture_output=True,
                shell=True,
            )
            tools["vss"] = result.returncode == 0
        except Exception:
            pass
        
        return tools
    
    @staticmethod
    def list_shadow_copies() -> List[Dict[str, str]]:
        """List available VSS shadow copies."""
        shadows = []
        
        try:
            result = subprocess.run(
                ["vssadmin", "list", "shadows"],
                capture_output=True,
                text=True,
                shell=True,
            )
            
            if result.returncode == 0:
                # Parse output
                current = {}
                for line in result.stdout.split("\n"):
                    if "Shadow Copy ID:" in line:
                        if current:
                            shadows.append(current)
                        current = {"id": line.split(":")[-1].strip()}
                    elif "Shadow Copy Volume:" in line:
                        current["volume"] = line.split(":")[-1].strip()
                    elif "Creation Time:" in line:
                        current["created"] = line.split(":", 1)[-1].strip()
                
                if current:
                    shadows.append(current)
        except Exception:
            pass
        
        return shadows
    
    @staticmethod
    async def search_in_shadow(
        shadow_path: str,
        search_pattern: str,
        file_pattern: str = "*",
    ) -> List[str]:
        """Search for pattern in shadow copy files."""
        matches = []
        
        try:
            cmd = f'findstr /S /I /M "{search_pattern}" "{shadow_path}\\{file_pattern}"'
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, _ = await process.communicate()
            
            if stdout:
                matches = stdout.decode("utf-8", errors="replace").strip().split("\n")
        except Exception:
            pass
        
        return matches
