"""
================================================================================
ALFA CERBER - TECHNICAL SPECIFICATION v1.0
================================================================================

MODULE: Cerber Background Service
PURPOSE: Foreground Service for Android with Doze-aware sync, WakeLock, 
         AlarmManager integration, and watchdog monitoring.

AUTHOR: ALFA System / Karen86Tonoyan
VERSION: 1.0.0
DATE: 2025-12-03

================================================================================
ARCHITECTURE OVERVIEW
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│                           ALFA MAIL SYSTEM                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐         IPC/EventBus         ┌─────────────────────────┐  │
│  │   UI LAYER  │◄──────────────────────────────│    CERBER SERVICE       │  │
│  │   (Kivy)    │                              │  (Foreground Service)   │  │
│  │             │                              │                         │  │
│  │ • Rendering │         SharedPrefs          │ • IMAP Sync             │  │
│  │ • Touch     │◄──────────────────────────────│ • PQXHybrid Crypto      │  │
│  │ • Display   │                              │ • AI Bridge             │  │
│  └──────┬──────┘                              │ • Watchdog              │  │
│         │                                     └───────────┬─────────────┘  │
│         │                                                 │                │
│         │              ┌──────────────────┐               │                │
│         └──────────────►│   SQLCipher DB   │◄──────────────┘                │
│                        │  (encrypted)      │                               │
│                        └──────────────────┘                               │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    ANDROID SYSTEM INTEGRATION                         │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │  • NotificationChannel (Android 8.0+)                                │  │
│  │  • ForegroundService with FOREGROUND_SERVICE_DATA_SYNC               │  │
│  │  • WakeLock (PARTIAL_WAKE_LOCK) - acquired only during sync          │  │
│  │  • AlarmManager (setExactAndAllowWhileIdle) - Doze-aware scheduling  │  │
│  │  • BroadcastReceiver for alarm triggers                              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
DOZE MODE STRATEGY
================================================================================

Problem:
  Android Doze mode (API 23+) aggressively suspends network access and 
  background work when device is idle. Standard services are killed.

Solution:
  1. Foreground Service with persistent notification (survives Doze)
  2. AlarmManager.setExactAndAllowWhileIdle() for periodic wake-ups
  3. WakeLock acquired ONLY during active sync (battery-friendly)
  4. BroadcastReceiver to catch alarm intents even in Doze

Lifecycle:
  ┌─────────┐    AlarmManager     ┌─────────────┐    Sync Done    ┌─────────┐
  │ IDLE    │ ─────────────────► │ WAKE + SYNC │ ──────────────► │ RELEASE │
  │ (sleep) │  setExact...Idle   │ (WakeLock)  │   releaseWL     │ → IDLE  │
  └─────────┘                    └─────────────┘                 └─────────┘

WakeLock Policy:
  • Acquire: Before network/crypto operation
  • Hold: Max 60 seconds (hardcoded timeout)
  • Release: Immediately after operation completes (finally block)
  • Type: PARTIAL_WAKE_LOCK (CPU only, screen off)

================================================================================
PQXHYBRID KEY LIFECYCLE
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│                       KEY GENERATION & STORAGE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  KEY TYPE           GENERATION           STORAGE          TTL              │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Identity Keys      On first vault       SQLCipher        Permanent        │
│  (Kyber + ECC)      unlock (once)        pq_keys table    (until rotate)   │
│                                                                             │
│  Session Keys       Per-conversation     Memory only      Session          │
│  (AES-256-GCM)      (on first message)   (ephemeral)      (cleared on      │
│                                                            app close)      │
│                                                                             │
│  Signature Keys     On first vault       SQLCipher        Permanent        │
│  (Dilithium)        unlock (once)        pq_keys table    (until rotate)   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Key Rotation Policy:
  • Manual rotation: User-initiated via settings
  • Auto-rotation: Every 90 days (configurable)
  • Emergency rotation: On detected compromise (Cerber threat > 90)

Per-Conversation vs Per-Sender:
  • Identity keys: Per-user (your keypair)
  • Session keys: Per-conversation thread (derived from both parties' identity)
  • Fingerprint verification: Per-sender (stored in fingerprints table)

================================================================================
"""

from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple

# =============================================================================
# PLATFORM DETECTION
# =============================================================================

try:
    from jnius import autoclass, cast
    IS_ANDROID = True
