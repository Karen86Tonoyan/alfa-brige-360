"""
ALFA_MIRROR PRO — VIDEO THUMBNAILS
Generowanie miniatur wideo z pełnym error handling.
Poziom: KERNEL-READY
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("ALFA.Mirror.Thumbnails")

# Lazy import cv2 - może nie być zainstalowane
_cv2 = None


def _get_cv2():
    """Lazy import OpenCV."""
    global _cv2
    if _cv2 is None:
        try:
            import cv2
            _cv2 = cv2
        except ImportError:
            logger.warning("OpenCV (cv2) not installed. Run: pip install opencv-python")
            _cv2 = False
    return _cv2 if _cv2 else None


# ═══════════════════════════════════════════════════════════════════════════
# GŁÓWNA FUNKCJA — THUMBNAIL GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_video_thumbnail(
    video_path: Path,
    thumb_path: Optional[Path] = None,
    frame_position: float = 0.1,
    max_size: Tuple[int, int] = (320, 180)
) -> Optional[Path]:
    """
    Generuje miniaturę z wideo.
    
    Args:
        video_path: Ścieżka do pliku wideo
        thumb_path: Ścieżka do zapisu miniatury (domyślnie: video_thumb.jpg)
        frame_position: Pozycja klatki (0.0 = początek, 0.5 = środek, 1.0 = koniec)
        max_size: Maksymalny rozmiar miniatury (width, height)
        
    Returns:
        Path do utworzonej miniatury lub None przy błędzie
        
    Raises:
        RuntimeError: Gdy nie można odczytać wideo (tylko w trybie debug)
    """
    cv2 = _get_cv2()
    if cv2 is None:
        logger.error("Cannot generate thumbnail - OpenCV not available")
        return None
    
    video_path = Path(video_path)
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        return None
    
    # Walidacja MIME przez rozszerzenie
    valid_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
    if video_path.suffix.lower() not in valid_extensions:
        logger.warning(f"Unknown video format: {video_path.suffix}")
    
    # Domyślna ścieżka miniatury
    if thumb_path is None:
        thumb_path = video_path.parent / f"{video_path.stem}_thumb.jpg"
    else:
        thumb_path = Path(thumb_path)
    
    cap = None
    try:
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")
        
        # Pobierz informacje o wideo
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        logger.debug(f"Video info: {total_frames} frames, {fps} FPS, {width}x{height}")
        
        if total_frames <= 0:
            # Fallback: spróbuj odczytać pierwszą klatkę
            logger.warning("Cannot get frame count, trying first frame")
            ok, frame = cap.read()
        else:
            # Przeskocz do wybranej pozycji
            target_frame = int(total_frames * min(max(frame_position, 0), 1))
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ok, frame = cap.read()
        
        if not ok or frame is None:
            # Fallback: spróbuj pierwszą klatkę
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
            
        if not ok or frame is None:
            raise RuntimeError(f"Cannot read any frame from: {video_path}")
        
        # Resize jeśli za duży
        h, w = frame.shape[:2]
        max_w, max_h = max_size
        
        if w > max_w or h > max_h:
            scale = min(max_w / w, max_h / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            logger.debug(f"Resized thumbnail: {w}x{h} → {new_w}x{new_h}")
        
        # Zapisz
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Użyj JPEG z dobrą jakością
        success = cv2.imwrite(
            str(thumb_path),
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, 85]
        )
        
        if not success:
            raise RuntimeError(f"Cannot write thumbnail: {thumb_path}")
        
        logger.info(f"✅ Thumbnail created: {thumb_path.name}")
        return thumb_path
        
    except Exception as e:
        logger.error(f"[THUMBNAIL_ERROR] {video_path.name}: {e}")
        return None
        
    finally:
        if cap is not None:
            cap.release()


# ═══════════════════════════════════════════════════════════════════════════
# BATCH PROCESSING
# ═══════════════════════════════════════════════════════════════════════════

def generate_thumbnails_for_folder(
    folder: Path,
    overwrite: bool = False
) -> dict:
    """
    Generuje miniatury dla wszystkich wideo w folderze.
    
    Args:
        folder: Folder z plikami wideo
        overwrite: Czy nadpisywać istniejące miniatury
        
    Returns:
        Słownik: {video_name: thumb_path or error}
    """
    folder = Path(folder)
    results = {}
    
    video_patterns = ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.webm']
    
    for pattern in video_patterns:
        for video in folder.glob(pattern):
            thumb = folder / f"{video.stem}_thumb.jpg"
            
            if thumb.exists() and not overwrite:
                results[video.name] = {"status": "exists", "path": str(thumb)}
                continue
            
            result = generate_video_thumbnail(video, thumb)
            
            if result:
                results[video.name] = {"status": "created", "path": str(result)}
            else:
                results[video.name] = {"status": "error", "path": None}
    
    return results


def get_video_info(video_path: Path) -> Optional[dict]:
    """
    Pobiera metadata wideo bez generowania miniatury.
    
    Returns:
        Dict z: duration, fps, width, height, codec
    """
    cv2 = _get_cv2()
    if cv2 is None:
        return None
    
    video_path = Path(video_path)
    if not video_path.exists():
        return None
    
    cap = None
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        
        # Decode fourcc to string
        codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
        
        duration = frames / fps if fps > 0 else 0
        
        return {
            "duration": round(duration, 2),
            "duration_str": f"{int(duration // 60)}:{int(duration % 60):02d}",
            "fps": round(fps, 2),
            "width": width,
            "height": height,
            "resolution": f"{width}x{height}",
            "codec": codec.strip(),
            "frames": frames,
            "size_mb": round(video_path.stat().st_size / (1024 * 1024), 2)
        }
        
    except Exception as e:
        logger.error(f"Cannot get video info: {e}")
        return None
        
    finally:
        if cap is not None:
            cap.release()


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    if len(sys.argv) > 1:
        video = Path(sys.argv[1])
        print(f"\n📹 Processing: {video}")
        
        info = get_video_info(video)
        if info:
            print(f"   Duration: {info['duration_str']}")
            print(f"   Resolution: {info['resolution']}")
            print(f"   FPS: {info['fps']}")
            print(f"   Size: {info['size_mb']} MB")
        
        result = generate_video_thumbnail(video)
        if result:
            print(f"✅ Thumbnail: {result}")
        else:
            print("❌ Failed to create thumbnail")
    else:
        print("Usage: python mirror_thumbnails.py <video_file>")
