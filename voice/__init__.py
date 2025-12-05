"""
ALFA VOICE v1 — PACKAGE
"""

from .tts import TTS, SimpleTTS
from .stt import STT, SimpleSTT
from .audio_utils import (
    convert_audio,
    convert_to_ogg,
    get_audio_duration,
    get_audio_info,
    split_audio,
    merge_audio,
    is_ffmpeg_available
)

__all__ = [
    "TTS",
    "SimpleTTS",
    "STT",
    "SimpleSTT",
    "convert_audio",
    "convert_to_ogg",
    "get_audio_duration",
    "get_audio_info",
    "split_audio",
    "merge_audio",
    "is_ffmpeg_available",
]
