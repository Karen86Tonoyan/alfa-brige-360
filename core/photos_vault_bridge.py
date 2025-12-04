#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# ALFA CORE v2.0 — PHOTOS VAULT BRIDGE — Rust ↔ Python Integration
# ═══════════════════════════════════════════════════════════════════════════
"""
Photos Vault Bridge: Integracja modułu Rust z ekosystemem Python ALFA.

Metody integracji:
1. FFI (Foreign Function Interface) - przez cdylib
2. CLI subprocess - przez alfa-photos binary
3. PyO3 bindings - natywne Python bindings (future)

Ten moduł zapewnia:
- Unified API dla Photos Vault z Pythona
- Integrację z EventBus (eventy photo_imported, photo_deleted, etc.)
- Integrację z SecureExecutor (walidacja operacji)
- Async wrapper dla operacji I/O
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# ALFA Core integrations
try:
    from .event_bus import get_bus, publish, Priority
    HAS_EVENTBUS = True
except ImportError:
    get_bus = lambda: None
    publish = lambda *a, **k: None
    Priority = None
    HAS_EVENTBUS = False

try:
    from .secure_executor import SecureExecutor, SecurityLevel
    HAS_EXECUTOR = True
except ImportError:
    SecureExecutor = None
    SecurityLevel = None
    HAS_EXECUTOR = False

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

LOG = logging.getLogger("alfa.photos_vault")

# Path to Rust binary
VAULT_BINARY = os.environ.get(
    "ALFA_PHOTOS_VAULT_BIN",
    str(Path(__file__).parent.parent / "alfa_photos_vault" / "target" / "release" / "alfa-photos")
)

# Default vault path
DEFAULT_VAULT_PATH = os.environ.get(
    "ALFA_PHOTOS_VAULT_PATH",
    str(Path.home() / ".alfa" / "photos_vault")
)


# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

class VaultState(Enum):
    """Stan vault."""
    CLOSED = "closed"
    LOCKED = "locked"
    UNLOCKED = "unlocked"


@dataclass
class PhotoInfo:
    """Informacje o zdjęciu."""
    id: str
    filename: str
    size: int
    imported_at: str
    tags: List[str] = field(default_factory=list)
    hidden: bool = False
    favorite: bool = False


@dataclass
class VaultStats:
    """Statystyki vault."""
    total_photos: int
    total_size: int
    hidden_count: int
    favorite_count: int
    tag_count: int


@dataclass
class OperationResult:
    """Wynik operacji."""
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# PHOTOS VAULT BRIDGE
# ═══════════════════════════════════════════════════════════════════════════

class PhotosVaultBridge:
    """
    Bridge do ALFA Photos Vault (Rust).
    
    Używa subprocess do komunikacji z binarką Rust.
    W przyszłości: PyO3 dla natywnych bindingów.
    """
    
    def __init__(
        self,
        vault_path: str = DEFAULT_VAULT_PATH,
        binary_path: str = VAULT_BINARY,
    ):
        """
        Inicjalizacja bridge.
        
        Args:
            vault_path: Ścieżka do vault
            binary_path: Ścieżka do binarki Rust
        """
        self.vault_path = Path(vault_path)
        self.binary_path = Path(binary_path)
        self.state = VaultState.CLOSED
        self._pin: Optional[str] = None
        
        # Check if binary exists
        if not self.binary_path.exists():
            LOG.warning(f"Photos Vault binary not found at {self.binary_path}")
            LOG.info("Run 'cargo build --release' in alfa_photos_vault directory")
    
    def _run_command(
        self,
        *args: str,
        input_data: Optional[bytes] = None,
        timeout: int = 60,
    ) -> Tuple[int, str, str]:
        """
        Wykonaj komendę vault.
        
        Args:
            *args: Argumenty komendy
            input_data: Dane do stdin
            timeout: Timeout w sekundach
            
        Returns:
            Tuple (exit_code, stdout, stderr)
        """
        cmd = [
            str(self.binary_path),
            "--vault", str(self.vault_path),
            *args
        ]
        
        try:
            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                timeout=timeout,
                text=True,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Timeout expired"
        except FileNotFoundError:
            return -1, "", f"Binary not found: {self.binary_path}"
        except Exception as e:
            return -1, "", str(e)
    
    async def _run_command_async(
        self,
        *args: str,
        input_data: Optional[bytes] = None,
        timeout: int = 60,
    ) -> Tuple[int, str, str]:
        """Async wrapper dla _run_command."""
        return await asyncio.to_thread(
            self._run_command,
            *args,
            input_data=input_data,
            timeout=timeout
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # VAULT MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════
    
    async def create(self, pin: str) -> OperationResult:
        """
        Utwórz nowy vault.
        
        Args:
            pin: PIN do vault
            
        Returns:
            OperationResult
        """
        code, out, err = await self._run_command_async("create", "--pin", pin)
        
        if code == 0:
            self._pin = pin
            self.state = VaultState.UNLOCKED
            
            if HAS_EVENTBUS:
                publish("vault_created", {"path": str(self.vault_path)})
            
            return OperationResult(
                success=True,
                message="Vault created successfully",
                data={"path": str(self.vault_path)}
            )
        
        return OperationResult(
            success=False,
            message="Failed to create vault",
            error=err or out
        )
    
    async def open(self, pin: str) -> OperationResult:
        """
        Otwórz istniejący vault.
        
        Args:
            pin: PIN do vault
            
        Returns:
            OperationResult
        """
        # Verify vault exists
        if not self.vault_path.exists():
            return OperationResult(
                success=False,
                message="Vault does not exist",
                error=f"Path not found: {self.vault_path}"
            )
        
        # Try to unlock
        code, out, err = await self._run_command_async("unlock", "--pin", pin)
        
        if code == 0:
            self._pin = pin
            self.state = VaultState.UNLOCKED
            
            if HAS_EVENTBUS:
                publish("vault_opened", {"path": str(self.vault_path)})
            
            return OperationResult(
                success=True,
                message="Vault opened successfully"
            )
        
        return OperationResult(
            success=False,
            message="Failed to open vault",
            error=err or out
        )
    
    async def lock(self) -> OperationResult:
        """Zablokuj vault."""
        code, out, err = await self._run_command_async("lock")
        
        if code == 0:
            self._pin = None
            self.state = VaultState.LOCKED
            
            if HAS_EVENTBUS:
                publish("vault_locked", {"path": str(self.vault_path)})
            
            return OperationResult(
                success=True,
                message="Vault locked"
            )
        
        return OperationResult(
            success=False,
            message="Failed to lock vault",
            error=err or out
        )
    
    async def close(self) -> OperationResult:
        """Zamknij vault."""
        if self.state == VaultState.UNLOCKED:
            await self.lock()
        
        self._pin = None
        self.state = VaultState.CLOSED
        
        return OperationResult(
            success=True,
            message="Vault closed"
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # PHOTO OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    async def import_photo(
        self,
        photo_path: str,
        tags: Optional[List[str]] = None,
    ) -> OperationResult:
        """
        Importuj zdjęcie do vault.
        
        Args:
            photo_path: Ścieżka do zdjęcia
            tags: Opcjonalne tagi
            
        Returns:
            OperationResult z ID zdjęcia
        """
        if self.state != VaultState.UNLOCKED:
            return OperationResult(
                success=False,
                message="Vault is not unlocked"
            )
        
        args = ["import", photo_path, "--pin", self._pin]
        
        if tags:
            args.extend(["--tags", ",".join(tags)])
        
        code, out, err = await self._run_command_async(*args)
        
        if code == 0:
            # Parse photo ID from output
            photo_id = out.strip().split(":")[-1].strip() if ":" in out else out.strip()
            
            if HAS_EVENTBUS:
                publish("photo_imported", {
                    "photo_id": photo_id,
                    "source": photo_path,
                    "tags": tags or []
                })
            
            return OperationResult(
                success=True,
                message="Photo imported",
                data={"photo_id": photo_id}
            )
        
        return OperationResult(
            success=False,
            message="Failed to import photo",
            error=err or out
        )
    
    async def export_photo(
        self,
        photo_id: str,
        output_path: str,
    ) -> OperationResult:
        """
        Eksportuj zdjęcie z vault.
        
        Args:
            photo_id: ID zdjęcia
            output_path: Ścieżka docelowa
            
        Returns:
            OperationResult
        """
        if self.state != VaultState.UNLOCKED:
            return OperationResult(
                success=False,
                message="Vault is not unlocked"
            )
        
        code, out, err = await self._run_command_async(
            "export", photo_id, output_path, "--pin", self._pin
        )
        
        if code == 0:
            if HAS_EVENTBUS:
                publish("photo_exported", {
                    "photo_id": photo_id,
                    "destination": output_path
                })
            
            return OperationResult(
                success=True,
                message="Photo exported",
                data={"path": output_path}
            )
        
        return OperationResult(
            success=False,
            message="Failed to export photo",
            error=err or out
        )
    
    async def delete_photo(self, photo_id: str) -> OperationResult:
        """
        Usuń zdjęcie z vault.
        
        Args:
            photo_id: ID zdjęcia
            
        Returns:
            OperationResult
        """
        if self.state != VaultState.UNLOCKED:
            return OperationResult(
                success=False,
                message="Vault is not unlocked"
            )
        
        code, out, err = await self._run_command_async(
            "delete", photo_id, "--pin", self._pin
        )
        
        if code == 0:
            if HAS_EVENTBUS:
                publish("photo_deleted", {"photo_id": photo_id})
            
            return OperationResult(
                success=True,
                message="Photo deleted"
            )
        
        return OperationResult(
            success=False,
            message="Failed to delete photo",
            error=err or out
        )
    
    async def get_thumbnail(self, photo_id: str) -> Optional[bytes]:
        """
        Pobierz miniaturkę zdjęcia.
        
        Args:
            photo_id: ID zdjęcia
            
        Returns:
            Bytes miniaturki lub None
        """
        if self.state != VaultState.UNLOCKED:
            return None
        
        # Export to temp file and read
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            code, out, err = await self._run_command_async(
                "thumbnail", photo_id, tmp_path, "--pin", self._pin
            )
            
            if code == 0 and Path(tmp_path).exists():
                with open(tmp_path, "rb") as f:
                    return f.read()
        finally:
            if Path(tmp_path).exists():
                os.unlink(tmp_path)
        
        return None
    
    async def list_photos(
        self,
        tags: Optional[List[str]] = None,
        hidden: bool = False,
    ) -> List[PhotoInfo]:
        """
        Lista zdjęć w vault.
        
        Args:
            tags: Filtruj po tagach
            hidden: Czy pokazać ukryte
            
        Returns:
            Lista PhotoInfo
        """
        if self.state != VaultState.UNLOCKED:
            return []
        
        args = ["list", "--pin", self._pin, "--format", "json"]
        
        if tags:
            args.extend(["--tags", ",".join(tags)])
        if hidden:
            args.append("--hidden")
        
        code, out, err = await self._run_command_async(*args)
        
        if code == 0 and out:
            try:
                data = json.loads(out)
                return [
                    PhotoInfo(
                        id=p.get("id", ""),
                        filename=p.get("filename", ""),
                        size=p.get("size", 0),
                        imported_at=p.get("imported_at", ""),
                        tags=p.get("tags", []),
                        hidden=p.get("hidden", False),
                        favorite=p.get("favorite", False),
                    )
                    for p in data.get("photos", [])
                ]
            except json.JSONDecodeError:
                LOG.error(f"Failed to parse JSON: {out[:100]}")
        
        return []
    
    async def get_stats(self) -> Optional[VaultStats]:
        """
        Pobierz statystyki vault.
        
        Returns:
            VaultStats lub None
        """
        if self.state != VaultState.UNLOCKED:
            return None
        
        code, out, err = await self._run_command_async(
            "stats", "--pin", self._pin, "--format", "json"
        )
        
        if code == 0 and out:
            try:
                data = json.loads(out)
                return VaultStats(
                    total_photos=data.get("total_photos", 0),
                    total_size=data.get("total_size", 0),
                    hidden_count=data.get("hidden_count", 0),
                    favorite_count=data.get("favorite_count", 0),
                    tag_count=data.get("tag_count", 0),
                )
            except json.JSONDecodeError:
                pass
        
        return None
    
    # ═══════════════════════════════════════════════════════════════════════
    # MAINTENANCE
    # ═══════════════════════════════════════════════════════════════════════
    
    async def reset(self) -> OperationResult:
        """
        Reset vault (czyści cache, odbudowuje index).
        
        Returns:
            OperationResult
        """
        if self.state != VaultState.UNLOCKED:
            return OperationResult(
                success=False,
                message="Vault is not unlocked"
            )
        
        code, out, err = await self._run_command_async(
            "reset", "--pin", self._pin
        )
        
        if code == 0:
            if HAS_EVENTBUS:
                publish("vault_reset", {"path": str(self.vault_path)})
            
            return OperationResult(
                success=True,
                message="Vault reset complete",
                data={"report": out}
            )
        
        return OperationResult(
            success=False,
            message="Failed to reset vault",
            error=err or out
        )
    
    async def verify_integrity(self) -> OperationResult:
        """
        Weryfikuj integralność vault.
        
        Returns:
            OperationResult z raportem
        """
        if self.state != VaultState.UNLOCKED:
            return OperationResult(
                success=False,
                message="Vault is not unlocked"
            )
        
        code, out, err = await self._run_command_async(
            "verify", "--pin", self._pin
        )
        
        if code == 0:
            return OperationResult(
                success=True,
                message="Integrity check passed",
                data={"report": out}
            )
        
        return OperationResult(
            success=False,
            message="Integrity check failed",
            error=err or out
        )
    
    async def rotate_keys(self, new_pin: str) -> OperationResult:
        """
        Rotuj klucze vault.
        
        Args:
            new_pin: Nowy PIN
            
        Returns:
            OperationResult
        """
        if self.state != VaultState.UNLOCKED:
            return OperationResult(
                success=False,
                message="Vault is not unlocked"
            )
        
        code, out, err = await self._run_command_async(
            "rotate", "--old-pin", self._pin, "--new-pin", new_pin
        )
        
        if code == 0:
            self._pin = new_pin
            
            if HAS_EVENTBUS:
                publish("keys_rotated", {"path": str(self.vault_path)})
            
            return OperationResult(
                success=True,
                message="Keys rotated successfully"
            )
        
        return OperationResult(
            success=False,
            message="Failed to rotate keys",
            error=err or out
        )


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON & FACTORY
# ═══════════════════════════════════════════════════════════════════════════

_default_bridge: Optional[PhotosVaultBridge] = None


def get_photos_vault(
    vault_path: str = DEFAULT_VAULT_PATH,
) -> PhotosVaultBridge:
    """
    Pobierz instancję PhotosVaultBridge (singleton per path).
    
    Args:
        vault_path: Ścieżka do vault
        
    Returns:
        PhotosVaultBridge
    """
    global _default_bridge
    
    if _default_bridge is None or str(_default_bridge.vault_path) != vault_path:
        _default_bridge = PhotosVaultBridge(vault_path)
    
    return _default_bridge


# ═══════════════════════════════════════════════════════════════════════════
# CLI TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    async def main():
        print("📸 PHOTOS VAULT BRIDGE - Test\n")
        
        vault = get_photos_vault()
        print(f"Vault path: {vault.vault_path}")
        print(f"Binary path: {vault.binary_path}")
        print(f"Binary exists: {vault.binary_path.exists()}")
        
        if not vault.binary_path.exists():
            print("\n⚠️  Build the Rust binary first:")
            print("   cd alfa_photos_vault && cargo build --release")
            return
        
        # Test create
        print("\n🔨 Creating vault...")
        result = await vault.create("123456")
        print(f"   {result.message}")
        
        if result.success:
            # Test stats
            stats = await vault.get_stats()
            if stats:
                print(f"\n📊 Stats: {stats.total_photos} photos")
            
            # Test lock
            print("\n🔒 Locking vault...")
            await vault.lock()
            print("   Vault locked")
        
        print("\n✅ Test complete")
    
    asyncio.run(main())
