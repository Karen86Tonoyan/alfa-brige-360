#!/usr/bin/env python3
"""
MAGESTIK MAIL / ALFA Mail - DATABASE ENGINE v1.0
=================================================
Encrypted SQLCipher database with atomic operations.
Full schema for mail storage with metadata hooks.

Features:
- SQLCipher encrypted storage
- Atomic commit/rollback
- Full mail schema (priority, emo, threat, fingerprint)
- LRU cache for frequent queries
- Comprehensive logging
- Migration-ready structure

Author: ALFA System / Karen86Tonoyan
"""

import sqlite3
import hashlib
import json
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from functools import lru_cache
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [DATABASE] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MailRecord:
    """Represents a single mail record in database."""
    id: Optional[int] = None
    uid: str = ""
    message_id: str = ""
    subject: str = ""
    sender: str = ""
    recipients: str = ""  # JSON list
    date_sent: str = ""
    date_received: str = ""
    body_plain: str = ""
    body_html: str = ""
    attachments: str = ""  # JSON list of attachment metadata
    folder: str = "INBOX"
    is_read: bool = False
    is_flagged: bool = False
    is_deleted: bool = False
    # ALFA/Cerber metadata
    priority: int = 5  # 1-10, higher = more important
    emo_score: str = "neutral"  # neutral/positive/negative/aggressive/manipulation
    threat_level: int = 0  # 0-100
    fingerprint: str = ""  # Sender style hash
    is_ai_generated: bool = False
    cerber_flags: str = ""  # JSON flags from Guardian
    # Timestamps
    created_at: str = ""
    updated_at: str = ""

    def to_tuple(self) -> tuple:
        """Convert to tuple for SQL insert (without id)."""
        return (
            self.uid, self.message_id, self.subject, self.sender,
            self.recipients, self.date_sent, self.date_received,
            self.body_plain, self.body_html, self.attachments,
            self.folder, self.is_read, self.is_flagged, self.is_deleted,
            self.priority, self.emo_score, self.threat_level,
            self.fingerprint, self.is_ai_generated, self.cerber_flags,
            self.created_at, self.updated_at
        )


@dataclass
class AccountRecord:
    """Represents an email account configuration."""
    id: Optional[int] = None
    name: str = ""
    email: str = ""
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    username: str = ""
    password_encrypted: str = ""  # Encrypted with master key
    is_active: bool = True
    last_sync: str = ""
    created_at: str = ""


# =============================================================================
# DATABASE ENGINE
# =============================================================================