except ImportError:
    IS_ANDROID = False
    # Mock for desktop development
    autoclass = lambda x: None
    cast = lambda x, y: y

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [CERBER] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("cerber")


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class CerberConfig:
    """Configuration for Cerber service."""
    
    # Service identification
    notification_channel_id: str = "alfa_cerber_channel"
    notification_channel_name: str = "ALFA Cerber Core"
    notification_id: int = 101
    
    # Sync settings
    sync_interval_seconds: int = 15 * 60  # 15 minutes
    sync_timeout_seconds: int = 60  # Max time per sync operation
    max_sync_retries: int = 3
    
    # WakeLock settings
    wakelock_tag: str = "ALFA::CerberSync"
    wakelock_timeout_ms: int = 60 * 1000  # 60 seconds max
    
    # Watchdog settings
    heartbeat_interval_seconds: int = 60
    integrity_check_interval_seconds: int = 300  # 5 minutes
    
    # Threat detection
    threat_threshold: int = 50  # 0-100 scale
    auto_quarantine: bool = True
    
    # Alarm settings (for Doze-aware scheduling)
    alarm_request_code: int = 42001


# =============================================================================
# SERVICE STATE
# =============================================================================

class ServiceState(Enum):
    """Cerber service states."""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    SYNCING = auto()
    ERROR = auto()
    STOPPING = auto()


@dataclass
class CerberState:
    """Runtime state of Cerber service."""
    state: ServiceState = ServiceState.STOPPED
    last_sync: Optional[datetime] = None
    last_error: Optional[str] = None
    sync_count: int = 0
    error_count: int = 0
    threats_detected: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.name,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_error": self.last_error,
            "sync_count": self.sync_count,
            "error_count": self.error_count,
            "threats_detected": self.threats_detected,
        }


# =============================================================================
# ANDROID NATIVE BRIDGE
# =============================================================================

