"""
ALFA_MIRROR PRO — AUDIO METADATA
Ekstrakcja metadanych audio z pełnym wsparciem formatów.
Poziom: KERNEL-READY
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger("ALFA.Mirror.Audio")

# Lazy import mutagen
_mutagen = None


def _get_mutagen():
    """Lazy import mutagen."""
    global _mutagen
    if _mutagen is None:
        try:
            import mutagen
            _mutagen = mutagen
        except ImportError:
            logger.warning("mutagen not installed. Run: pip install mutagen")
            _mutagen = False
    return _mutagen if _mutagen else None


# ═══════════════════════════════════════════════════════════════════════════
# DATACLASS — AUDIO INFO
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AudioInfo:
    """Metadane pliku audio."""
    path: str
    filename: str
    duration: float  # sekundy
    duration_str: str  # "MM:SS"
    bitrate: Optional[int]  # kbps
    sample_rate: Optional[int]  # Hz
    channels: Optional[int]
    format: str
    mime_type: str
    size_mb: float
    
    # Opcjonalne tagi
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════
# GŁÓWNA FUNKCJA — GET AUDIO METADATA
# ═══════════════════════════════════════════════════════════════════════════

def get_audio_metadata(audio_path: Path) -> Optional[AudioInfo]:
    """
    Pobiera pełne metadane pliku audio.
    
    Args:
        audio_path: Ścieżka do pliku audio
        
    Returns:
        AudioInfo lub None przy błędzie
        
    Obsługiwane formaty:
        - MP3, OGG, FLAC, WAV, M4A, AAC, WMA, OPUS
    """
    mutagen = _get_mutagen()
    audio_path = Path(audio_path)
    
    if not audio_path.exists():
        logger.error(f"Audio file not found: {audio_path}")
        return None
    
    # Podstawowe info bez mutagen
    size_mb = round(audio_path.stat().st_size / (1024 * 1024), 2)
    
    # Rozpoznaj format po rozszerzeniu
    ext = audio_path.suffix.lower()
    format_map = {
        '.mp3': 'MP3',
        '.ogg': 'OGG Vorbis',
        '.opus': 'Opus',
        '.flac': 'FLAC',
        '.wav': 'WAV',
        '.m4a': 'AAC/M4A',
        '.aac': 'AAC',
        '.wma': 'WMA',
        '.webm': 'WebM Audio'
    }
    audio_format = format_map.get(ext, ext.upper().lstrip('.'))
    
    mime_map = {
        '.mp3': 'audio/mpeg',
        '.ogg': 'audio/ogg',
        '.opus': 'audio/opus',
        '.flac': 'audio/flac',
        '.wav': 'audio/wav',
        '.m4a': 'audio/mp4',
        '.aac': 'audio/aac',
        '.wma': 'audio/x-ms-wma',
        '.webm': 'audio/webm'
    }
    mime_type = mime_map.get(ext, 'audio/unknown')
    
    # Fallback bez mutagen
    if mutagen is None:
        return AudioInfo(
            path=str(audio_path),
            filename=audio_path.name,
            duration=0,
            duration_str="??:??",
            bitrate=None,
            sample_rate=None,
            channels=None,
            format=audio_format,
            mime_type=mime_type,
            size_mb=size_mb
        )
    
    try:
        meta = mutagen.File(audio_path)
        
        if meta is None:
            logger.warning(f"Cannot read audio metadata: {audio_path}")
            return AudioInfo(
                path=str(audio_path),
                filename=audio_path.name,
                duration=0,
                duration_str="??:??",
                bitrate=None,
                sample_rate=None,
                channels=None,
                format=audio_format,
                mime_type=mime_type,
                size_mb=size_mb
            )
        
        # Pobierz info z mutagen
        info = meta.info
        
        duration = getattr(info, 'length', 0) or 0
        bitrate = getattr(info, 'bitrate', None)
        sample_rate = getattr(info, 'sample_rate', None)
        channels = getattr(info, 'channels', None)
        
        # Konwersja duration na string
        mins = int(duration // 60)
        secs = int(duration % 60)
        duration_str = f"{mins}:{secs:02d}"
        
        # Pobierz tagi (zależne od formatu)
        title = None
        artist = None
        album = None
        
        if hasattr(meta, 'tags') and meta.tags:
            tags = meta.tags
            
            # ID3 (MP3)
            if hasattr(tags, 'get'):
                title = _get_tag(tags, ['TIT2', 'title', 'TITLE'])
                artist = _get_tag(tags, ['TPE1', 'artist', 'ARTIST'])
                album = _get_tag(tags, ['TALB', 'album', 'ALBUM'])
        
        # Użyj mime z mutagen jeśli dostępne
        if hasattr(meta, 'mime') and meta.mime:
            mime_type = meta.mime[0]
        
        return AudioInfo(
            path=str(audio_path),
            filename=audio_path.name,
            duration=round(duration, 2),
            duration_str=duration_str,
            bitrate=int(bitrate) if bitrate else None,
            sample_rate=sample_rate,
            channels=channels,
            format=audio_format,
            mime_type=mime_type,
            size_mb=size_mb,
            title=title,
            artist=artist,
            album=album
        )
        
    except Exception as e:
        logger.error(f"Error reading audio metadata: {e}")
        return AudioInfo(
            path=str(audio_path),
            filename=audio_path.name,
            duration=0,
            duration_str="??:??",
            bitrate=None,
            sample_rate=None,
            channels=None,
            format=audio_format,
            mime_type=mime_type,
            size_mb=size_mb
        )


def _get_tag(tags: Any, keys: list) -> Optional[str]:
    """Helper: pobierz tag z różnych kluczy."""
    for key in keys:
        try:
            val = tags.get(key)
            if val:
                if isinstance(val, list):
                    return str(val[0])
                return str(val)
        except:
            continue
    return None


# ═══════════════════════════════════════════════════════════════════════════
# BATCH PROCESSING
# ═══════════════════════════════════════════════════════════════════════════

def get_folder_audio_metadata(folder: Path) -> Dict[str, AudioInfo]:
    """
    Pobiera metadane wszystkich plików audio w folderze.
    
    Returns:
        Dict: {filename: AudioInfo}
    """
    folder = Path(folder)
    results = {}
    
    audio_patterns = ['*.mp3', '*.ogg', '*.opus', '*.flac', '*.wav', '*.m4a', '*.aac']
    
    for pattern in audio_patterns:
        for audio in folder.glob(pattern):
            info = get_audio_metadata(audio)
            if info:
                results[audio.name] = info
    
    return results


def get_total_duration(folder: Path) -> Dict[str, Any]:
    """
    Oblicza łączny czas trwania audio w folderze.
    
    Returns:
        Dict z total_seconds, total_str, file_count
    """
    metadata = get_folder_audio_metadata(folder)
    
    total = sum(m.duration for m in metadata.values())
    
    hours = int(total // 3600)
    mins = int((total % 3600) // 60)
    secs = int(total % 60)
    
    if hours > 0:
        total_str = f"{hours}h {mins}m {secs}s"
    else:
        total_str = f"{mins}m {secs}s"
    
    return {
        "total_seconds": round(total, 2),
        "total_str": total_str,
        "file_count": len(metadata),
        "files": list(metadata.keys())
    }


# ═══════════════════════════════════════════════════════════════════════════
# HTML EMBED GENERATOR
# ═══════════════════════════════════════════════════════════════════════════

def generate_audio_embed(
    audio_path: Path,
    base_url: str = "/static",
    show_metadata: bool = True,
    style: str = "dark"
) -> str:
    """
    Generuje HTML embed dla pliku audio.
    
    Args:
        audio_path: Ścieżka do pliku audio
        base_url: Bazowy URL do statycznych plików
        show_metadata: Czy pokazać metadane
        style: 'dark' lub 'light'
        
    Returns:
        HTML string
    """
    audio_path = Path(audio_path)
    meta = get_audio_metadata(audio_path)
    
    if not meta:
        return f"<!-- Audio not found: {audio_path} -->"
    
    # URL do pliku
    url = f"{base_url}/{audio_path.parent.name}/{audio_path.name}"
    
    # Style
    if style == "dark":
        bg = "#1a1a1a"
        text = "#f0f0f0"
        accent = "#FFD700"
        border = "#333"
    else:
        bg = "#f5f5f5"
        text = "#333"
        accent = "#c9a227"
        border = "#ddd"
    
    # Metadata string
    meta_html = ""
    if show_metadata:
        parts = [meta.duration_str]
        if meta.bitrate:
            parts.append(f"{meta.bitrate} kbps")
        if meta.format:
            parts.append(meta.format)
        
        meta_html = f"""
        <div style="font-size:11px; color:{accent}; margin-top:4px;">
            {' • '.join(parts)}
        </div>
        """
        
        if meta.title or meta.artist:
            title_info = meta.title or meta.filename
            artist_info = meta.artist or ""
            meta_html += f"""
            <div style="font-size:10px; opacity:0.7; margin-top:2px;">
                {title_info} {f'— {artist_info}' if artist_info else ''}
            </div>
            """
    
    html = f"""
    <div style="
        background:{bg}; 
        border:1px solid {border}; 
        border-radius:8px; 
        padding:12px; 
        margin:8px 0;
        max-width:350px;
    ">
        <div style="font-size:12px; color:{text}; margin-bottom:8px; word-break:break-all;">
            🎵 {meta.filename}
        </div>
        <audio controls style="width:100%; height:36px;">
            <source src="{url}" type="{meta.mime_type}">
            Your browser does not support audio.
        </audio>
        {meta_html}
    </div>
    """
    
    return html


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    if len(sys.argv) > 1:
        audio = Path(sys.argv[1])
        print(f"\n🎵 Processing: {audio}")
        
        info = get_audio_metadata(audio)
        if info:
            print(f"   Duration: {info.duration_str}")
            print(f"   Bitrate: {info.bitrate} kbps")
            print(f"   Sample Rate: {info.sample_rate} Hz")
            print(f"   Channels: {info.channels}")
            print(f"   Format: {info.format}")
            print(f"   Size: {info.size_mb} MB")
            if info.title:
                print(f"   Title: {info.title}")
            if info.artist:
                print(f"   Artist: {info.artist}")
        else:
            print("❌ Failed to read metadata")
    else:
        print("Usage: python mirror_audio.py <audio_file>")
