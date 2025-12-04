#!/usr/bin/env python3
"""
ALFA Disk Scanner

Low-level disk scanning utilities for forensics:
- Partition enumeration
- Block device access
- Raw disk reading

Author: ALFA System / Karen86Tonoyan
Version: 1.0.0
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# ═══════════════════════════════════════════════════════════════════════════
# PARTITION INFO
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PartitionInfo:
    """Information about a disk partition."""
    device: str          # e.g., /dev/sda1 or \\.\PhysicalDrive0
    name: str            # Human-readable name
    size_bytes: int
    size_human: str      # e.g., "256G"
    filesystem: str      # e.g., "ext4", "ntfs"
    mountpoint: str      # e.g., "/home" or "C:\"
    is_mounted: bool
    is_system: bool      # Contains OS
    
    def to_dict(self) -> dict:
        return {
            "device": self.device,
            "name": self.name,
            "size_bytes": self.size_bytes,
            "size_human": self.size_human,
            "filesystem": self.filesystem,
            "mountpoint": self.mountpoint,
            "is_mounted": self.is_mounted,
            "is_system": self.is_system,
        }


# ═══════════════════════════════════════════════════════════════════════════
# LINUX SCANNER
# ═══════════════════════════════════════════════════════════════════════════

def _list_partitions_linux() -> List[PartitionInfo]:
    """List partitions on Linux using lsblk."""
    partitions = []
    
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,PKNAME"],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            return partitions
        
        data = json.loads(result.stdout)
        
        def process_device(device: dict, parent_name: str = ""):
            if device.get("type") == "part":
                size_bytes = int(device.get("size", 0))
                mountpoint = device.get("mountpoint", "") or ""
                
                partitions.append(PartitionInfo(
                    device=f"/dev/{device['name']}",
                    name=device["name"],
                    size_bytes=size_bytes,
                    size_human=_format_size(size_bytes),
                    filesystem=device.get("fstype", "") or "unknown",
                    mountpoint=mountpoint,
                    is_mounted=bool(mountpoint),
                    is_system=mountpoint in ["/", "/boot", "/boot/efi"],
                ))
            
            for child in device.get("children", []):
                process_device(child, device["name"])
        
        for device in data.get("blockdevices", []):
            process_device(device)
            
    except Exception:
        pass
    
    return partitions


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ["B", "K", "M", "G", "T"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}P"


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS SCANNER
# ═══════════════════════════════════════════════════════════════════════════

def _list_partitions_windows() -> List[PartitionInfo]:
    """List partitions on Windows using WMI."""
    partitions = []
    
    try:
        # Use wmic for partition info
        result = subprocess.run(
            ["wmic", "logicaldisk", "get", "DeviceID,FileSystem,Size,VolumeName", "/format:csv"],
            capture_output=True,
            text=True,
            shell=True,
        )
        
        if result.returncode != 0:
            return partitions
        
        lines = result.stdout.strip().split("\n")
        
        for line in lines[1:]:  # Skip header
            if not line.strip():
                continue
            
            parts = line.strip().split(",")
            if len(parts) >= 4:
                drive_letter = parts[1]  # e.g., "C:"
                filesystem = parts[2] or "unknown"
                size_str = parts[3]
                volume_name = parts[4] if len(parts) > 4 else ""
                
                try:
                    size_bytes = int(size_str) if size_str else 0
                except ValueError:
                    size_bytes = 0
                
                partitions.append(PartitionInfo(
                    device=f"\\\\.\\{drive_letter}",
                    name=volume_name or drive_letter,
                    size_bytes=size_bytes,
                    size_human=_format_size(size_bytes),
                    filesystem=filesystem,
                    mountpoint=drive_letter + "\\",
                    is_mounted=True,
                    is_system=drive_letter.upper() == "C:",
                ))
                
    except Exception:
        pass
    
    return partitions


# ═══════════════════════════════════════════════════════════════════════════
# CROSS-PLATFORM API
# ═══════════════════════════════════════════════════════════════════════════

def list_partitions() -> List[PartitionInfo]:
    """List all partitions on the system."""
    if sys.platform == "linux":
        return _list_partitions_linux()
    elif sys.platform == "win32":
        return _list_partitions_windows()
    else:
        return []


class DiskScanner:
    """
    Cross-platform disk scanner.
    
    Provides safe access to disk blocks for forensics.
    """
    
    def __init__(self):
        self.partitions = list_partitions()
    
    def refresh(self) -> List[PartitionInfo]:
        """Refresh partition list."""
        self.partitions = list_partitions()
        return self.partitions
    
    def get_partition(self, identifier: str) -> Optional[PartitionInfo]:
        """
        Get partition by device path or mountpoint.
        
        Examples:
            get_partition("/dev/sda1")
            get_partition("C:")
            get_partition("/home")
        """
        for p in self.partitions:
            if p.device == identifier:
                return p
            if p.mountpoint == identifier:
                return p
            if p.name == identifier:
                return p
        return None
    
    def is_safe_to_scan(self, partition: PartitionInfo) -> tuple[bool, str]:
        """
        Check if partition is safe to scan.
        
        Returns: (is_safe, reason)
        """
        if partition.is_system:
            return False, "System partition - scanning may cause instability"
        
        if partition.is_mounted:
            return False, f"Partition mounted at {partition.mountpoint} - unmount first for reliable results"
        
        return True, "OK to scan"
    
    def read_block(
        self,
        partition: PartitionInfo,
        block_number: int,
        block_size: int = 4096,
    ) -> Optional[bytes]:
        """
        Read single block from partition.
        
        Requires elevated privileges.
        """
        try:
            with open(partition.device, "rb") as f:
                f.seek(block_number * block_size)
                return f.read(block_size)
        except PermissionError:
            return None
        except Exception:
            return None
    
    def search_blocks(
        self,
        partition: PartitionInfo,
        pattern: bytes,
        start_block: int = 0,
        max_blocks: int = 1000000,
        block_size: int = 4096,
    ) -> List[tuple[int, int]]:
        """
        Search for pattern in partition blocks.
        
        Returns: List of (block_number, offset_in_block)
        
        WARNING: This is slow for large partitions.
        Use RecoverPy for production scanning.
        """
        matches = []
        
        try:
            with open(partition.device, "rb") as f:
                f.seek(start_block * block_size)
                
                for block_num in range(start_block, start_block + max_blocks):
                    data = f.read(block_size)
                    if not data:
                        break
                    
                    pos = data.find(pattern)
                    if pos != -1:
                        matches.append((block_num, pos))
                        
        except Exception:
            pass
        
        return matches


# ═══════════════════════════════════════════════════════════════════════════
# CLI HELPER
# ═══════════════════════════════════════════════════════════════════════════

def print_partition_table():
    """Print partition table to stdout."""
    partitions = list_partitions()
    
    if not partitions:
        print("No partitions found or insufficient privileges")
        return
    
    print(f"{'Device':<20} {'Size':>10} {'FS':<10} {'Mount':<15} {'Status'}")
    print("-" * 70)
    
    for p in partitions:
        status = "SYSTEM" if p.is_system else ("mounted" if p.is_mounted else "unmounted")
        print(f"{p.device:<20} {p.size_human:>10} {p.filesystem:<10} {p.mountpoint:<15} {status}")


if __name__ == "__main__":
    print_partition_table()
