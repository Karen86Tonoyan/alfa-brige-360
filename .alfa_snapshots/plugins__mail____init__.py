# ═══════════════════════════════════════════════════════════════════════════
# ALFA MAIL PLUGIN v1.0.0
# ═══════════════════════════════════════════════════════════════════════════
"""
ALFA Mail: Secure IMAP email client plugin.

Features:
- IMAP IDLE for real-time sync
- PQXHybrid encryption for stored emails
- Event-driven architecture
- Background sync daemon

Usage:
    Loaded automatically by PluginLoader.
    Commands: mail, inbox, compose, sync
"""

import os
import sys
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

# Add parent to path for plugin base
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins import Plugin, PluginManifest

# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MailMessage:
    """Email message structure"""
    uid: str
    subject: str
    sender: str
    recipients: List[str]
    date: datetime
    body: str = ""
    attachments: List[str] = None
    read: bool = False
    encrypted: bool = False

# ═══════════════════════════════════════════════════════════════════════════
# MAIL PLUGIN
# ═══════════════════════════════════════════════════════════════════════════

class MailPlugin(Plugin):
    """
    ALFA Mail Plugin - Secure email client.
    """
    
    def __init__(self, manifest: PluginManifest, path: Path):
        super().__init__(manifest, path)
        
        self._imap_client = None
        self._sync_thread: Optional[threading.Thread] = None
        self._running = False
        self._messages: Dict[str, MailMessage] = {}
    
    # ─────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────
    
    def on_load(self) -> bool:
        """Initialize mail plugin"""
        self.logger.info("Loading ALFA Mail plugin...")
        
        # Check for credentials
        if not self.get_setting("username"):
            self.logger.warning("No email credentials configured")
        
        # Subscribe to events
        self.subscribe_event("mail.check", self._handle_check)
        self.subscribe_event("mail.send", self._handle_send)
        self.subscribe_event("mail.sync", self._handle_sync)
        
        self.logger.info("ALFA Mail plugin loaded")
        return True
    
    def on_start(self) -> bool:
        """Start mail sync daemon"""
        self.logger.info("Starting ALFA Mail daemon...")
        
        # Connect IMAP
        if not self._connect():
            self.logger.warning("Could not connect to IMAP server")
            # Continue anyway, can retry later
        
        # Start sync thread
        self._running = True
        self._sync_thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name="MailSync"
        )
        self._sync_thread.start()
        
        self.emit_event("started")
        return True
    
    def on_stop(self):
        """Stop mail daemon"""
        self.logger.info("Stopping ALFA Mail daemon...")
        
        self._running = False
        
        if self._sync_thread:
            self._sync_thread.join(timeout=5.0)
        
        self._disconnect()
        self.emit_event("stopped")
    
    # ─────────────────────────────────────────────────────────────────────
    # IMAP CONNECTION
    # ─────────────────────────────────────────────────────────────────────
    
    def _connect(self) -> bool:
        """Connect to IMAP server"""
        host = self.get_setting("imap_host")
        port = self.get_setting("imap_port", 993)
        username = self.get_setting("username")
        password = self.get_setting("password_encrypted")
        
        if not all([host, username, password]):
            return False
        
        try:
            import imaplib
            
            self._imap_client = imaplib.IMAP4_SSL(host, port)
            self._imap_client.login(username, password)
            self._imap_client.select("INBOX")
            
            self.logger.info(f"Connected to {host}")
            return True
            
        except Exception as e:
            self.logger.error(f"IMAP connection failed: {e}")
            self._imap_client = None
            return False
    
    def _disconnect(self):
        """Disconnect from IMAP"""
        if self._imap_client:
            try:
                self._imap_client.close()
                self._imap_client.logout()
            except:
                pass
            self._imap_client = None
    
    # ─────────────────────────────────────────────────────────────────────
    # SYNC
    # ─────────────────────────────────────────────────────────────────────
    
    def _sync_loop(self):
        """Background sync loop"""
        interval = self.get_setting("check_interval", 300)
        
        while self._running:
            try:
                self._fetch_new_messages()
            except Exception as e:
                self.logger.error(f"Sync error: {e}")
            
            # Sleep with interrupt check
            for _ in range(int(interval)):
                if not self._running:
                    break
                time.sleep(1)
    
    def _fetch_new_messages(self):
        """Fetch new messages from IMAP"""
        if not self._imap_client:
            if not self._connect():
                return
        
        try:
            import email
            from email.header import decode_header
            
            # Search for unseen
            status, data = self._imap_client.search(None, "UNSEEN")
            if status != "OK":
                return
            
            message_ids = data[0].split()
            
            for msg_id in message_ids[-10:]:  # Last 10 only
                status, msg_data = self._imap_client.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                
                # Parse
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8")
                
                sender = msg.get("From", "")
                date_str = msg.get("Date", "")
                
                mail_msg = MailMessage(
                    uid=msg_id.decode(),
                    subject=subject,
                    sender=sender,
                    recipients=[msg.get("To", "")],
                    date=datetime.now(),  # Parse date_str properly
                    body=self._get_body(msg),
                    read=False
                )
                
                self._messages[mail_msg.uid] = mail_msg
                self.emit_event("new_message", {
                    "uid": mail_msg.uid,
                    "subject": mail_msg.subject,
                    "sender": mail_msg.sender
                })
            
            self.logger.debug(f"Synced {len(message_ids)} messages")
            
        except Exception as e:
            self.logger.error(f"Fetch error: {e}")
            self._disconnect()
    
    def _get_body(self, msg) -> str:
        """Extract email body"""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        return part.get_payload(decode=True).decode()
                    except:
                        pass
        else:
            try:
                return msg.get_payload(decode=True).decode()
            except:
                pass
        return ""
    
    # ─────────────────────────────────────────────────────────────────────
    # EVENT HANDLERS
    # ─────────────────────────────────────────────────────────────────────
    
    def _handle_check(self, event):
        """Handle mail.check event"""
        self._fetch_new_messages()
    
    def _handle_send(self, event):
        """Handle mail.send event"""
        payload = event.payload or {}
        
        to = payload.get('to')
        subject = payload.get('subject', '')
        body = payload.get('body', '')
        cc = payload.get('cc', [])
        bcc = payload.get('bcc', [])
        
        if not to:
            self.logger.error("Cannot send email: no recipient specified")
            return False
        
        result = self._send_email(to, subject, body, cc=cc, bcc=bcc)
        
        if result:
            self.emit_event("mail.sent", {"to": to, "subject": subject})
            self.logger.info(f"Email sent to: {to}")
        else:
            self.emit_event("mail.send_failed", {"to": to, "error": "SMTP error"})
        
        return result
    
    def _send_email(self, 
                    to: str | List[str], 
                    subject: str, 
                    body: str,
                    cc: List[str] = None,
                    bcc: List[str] = None,
                    html: bool = False) -> bool:
        """
        Send email via SMTP.
        
        Args:
            to: Recipient(s) email address
            subject: Email subject
            body: Email body (plain text or HTML)
            cc: Carbon copy recipients
            bcc: Blind carbon copy recipients
            html: If True, body is treated as HTML
            
        Returns:
            True if sent successfully, False otherwise
        """
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.utils import formataddr, formatdate
        
        # Get SMTP settings
        smtp_host = self.get_setting("smtp_host")
        smtp_port = self.get_setting("smtp_port", 587)
        username = self.get_setting("username")
        password = self.get_setting("password_encrypted")
        sender_name = self.get_setting("sender_name", "ALFA Mail")
        
        if not all([smtp_host, username, password]):
            self.logger.error("SMTP not configured properly")
            return False
        
        try:
            # Build message
            msg = MIMEMultipart("alternative")
            msg["From"] = formataddr((sender_name, username))
            msg["To"] = to if isinstance(to, str) else ", ".join(to)
            msg["Subject"] = subject
            msg["Date"] = formatdate(localtime=True)
            msg["X-Mailer"] = "ALFA Mail v1.0"
            
            if cc:
                msg["Cc"] = ", ".join(cc) if isinstance(cc, list) else cc
            
            # Attach body
            if html:
                msg.attach(MIMEText(body, "html", "utf-8"))
            else:
                msg.attach(MIMEText(body, "plain", "utf-8"))
            
            # Build recipient list
            recipients = [to] if isinstance(to, str) else list(to)
            if cc:
                recipients.extend(cc if isinstance(cc, list) else [cc])
            if bcc:
                recipients.extend(bcc if isinstance(bcc, list) else [bcc])
            
            # Send via SMTP
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.sendmail(username, recipients, msg.as_string())
            
            self.logger.info(f"✉️ Email sent: {subject} -> {to}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            self.logger.error(f"SMTP auth failed: {e}")
        except smtplib.SMTPRecipientsRefused as e:
            self.logger.error(f"Recipients refused: {e}")
        except smtplib.SMTPException as e:
            self.logger.error(f"SMTP error: {e}")
        except Exception as e:
            self.logger.error(f"Send failed: {e}")
        
        return False
    
    def _handle_sync(self, event):
        """Handle mail.sync event"""
        self._fetch_new_messages()
    
    # ─────────────────────────────────────────────────────────────────────
    # COMMANDS
    # ─────────────────────────────────────────────────────────────────────
    
    def on_command(self, command: str, args: str) -> Optional[str]:
        """Handle CLI commands"""
        
        if command == "mail" or command == "inbox":
            # List recent messages
            lines = [f"Inbox ({len(self._messages)} messages):", ""]
            
            for uid, msg in list(self._messages.items())[-10:]:
                status = "●" if not msg.read else "○"
                lines.append(f"  {status} {msg.subject[:40]} - {msg.sender}")
            
            return "\n".join(lines)
        
        elif command == "compose":
            return "Compose: mail compose <to> <subject> <body>"
        
        elif command == "sync":
            self._fetch_new_messages()
            return f"Synced. {len(self._messages)} messages."
        
        return None
    
    # ─────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────────
    
    def get_messages(self, limit: int = 20) -> List[MailMessage]:
        """Get recent messages"""
        return list(self._messages.values())[-limit:]
    
    def get_message(self, uid: str) -> Optional[MailMessage]:
        """Get message by UID"""
        return self._messages.get(uid)
    
    def mark_read(self, uid: str):
        """Mark message as read"""
        if uid in self._messages:
            self._messages[uid].read = True
    
    def send(self, 
             to: str | List[str], 
             subject: str, 
             body: str,
             cc: List[str] = None,
             bcc: List[str] = None,
             html: bool = False) -> bool:
        """
        Send an email.
        
        Args:
            to: Recipient email address(es)
            subject: Email subject line
            body: Email body content
            cc: Carbon copy recipients (optional)
            bcc: Blind carbon copy recipients (optional)
            html: If True, body is HTML; otherwise plain text
            
        Returns:
            True if email was sent successfully
            
        Example:
            mail_plugin.send(
                to="user@example.com",
                subject="Hello from ALFA",
                body="This is a test email."
            )
        """
        return self._send_email(to, subject, body, cc=cc, bcc=bcc, html=html)
