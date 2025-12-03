# ═══════════════════════════════════════════════════════════════════════════
# ALFA MAIL PLUGIN
# ═══════════════════════════════════════════════════════════════════════════
"""
IMAP email sync with background daemon.

Commands: mail, inbox, sync
"""

import logging
import threading
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.plugin_engine import Plugin, PluginManifest

LOG = logging.getLogger("alfa.plugin.mail")

@dataclass
class MailMessage:
    uid: str
    subject: str
    sender: str
    date: datetime
    read: bool = False

class MailPlugin(Plugin):
    """ALFA Mail Plugin."""
    
    def __init__(self, manifest: PluginManifest, engine):
        super().__init__(manifest, engine)
        self._messages: Dict[str, MailMessage] = {}
        self._running = False
        self._worker: Optional[threading.Thread] = None
    
    def on_load(self) -> bool:
        LOG.info("Mail plugin loading...")
        self.subscribe("mail.*", self._on_mail_event)
        return True
    
    def on_start(self) -> bool:
        LOG.info("Mail plugin starting...")
        self._running = True
        self._worker = threading.Thread(target=self._sync_loop, daemon=True, name="MailSync")
        self._worker.start()
        self.emit("started")
        return True
    
    def on_stop(self):
        LOG.info("Mail plugin stopping...")
        self._running = False
        if self._worker:
            self._worker.join(timeout=5)
        self.emit("stopped")
    
    def _sync_loop(self):
        """Background sync loop."""
        interval = self.get_setting("check_interval", 300)
        
        while self._running:
            try:
                self._fetch_messages()
            except Exception as e:
                LOG.error(f"Sync error: {e}")
            
            for _ in range(interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _fetch_messages(self):
        """Fetch new messages (stub)."""
        # TODO: Implement actual IMAP fetch
        LOG.debug("Checking for new messages...")
    
    def _on_mail_event(self, event):
        """Handle mail events."""
        LOG.debug(f"Mail event: {event.topic}")
    
    def on_command(self, command: str, args: str) -> Optional[str]:
        if command == "mail" or command == "inbox":
            return f"Inbox: {len(self._messages)} messages"
        
        elif command == "sync":
            self._fetch_messages()
            return "Sync complete"
        
        return None
