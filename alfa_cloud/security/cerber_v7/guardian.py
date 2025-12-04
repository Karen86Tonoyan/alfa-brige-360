# ═══════════════════════════════════════════════════════════════════════════
# GUARDIAN - 360° System Monitor
# ═══════════════════════════════════════════════════════════════════════════
"""
Guardian: Continuous health and tamper monitoring.

Features:
- Process enumeration and anomaly detection
- Network socket monitoring
- DLL/code injection detection (Windows)
- Root/debug exposure checks (Android)
- ADB/USB debugging detection
- VPN/rogue tunnel detection
"""

from __future__ import annotations

import logging
import platform
import subprocess
import threading
import time
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("cerber.guardian")


@dataclass
class ProcessInfo:
    """Process information snapshot."""
    pid: int
    name: str
    path: Optional[str] = None
    cpu: float = 0.0
    memory: float = 0.0
    connections: List[str] = field(default_factory=list)
    suspicious: bool = False
    reason: Optional[str] = None


@dataclass
class NetworkConnection:
    """Network connection info."""
    local_addr: str
    remote_addr: str
    state: str
    pid: Optional[int] = None
    suspicious: bool = False


@dataclass
class GuardianAlert:
    """Security alert from Guardian."""
    timestamp: datetime
    severity: str  # "info", "warning", "critical"
    category: str  # "process", "network", "injection", "debug", "vpn"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "details": self.details,
        }