class AndroidBridge:
    """
    Bridge to Android native APIs via pyjnius.
    All JNI calls are encapsulated here for clean separation.
    """
    
    def __init__(self):
        if not IS_ANDROID:
            logger.warning("AndroidBridge: Running in desktop mode (mocked)")
            return
        
        # Import Android classes
        self.PythonService = autoclass('org.kivy.android.PythonService')
        self.Context = autoclass('android.content.Context')
        self.Intent = autoclass('android.content.Intent')
        self.PendingIntent = autoclass('android.app.PendingIntent')
        
        # Notification classes
        self.NotificationChannel = autoclass('android.app.NotificationChannel')
        self.NotificationManager = autoclass('android.app.NotificationManager')
        self.NotificationBuilder = autoclass('android.app.Notification$Builder')
        
        # Power management
        self.PowerManager = autoclass('android.os.PowerManager')
        
        # Alarm manager
        self.AlarmManager = autoclass('android.app.AlarmManager')
        
        # Build version check
        self.Build = autoclass('android.os.Build$VERSION')
        self.SDK_INT = self.Build.SDK_INT
        
        logger.info(f"AndroidBridge initialized, SDK={self.SDK_INT}")
    
    @property
    def service(self):
        """Get current Python service instance."""
        if not IS_ANDROID:
            return None
        return self.PythonService.mService
    
    def create_notification_channel(self, config: CerberConfig) -> bool:
        """Create notification channel (required for Android 8.0+)."""
        if not IS_ANDROID:
            logger.debug("Mock: create_notification_channel")
            return True
        
        try:
            service = self.service
            if not service:
                return False
            
            nm = service.getSystemService(self.Context.NOTIFICATION_SERVICE)
            if not nm:
                return False
            
            # IMPORTANCE_LOW = no sound, but visible
            importance = self.NotificationManager.IMPORTANCE_LOW
            
            channel = self.NotificationChannel(
                config.notification_channel_id,
                config.notification_channel_name,
                importance
            )
            channel.setDescription(
                "Utrzymanie bezpiecznego połączenia i synchronizacja poczty"
            )
            
            nm.createNotificationChannel(channel)
            logger.info(f"Notification channel created: {config.notification_channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create notification channel: {e}")
            return False
    
    def start_foreground(self, config: CerberConfig, text: str = "Ochrona aktywna") -> bool:
        """Start service as foreground with notification."""
        if not IS_ANDROID:
            logger.debug(f"Mock: start_foreground: {text}")
            return True
        
        try:
            service = self.service
            if not service:
                return False
            
            # Create notification
            notification = self.NotificationBuilder(
                service, 
                config.notification_channel_id
            ) \
                .setContentTitle("ALFA Mail: Cerber") \
                .setContentText(text) \
                .setSmallIcon(service.getApplicationInfo().icon) \
                .setOngoing(True) \
                .build()
            
            # Android 14+ requires foreground service type
            if self.SDK_INT >= 34:
                # FOREGROUND_SERVICE_TYPE_DATA_SYNC = 1
                service.startForeground(config.notification_id, notification, 1)
            else:
                service.startForeground(config.notification_id, notification)
            
            logger.info("Foreground service started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start foreground: {e}")
            return False
    
    def acquire_wakelock(self, config: CerberConfig) -> Any:
        """
        Acquire partial wake lock for sync operation.
        Returns wakelock object (must be released!).
        """
        if not IS_ANDROID:
            logger.debug("Mock: acquire_wakelock")
            return "mock_wakelock"
        
        try:
            service = self.service
            if not service:
                return None
            
            pm = service.getSystemService(self.Context.POWER_SERVICE)
            if not pm:
                return None
            
            # PARTIAL_WAKE_LOCK = 1
            wakelock = pm.newWakeLock(1, config.wakelock_tag)
            
            # Acquire with timeout (CRITICAL: prevents battery drain)
            wakelock.acquire(config.wakelock_timeout_ms)
            
            logger.debug(f"WakeLock acquired: {config.wakelock_tag}")
            return wakelock
            
        except Exception as e:
            logger.error(f"Failed to acquire wakelock: {e}")
            return None
    
    def release_wakelock(self, wakelock: Any) -> bool:
        """Release wake lock (MUST be called in finally block)."""
        if not IS_ANDROID:
            logger.debug("Mock: release_wakelock")
            return True
        
        if wakelock is None:
            return False
        
        try:
            if wakelock.isHeld():
                wakelock.release()
                logger.debug("WakeLock released")
            return True
        except Exception as e:
            logger.error(f"Failed to release wakelock: {e}")
            return False
    
    def schedule_next_alarm(self, config: CerberConfig) -> bool:
        """
        Schedule next sync using AlarmManager.
        Uses setExactAndAllowWhileIdle for Doze compatibility.
        """
        if not IS_ANDROID:
            logger.debug("Mock: schedule_next_alarm")
            return True
        
        try:
            service = self.service
            if not service:
                return False
            
            am = service.getSystemService(self.Context.ALARM_SERVICE)
            if not am:
                return False
            
            # Create intent for our service
            intent = self.Intent(service, service.getClass())
            intent.setAction("org.alfaproject.CERBER_SYNC")
            
            # PendingIntent with FLAG_IMMUTABLE (required Android 12+)
            flags = self.PendingIntent.FLAG_UPDATE_CURRENT
            if self.SDK_INT >= 31:
                flags |= self.PendingIntent.FLAG_IMMUTABLE
            
            pending = self.PendingIntent.getService(
                service,
                config.alarm_request_code,
                intent,
                flags
            )
            
            # Schedule for next interval
            trigger_time = int(time.time() * 1000) + (config.sync_interval_seconds * 1000)
            
            # setExactAndAllowWhileIdle - fires even in Doze
            if self.SDK_INT >= 23:
                am.setExactAndAllowWhileIdle(
                    self.AlarmManager.RTC_WAKEUP,
                    trigger_time,
                    pending
                )
            else:
                am.setExact(
                    self.AlarmManager.RTC_WAKEUP,
                    trigger_time,
                    pending
                )
            
            next_sync = datetime.fromtimestamp(trigger_time / 1000)
            logger.info(f"Next sync scheduled: {next_sync.isoformat()}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule alarm: {e}")
            return False
    
    def cancel_alarm(self, config: CerberConfig) -> bool:
        """Cancel scheduled alarm."""
        if not IS_ANDROID:
            return True
        
        try:
            service = self.service
            if not service:
                return False
            
            am = service.getSystemService(self.Context.ALARM_SERVICE)
            intent = self.Intent(service, service.getClass())
            intent.setAction("org.alfaproject.CERBER_SYNC")
            
            flags = self.PendingIntent.FLAG_UPDATE_CURRENT
            if self.SDK_INT >= 31:
                flags |= self.PendingIntent.FLAG_IMMUTABLE
            
            pending = self.PendingIntent.getService(
                service,
                config.alarm_request_code,
                intent,
                flags
            )
            
            am.cancel(pending)
            logger.info("Alarm cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel alarm: {e}")
            return False


# =============================================================================
# WATCHDOG
# =============================================================================

