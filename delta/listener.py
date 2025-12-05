"""
ALFA DELTA v1 — LISTENER
IMAP listener dla Delta Chat.
"""

from typing import Optional, Dict, Any, Callable
import logging
import time
import threading
import email
from email.header import decode_header
import imaplib
from dataclasses import dataclass, field

logger = logging.getLogger("ALFA.Delta.Listener")


@dataclass
class DeltaMessage:
    """Wiadomość Delta Chat."""
    uid: str
    sender: str
    subject: str
    body: str
    timestamp: float
    attachments: list = field(default_factory=list)
    raw: Optional[email.message.Message] = None


class DeltaListener:
    """
    IMAP Listener dla Delta Chat.
    Nasłuchuje na wiadomości i wywołuje callback.
    """
    
    def __init__(
        self,
        imap_host: str,
        imap_port: int = 993,
        email_address: str = "",
        password: str = "",
        folder: str = "INBOX",
        check_interval: float = 5.0
    ):
        """
        Args:
            imap_host: Host IMAP
            imap_port: Port IMAP (993 dla SSL)
            email_address: Adres email
            password: Hasło
            folder: Folder do monitorowania
            check_interval: Interwał sprawdzania (sekundy)
        """
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.email_address = email_address
        self.password = password
        self.folder = folder
        self.check_interval = check_interval
        
        self._imap: Optional[imaplib.IMAP4_SSL] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[DeltaMessage], None]] = None
        self._last_uid: Optional[str] = None
        
        logger.info(f"DeltaListener initialized ({imap_host})")
    
    def connect(self) -> bool:
        """Łączy z serwerem IMAP."""
        try:
            self._imap = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            self._imap.login(self.email_address, self.password)
            self._imap.select(self.folder)
            logger.info("Connected to IMAP server")
            return True
        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """Rozłącza z serwerem."""
        if self._imap:
            try:
                self._imap.close()
                self._imap.logout()
            except:
                pass
            self._imap = None
        logger.info("Disconnected from IMAP")
    
    def start(self, callback: Callable[[DeltaMessage], None]) -> None:
        """
        Uruchamia listener w tle.
        
        Args:
            callback: Funkcja wywoływana dla każdej wiadomości
        """
        if self._running:
            logger.warning("Listener already running")
            return
        
        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        
        logger.info("Delta listener started")
    
    def stop(self) -> None:
        """Zatrzymuje listener."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        self.disconnect()
        logger.info("Delta listener stopped")
    
    def _listen_loop(self) -> None:
        """Główna pętla nasłuchiwania."""
        while self._running:
            try:
                if not self._imap:
                    if not self.connect():
                        time.sleep(10)
                        continue
                
                # Check for new messages
                messages = self._fetch_new_messages()
                
                for msg in messages:
                    if self._callback:
                        try:
                            self._callback(msg)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
                
                time.sleep(self.check_interval)
                
            except imaplib.IMAP4.abort:
                logger.warning("IMAP connection lost, reconnecting...")
                self._imap = None
            except Exception as e:
                logger.error(f"Listener error: {e}")
                time.sleep(5)
    
    def _fetch_new_messages(self) -> list:
        """Pobiera nowe wiadomości."""
        if not self._imap:
            return []
        
        messages = []
        
        try:
            # Search for unseen messages
            status, data = self._imap.search(None, "UNSEEN")
            
            if status != "OK":
                return []
            
            message_nums = data[0].split()
            
            for num in message_nums:
                msg = self._fetch_message(num)
                if msg:
                    messages.append(msg)
                    # Mark as seen
                    self._imap.store(num, "+FLAGS", "\\Seen")
            
        except Exception as e:
            logger.error(f"Fetch error: {e}")
        
        return messages
    
    def _fetch_message(self, num: bytes) -> Optional[DeltaMessage]:
        """Pobiera pojedynczą wiadomość."""
        try:
            status, data = self._imap.fetch(num, "(RFC822)")
            
            if status != "OK":
                return None
            
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Parse sender
            sender = msg.get("From", "")
            
            # Parse subject
            subject = ""
            raw_subject = msg.get("Subject", "")
            if raw_subject:
                decoded = decode_header(raw_subject)
                subject = decoded[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode(decoded[0][1] or "utf-8", errors="ignore")
            
            # Parse body
            body = self._extract_body(msg)
            
            # Parse attachments
            attachments = self._extract_attachments(msg)
            
            return DeltaMessage(
                uid=num.decode(),
                sender=sender,
                subject=subject,
                body=body,
                timestamp=time.time(),
                attachments=attachments,
                raw=msg
            )
            
        except Exception as e:
            logger.error(f"Message parse error: {e}")
            return None
    
    def _extract_body(self, msg: email.message.Message) -> str:
        """Wyciąga treść wiadomości."""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="ignore")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="ignore")
        
        return body.strip()
    
    def _extract_attachments(self, msg: email.message.Message) -> list:
        """Wyciąga załączniki."""
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                filename = part.get_filename()
                if filename:
                    attachments.append({
                        "filename": filename,
                        "content_type": part.get_content_type(),
                        "size": len(part.get_payload(decode=True) or b"")
                    })
        
        return attachments
    
    def status(self) -> Dict[str, Any]:
        """Status listenera."""
        return {
            "running": self._running,
            "connected": self._imap is not None,
            "host": self.imap_host,
            "folder": self.folder,
            "check_interval": self.check_interval
        }
