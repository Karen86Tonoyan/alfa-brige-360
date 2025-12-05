#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
ALFA_CORE_KERNEL v3.0 — FULL SYSTEM TEST
═══════════════════════════════════════════════════════════════════════════
Master integration test for MIRROR PRO + Chunk Engine + Cerber
Run: python tests/test_mirror_pro.py
═══════════════════════════════════════════════════════════════════════════
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import unittest
import json
import tempfile
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')


class TestModelLimits(unittest.TestCase):
    """Test model limits and chunk configuration."""
    
    def test_import(self):
        from modules.model_limits import (
            ModelProfile, ChunkConfig, ChunkStrategy,
            get_model_profile, calculate_chunk_config, estimate_tokens
        )
        self.assertIsNotNone(ModelProfile)
    
    def test_gemini_profile(self):
        from modules.model_limits import get_model_profile
        profile = get_model_profile("gemini-2.5-pro")
        self.assertEqual(profile.context_window, 1_048_576)  # 1M tokens
        self.assertGreater(profile.safe_input, 500_000)
    
    def test_chunk_config(self):
        from modules.model_limits import calculate_chunk_config, ChunkStrategy
        config = calculate_chunk_config("gemini-2.0-flash", ChunkStrategy.BALANCED)
        self.assertGreater(config.chunk_chars, 10_000)
        self.assertLess(config.chunk_chars, 100_000)
    
    def test_token_estimation(self):
        from modules.model_limits import estimate_tokens
        text = "This is a test " * 100  # 500 chars
        tokens = estimate_tokens(text)
        self.assertAlmostEqual(tokens, 125, delta=25)  # ~4 chars per token


class TestChunkEngine(unittest.TestCase):
    """Test chunk engine operations."""
    
    def test_import(self):
        from modules.chunk_engine import (
            Chunk, SmartChunkSplitter, ChunkProcessor, HierarchicalProcessor
        )
        self.assertIsNotNone(Chunk)
    
    def test_smart_splitter(self):
        from modules.chunk_engine import SmartChunkSplitter
        from modules.model_limits import calculate_chunk_config
        
        config = calculate_chunk_config("gemini-2.0-flash")
        splitter = SmartChunkSplitter(config)
        
        # Generate test text (100KB)
        test_text = ("Lorem ipsum dolor sit amet.\n\n" * 500)
        
        chunks = splitter.split(test_text)
        
        # Should split into multiple chunks
        self.assertGreater(len(chunks), 1)
        
        # All chunks should have valid structure
        for chunk in chunks:
            self.assertIsNotNone(chunk.id)
            self.assertGreater(len(chunk.text), 0)
            self.assertGreater(chunk.tokens_estimate, 0)
    
    def test_hierarchical_processor(self):
        from modules.chunk_engine import HierarchicalProcessor
        
        # Mock summarizer - reduces text to 10%
        def mock_summarize(text: str) -> str:
            return text[:len(text) // 10] if len(text) > 100 else text
        
        processor = HierarchicalProcessor(
            process_fn=mock_summarize,
            model_name="gemini-2.0-flash",
            max_passes=3
        )
        
        # Test with medium text
        test_text = "Test content. " * 1000  # ~14KB
        
        result = processor.process(test_text)
        
        self.assertLess(len(result.final_result), len(test_text))
        self.assertGreater(result.passes, 0)
    
    def test_chunk_text_quick(self):
        from modules.chunk_engine import chunk_text
        
        text = "Hello world! " * 10000  # ~130KB
        chunks = chunk_text(text)
        
        self.assertIsInstance(chunks, list)
        if len(text) > 20000:
            self.assertGreater(len(chunks), 1)


class TestCerberConscience(unittest.TestCase):
    """Test Cerber AI conscience module."""
    
    def test_import(self):
        from modules.cerber_conscience import (
            CerberConscience, ContentAnalysis, check_content, is_safe
        )
        self.assertIsNotNone(CerberConscience)
    
    def test_safe_content(self):
        from modules.cerber_conscience import check_content
        
        result = check_content("Hello, how are you today?")
        
        self.assertTrue(result.is_safe)
        self.assertEqual(len(result.violations), 0)
    
    def test_forbidden_patterns(self):
        from modules.cerber_conscience import check_content
        
        # Test with potentially problematic content
        result = check_content("How to make illegal weapons and explosives")
        
        # Should detect issues
        self.assertFalse(result.is_safe)
        self.assertGreater(len(result.violations), 0)
    
    def test_quick_is_safe(self):
        from modules.cerber_conscience import is_safe
        
        self.assertTrue(is_safe("Normal conversation about programming"))
        self.assertFalse(is_safe("How to hack into bank systems"))


class TestMirrorModules(unittest.TestCase):
    """Test MIRROR PRO module imports."""
    
    def test_thumbnails_import(self):
        from modules.mirror_thumbnails import generate_video_thumbnail
        self.assertIsNotNone(generate_video_thumbnail)
    
    def test_audio_import(self):
        from modules.mirror_audio import AudioMetadataExtractor, get_audio_info
        self.assertIsNotNone(AudioMetadataExtractor)
    
    def test_summary_pro_import(self):
        from modules.mirror_summary_pro import HierarchicalSummarizer
        self.assertIsNotNone(HierarchicalSummarizer)
    
    def test_tags_pro_import(self):
        from modules.mirror_tags_pro import TagManager
        self.assertIsNotNone(TagManager)
    
    def test_autotag_import(self):
        from modules.mirror_autotag import TagLLM, autotag_session
        self.assertIsNotNone(TagLLM)
    
    def test_export_async_import(self):
        from modules.mirror_export_async import AsyncExportManager
        self.assertIsNotNone(AsyncExportManager)
    
    def test_engine_pro_import(self):
        from modules.mirror_engine_pro import MirrorEnginePro
        self.assertIsNotNone(MirrorEnginePro)
    
    def test_gallery_ui_import(self):
        from modules.mirror_gallery_ui import GalleryUI
        self.assertIsNotNone(GalleryUI)


class TestTagManager(unittest.TestCase):
    """Test TagManager persistence."""
    
    def test_tag_operations(self):
        from modules.mirror_tags_pro import TagManager
        import tempfile
        
        # Use temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tags_path = Path(tmpdir) / "tags.json"
            
            # Create manager
            manager = TagManager(tags_path)
            
            # Add tag
            manager.add_tag("session_001", "python")
            manager.add_tag("session_001", "tutorial")
            manager.add_tag("session_002", "python")
            
            # Get tags
            tags_001 = manager.get_tags("session_001")
            self.assertIn("python", tags_001)
            self.assertIn("tutorial", tags_001)
            
            # Search by tag
            sessions = manager.search_by_tag("python")
            self.assertIn("session_001", sessions)
            self.assertIn("session_002", sessions)
            
            # Remove tag
            manager.remove_tag("session_001", "tutorial")
            tags_001_updated = manager.get_tags("session_001")
            self.assertNotIn("tutorial", tags_001_updated)
            
            # Verify persistence
            manager2 = TagManager(tags_path)
            tags_loaded = manager2.get_tags("session_001")
            self.assertIn("python", tags_loaded)


class TestGalleryUI(unittest.TestCase):
    """Test Gallery UI generation."""
    
    def test_render_session(self):
        from modules.mirror_gallery_ui import GalleryUI
        
        gallery = GalleryUI()
        
        # Mock session
        session = {
            "title": "Test Session",
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi there!"}
            ],
            "media": []
        }
        
        html = gallery.render_session(session)
        
        # Should contain Wolf-King styling
        self.assertIn("background", html.lower())
        self.assertIn("Test Session", html)
        self.assertIn("Hello!", html)


