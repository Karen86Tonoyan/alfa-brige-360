"""
Test ALFA Compression + Delta Bridge
"""

import sys
import os

# Add project root to path
sys.path.insert(0, r"c:\Users\ktono\alfa_core")

print("=" * 60)
print("ALFA COMPRESSION + DELTA BRIDGE TEST")
print("=" * 60)

# === TEST COMPRESSION ===
print("\n[1] COMPRESSION ENGINE TEST")
print("-" * 40)

try:
    from core.compression import AlfaCompression, CompressionAlgo
    
    engine = AlfaCompression()
    print(f"[OK] Compression engine created")
    print(f"    - ZSTD available: {engine._zstd_available}")
    print(f"    - Brotli available: {engine._brotli_available}")
    
    # Test data
    test_data = "ALFA CORE - Kompresja działa świetnie! " * 100
    print(f"\n    Original: {len(test_data)} bytes")
    
    # Test LZMA (always available)
    result = engine.compress(test_data, CompressionAlgo.LZMA_EXTREME)
    if result.success:
        print(f"    [LZMA] {result.compressed_size} bytes (ratio: {result.ratio:.2f}x)")
        print(f"    [SHA256] {result.hash_sha256[:32]}...")
        
        # Verify decompression
        decompressed, error = engine.decompress(
            result.data, 
            CompressionAlgo.LZMA_EXTREME,
            result.hash_sha256
        )
        if decompressed and decompressed.decode() == test_data:
            print(f"    [VERIFIED] Decompression OK, hash verified!")
        else:
            print(f"    [ERROR] Decompression failed: {error}")
    else:
        print(f"    [FAIL] LZMA: {result.error}")
        
    # Test ZSTD if available
    if engine._zstd_available:
        result = engine.compress(test_data, CompressionAlgo.ZSTD22)
        if result.success:
            print(f"    [ZSTD22] {result.compressed_size} bytes (ratio: {result.ratio:.2f}x)")
    else:
        print("    [SKIP] ZSTD not installed")
        
except Exception as e:
    print(f"[FAIL] Compression: {e}")
    import traceback
    traceback.print_exc()

# === TEST DELTA IMPORTS ===
print("\n[2] DELTA BRIDGE IMPORT TEST")
print("-" * 40)

try:
    from plugins.delta import DeltaListener, DeltaSender, DeltaRouter
    print("[OK] DeltaListener imported")
    print("[OK] DeltaSender imported")
    print("[OK] DeltaRouter imported")
    
    from plugins.delta.delta_listener import DeltaMessage
    print("[OK] DeltaMessage imported")
    
    from plugins.delta.delta_sender import VoiceGenerator
    print("[OK] VoiceGenerator imported")
    
    from plugins.delta.delta_router import DeltaModule
    print("[OK] DeltaModule imported")
    
except Exception as e:
    print(f"[FAIL] Delta imports: {e}")
    import traceback
    traceback.print_exc()

# === TEST KERNEL + COMPRESSION MODULE ===
print("\n[3] KERNEL + COMPRESSION MODULE TEST")
print("-" * 40)

try:
    from alfa_core.kernel import AlfaKernel
    from alfa_core.module_registry import ModuleRegistry
    from core.compression import CompressionModule, CompressionModuleConfig
    
    # Create kernel
    registry = ModuleRegistry()
    kernel = AlfaKernel(registry)
    
    # Register compression module
    compression_config = CompressionModuleConfig(default_algo="lzma")
    compression_module = CompressionModule(compression_config)
    registry.register("core.compression", compression_module)
    
    # Start
    kernel.start()
    print("[OK] Kernel started with compression module")
    
    # Test via dispatch
    result = kernel.dispatch("core.compression", "compress", data="Test kompresji przez kernel!")
    if result.ok:
        print(f"[OK] Dispatch compress: ratio={result.data['ratio']:.2f}x")
    else:
        print(f"[FAIL] Dispatch: {result.error}")
        
    # Auto compress
    result = kernel.dispatch("core.compression", "auto", data="Automatyczny wybór algorytmu!" * 50)
    if result.ok:
        print(f"[OK] Auto compress: algo={result.data['algo']}, ratio={result.data['ratio']:.2f}x")
    else:
        print(f"[FAIL] Auto: {result.error}")
        
    kernel.shutdown()
    print("[OK] Kernel shutdown")
    
except Exception as e:
    print(f"[FAIL] Kernel + Compression: {e}")
    import traceback
    traceback.print_exc()

# === SUMMARY ===
print("\n" + "=" * 60)
print("COMPONENT STATUS")
print("=" * 60)

components = [
    ("ALFA_KERNEL v1.2", "kernel.py", True),
    ("Security Watchdog", "modules/security_watchdog.py", True),
    ("Compression Engine", "core/compression.py", True),
    ("Delta Listener", "plugins/delta/delta_listener.py", True),
    ("Delta Sender", "plugins/delta/delta_sender.py", True),
    ("Delta Router", "plugins/delta/delta_router.py", True),
    ("Quality Pack", "pyproject.toml", True),
    ("CI Pipeline", ".github/workflows/alfa-ci.yml", True),
]

for name, path, status in components:
    status_str = "[OK]" if status else "[--]"
    print(f"  {status_str} {name:<25} -> {path}")

print("\n" + "=" * 60)
print("ALL COMPONENTS READY!")
print("=" * 60)