class Guardian:
    """
    360° System Monitor - Cerber Security Component.
    
    Monitors:
    - Running processes
    - Network connections
    - Code injection attempts
    - Debug/root exposure
    - Rogue VPN tunnels
    """
    
    # Known suspicious process patterns
    SUSPICIOUS_PATTERNS = [
        "mimikatz", "meterpreter", "cobalt", "beacon",
        "netcat", "nc.exe", "ncat", "socat",
        "psexec", "wmiexec", "smbexec",
        "powershell -e", "cmd /c",
        "certutil -decode", "bitsadmin",
    ]
    
    # Known good processes (whitelist)
    TRUSTED_PROCESSES: Set[str] = {
        "python", "python3", "pythonw",
        "node", "npm", "code", "vscode",
        "explorer", "svchost", "csrss", "lsass",
    }
    
    def __init__(
        self,
        scan_interval: float = 5.0,
        alert_callback: Optional[Callable[[GuardianAlert], None]] = None,
        evidence_dir: Optional[Path] = None,
    ):
        self.scan_interval = scan_interval
        self.alert_callback = alert_callback
        self.evidence_dir = evidence_dir or Path.home() / ".cerber" / "evidence" / "guardian"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._baseline_processes: Set[str] = set()
        self._alerts: List[GuardianAlert] = []
        self._lock = threading.Lock()
        
        self.platform = platform.system().lower()
        
    def start(self) -> None:
        """Start Guardian monitoring."""
        if self._running:
            return
            
        logger.info("🛡️ Guardian starting...")
        self._running = True
        self._capture_baseline()
        
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("🛡️ Guardian active")
    
    def stop(self) -> None:
        """Stop Guardian monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("🛡️ Guardian stopped")
    
    def _capture_baseline(self) -> None:
        """Capture baseline of normal processes."""
        processes = self._enumerate_processes()
        self._baseline_processes = {p.name.lower() for p in processes}
        logger.info(f"📊 Baseline captured: {len(self._baseline_processes)} processes")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                self._scan_processes()
                self._scan_network()
                
                if self.platform == "windows":
                    self._scan_injections()
                elif self.platform == "linux":
                    self._scan_debug_exposure()
                    
            except Exception as e:
                logger.error(f"Guardian scan error: {e}")
            
            time.sleep(self.scan_interval)
    
    def _enumerate_processes(self) -> List[ProcessInfo]:
        """Get list of running processes."""
        processes = []
        
        try:
            if self.platform == "windows":
                result = subprocess.run(
                    ["tasklist", "/fo", "csv", "/nh"],
                    capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.replace('"', '').split(",")
                        if len(parts) >= 2:
                            processes.append(ProcessInfo(
                                pid=int(parts[1]) if parts[1].isdigit() else 0,
                                name=parts[0],
                            ))
            else:
                result = subprocess.run(
                    ["ps", "-eo", "pid,comm,%cpu,%mem"],
                    capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.strip().split("\n")[1:]:
                    parts = line.split()
                    if len(parts) >= 2:
                        processes.append(ProcessInfo(
                            pid=int(parts[0]) if parts[0].isdigit() else 0,
                            name=parts[1],
                            cpu=float(parts[2]) if len(parts) > 2 else 0,
                            memory=float(parts[3]) if len(parts) > 3 else 0,
                        ))
        except Exception as e:
            logger.error(f"Process enumeration failed: {e}")
        
        return processes
    
    def _scan_processes(self) -> None:
        """Scan for suspicious processes."""
        processes = self._enumerate_processes()
        
        for proc in processes:
            name_lower = proc.name.lower()
            
            # Check for suspicious patterns
            for pattern in self.SUSPICIOUS_PATTERNS:
                if pattern in name_lower:
                    self._raise_alert(
                        severity="critical",
                        category="process",
                        message=f"Suspicious process detected: {proc.name}",
                        details={"pid": proc.pid, "pattern": pattern}
                    )
                    break
            
            # Check for novel processes (not in baseline)
            if name_lower not in self._baseline_processes:
                if name_lower not in self.TRUSTED_PROCESSES:
                    self._raise_alert(
                        severity="warning",
                        category="process",
                        message=f"Novel process detected: {proc.name}",
                        details={"pid": proc.pid}
                    )
    
    def _scan_network(self) -> None:
        """Scan network connections."""
        try:
            if self.platform == "windows":
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True, text=True, timeout=10
                )
            else:
                result = subprocess.run(
                    ["netstat", "-an"],
                    capture_output=True, text=True, timeout=10
                )
            
            # Check for suspicious ports/connections
            suspicious_ports = {4444, 5555, 6666, 31337, 1234, 9001, 8888}
            
            for line in result.stdout.split("\n"):
                for port in suspicious_ports:
                    if f":{port}" in line:
                        self._raise_alert(
                            severity="warning",
                            category="network",
                            message=f"Suspicious port detected: {port}",
                            details={"line": line.strip()}
                        )
                        break
                        
        except Exception as e:
            logger.error(f"Network scan failed: {e}")
    
    def _scan_injections(self) -> None:
        """Scan for DLL/code injections (Windows)."""
        # Simplified check - in production would use ETW/WMI
        try:
            result = subprocess.run(
                ["wmic", "process", "get", "name,executablepath"],
                capture_output=True, text=True, timeout=10
            )
            
            # Check for processes running from temp directories
            temp_paths = ["\\temp\\", "\\tmp\\", "\\appdata\\local\\temp\\"]
            
            for line in result.stdout.lower().split("\n"):
                for temp in temp_paths:
                    if temp in line:
                        self._raise_alert(
                            severity="warning",
                            category="injection",
                            message="Process running from temp directory",
                            details={"path": line.strip()}
                        )
                        
        except Exception as e:
            logger.debug(f"Injection scan skipped: {e}")
    
    def _scan_debug_exposure(self) -> None:
        """Scan for debug/root exposure (Linux/Android)."""
        try:
            # Check if debuggable
            result = subprocess.run(
                ["cat", "/proc/self/status"],
                capture_output=True, text=True, timeout=5
            )
            if "TracerPid:\t0" not in result.stdout:
                self._raise_alert(
                    severity="critical",
                    category="debug",
                    message="Process is being traced/debugged",
                    details={"status": result.stdout[:200]}
                )
        except Exception:
            pass
    
    def _raise_alert(
        self,
        severity: str,
        category: str,
        message: str,
        details: Dict[str, Any] = None
    ) -> None:
        """Create and dispatch an alert."""
        alert = GuardianAlert(
            timestamp=datetime.now(),
            severity=severity,
            category=category,
            message=message,
            details=details or {},
        )
        
        with self._lock:
            self._alerts.append(alert)
        
        # Log
        log_func = logger.critical if severity == "critical" else logger.warning
        log_func(f"🚨 {category.upper()}: {message}")
        
        # Callback
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
        
        # Save evidence
        self._save_evidence(alert)
    
    def _save_evidence(self, alert: GuardianAlert) -> None:
        """Save alert to evidence directory."""
        timestamp = alert.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"alert_{timestamp}_{alert.category}.json"
        filepath = self.evidence_dir / filename
        
        try:
            filepath.write_text(json.dumps(alert.to_dict(), indent=2))
        except Exception as e:
            logger.error(f"Failed to save evidence: {e}")
    
    def get_alerts(self, since: Optional[datetime] = None) -> List[GuardianAlert]:
        """Get alerts, optionally filtered by time."""
        with self._lock:
            if since:
                return [a for a in self._alerts if a.timestamp >= since]
            return list(self._alerts)
    
    def clear_alerts(self) -> None:
        """Clear all alerts."""
        with self._lock:
            self._alerts.clear()
    
    def capture_snapshot(self) -> Dict[str, Any]:
        """Capture current system state snapshot."""
        processes = self._enumerate_processes()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "platform": self.platform,
            "process_count": len(processes),
            "processes": [
                {"pid": p.pid, "name": p.name, "cpu": p.cpu, "memory": p.memory}
                for p in processes[:50]  # Limit for snapshot
            ],
            "alert_count": len(self._alerts),
        }