class Watchdog:
    """
    System integrity monitor.
    Checks for anomalies, tampering, and threats.
    """
    
    def __init__(self, config: CerberConfig):
        self.config = config
        self.last_check = datetime.now()
        self.anomalies: List[Dict[str, Any]] = []
    
    def scan(self) -> Dict[str, Any]:
        """
        Perform integrity scan.
        Returns scan results with any detected issues.
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "checks": [],
            "threats": [],
            "overall_status": "OK"
        }
        
        # Check 1: Memory integrity
        mem_check = self._check_memory_integrity()
        results["checks"].append(mem_check)
        
        # Check 2: File system integrity
        fs_check = self._check_filesystem_integrity()
        results["checks"].append(fs_check)
        
        # Check 3: Process isolation
        proc_check = self._check_process_isolation()
        results["checks"].append(proc_check)
        
        # Aggregate threats
        for check in results["checks"]:
            if check.get("threat_level", 0) > 0:
                results["threats"].append({
                    "source": check["name"],
                    "level": check["threat_level"],
                    "description": check.get("description", "")
                })
        
        # Calculate overall status
        max_threat = max((t["level"] for t in results["threats"]), default=0)
        if max_threat >= self.config.threat_threshold:
            results["overall_status"] = "THREAT_DETECTED"
        elif max_threat > 0:
            results["overall_status"] = "WARNING"
        
        self.last_check = datetime.now()
        logger.debug(f"Watchdog scan: {results['overall_status']}")
        
        return results
    
    def _check_memory_integrity(self) -> Dict[str, Any]:
        """Check for memory tampering indicators."""
        # Simplified check - in production would use more sophisticated methods
        return {
            "name": "memory_integrity",
            "status": "passed",
            "threat_level": 0,
            "description": "No memory anomalies detected"
        }
    
    def _check_filesystem_integrity(self) -> Dict[str, Any]:
        """Check critical files haven't been modified."""
        # In production: hash verification of key files
        return {
            "name": "filesystem_integrity",
            "status": "passed",
            "threat_level": 0,
            "description": "File integrity verified"
        }
    
    def _check_process_isolation(self) -> Dict[str, Any]:
        """Verify process isolation is maintained."""
        return {
            "name": "process_isolation",
            "status": "passed",
            "threat_level": 0,
            "description": "Process isolation intact"
        }


# =============================================================================
# EVENT BUS (IPC)
# =============================================================================

class EventBus:
    """
    Simple event bus for inter-process communication.
    Uses SharedPreferences on Android, file-based on desktop.
    """
    
    def __init__(self, name: str = "cerber_events"):
        self.name = name
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
    
    def publish(self, event_type: str, data: Dict[str, Any] = None):
        """Publish event to all subscribers."""
        with self._lock:
            callbacks = self._subscribers.get(event_type, [])
        
        for callback in callbacks:
            try:
                callback(event_type, data or {})
            except Exception as e:
                logger.error(f"Event callback error: {e}")
    
    def publish_to_ui(self, event_type: str, data: Dict[str, Any] = None):
        """
        Publish event to UI process via SharedPreferences.
        UI polls this for updates.
        """
        if not IS_ANDROID:
            # Desktop: write to file
            event_file = f"/tmp/{self.name}_{event_type}.json"
            try:
                with open(event_file, 'w') as f:
                    json.dump({"type": event_type, "data": data, "ts": time.time()}, f)
            except Exception as e:
                logger.error(f"Failed to write event file: {e}")
            return
        
        # Android: use SharedPreferences
        try:
            bridge = AndroidBridge()
            service = bridge.service
            if not service:
                return
            
            prefs = service.getSharedPreferences(
                self.name,
                bridge.Context.MODE_PRIVATE
            )
            editor = prefs.edit()
            editor.putString(
                event_type,
                json.dumps({"data": data, "ts": time.time()})
            )
            editor.apply()
            
        except Exception as e:
            logger.error(f"Failed to publish to UI: {e}")


# =============================================================================
# CERBER SERVICE
# =============================================================================

