"""
ALFA_MIRROR PRO — INTEGRATED ENGINE
Pełny silnik archiwizacji Gemini z wszystkimi modułami.
Poziom: PRODUCTION-READY + OPUS-LEVEL
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, asdict, field
import threading
import uuid

logger = logging.getLogger("ALFA.Mirror.Engine")


# ═══════════════════════════════════════════════════════════════════════════
# KONFIGURACJA
# ═══════════════════════════════════════════════════════════════════════════

MIRROR_ROOT = Path("storage/gemini_mirror")
MIRROR_ROOT.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MirrorSession:
    """Reprezentuje sesję archiwizacji."""
    session_id: str
    created_at: str
    folder: str
    files: List[str] = field(default_factory=list)
    text_count: int = 0
    image_count: int = 0
    video_count: int = 0
    audio_count: int = 0
    file_count: int = 0
    function_count: int = 0
    total_size_bytes: int = 0
    has_summary: bool = False
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MirrorStats:
    """Statystyki MIRROR."""
    total_sessions: int
    total_files: int
    total_size_mb: float
    sessions_with_media: int
    sessions_with_summary: int
    by_month: Dict[str, int]


# ═══════════════════════════════════════════════════════════════════════════
# CERBER INTEGRATION — CONTENT FILTER
# ═══════════════════════════════════════════════════════════════════════════

class CerberContentFilter:
    """
    Cerber jako sumienie AI — filtruje nieetyczne treści.
    """
    
    # Zakazane wzorce w tekście
    FORBIDDEN_PATTERNS = [
        # Przemoc
        r'\b(kill|murder|attack|bomb|weapon)\b.*\b(how|tutorial|guide)\b',
        # Nielegalne
        r'\b(hack|crack|exploit)\b.*\b(password|account|system)\b',
        # NSFW
        r'\b(porn|xxx|nsfw|nude)\b',
    ]
    
    # Dozwolone konteksty (edukacja, bezpieczeństwo)
    ALLOWED_CONTEXTS = [
        "security research",
        "penetration testing",
        "educational",
        "defensive",
        "ethical hacking"
    ]
    
    def __init__(self, strict: bool = False):
        self.strict = strict
        self._violations: List[dict] = []
        
    def check_text(self, text: str) -> tuple[bool, str]:
        """
        Sprawdza tekst pod kątem naruszeń.
        
        Returns:
            (is_safe, reason)
        """
        import re
        
        text_lower = text.lower()
        
        # Sprawdź dozwolone konteksty
        for context in self.ALLOWED_CONTEXTS:
            if context in text_lower:
                return True, "allowed_context"
        
        # Sprawdź zakazane wzorce
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                reason = f"forbidden_pattern: {pattern[:30]}..."
                self._log_violation(text[:100], reason)
                
                if self.strict:
                    return False, reason
                else:
                    # W trybie non-strict - loguj ale przepuść
                    logger.warning(f"🛡️ CERBER: Suspicious content detected (non-strict mode)")
                    return True, "warning_logged"
        
        return True, "clean"
    
    def _log_violation(self, sample: str, reason: str) -> None:
        """Loguje naruszenie."""
        self._violations.append({
            "timestamp": datetime.now().isoformat(),
            "sample": sample,
            "reason": reason
        })
        logger.warning(f"🛡️ CERBER VIOLATION: {reason}")
    
    def get_violations(self) -> List[dict]:
        """Zwraca listę naruszeń."""
        return self._violations.copy()


# ═══════════════════════════════════════════════════════════════════════════
# MIRROR ENGINE PRO
# ═══════════════════════════════════════════════════════════════════════════

class MirrorEngine:
    """
    Główny silnik ALFA_MIRROR PRO.
    
    Features:
    - Archiwizacja wszystkich typów mediów z Gemini
    - Automatyczne thumbnails dla wideo
    - Metadata dla audio
    - Cerber content filtering
    - Hooks dla summary i autotag
    """
    
    def __init__(
        self,
        root: Optional[Path] = None,
        cerber_strict: bool = False,
        auto_thumbnail: bool = True,
        auto_summary: bool = False,
        auto_tag: bool = False
    ):
        """
        Args:
            root: Folder archiwum
            cerber_strict: Tryb ścisły Cerber (blokuje podejrzane treści)
            auto_thumbnail: Automatyczne thumbnails dla wideo
            auto_summary: Automatyczne podsumowanie sesji
            auto_tag: Automatyczne tagowanie sesji
        """
        self.root = Path(root) if root else MIRROR_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        
        self.cerber = CerberContentFilter(strict=cerber_strict)
        self.auto_thumbnail = auto_thumbnail
        self.auto_summary = auto_summary
        self.auto_tag = auto_tag
        
        self._lock = threading.RLock()
        
        # Hooks
        self._on_session_complete: List[Callable[[str], None]] = []
        
        logger.info(f"🐺 MirrorEngine initialized: {self.root}")
    
    def _generate_session_id(self) -> str:
        """Generuje unikalne ID sesji."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique = uuid.uuid4().hex[:8]
        return f"{timestamp}_{unique}"
    
    def _save_file(self, folder: Path, filename: str, data: bytes) -> Path:
        """Zapisuje plik z hash verification."""
        filepath = folder / filename
        filepath.write_bytes(data)
        
        # Zapisz hash
        hash_md5 = hashlib.md5(data).hexdigest()
        hash_file = folder / f"{filename}.md5"
        hash_file.write_text(hash_md5)
        
        return filepath
    
    def _get_extension(self, mime_type: str) -> str:
        """Mapuje MIME type na rozszerzenie."""
        mime_map = {
            # Obrazy
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/gif": "gif",
            "image/webp": "webp",
            "image/svg+xml": "svg",
            
            # Wideo
            "video/mp4": "mp4",
            "video/webm": "webm",
            "video/quicktime": "mov",
            "video/x-msvideo": "avi",
            
            # Audio
            "audio/mpeg": "mp3",
            "audio/ogg": "ogg",
            "audio/wav": "wav",
            "audio/webm": "webm",
            "audio/opus": "opus",
            
            # Dokumenty
            "application/pdf": "pdf",
            "text/plain": "txt",
            "text/markdown": "md",
            "application/json": "json",
        }
        
        return mime_map.get(mime_type, mime_type.split("/")[-1])
    
    # ═══════════════════════════════════════════════════════════════════════
    # GŁÓWNA FUNKCJA — MIRROR GEMINI RESPONSE
    # ═══════════════════════════════════════════════════════════════════════
    
    def mirror_gemini_response(
        self,
        response_data: dict,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> MirrorSession:
        """
        Archiwizuje pełną odpowiedź Gemini.
        
        Args:
            response_data: Surowa odpowiedź JSON z Gemini API
            session_id: Opcjonalne ID sesji (generowane automatycznie)
            metadata: Dodatkowe metadane do zapisania
            
        Returns:
            MirrorSession z informacjami o zarchiwizowanych plikach
        """
        with self._lock:
            # Generuj ID sesji
            if session_id is None:
                session_id = self._generate_session_id()
            
            folder = self.root / session_id
            folder.mkdir(parents=True, exist_ok=True)
            
            session = MirrorSession(
                session_id=session_id,
                created_at=datetime.now().isoformat(),
                folder=str(folder)
            )
            
            try:
                # 1. Zapisz raw.json
                raw_path = folder / "raw.json"
                raw_path.write_text(
                    json.dumps(response_data, indent=2, ensure_ascii=False),
                    encoding="utf8"
                )
                session.files.append("raw.json")
                
                # 2. Zapisz SHA256 hash
                raw_hash = hashlib.sha256(
                    json.dumps(response_data).encode()
                ).hexdigest()
                (folder / "hash.sha256").write_text(raw_hash)
                session.files.append("hash.sha256")
                
                # 3. Zapisz metadata
                if metadata:
                    (folder / "metadata.json").write_text(
                        json.dumps(metadata, indent=2),
                        encoding="utf8"
                    )
                    session.files.append("metadata.json")
                
                # 4. Parsuj candidates → parts
                candidates = response_data.get("candidates", [])
                
                for candidate in candidates:
                    content = candidate.get("content", {})
                    parts = content.get("parts", [])
                    
                    for idx, part in enumerate(parts):
                        self._process_part(folder, session, idx, part)
                
                # 5. Oblicz total size
                session.total_size_bytes = sum(
                    f.stat().st_size
                    for f in folder.iterdir()
                    if f.is_file()
                )
                
                # 6. Post-processing hooks
                self._run_post_hooks(session)
                
                logger.info(
                    f"✅ Mirrored session {session_id}: "
                    f"{session.text_count}T {session.image_count}I "
                    f"{session.video_count}V {session.audio_count}A "
                    f"{session.file_count}F"
                )
                
                # 7. Wywołaj hooki
                for hook in self._on_session_complete:
                    try:
                        hook(session_id)
                    except Exception as e:
                        logger.warning(f"Hook failed: {e}")
                
                return session
                
            except Exception as e:
                logger.error(f"Mirror failed: {e}")
                raise
    
    def _process_part(
        self,
        folder: Path,
        session: MirrorSession,
        idx: int,
        part: dict
    ) -> None:
        """Przetwarza pojedynczą część odpowiedzi."""
        
        # TEXT
        if "text" in part:
            text = part["text"]
            
            # Cerber check
            is_safe, reason = self.cerber.check_text(text)
            if not is_safe:
                text = f"[CERBER BLOCKED: {reason}]\n\n" + text[:200] + "..."
            
            filename = f"text_{idx}.md"
            (folder / filename).write_text(text, encoding="utf8")
            session.files.append(filename)
            session.text_count += 1
        
        # INLINE DATA (obrazy, audio, wideo, pliki)
        if "inlineData" in part:
            inline = part["inlineData"]
            mime = inline.get("mimeType", "application/octet-stream")
            data = base64.b64decode(inline.get("data", ""))
            ext = self._get_extension(mime)
            
            if mime.startswith("image/"):
                filename = f"image_{idx}.{ext}"
                self._save_file(folder, filename, data)
                session.files.append(filename)
                session.image_count += 1
                
            elif mime.startswith("video/"):
                filename = f"video_{idx}.{ext}"
                video_path = self._save_file(folder, filename, data)
                session.files.append(filename)
                session.video_count += 1
                
                # Auto-thumbnail
                if self.auto_thumbnail:
                    self._generate_thumbnail(video_path, folder, idx)
                
            elif mime.startswith("audio/"):
                filename = f"audio_{idx}.{ext}"
                audio_path = self._save_file(folder, filename, data)
                session.files.append(filename)
                session.audio_count += 1
                
                # Audio metadata
                self._save_audio_metadata(audio_path, folder, idx)
                
            else:
                filename = f"file_{idx}.{ext}"
                self._save_file(folder, filename, data)
                session.files.append(filename)
                session.file_count += 1
        
        # FILE DATA (Google Files API)
        if "fileData" in part:
            file_data = part["fileData"]
            mime = file_data.get("mimeType", "")
            file_uri = file_data.get("fileUri", "")
            
            # Zapisz info o pliku (nie możemy pobrać bez dodatkowego API call)
            info = {
                "mimeType": mime,
                "fileUri": file_uri,
                "idx": idx
            }
            
            info_file = folder / f"fileref_{idx}.json"
            info_file.write_text(json.dumps(info, indent=2), encoding="utf8")
            session.files.append(f"fileref_{idx}.json")
        
        # FUNCTION CALL
        if "functionCall" in part:
            func = part["functionCall"]
            filename = f"function_{idx}.json"
            (folder / filename).write_text(
                json.dumps(func, indent=2, ensure_ascii=False),
                encoding="utf8"
            )
            session.files.append(filename)
            session.function_count += 1
        
        # FUNCTION RESPONSE
        if "functionResponse" in part:
            resp = part["functionResponse"]
            filename = f"function_response_{idx}.json"
            (folder / filename).write_text(
                json.dumps(resp, indent=2, ensure_ascii=False),
                encoding="utf8"
            )
            session.files.append(filename)
    
    def _generate_thumbnail(
        self,
        video_path: Path,
        folder: Path,
        idx: int
    ) -> None:
        """Generuje thumbnail dla wideo."""
        try:
            from .mirror_thumbnails import generate_video_thumbnail
            
            thumb_path = folder / f"video_{idx}_thumb.jpg"
            result = generate_video_thumbnail(video_path, thumb_path)
            
            if result:
                logger.debug(f"   Thumbnail created: {thumb_path.name}")
        except ImportError:
            logger.debug("Thumbnails module not available")
        except Exception as e:
            logger.warning(f"Thumbnail generation failed: {e}")
    
    def _save_audio_metadata(
        self,
        audio_path: Path,
        folder: Path,
        idx: int
    ) -> None:
        """Zapisuje metadata audio."""
        try:
            from .mirror_audio import get_audio_metadata
            
            meta = get_audio_metadata(audio_path)
            if meta:
                meta_path = folder / f"audio_{idx}_meta.json"
                meta_path.write_text(
                    json.dumps(meta.to_dict(), indent=2),
                    encoding="utf8"
                )
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Audio metadata extraction failed: {e}")
    
    def _run_post_hooks(self, session: MirrorSession) -> None:
        """Uruchamia post-processing hooks."""
        
        # Auto-summary
        if self.auto_summary and session.text_count > 0:
            try:
                from .mirror_summary_pro import summarize_session, GeminiSummarizer
                
                summarizer = GeminiSummarizer()
                result = summarize_session(session.session_id, summarizer)
                session.has_summary = bool(result.summary)
                
            except Exception as e:
                logger.warning(f"Auto-summary failed: {e}")
        
        # Auto-tag
        if self.auto_tag and session.text_count > 0:
            try:
                from .mirror_autotag import autotag_session, GeminiTagLLM
                
                llm = GeminiTagLLM()
                result = autotag_session(session.session_id, llm)
                session.tags = result.tags
                
            except Exception as e:
                logger.warning(f"Auto-tag failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # QUERY API
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_all_sessions(self) -> List[str]:
        """Pobiera listę wszystkich sesji."""
        sessions = []
        
        for folder in self.root.iterdir():
            if folder.is_dir() and (folder / "raw.json").exists():
                sessions.append(folder.name)
        
        return sorted(sessions, reverse=True)
    
    def get_session(self, session_id: str) -> Optional[MirrorSession]:
        """Pobiera informacje o sesji."""
        folder = self.root / session_id
        
        if not folder.exists():
            return None
        
        # Buduj sesję z plików
        files = [f.name for f in folder.iterdir() if f.is_file()]
        
        session = MirrorSession(
            session_id=session_id,
            created_at=datetime.fromtimestamp(folder.stat().st_ctime).isoformat(),
            folder=str(folder),
            files=files,
            text_count=len([f for f in files if f.startswith("text_")]),
            image_count=len([f for f in files if f.startswith("image_")]),
            video_count=len([f for f in files if f.startswith("video_") and not f.endswith("_thumb.jpg")]),
            audio_count=len([f for f in files if f.startswith("audio_") and not f.endswith("_meta.json")]),
            file_count=len([f for f in files if f.startswith("file_")]),
            function_count=len([f for f in files if f.startswith("function_")]),
            total_size_bytes=sum(f.stat().st_size for f in folder.iterdir() if f.is_file()),
            has_summary="summary.md" in files
        )
        
        # Pobierz tagi
        try:
            from .mirror_tags_pro import get_tag_manager
            session.tags = get_tag_manager().get_tags(session_id)
        except:
            pass
        
        return session
    
    def get_session_path(self, session_id: str) -> Optional[Path]:
        """Pobiera ścieżkę do folderu sesji."""
        folder = self.root / session_id
        return folder if folder.exists() else None
    
    def get_stats(self) -> MirrorStats:
        """Pobiera statystyki archiwum."""
        sessions = self.get_all_sessions()
        
        total_files = 0
        total_size = 0
        with_media = 0
        with_summary = 0
        by_month: Dict[str, int] = {}
        
        for session_id in sessions:
            session = self.get_session(session_id)
            if session:
                total_files += len(session.files)
                total_size += session.total_size_bytes
                
                if session.image_count or session.video_count or session.audio_count:
                    with_media += 1
                
                if session.has_summary:
                    with_summary += 1
                
                # Extract month
                try:
                    date_part = session_id.split("_")[0]
                    month = date_part[:6]  # YYYYMM
                    month_key = f"{month[:4]}-{month[4:]}"
                    by_month[month_key] = by_month.get(month_key, 0) + 1
                except:
                    pass
        
        return MirrorStats(
            total_sessions=len(sessions),
            total_files=total_files,
            total_size_mb=round(total_size / (1024 * 1024), 2),
            sessions_with_media=with_media,
            sessions_with_summary=with_summary,
            by_month=by_month
        )
    
    def add_hook(self, callback: Callable[[str], None]) -> None:
        """Dodaje hook wywoływany po zakończeniu sesji."""
        self._on_session_complete.append(callback)


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON & QUICK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

_engine: Optional[MirrorEngine] = None


def get_mirror_engine(
    auto_thumbnail: bool = True,
    auto_summary: bool = False,
    auto_tag: bool = False
) -> MirrorEngine:
    """Pobiera globalną instancję MirrorEngine."""
    global _engine
    if _engine is None:
        _engine = MirrorEngine(
            auto_thumbnail=auto_thumbnail,
            auto_summary=auto_summary,
            auto_tag=auto_tag
        )
    return _engine


def mirror_gemini_response(response_data: dict) -> MirrorSession:
    """Quick: Archiwizuje odpowiedź Gemini."""
    return get_mirror_engine().mirror_gemini_response(response_data)


def get_all_sessions() -> List[str]:
    """Quick: Pobiera wszystkie sesje."""
    return get_mirror_engine().get_all_sessions()


def get_session_path(session_id: str) -> Optional[Path]:
    """Quick: Pobiera ścieżkę sesji."""
    return get_mirror_engine().get_session_path(session_id)


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("\n" + "═" * 60)
    print("🐺 ALFA MIRROR ENGINE PRO TEST")
    print("═" * 60)
    
    engine = MirrorEngine(
        root=Path("test_mirror"),
        auto_thumbnail=True
    )
    
    # Test z przykładową odpowiedzią
    test_response = {
        "candidates": [{
            "content": {
                "parts": [
                    {"text": "To jest testowa odpowiedź z Gemini API."},
                    {"text": "## Drugi fragment\n\nZ formatowaniem Markdown."},
                    {
                        "functionCall": {
                            "name": "search",
                            "args": {"query": "test"}
                        }
                    }
                ]
            }
        }]
    }
    
    print("\n📥 Mirroring test response...")
    session = engine.mirror_gemini_response(test_response)
    
    print(f"\n✅ Session created: {session.session_id}")
    print(f"   Folder: {session.folder}")
    print(f"   Files: {session.files}")
    print(f"   Text: {session.text_count}, Functions: {session.function_count}")
    
    # Stats
    stats = engine.get_stats()
    print(f"\n📊 Stats:")
    print(f"   Total sessions: {stats.total_sessions}")
    print(f"   Total size: {stats.total_size_mb} MB")
    
    # Cleanup
    import shutil
    shutil.rmtree("test_mirror", ignore_errors=True)
    
    print("\n✅ Test complete!")