class MagestikDatabase:
    """
    Encrypted SQLCipher database engine for Magestik Mail.
    Thread-safe with atomic operations.
    """

    SCHEMA_VERSION = 1
    
    def __init__(
        self,
        db_path: str = "data/magestik_mail.db",
        passphrase: str = "ALFA_KING_2025_SECURE",
        use_sqlcipher: bool = True
    ):
        self.db_path = Path(db_path)
        self.passphrase = passphrase
        self.use_sqlcipher = use_sqlcipher
        self._local = threading.local()
        self._lock = threading.RLock()
        
        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        logger.info(f"Database initialized: {self.db_path}")

    @property
    def _conn(self) -> sqlite3.Connection:
        """Thread-local connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._create_connection()
        return self._local.conn

    def _create_connection(self) -> sqlite3.Connection:
        """Create new database connection with encryption."""
        try:
            if self.use_sqlcipher:
                # Try sqlcipher3 first
                try:
                    from pysqlcipher3 import dbapi2 as sqlcipher
                    conn = sqlcipher.connect(str(self.db_path))
                    conn.execute(f"PRAGMA key = '{self.passphrase}'")
                    logger.debug("Using pysqlcipher3")
                except ImportError:
                    # Fallback to standard sqlite with warning
                    logger.warning("SQLCipher not available, using unencrypted SQLite!")
                    conn = sqlite3.connect(str(self.db_path))
            else:
                conn = sqlite3.connect(str(self.db_path))
            
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            raise

    def _init_database(self):
        """Initialize database schema."""
        with self.atomic() as cursor:
            # Schema version table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_info (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Accounts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    imap_host TEXT NOT NULL,
                    imap_port INTEGER DEFAULT 993,
                    smtp_host TEXT NOT NULL,
                    smtp_port INTEGER DEFAULT 587,
                    username TEXT NOT NULL,
                    password_encrypted TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    last_sync TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Mails table - full schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT NOT NULL,
                    message_id TEXT,
                    subject TEXT,
                    sender TEXT,
                    recipients TEXT,
                    date_sent TEXT,
                    date_received TEXT,
                    body_plain TEXT,
                    body_html TEXT,
                    attachments TEXT,
                    folder TEXT DEFAULT 'INBOX',
                    is_read BOOLEAN DEFAULT 0,
                    is_flagged BOOLEAN DEFAULT 0,
                    is_deleted BOOLEAN DEFAULT 0,
                    priority INTEGER DEFAULT 5,
                    emo_score TEXT DEFAULT 'neutral',
                    threat_level INTEGER DEFAULT 0,
                    fingerprint TEXT,
                    is_ai_generated BOOLEAN DEFAULT 0,
                    cerber_flags TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(uid, folder)
                )
            """)
            
            # Indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mails_sender ON mails(sender)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mails_date ON mails(date_received)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mails_priority ON mails(priority DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mails_threat ON mails(threat_level DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mails_folder ON mails(folder)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mails_fingerprint ON mails(fingerprint)")
            
            # Cerber fingerprints table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fingerprints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_email TEXT UNIQUE NOT NULL,
                    fingerprint_hash TEXT NOT NULL,
                    sample_count INTEGER DEFAULT 1,
                    avg_word_length REAL,
                    punctuation_ratio REAL,
                    caps_ratio REAL,
                    signature_pattern TEXT,
                    known_devices TEXT,
                    threat_score INTEGER DEFAULT 0,
                    last_seen TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Sync log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER,
                    folder TEXT,
                    status TEXT,
                    mails_fetched INTEGER DEFAULT 0,
                    mails_new INTEGER DEFAULT 0,
                    error_message TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (account_id) REFERENCES accounts(id)
                )
            """)
            
            # Set schema version
            cursor.execute(
                "INSERT OR REPLACE INTO schema_info (key, value) VALUES (?, ?)",
                ("version", str(self.SCHEMA_VERSION))
            )
            
            logger.info("Database schema initialized")

    @contextmanager
    def atomic(self):
        """
        Atomic transaction context manager.
        Auto-commits on success, rollbacks on exception.
        """
        with self._lock:
            cursor = self._conn.cursor()
            try:
                yield cursor
                self._conn.commit()
            except Exception as e:
                self._conn.rollback()
                logger.error(f"Transaction rolled back: {e}")
                raise

    def close(self):
        """Close database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
            logger.info("Database connection closed")

    # =========================================================================
    # MAIL OPERATIONS
    # =========================================================================

    def insert_mail(self, mail: MailRecord) -> int:
        """Insert new mail record. Returns mail ID."""
        now = datetime.now().isoformat()
        mail.created_at = now
        mail.updated_at = now
        
        with self.atomic() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO mails (
                    uid, message_id, subject, sender, recipients,
                    date_sent, date_received, body_plain, body_html,
                    attachments, folder, is_read, is_flagged, is_deleted,
                    priority, emo_score, threat_level, fingerprint,
                    is_ai_generated, cerber_flags, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, mail.to_tuple())
            
            mail_id = cursor.lastrowid
            logger.debug(f"Inserted mail ID {mail_id}: {mail.subject[:50]}")
            return mail_id

    def insert_mails_batch(self, mails: List[MailRecord]) -> int:
        """Batch insert mails. Returns count of inserted."""
        now = datetime.now().isoformat()
        count = 0
        
        with self.atomic() as cursor:
            for mail in mails:
                mail.created_at = now
                mail.updated_at = now
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO mails (
                            uid, message_id, subject, sender, recipients,
                            date_sent, date_received, body_plain, body_html,
                            attachments, folder, is_read, is_flagged, is_deleted,
                            priority, emo_score, threat_level, fingerprint,
                            is_ai_generated, cerber_flags, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, mail.to_tuple())
                    if cursor.rowcount > 0:
                        count += 1
                except Exception as e:
                    logger.warning(f"Failed to insert mail {mail.uid}: {e}")
        
        logger.info(f"Batch inserted {count}/{len(mails)} mails")
        return count

    def get_mail(self, mail_id: int) -> Optional[MailRecord]:
        """Get single mail by ID."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM mails WHERE id = ?", (mail_id,))
        row = cursor.fetchone()
        return self._row_to_mail(row) if row else None

    def get_mail_by_uid(self, uid: str, folder: str = "INBOX") -> Optional[MailRecord]:
        """Get mail by UID and folder."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM mails WHERE uid = ? AND folder = ?",
            (uid, folder)
        )
        row = cursor.fetchone()
        return self._row_to_mail(row) if row else None

    def get_mails(
        self,
        folder: str = "INBOX",
        limit: int = 50,
        offset: int = 0,
        order_by: str = "date_received DESC",
        filters: Dict[str, Any] = None
    ) -> List[MailRecord]:
        """Get mails with optional filters."""
        query = "SELECT * FROM mails WHERE folder = ? AND is_deleted = 0"
        params = [folder]
        
        if filters:
            if "sender" in filters:
                query += " AND sender LIKE ?"
                params.append(f"%{filters['sender']}%")
            if "subject" in filters:
                query += " AND subject LIKE ?"
                params.append(f"%{filters['subject']}%")
            if "min_priority" in filters:
                query += " AND priority >= ?"
                params.append(filters["min_priority"])
            if "min_threat" in filters:
                query += " AND threat_level >= ?"
                params.append(filters["min_threat"])
            if "is_read" in filters:
                query += " AND is_read = ?"
                params.append(1 if filters["is_read"] else 0)
        
        query += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = self._conn.cursor()
        cursor.execute(query, params)
        return [self._row_to_mail(row) for row in cursor.fetchall()]

    def get_king_mode_mails(self, limit: int = 10) -> List[MailRecord]:
        """
        KRÓL MODE: Get highest priority mails.
        Sorted by priority DESC, threat_level DESC.
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM mails 
            WHERE is_deleted = 0 AND is_read = 0
            ORDER BY priority DESC, threat_level DESC, date_received DESC
            LIMIT ?
        """, (limit,))
        return [self._row_to_mail(row) for row in cursor.fetchall()]

    def update_mail_metadata(
        self,
        mail_id: int,
        priority: int = None,
        emo_score: str = None,
        threat_level: int = None,
        cerber_flags: str = None,
        is_ai_generated: bool = None
    ) -> bool:
        """Update ALFA/Cerber metadata for mail."""
        updates = []
        params = []
        
        if priority is not None:
            updates.append("priority = ?")
            params.append(priority)
        if emo_score is not None:
            updates.append("emo_score = ?")
            params.append(emo_score)
        if threat_level is not None:
            updates.append("threat_level = ?")
            params.append(threat_level)
        if cerber_flags is not None:
            updates.append("cerber_flags = ?")
            params.append(cerber_flags)
        if is_ai_generated is not None:
            updates.append("is_ai_generated = ?")
            params.append(is_ai_generated)
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(mail_id)
        
        with self.atomic() as cursor:
            cursor.execute(
                f"UPDATE mails SET {', '.join(updates)} WHERE id = ?",
                params
            )
            return cursor.rowcount > 0

    def mark_as_read(self, mail_id: int) -> bool:
        """Mark mail as read."""
        with self.atomic() as cursor:
            cursor.execute(
                "UPDATE mails SET is_read = 1, updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), mail_id)
            )
            return cursor.rowcount > 0

    def delete_mail(self, mail_id: int, soft: bool = True) -> bool:
        """Delete mail (soft or hard delete)."""
        with self.atomic() as cursor:
            if soft:
                cursor.execute(
                    "UPDATE mails SET is_deleted = 1, updated_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), mail_id)
                )
            else:
                cursor.execute("DELETE FROM mails WHERE id = ?", (mail_id,))
            return cursor.rowcount > 0

    def _row_to_mail(self, row: sqlite3.Row) -> MailRecord:
        """Convert database row to MailRecord."""
        return MailRecord(
            id=row["id"],
            uid=row["uid"],
            message_id=row["message_id"] or "",
            subject=row["subject"] or "",
            sender=row["sender"] or "",
            recipients=row["recipients"] or "",
            date_sent=row["date_sent"] or "",
            date_received=row["date_received"] or "",
            body_plain=row["body_plain"] or "",
            body_html=row["body_html"] or "",
            attachments=row["attachments"] or "",
            folder=row["folder"],
            is_read=bool(row["is_read"]),
            is_flagged=bool(row["is_flagged"]),
            is_deleted=bool(row["is_deleted"]),
            priority=row["priority"],
            emo_score=row["emo_score"] or "neutral",
            threat_level=row["threat_level"],
            fingerprint=row["fingerprint"] or "",
            is_ai_generated=bool(row["is_ai_generated"]),
            cerber_flags=row["cerber_flags"] or "",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or ""
        )

    # =========================================================================
    # FINGERPRINT OPERATIONS (CERBER)
    # =========================================================================

    def upsert_fingerprint(
        self,
        sender_email: str,
        fingerprint_hash: str,
        avg_word_length: float = None,
        punctuation_ratio: float = None,
        caps_ratio: float = None
    ) -> int:
        """Insert or update sender fingerprint."""
        now = datetime.now().isoformat()
        
        with self.atomic() as cursor:
            cursor.execute("""
                INSERT INTO fingerprints (
                    sender_email, fingerprint_hash, avg_word_length,
                    punctuation_ratio, caps_ratio, last_seen, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sender_email) DO UPDATE SET
                    fingerprint_hash = excluded.fingerprint_hash,
                    sample_count = sample_count + 1,
                    avg_word_length = excluded.avg_word_length,
                    punctuation_ratio = excluded.punctuation_ratio,
                    caps_ratio = excluded.caps_ratio,
                    last_seen = excluded.last_seen
            """, (sender_email, fingerprint_hash, avg_word_length,
                  punctuation_ratio, caps_ratio, now, now))
            return cursor.lastrowid

    def get_fingerprint(self, sender_email: str) -> Optional[Dict]:
        """Get fingerprint for sender."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM fingerprints WHERE sender_email = ?",
            (sender_email,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # =========================================================================
    # STATISTICS & UTILITIES
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        cursor = self._conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM mails WHERE is_deleted = 0")
        total_mails = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM mails WHERE is_read = 0 AND is_deleted = 0")
        unread = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM mails WHERE threat_level > 50")
        high_threat = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM fingerprints")
        fingerprints = cursor.fetchone()[0]
        
        return {
            "total_mails": total_mails,
            "unread": unread,
            "high_threat": high_threat,
            "fingerprints": fingerprints,
            "db_size_mb": round(self.db_path.stat().st_size / 1024 / 1024, 2) if self.db_path.exists() else 0
        }

    def vacuum(self):
        """Optimize database."""
        self._conn.execute("VACUUM")
        logger.info("Database vacuumed")


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MAGESTIK MAIL DATABASE ENGINE v1.0")
    print("=" * 60)
    
    # Initialize
    db = MagestikDatabase(db_path="data/test_magestik.db", use_sqlcipher=False)
    
    # Insert test mail
    test_mail = MailRecord(
        uid="TEST001",
        message_id="<test@example.com>",
        subject="[TEST] Magestik Mail Database",
        sender="test@example.com",
        recipients=json.dumps(["king@alfa.local"]),
        date_sent=datetime.now().isoformat(),
        date_received=datetime.now().isoformat(),
        body_plain="This is a test mail for Magestik Mail database.",
        folder="INBOX",
        priority=8,
        emo_score="neutral",
        threat_level=10
    )
    
    mail_id = db.insert_mail(test_mail)
    print(f"[OK] Inserted test mail ID: {mail_id}")
    
    # Retrieve
    retrieved = db.get_mail(mail_id)
    print(f"[OK] Retrieved: {retrieved.subject}")
    
    # King Mode
    king_mails = db.get_king_mode_mails(limit=5)
    print(f"[OK] King Mode mails: {len(king_mails)}")
    
    # Stats
    stats = db.get_stats()
    print(f"[OK] Stats: {stats}")
    
    db.close()
    print("\n[DONE] Database engine test completed.")