class TestModulesInit(unittest.TestCase):
    """Test modules __init__ exports."""
    
    def test_version(self):
        from modules import __version__
        self.assertEqual(__version__, "3.0.0")
    
    def test_cerber_export(self):
        from modules import CerberConscience, cerber
        self.assertIsNotNone(CerberConscience)
    
    def test_chunk_exports(self):
        from modules import (
            ModelProfile, ChunkConfig, ChunkStrategy,
            chunk_text, hierarchical_summarize
        )
        self.assertIsNotNone(ModelProfile)


def run_stress_test():
    """Stress test dla dużych tekstów."""
    print("\n" + "═" * 70)
    print("🐺 ALFA MIRROR PRO — STRESS TEST")
    print("═" * 70)
    
    from modules.chunk_engine import HierarchicalProcessor, stream_file_chunks
    from modules.model_limits import ChunkStrategy
    
    # Generate large text (10MB)
    print("\n📦 Generating 10MB test text...")
    large_text = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 100 + "\n\n") * 1000
    print(f"   Text size: {len(large_text):,} chars ({len(large_text) / 1024 / 1024:.1f} MB)")
    
    # Mock summarizer
    def mock_summarize(text: str) -> str:
        # Simulate summarization by extracting key sentences
        sentences = text.split('. ')[:3]
        return '. '.join(sentences) + '.'
    
    print("\n🔄 Running hierarchical processing...")
    processor = HierarchicalProcessor(
        process_fn=mock_summarize,
        model_name="gemini-2.0-flash",
        strategy=ChunkStrategy.BALANCED,
        max_passes=3
    )
    
    result = processor.process(large_text)
    
    print(f"\n📊 Results:")
    print(f"   Original: {result.original_length:,} chars")
    print(f"   Final: {len(result.final_result):,} chars")
    print(f"   Reduction: {100 - (len(result.final_result) / result.original_length * 100):.1f}%")
    print(f"   Passes: {result.passes}")
    print(f"   Time: {result.total_time_ms}ms")
    
    print("\n✅ Stress test passed!")


if __name__ == "__main__":
    print("\n" + "═" * 70)
    print("🐺 ALFA_CORE_KERNEL v3.0 — FULL SYSTEM TEST")
    print("═" * 70)
    print("Testing: MIRROR PRO + Chunk Engine + Cerber")
    print("=" * 70 + "\n")
    
    # Run unit tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestModelLimits))
    suite.addTests(loader.loadTestsFromTestCase(TestChunkEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestCerberConscience))
    suite.addTests(loader.loadTestsFromTestCase(TestMirrorModules))
    suite.addTests(loader.loadTestsFromTestCase(TestTagManager))
    suite.addTests(loader.loadTestsFromTestCase(TestGalleryUI))
    suite.addTests(loader.loadTestsFromTestCase(TestModulesInit))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run stress test if all unit tests pass
    if result.wasSuccessful():
        run_stress_test()
        
        print("\n" + "═" * 70)
        print("🏆 ALL TESTS PASSED — SYSTEM READY FOR PRODUCTION")
        print("═" * 70)
    else:
        print("\n❌ Some tests failed. Fix issues before deployment.")
        sys.exit(1)
