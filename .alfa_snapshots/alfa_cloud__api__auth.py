"""
🔐 ALFA CLOUD AUTH
Autoryzacja lokalna dla ALFA CLOUD OFFLINE
"""

from __future__ import annotations
import os
import hashlib
import secrets
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass

from fastapi import Header, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Token developerski (zmień na produkcji!)
DEV_TOKEN = "alfa-dev-token"

# Ścieżka do tokensów
TOKENS_PATH = Path(__file__).parent.parent / "config" / "tokens.json"

# Bearer security
security = HTTPBearer(auto_error=False)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA CLASSES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class User:
    """Użytkownik lokalny"""
    id: str
    name: str
    role: str = "user"
    created_at: str = ""


@dataclass
class Token:
    """Token sesji"""
    token: str
    user_id: str
    expires_at: datetime
    created_at: datetime


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOKEN STORAGE (prosty plik JSON)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TokenStore:
    """Magazyn tokenów"""
    
    def __init__(self, path: Path = TOKENS_PATH):
        self.path = path
        self._tokens: Dict[str, dict] = {}
        self._load()
    
    def _load(self):
        """Ładuje tokeny z pliku"""
        if self.path.exists():
            try:
                self._tokens = json.loads(self.path.read_text(encoding='utf-8'))
            except:
                self._tokens = {}
    
    def _save(self):
        """Zapisuje tokeny do pliku"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._tokens, indent=2), encoding='utf-8')
    
    def add(self, token: str, user_id: str, expires_minutes: int = 120):
        """Dodaje token"""
        expires_at = datetime.now() + timedelta(minutes=expires_minutes)
        self._tokens[token] = {
            "user_id": user_id,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now().isoformat()
        }
        self._save()
    
    def validate(self, token: str) -> Optional[str]:
        """Waliduje token, zwraca user_id lub None"""
        # Dev token - zawsze valid
        if token == DEV_TOKEN:
            return "dev"
        
        if token not in self._tokens:
            return None
        
        data = self._tokens[token]
        expires_at = datetime.fromisoformat(data["expires_at"])
        
        if datetime.now() > expires_at:
            # Token wygasł
            del self._tokens[token]
            self._save()
            return None
        
        return data["user_id"]
    
    def revoke(self, token: str):
        """Usuwa token"""
        if token in self._tokens:
            del self._tokens[token]
            self._save()
    
    def revoke_all(self, user_id: str):
        """Usuwa wszystkie tokeny użytkownika"""
        to_remove = [t for t, d in self._tokens.items() if d["user_id"] == user_id]
        for t in to_remove:
            del self._tokens[t]
        self._save()


# Globalny store
_token_store = TokenStore()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PASSWORD UTILS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, bytes]:
    """
    Hashuje hasło z PBKDF2 (fallback dla argon2)
    
    Returns:
        (hash_hex, salt)
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        iterations=100000,
        dklen=32
    )
    
    return key.hex(), salt


def verify_password(password: str, hash_hex: str, salt: bytes) -> bool:
    """Weryfikuje hasło"""
    expected, _ = hash_password(password, salt)
    return secrets.compare_digest(expected, hash_hex)


def generate_token(length: int = 32) -> str:
    """Generuje losowy token"""
    return secrets.token_urlsafe(length)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DEPENDENCIES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(None)
):
    """
    Wymaga autoryzacji Bearer token
    
    Akceptuje:
    - Header: Authorization: Bearer <token>
    - Lub dev token dla developmentu
    """
    token = None
    
    # Z HTTPBearer
    if credentials:
        token = credentials.credentials
    # Z raw header
    elif authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Brak tokenu autoryzacji",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id = _token_store.validate(token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy lub wygasły token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user_id


async def get_current_user(user_id: str = Depends(require_auth)) -> User:
    """Pobiera aktualnego użytkownika"""
    # W prostej wersji - zwracamy User z ID
    return User(id=user_id, name=user_id, role="admin" if user_id == "dev" else "user")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AUTH FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def login(user_id: str, expires_minutes: int = 120) -> str:
    """
    Loguje użytkownika i zwraca token
    """
    token = generate_token()
    _token_store.add(token, user_id, expires_minutes)
    return token


def logout(token: str):
    """Wylogowuje (unieważnia token)"""
    _token_store.revoke(token)


def logout_all(user_id: str):
    """Wylogowuje wszystkie sesje użytkownika"""
    _token_store.revoke_all(user_id)
