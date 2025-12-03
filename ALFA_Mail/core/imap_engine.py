#!/usr/bin/env python3
"""
MAGESTIK MAIL / ALFA Mail - IMAP ENGINE v1.0
=============================================
IMAP client with retry logic, parser, and database pipeline.

Features:
- IMAP_SSL secure connection
- Exponential backoff retry
- Full mail parser (headers + body + attachments)
- Pipeline: fetch → parse → database
- Fingerprint extraction (Cerber prep)
- Comprehensive logging

Author: ALFA System / Karen86Tonoyan
"""

import imaplib
import email
import email.header
import email.utils
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from email.message import Message
from pathlib import Path

from database import MagestikDatabase, MailRecord

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [IMAP] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class IMAPConfig:
    """IMAP connection configuration."""
    host: str
    port: int = 993
    username: str = ""
    password: str = ""
    use_ssl: bool = True
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 2.0


# =============================================================================
# MAIL PARSER
# =============================================================================

class MailParser:
    """
    Email parser - extracts all relevant data from email.message.Message.
    Prepares data for database storage.
    """

    @staticmethod
    def decode_header(header_value: str) -> str:
        """Decode email header to readable string."""
        if not header_value:
            return ""
        
        try:
            decoded_parts = email.header.decode_header(header_value)
            result = []
            for part, charset in decoded_parts:
                if isinstance(part, bytes):
                    charset = charset or 'utf-8'
                    try:
                        part = part.decode(charset, errors='replace')
                    except (LookupError, UnicodeDecodeError):
                        part = part.decode('utf-8', errors='replace')
                result.append(str(part))
            return ' '.join(result).strip()
        except Exception as e:
            logger.warning(f"Header decode error: {e}")
            return str(header_value)

    @staticmethod
    def parse_email_address(addr_str: str) -> Tuple[str, str]:
        """Parse email address. Returns (name, email)."""
        if not addr_str:
            return ("", "")
        try:
            name, email_addr = email.utils.parseaddr(addr_str)
            return (MailParser.decode_header(name), email_addr)
        except:
            return ("", addr_str)

    @staticmethod
    def get_body(msg: Message) -> Tuple[str, str]:
        """
        Extract plain text and HTML body from message.
        Returns (plain_text, html_text).
        """
        plain_body = ""
        html_body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                try:
                    payload = part.get_payload(decode=True)
                    if payload is None:
                        continue
                    
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        text = payload.decode(charset, errors='replace')
                    except (LookupError, UnicodeDecodeError):
                        text = payload.decode('utf-8', errors='replace')
                    
                    if content_type == "text/plain" and not plain_body:
                        plain_body = text
                    elif content_type == "text/html" and not html_body:
                        html_body = text
                        
                except Exception as e:
                    logger.debug(f"Body extraction error: {e}")
                    continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or 'utf-8'
                    try:
                        text = payload.decode(charset, errors='replace')
                    except (LookupError, UnicodeDecodeError):
                        text = payload.decode('utf-8', errors='replace')
                    
                    if msg.get_content_type() == "text/html":
                        html_body = text
                    else:
                        plain_body = text
            except Exception as e:
                logger.debug(f"Single-part body error: {e}")
        
        return (plain_body, html_body)

    @staticmethod
    def get_attachments(msg: Message) -> List[Dict[str, Any]]:
        """Extract attachment metadata (not content)."""
        attachments = []
        
        if not msg.is_multipart():
            return attachments
        
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    filename = MailParser.decode_header(filename)
                    content_type = part.get_content_type()
                    size = len(part.get_payload(decode=True) or b"")
                    
                    attachments.append({
                        "filename": filename,
                        "content_type": content_type,
                        "size": size
                    })
        
        return attachments

    @staticmethod
    def compute_fingerprint(body: str, sender: str) -> str:
        """
        Compute sender fingerprint hash based on writing style.
        Used by Cerber Guardian for anomaly detection.
        """
        if not body:
            return hashlib.md5(sender.encode()).hexdigest()[:16]
        
        # Extract style features
        words = body.split()
        if not words:
            return hashlib.md5(sender.encode()).hexdigest()[:16]
        
        avg_word_len = sum(len(w) for w in words) / len(words)
        punct_count = sum(1 for c in body if c in '.,!?;:')
        caps_count = sum(1 for c in body if c.isupper())
        
        # Create feature string
        features = f"{sender}|{avg_word_len:.2f}|{punct_count}|{caps_count}"
        return hashlib.md5(features.encode()).hexdigest()[:16]

    @classmethod
    def parse(cls, uid: str, raw_email: bytes, folder: str = "INBOX") -> MailRecord:
        """
        Parse raw email bytes into MailRecord.
        Main entry point for parsing.
        """
        msg = email.message_from_bytes(raw_email)
        
        # Headers
        subject = cls.decode_header(msg.get("Subject", ""))
        sender_name, sender_email = cls.parse_email_address(msg.get("From", ""))
        sender = f"{sender_name} <{sender_email}>" if sender_name else sender_email
        
        # Recipients
        to_addrs = msg.get_all("To", [])
        cc_addrs = msg.get_all("Cc", [])
        recipients = []
        for addr in to_addrs + cc_addrs:
            _, email_addr = cls.parse_email_address(addr)
            if email_addr:
                recipients.append(email_addr)
        
        # Dates
        date_sent = msg.get("Date", "")
        try:
            parsed_date = email.utils.parsedate_to_datetime(date_sent)
            date_sent = parsed_date.isoformat()
        except:
            date_sent = ""
        
        date_received = datetime.now().isoformat()
        
        # Message ID
        message_id = msg.get("Message-ID", "") or ""
        
        # Body
        plain_body, html_body = cls.get_body(msg)
        
        # Attachments
        attachments = cls.get_attachments(msg)
        
        # Fingerprint
        fingerprint = cls.compute_fingerprint(plain_body, sender_email)
        
        return MailRecord(
            uid=uid,
            message_id=message_id,
            subject=subject,
            sender=sender,
            recipients=json.dumps(recipients),
            date_sent=date_sent,
            date_received=date_received,
            body_plain=plain_body,
            body_html=html_body,
            attachments=json.dumps(attachments),
            folder=folder,
            fingerprint=fingerprint
        )