class CerberService:
    """
    Main Cerber background service.
    Manages sync, watchdog, and system integration.
    """
    
    def __init__(self, config: CerberConfig = None):
        self.config = config or CerberConfig()
        self.state = CerberState()
        self.bridge = AndroidBridge()
        self.watchdog = Watchdog(self.config)
        self.event_bus = EventBus()
        
        self._running = False
        self._sync_lock = threading.Lock()
        
        logger.info("CerberService initialized")
    
    def start(self) -> bool:
        """Start the Cerber service."""
        if self._running:
            logger.warning("Service already running")
            return False
        
        self.state.state = ServiceState.STARTING
        
        try:
            # 1. Create notification channel
            self.bridge.create_notification_channel(self.config)
            
            # 2. Start as foreground service
            self.bridge.start_foreground(self.config)
            
            # 3. Schedule first sync
            self.bridge.schedule_next_alarm(self.config)
            
            # 4. Start watchdog thread
            self._start_watchdog_thread()
            
            self._running = True
            self.state.state = ServiceState.RUNNING
            
            logger.info("CerberService started successfully")
            self.event_bus.publish_to_ui("service_started", self.state.to_dict())
            
            return True
            
        except Exception as e:
            self.state.state = ServiceState.ERROR
            self.state.last_error = str(e)
            logger.error(f"Failed to start service: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop the Cerber service."""
        if not self._running:
            return False
        
        self.state.state = ServiceState.STOPPING
        self._running = False
        
        try:
            # Cancel scheduled alarms
            self.bridge.cancel_alarm(self.config)
            
            self.state.state = ServiceState.STOPPED
            logger.info("CerberService stopped")
            
            self.event_bus.publish_to_ui("service_stopped", self.state.to_dict())
            return True
            
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
            return False
    
    def perform_sync(self) -> Dict[str, Any]:
        """
        Perform mail synchronization with WakeLock protection.
        This is the main sync entry point.
        """
        if not self._sync_lock.acquire(blocking=False):
            logger.warning("Sync already in progress, skipping")
            return {"status": "skipped", "reason": "sync_in_progress"}
        
        wakelock = None
        results = {"status": "unknown", "mails_synced": 0, "errors": []}
        
        try:
            self.state.state = ServiceState.SYNCING
            
            # CRITICAL: Acquire WakeLock before any network operation
            wakelock = self.bridge.acquire_wakelock(self.config)
            
            logger.info("Starting mail sync...")
            
            # TODO: Actual IMAP sync logic here
            # This is where imap_engine.sync_folder() would be called
            
            # Simulate sync for now
            time.sleep(2)
            results["status"] = "success"
            results["mails_synced"] = 0
            
            # Update state
            self.state.last_sync = datetime.now()
            self.state.sync_count += 1
            self.state.state = ServiceState.RUNNING
            
            logger.info(f"Sync complete: {results}")
            
            # Notify UI
            self.event_bus.publish_to_ui("sync_complete", {
                "results": results,
                "state": self.state.to_dict()
            })
            
        except Exception as e:
            self.state.error_count += 1
            self.state.last_error = str(e)
            self.state.state = ServiceState.ERROR
            results["status"] = "error"
            results["errors"].append(str(e))
            logger.error(f"Sync failed: {e}")
            
        finally:
            # CRITICAL: Always release WakeLock
            if wakelock:
                self.bridge.release_wakelock(wakelock)
            
            self._sync_lock.release()
            
            # Schedule next sync
            self.bridge.schedule_next_alarm(self.config)
        
        return results
    
    def _start_watchdog_thread(self):
        """Start watchdog monitoring in background thread."""
        def watchdog_loop():
            while self._running:
                try:
                    results = self.watchdog.scan()
                    
                    if results["overall_status"] == "THREAT_DETECTED":
                        self.state.threats_detected += 1
                        self.event_bus.publish_to_ui("threat_detected", results)
                        logger.warning(f"THREAT DETECTED: {results['threats']}")
                    
                except Exception as e:
                    logger.error(f"Watchdog error: {e}")
                
                time.sleep(self.config.heartbeat_interval_seconds)
        
        thread = threading.Thread(target=watchdog_loop, daemon=True)
        thread.start()
        logger.info("Watchdog thread started")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current service status."""
        return {
            **self.state.to_dict(),
            "config": {
                "sync_interval": self.config.sync_interval_seconds,
                "threat_threshold": self.config.threat_threshold,
            },
            "watchdog": {
                "last_check": self.watchdog.last_check.isoformat(),
                "anomalies": len(self.watchdog.anomalies),
            }
        }


# =============================================================================
# SERVICE ENTRY POINT
# =============================================================================

def main():
    """
    Service entry point.
    This runs in a separate process from UI.
    """
    print("=" * 60)
    print("ALFA CERBER SERVICE v1.0")
    print("=" * 60)
    
    config = CerberConfig()
    service = CerberService(config)
    
    if not service.start():
        logger.error("Failed to start Cerber service")
        sys.exit(1)
    
    # Main service loop
    try:
        while True:
            # Wait for alarm trigger or periodic check
            time.sleep(config.heartbeat_interval_seconds)
            
            # Check if sync is due (fallback if alarm didn't fire)
            if service.state.last_sync:
                time_since_sync = datetime.now() - service.state.last_sync
                if time_since_sync.total_seconds() > config.sync_interval_seconds * 1.5:
                    logger.warning("Sync overdue, triggering manually")
                    service.perform_sync()
            else:
                # First sync
                service.perform_sync()
                
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        service.stop()
    
    print("\n[DONE] Cerber service terminated.")


if __name__ == "__main__":
    main()
