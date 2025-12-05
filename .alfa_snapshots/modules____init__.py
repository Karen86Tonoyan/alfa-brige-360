"""
ALFA_CORE / MODULES v3.0
========================
Modular layer system for ALFA Kernel.

Core Modules:
- security_watchdog: Kernel monitoring, Predator Mode, auto-restart
- cerber_conscience: AI ethics guardian

MIRROR PRO Modules:
- mirror_thumbnails: Video thumbnail generation
- mirror_audio: Audio metadata extraction  
- mirror_summary_pro: Hierarchical summarization
- mirror_tags_pro: Persistent tag management
- mirror_autotag: AI auto-tagging
- mirror_export_async: Async month export
- mirror_engine_pro: Integrated MIRROR engine
- mirror_gallery_ui: Wolf-King gallery interface

Chunk Processing:
- model_limits: Token limits and configurations
- chunk_engine: OPUS-level hierarchical processing

Integration Layers:
- creative: Design & Web Publishing (figma, webflow)
- knowledge: Documentation & Knowledge Base (deepwiki, microsoft-docs)
- automation: Data Processing & Web Scraping (apify, markitdown)
- dev: Local Developer Tools (idl-vscode, pylance)
"""

from typing import Dict, Any

# ═══════════════════════════════════════════════════════════════════════════
# CORE MODULES
# ═══════════════════════════════════════════════════════════════════════════
from .security_watchdog import SecurityWatchdog, SecurityWatchdogConfig

# ═══════════════════════════════════════════════════════════════════════════
# CERBER — AI CONSCIENCE
# ═══════════════════════════════════════════════════════════════════════════
try:
    from .cerber_conscience import (
        CerberConscience,
        ContentAnalysis,
        cerber,
        check_content,
        is_safe,
    )
except ImportError:
    CerberConscience = None
    cerber = None

# ═══════════════════════════════════════════════════════════════════════════
# CHUNK PROCESSING
# ═══════════════════════════════════════════════════════════════════════════
try:
    from .model_limits import (
        ModelProfile,
        ChunkConfig,
        ChunkStrategy,
        get_model_profile,
        calculate_chunk_config,
        estimate_tokens,
        PROVIDER_MODELS,
    )
    from .chunk_engine import (
        Chunk,
        ChunkResult,
        HierarchicalResult,
        SmartChunkSplitter,
        ChunkProcessor,
        HierarchicalProcessor,
        chunk_text,
        hierarchical_summarize,
        process_large_file,
        stream_file_chunks,
    )
except ImportError:
    ModelProfile = None
    ChunkConfig = None

# ═══════════════════════════════════════════════════════════════════════════
# MIRROR PRO MODULES
# ═══════════════════════════════════════════════════════════════════════════
try:
    from .mirror_thumbnails import generate_video_thumbnail
    from .mirror_audio import AudioMetadataExtractor, get_audio_info
    from .mirror_summary_pro import HierarchicalSummarizer, summarize_session
    from .mirror_tags_pro import TagManager, tags
    from .mirror_autotag import TagLLM, GeminiTagLLM, autotag_session
    from .mirror_export_async import AsyncExportManager
    from .mirror_engine_pro import MirrorEnginePro
    from .mirror_gallery_ui import GalleryUI
except ImportError as e:
    # Graceful degradation
    pass

__version__ = "3.0.0"
__all__ = [
    # Core
    "SecurityWatchdog",
    "SecurityWatchdogConfig",
    # Cerber
    "CerberConscience",
    "cerber",
    "check_content",
    "is_safe",
    # Chunk Processing
    "ModelProfile",
    "ChunkConfig", 
    "ChunkStrategy",
    "get_model_profile",
    "calculate_chunk_config",
    "estimate_tokens",
    "Chunk",
    "ChunkResult",
    "HierarchicalResult",
    "SmartChunkSplitter",
    "ChunkProcessor",
    "HierarchicalProcessor",
    "chunk_text",
    "hierarchical_summarize",
    "process_large_file",
    "stream_file_chunks",
    # MIRROR PRO
    "generate_video_thumbnail",
    "AudioMetadataExtractor",
    "get_audio_info",
    "HierarchicalSummarizer",
    "summarize_session",
    "TagManager",
    "tags",
    "TagLLM",
    "GeminiTagLLM",
    "autotag_session",
    "AsyncExportManager",
    "MirrorEnginePro",
    "GalleryUI",
    # Layers
    "creative",
    "knowledge", 
    "automation",
    "dev",
]