# =============================================================================
# IMAP ENGINE
# =============================================================================

class IMAPEngine:
    """
    IMAP client with retry logic and database pipeline.
    Thread-safe, supports multiple folders.
    """

    def __init__(self, config: IMAPConfig, db: MagestikDatabase = None):
        self.config = config
        self.db = db or MagestikDatabase()
        self._connection: Optional[imaplib.IMAP4_SSL] = None
        self._parser = MailParser()
        
        logger.info(f"IMAP Engine initialized for {config.host}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to IMAP server."""
        if self._connection is None:
            return False
        try:
            self._connection.noop()
            return True
        except:
            return False

    def _retry_operation(self, operation, *args, **kwargs):
        """Execute operation with exponential backoff retry."""
        last_error = None
        
        for attempt in range(1, self.config.max_retries + 1):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"Attempt {attempt} failed: {e}. Retrying in {delay}s..."
                    )
                    time.sleep(delay)
        
        logger.error(f"All {self.config.max_retries} attempts failed: {last_error}")
        raise last_error

    def connect(self) -> bool:
        """Connect to IMAP server."""
        def _do_connect():
            if self.config.use_ssl:
                self._connection = imaplib.IMAP4_SSL(
                    self.config.host,
                    self.config.port,
                    timeout=self.config.timeout
                )
            else:
                self._connection = imaplib.IMAP4(
                    self.config.host,
                    self.config.port
                )
                self._connection.starttls()
            
            self._connection.login(
                self.config.username,
                self.config.password
            )
            
            logger.info(f"Connected to {self.config.host} as {self.config.username}")
            return True
        
        try:
            return self._retry_operation(_do_connect)
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Disconnect from IMAP server."""
        if self._connection:
            try:
                self._connection.logout()
            except:
                pass
            self._connection = None
            logger.info("Disconnected from IMAP server")

    def list_folders(self) -> List[str]:
        """List available folders/mailboxes."""
        if not self.is_connected:
            if not self.connect():
                return []
        
        try:
            status, folders = self._connection.list()
            if status != "OK":
                return []
            
            result = []
            for folder in folders:
                if isinstance(folder, bytes):
                    # Parse folder name from response
                    match = re.search(rb'"([^"]+)"$|(\S+)$', folder)
                    if match:
                        name = match.group(1) or match.group(2)
                        result.append(name.decode('utf-8', errors='replace'))
            
            logger.debug(f"Found {len(result)} folders")
            return result
            
        except Exception as e:
            logger.error(f"Failed to list folders: {e}")
            return []

    def get_folder_status(self, folder: str = "INBOX") -> Dict[str, int]:
        """Get folder status (total, unseen, recent)."""
        if not self.is_connected:
            if not self.connect():
                return {}
        
        try:
            status, data = self._connection.select(folder, readonly=True)
            if status != "OK":
                return {}
            
            total = int(data[0])
            
            # Get unseen count
            status, data = self._connection.search(None, "UNSEEN")
            unseen = len(data[0].split()) if status == "OK" and data[0] else 0
            
            return {
                "total": total,
                "unseen": unseen,
                "folder": folder
            }
            
        except Exception as e:
            logger.error(f"Failed to get folder status: {e}")
            return {}

    def fetch_uids(
        self,
        folder: str = "INBOX",
        criteria: str = "ALL",
        limit: int = 100
    ) -> List[str]:
        """Fetch message UIDs matching criteria."""
        if not self.is_connected:
            if not self.connect():
                return []
        
        try:
            status, _ = self._connection.select(folder, readonly=True)
            if status != "OK":
                logger.error(f"Failed to select folder {folder}")
                return []
            
            status, data = self._connection.uid("SEARCH", None, criteria)
            if status != "OK":
                return []
            
            uids = data[0].split() if data[0] else []
            uids = [uid.decode() for uid in uids]
            
            # Return most recent UIDs (last N)
            if limit and len(uids) > limit:
                uids = uids[-limit:]
            
            logger.debug(f"Found {len(uids)} UIDs in {folder}")
            return uids
            
        except Exception as e:
            logger.error(f"Failed to fetch UIDs: {e}")
            return []

    def fetch_new_uids(self, folder: str = "INBOX", since_days: int = 7) -> List[str]:
        """Fetch UIDs of mails received in last N days."""
        since_date = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
        return self.fetch_uids(folder, f'(SINCE "{since_date}")')

    def fetch_mail(self, uid: str, folder: str = "INBOX") -> Optional[MailRecord]:
        """Fetch and parse single mail by UID."""
        if not self.is_connected:
            if not self.connect():
                return None
        
        try:
            status, _ = self._connection.select(folder, readonly=True)
            if status != "OK":
                return None
            
            status, data = self._connection.uid("FETCH", uid, "(RFC822)")
            if status != "OK" or not data or not data[0]:
                return None
            
            raw_email = data[0][1]
            mail = self._parser.parse(uid, raw_email, folder)
            
            logger.debug(f"Fetched mail UID {uid}: {mail.subject[:50]}")
            return mail
            
        except Exception as e:
            logger.error(f"Failed to fetch mail UID {uid}: {e}")
            return None

    def sync_folder(
        self,
        folder: str = "INBOX",
        limit: int = 100,
        since_days: int = 30
    ) -> Dict[str, int]:
        """
        Sync folder: fetch new mails → parse → store in database.
        Returns sync statistics.
        """
        stats = {"fetched": 0, "new": 0, "errors": 0}
        
        logger.info(f"Starting sync for {folder} (last {since_days} days, limit {limit})")
        
        # Get UIDs
        uids = self.fetch_new_uids(folder, since_days)
        if not uids:
            logger.info(f"No new mails in {folder}")
            return stats
        
        # Limit UIDs
        if len(uids) > limit:
            uids = uids[-limit:]  # Most recent
        
        # Fetch and store
        mails_to_insert = []
        
        for uid in uids:
            # Check if already in database
            existing = self.db.get_mail_by_uid(uid, folder)
            if existing:
                continue
            
            mail = self.fetch_mail(uid, folder)
            if mail:
                mails_to_insert.append(mail)
                stats["fetched"] += 1
            else:
                stats["errors"] += 1
        
        # Batch insert
        if mails_to_insert:
            stats["new"] = self.db.insert_mails_batch(mails_to_insert)
        
        logger.info(
            f"Sync complete: {stats['fetched']} fetched, "
            f"{stats['new']} new, {stats['errors']} errors"
        )
        
        return stats

    def fetch_all_folders(self, limit_per_folder: int = 50) -> Dict[str, Dict]:
        """Sync all folders."""
        folders = self.list_folders()
        results = {}
        
        for folder in folders:
            # Skip special folders
            if folder.lower() in ['[gmail]', 'drafts', 'trash', 'spam', 'junk']:
                continue
            
            try:
                results[folder] = self.sync_folder(folder, limit=limit_per_folder)
            except Exception as e:
                logger.error(f"Failed to sync {folder}: {e}")
                results[folder] = {"error": str(e)}
        
        return results


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MAGESTIK MAIL IMAP ENGINE v1.0")
    print("=" * 60)
    
    # Test parser only (no IMAP connection)
    print("\n[TEST] Mail Parser...")
    
    # Create mock email
    mock_raw = b"""From: John Doe <john@example.com>
To: king@alfa.local
Subject: Test Email for Magestik
Date: Thu, 01 Jan 2025 12:00:00 +0000
Message-ID: <test123@example.com>
Content-Type: text/plain; charset="utf-8"

Hello, this is a test email for the Magestik Mail system.
Testing parser functionality.

Best regards,
John
"""
    
    mail = MailParser.parse("TEST_UID_001", mock_raw, "INBOX")
    
    print(f"  Subject: {mail.subject}")
    print(f"  Sender: {mail.sender}")
    print(f"  Date: {mail.date_sent}")
    print(f"  Fingerprint: {mail.fingerprint}")
    print(f"  Body preview: {mail.body_plain[:50]}...")
    
    print("\n[INFO] IMAP connection test requires real credentials.")
    print("[INFO] Set up config/magestik_config.json with IMAP details.")
    
    # Example config (not used without real server)
    example_config = IMAPConfig(
        host="imap.gmail.com",
        port=993,
        username="your-email@gmail.com",
        password="your-app-password",
        use_ssl=True
    )
    
    print(f"\n[EXAMPLE] Config: {example_config.host}:{example_config.port}")
    print("\n[DONE] IMAP Engine test completed.")
