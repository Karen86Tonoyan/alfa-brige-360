"""
ALFA Delta Listener v1.0
Nasłuchuje na nowe wiadomości przez IMAP
"""

from __future__ import annotations

import asyncio
import email
import imaplib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from email.header import decode_header
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("alfa.delta.listener")


@dataclass
class DeltaMessage:
    """Reprezentacja wiadomości Delta Chat."""
    
    uid: str
    sender: str
    subject: str
    body: str
    timestamp: datetime
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    raw: Optional[email.message.Message] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,
            "sender": self.sender,
            "subject": self.subject,
            "body": self.body,
            "timestamp": self.timestamp.isoformat(),
            "attachments": [a["filename"] for a in self.attachments],
        }


class DeltaListener:
    """
    IMAP Listener dla Delta Chat.
    
    Nasłuchuje na nowe wiadomości i przekazuje je do przetworzenia.
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        *,
        ssl: bool = True,
        folder: str = "INBOX",
        poll_interval: float = 5.0,
        allowed_senders: Optional[List[str]] = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ssl = ssl
        self.folder = folder
        self.poll_interval = poll_interval
        self.allowed_senders = allowed_senders or []
        
        self._connection: Optional[imaplib.IMAP4_SSL] = None
        self._running = False
        self._handlers: List[Callable[[DeltaMessage], None]] = []
        self._last_uid: Optional[str] = None
        
    # --- Connection Management ---
    
    def connect(self) -> bool:
        """Połącz z serwerem IMAP."""
        try:
            if self.ssl:
                self._connection = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                self._connection = imaplib.IMAP4(self.host, self.port)
                
            self._connection.login(self.username, self.password)
            self._connection.select(self.folder)
            
            logger.info(f"[DELTA] Connected to {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"[DELTA] Connection failed: {e}")
            return False
            
    def disconnect(self) -> None:
        """Rozłącz z serwerem."""
        if self._connection:
            try:
                self._connection.logout()
            except Exception:
                pass
            self._connection = None
            logger.info("[DELTA] Disconnected")
            
    # --- Message Handling ---
    
    def register_handler(self, handler: Callable[[DeltaMessage], None]) -> None:
        """Zarejestruj handler dla nowych wiadomości."""
        self._handlers.append(handler)
        
    def _decode_header(self, header: str) -> str:
        """Dekoduj nagłówek email."""
        if not header:
            return ""
        decoded = decode_header(header)
        parts = []
        for content, encoding in decoded:
            if isinstance(content, bytes):
                parts.append(content.decode(encoding or "utf-8", errors="replace"))
            else:
                parts.append(content)
        return "".join(parts)
        
    def _parse_message(self, uid: str, raw_data: bytes) -> Optional[DeltaMessage]:
        """Parsuj surową wiadomość email."""
        try:
            msg = email.message_from_bytes(raw_data)
            
            # Wyciągnij podstawowe dane
            sender = self._decode_header(msg.get("From", ""))
            subject = self._decode_header(msg.get("Subject", ""))
            date_str = msg.get("Date", "")
            
            # Sprawdź allowed senders
            if self.allowed_senders:
                sender_email = sender.lower()
                if not any(allowed.lower() in sender_email for allowed in self.allowed_senders):
                    logger.debug(f"[DELTA] Sender not allowed: {sender}")
                    return None
                    
            # Parsuj datę
            try:
                timestamp = email.utils.parsedate_to_datetime(date_str)
            except Exception:
                timestamp = datetime.utcnow()
                
            # Wyciągnij body i attachments
            body = ""
            attachments = []
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    disposition = str(part.get("Content-Disposition", ""))
                    
                    if "attachment" in disposition:
                        filename = part.get_filename() or "attachment"
                        attachments.append({
                            "filename": filename,
                            "content_type": content_type,
                            "data": part.get_payload(decode=True),
                        })
                    elif content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="replace")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")
                    
            return DeltaMessage(
                uid=uid,
                sender=sender,
                subject=subject,
                body=body.strip(),
                timestamp=timestamp,
                attachments=attachments,
                raw=msg,
            )
            
        except Exception as e:
            logger.error(f"[DELTA] Failed to parse message {uid}: {e}")
            return None
            
    def fetch_new_messages(self) -> List[DeltaMessage]:
        """Pobierz nowe wiadomości."""
        if not self._connection:
            return []
            
        messages = []
        
        try:
            # Szukaj nieprzeczytanych
            status, data = self._connection.search(None, "UNSEEN")
            if status != "OK":
                return []
                
            uids = data[0].split()
            
            for uid in uids:
                uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
                
                # Pobierz wiadomość
                status, msg_data = self._connection.fetch(uid, "(RFC822)")
                if status != "OK":
                    continue
                    
                raw_email = msg_data[0][1]
                message = self._parse_message(uid_str, raw_email)
                
                if message:
                    messages.append(message)
                    self._last_uid = uid_str
                    
        except Exception as e:
            logger.error(f"[DELTA] Fetch error: {e}")
            # Reconnect on error
            self.disconnect()
            self.connect()
            
        return messages
        
    def _dispatch_message(self, message: DeltaMessage) -> None:
        """Wyślij wiadomość do wszystkich handlerów."""
        for handler in self._handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"[DELTA] Handler error: {e}")
                
    # --- Async Loop ---
    
    async def start_listening(self) -> None:
        """Rozpocznij nasłuchiwanie (async)."""
        if not self.connect():
            raise RuntimeError("Failed to connect to IMAP server")
            
        self._running = True
        logger.info(f"[DELTA] Listening started (poll every {self.poll_interval}s)")
        
        while self._running:
            messages = self.fetch_new_messages()
            
            for message in messages:
                logger.info(f"[DELTA] New message from {message.sender}: {message.subject[:50]}")
                self._dispatch_message(message)
                
            await asyncio.sleep(self.poll_interval)
            
    def stop_listening(self) -> None:
        """Zatrzymaj nasłuchiwanie."""
        self._running = False
        self.disconnect()
        logger.info("[DELTA] Listening stopped")
        
    # --- Sync API ---
    
    def poll_once(self) -> List[DeltaMessage]:
        """Jednorazowe odpytanie (sync)."""
        if not self._connection:
            if not self.connect():
                return []
        return self.fetch_new_messages()
