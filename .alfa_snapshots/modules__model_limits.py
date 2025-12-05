"""
ALFA_MIRROR PRO — TOKEN LIMITS & MODEL PROFILES
Realne limity tokenów dla wszystkich modeli + optymalne chunk-size.
Poziom: PRODUCTION CRITICAL
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Literal
from enum import Enum

logger = logging.getLogger("ALFA.Mirror.Limits")


# ═══════════════════════════════════════════════════════════════════════════
# MODEL PROFILES — REALNE LIMITY (grudzień 2024)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ModelProfile:
    """Profil modelu z limitami."""
    name: str
    provider: str
    
    # Limity tokenów
    context_window: int          # Max context (input + output)
    max_input_tokens: int        # Max input (praktyczny limit)
    max_output_tokens: int       # Max output per request
    
    # Rekomendowane ustawienia
    safe_chunk_tokens: int       # Bezpieczny rozmiar chunka
    optimal_summary_tokens: int  # Optymalny rozmiar summary
    
    # Charakterystyka
    chars_per_token: float       # Średnio znaków na token (dla PL ~3.5, EN ~4)
    cost_per_1k_input: float     # Koszt za 1K input tokens (USD)
    cost_per_1k_output: float    # Koszt za 1K output tokens (USD)
    
    # Flagi
    supports_vision: bool = False
    supports_audio: bool = False
    supports_streaming: bool = True
    
    @property
    def safe_chunk_chars(self) -> int:
        """Bezpieczny rozmiar chunka w znakach."""
        return int(self.safe_chunk_tokens * self.chars_per_token)
    
    @property
    def max_input_chars(self) -> int:
        """Max input w znakach."""
        return int(self.max_input_tokens * self.chars_per_token)


# ═══════════════════════════════════════════════════════════════════════════
# GEMINI MODELS
# ═══════════════════════════════════════════════════════════════════════════

GEMINI_2_FLASH = ModelProfile(
    name="gemini-2.0-flash-exp",
    provider="google",
    context_window=1_000_000,     # 1M tokens!
    max_input_tokens=900_000,     # Praktycznie ~900K safe
    max_output_tokens=8_192,      # 8K output limit
    safe_chunk_tokens=50_000,     # 50K per chunk (dla summary)
    optimal_summary_tokens=1_000, # 1K na summary
    chars_per_token=3.5,          # Polski tekst
    cost_per_1k_input=0.0,        # Free tier
    cost_per_1k_output=0.0,
    supports_vision=True,
    supports_audio=True,
)

GEMINI_1_5_PRO = ModelProfile(
    name="gemini-1.5-pro",
    provider="google",
    context_window=2_000_000,     # 2M tokens (largest!)
    max_input_tokens=1_800_000,
    max_output_tokens=8_192,
    safe_chunk_tokens=100_000,    # 100K per chunk
    optimal_summary_tokens=2_000,
    chars_per_token=3.5,
    cost_per_1k_input=0.00125,    # $1.25/1M input
    cost_per_1k_output=0.005,     # $5/1M output
    supports_vision=True,
    supports_audio=True,
)

GEMINI_1_5_FLASH = ModelProfile(
    name="gemini-1.5-flash",
    provider="google",
    context_window=1_000_000,
    max_input_tokens=900_000,
    max_output_tokens=8_192,
    safe_chunk_tokens=50_000,
    optimal_summary_tokens=1_000,
    chars_per_token=3.5,
    cost_per_1k_input=0.000075,   # $0.075/1M
    cost_per_1k_output=0.0003,
    supports_vision=True,
    supports_audio=True,
)


# ═══════════════════════════════════════════════════════════════════════════
# DEEPSEEK MODELS
# ═══════════════════════════════════════════════════════════════════════════

DEEPSEEK_CHAT = ModelProfile(
    name="deepseek-chat",
    provider="deepseek",
    context_window=128_000,       # 128K (znacznie mniej niż Gemini!)
    max_input_tokens=120_000,
    max_output_tokens=8_192,
    safe_chunk_tokens=20_000,     # 20K per chunk - MNIEJSZE!
    optimal_summary_tokens=800,
    chars_per_token=3.5,
    cost_per_1k_input=0.00014,    # $0.14/1M
    cost_per_1k_output=0.00028,
    supports_vision=False,
    supports_streaming=True,
)

DEEPSEEK_CODER = ModelProfile(
    name="deepseek-coder",
    provider="deepseek",
    context_window=128_000,
    max_input_tokens=120_000,
    max_output_tokens=8_192,
    safe_chunk_tokens=25_000,
    optimal_summary_tokens=1_000,
    chars_per_token=4.0,          # Kod = więcej ASCII
    cost_per_1k_input=0.00014,
    cost_per_1k_output=0.00028,
    supports_vision=False,
)

DEEPSEEK_R1 = ModelProfile(
    name="deepseek-reasoner",
    provider="deepseek",
    context_window=64_000,        # R1 ma mniejszy kontekst!
    max_input_tokens=56_000,
    max_output_tokens=8_192,
    safe_chunk_tokens=10_000,     # MAŁE chunki dla R1
    optimal_summary_tokens=500,
    chars_per_token=3.5,
    cost_per_1k_input=0.00055,    # Droższy
    cost_per_1k_output=0.00219,
    supports_vision=False,
)


# ═══════════════════════════════════════════════════════════════════════════
# OLLAMA / LOCAL MODELS
# ═══════════════════════════════════════════════════════════════════════════

LLAMA_3_8B = ModelProfile(
    name="llama3:8b",
    provider="ollama",
    context_window=8_192,         # 8K - MAŁE!
    max_input_tokens=7_000,
    max_output_tokens=2_048,
    safe_chunk_tokens=2_000,      # Bardzo małe chunki
    optimal_summary_tokens=300,
    chars_per_token=4.0,
    cost_per_1k_input=0.0,        # Free
    cost_per_1k_output=0.0,
)

LLAMA_3_70B = ModelProfile(
    name="llama3:70b",
    provider="ollama",
    context_window=8_192,
    max_input_tokens=7_000,
    max_output_tokens=2_048,
    safe_chunk_tokens=2_500,
    optimal_summary_tokens=400,
    chars_per_token=4.0,
    cost_per_1k_input=0.0,
    cost_per_1k_output=0.0,
)

MISTRAL_7B = ModelProfile(
    name="mistral:7b",
    provider="ollama",
    context_window=32_768,        # 32K - lepszy!
    max_input_tokens=28_000,
    max_output_tokens=4_096,
    safe_chunk_tokens=8_000,
    optimal_summary_tokens=500,
    chars_per_token=4.0,
    cost_per_1k_input=0.0,
    cost_per_1k_output=0.0,
)

MIXTRAL_8X7B = ModelProfile(
    name="mixtral:8x7b",
    provider="ollama",
    context_window=32_768,
    max_input_tokens=28_000,
    max_output_tokens=4_096,
    safe_chunk_tokens=10_000,
    optimal_summary_tokens=600,
    chars_per_token=4.0,
    cost_per_1k_input=0.0,
    cost_per_1k_output=0.0,
)

QWEN_2_5_72B = ModelProfile(
    name="qwen2.5:72b",
    provider="ollama",
    context_window=131_072,       # 128K - najlepszy lokalny!
    max_input_tokens=120_000,
    max_output_tokens=8_192,
    safe_chunk_tokens=30_000,
    optimal_summary_tokens=1_000,
    chars_per_token=3.5,
    cost_per_1k_input=0.0,
    cost_per_1k_output=0.0,
)

PHI_3_MINI = ModelProfile(
    name="phi3:mini",
    provider="ollama",
    context_window=4_096,         # BARDZO MAŁE
    max_input_tokens=3_500,
    max_output_tokens=1_024,
    safe_chunk_tokens=1_000,
    optimal_summary_tokens=200,
    chars_per_token=4.0,
    cost_per_1k_input=0.0,
    cost_per_1k_output=0.0,
)


# ═══════════════════════════════════════════════════════════════════════════
# OPENAI (dla porównania)
# ═══════════════════════════════════════════════════════════════════════════

GPT_4O = ModelProfile(
    name="gpt-4o",
    provider="openai",
    context_window=128_000,
    max_input_tokens=120_000,
    max_output_tokens=4_096,
    safe_chunk_tokens=25_000,
    optimal_summary_tokens=800,
    chars_per_token=4.0,
    cost_per_1k_input=0.005,      # $5/1M
    cost_per_1k_output=0.015,     # $15/1M
    supports_vision=True,
)

GPT_4O_MINI = ModelProfile(
    name="gpt-4o-mini",
    provider="openai",
    context_window=128_000,
    max_input_tokens=120_000,
    max_output_tokens=4_096,
    safe_chunk_tokens=20_000,
    optimal_summary_tokens=600,
    chars_per_token=4.0,
    cost_per_1k_input=0.00015,    # $0.15/1M
    cost_per_1k_output=0.0006,
    supports_vision=True,
)


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE (dla porównania)
# ═══════════════════════════════════════════════════════════════════════════

CLAUDE_3_5_SONNET = ModelProfile(
    name="claude-3-5-sonnet-20241022",
    provider="anthropic",
    context_window=200_000,
    max_input_tokens=180_000,
    max_output_tokens=8_192,
    safe_chunk_tokens=40_000,
    optimal_summary_tokens=1_500,
    chars_per_token=4.0,
    cost_per_1k_input=0.003,      # $3/1M
    cost_per_1k_output=0.015,     # $15/1M
    supports_vision=True,
)

CLAUDE_3_OPUS = ModelProfile(
    name="claude-3-opus-20240229",
    provider="anthropic",
    context_window=200_000,
    max_input_tokens=180_000,
    max_output_tokens=4_096,
    safe_chunk_tokens=50_000,
    optimal_summary_tokens=2_000,
    chars_per_token=4.0,
    cost_per_1k_input=0.015,      # $15/1M
    cost_per_1k_output=0.075,     # $75/1M
    supports_vision=True,
)


# ═══════════════════════════════════════════════════════════════════════════
# MODEL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

ALL_MODELS: Dict[str, ModelProfile] = {
    # Gemini
    "gemini-2.0-flash": GEMINI_2_FLASH,
    "gemini-2.0-flash-exp": GEMINI_2_FLASH,
    "gemini-1.5-pro": GEMINI_1_5_PRO,
    "gemini-1.5-flash": GEMINI_1_5_FLASH,
    
    # DeepSeek
    "deepseek-chat": DEEPSEEK_CHAT,
    "deepseek-coder": DEEPSEEK_CODER,
    "deepseek-r1": DEEPSEEK_R1,
    "deepseek-reasoner": DEEPSEEK_R1,
    
    # Ollama
    "llama3": LLAMA_3_8B,
    "llama3:8b": LLAMA_3_8B,
    "llama3:70b": LLAMA_3_70B,
    "mistral": MISTRAL_7B,
    "mistral:7b": MISTRAL_7B,
    "mixtral": MIXTRAL_8X7B,
    "mixtral:8x7b": MIXTRAL_8X7B,
    "qwen2.5": QWEN_2_5_72B,
    "qwen2.5:72b": QWEN_2_5_72B,
    "phi3": PHI_3_MINI,
    "phi3:mini": PHI_3_MINI,
    
    # OpenAI
    "gpt-4o": GPT_4O,
    "gpt-4o-mini": GPT_4O_MINI,
    
    # Claude
    "claude-3-5-sonnet": CLAUDE_3_5_SONNET,
    "claude-3-opus": CLAUDE_3_OPUS,
}


def get_model_profile(model_name: str) -> Optional[ModelProfile]:
    """Pobiera profil modelu po nazwie."""
    # Exact match
    if model_name in ALL_MODELS:
        return ALL_MODELS[model_name]
    
    # Partial match
    model_lower = model_name.lower()
    for key, profile in ALL_MODELS.items():
        if key in model_lower or model_lower in key:
            return profile
    
    return None


def get_default_profile() -> ModelProfile:
    """Zwraca domyślny profil (Gemini 2.0 Flash)."""
    return GEMINI_2_FLASH


# ═══════════════════════════════════════════════════════════════════════════
# CHUNK SIZE CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════

class ChunkStrategy(Enum):
    """Strategia chunkowania."""
    CONSERVATIVE = "conservative"  # Małe chunki, bezpieczne
    BALANCED = "balanced"          # Standardowe
    AGGRESSIVE = "aggressive"      # Duże chunki, ryzykowne


@dataclass
class ChunkConfig:
    """Konfiguracja chunkowania dla modelu."""
    model: ModelProfile
    chunk_tokens: int
    chunk_chars: int
    max_chunks_per_pass: int
    overlap_tokens: int
    strategy: ChunkStrategy


def calculate_chunk_config(
    model_name: str,
    strategy: ChunkStrategy = ChunkStrategy.BALANCED,
    custom_chunk_tokens: Optional[int] = None
) -> ChunkConfig:
    """
    Oblicza optymalną konfigurację chunkowania dla modelu.
    
    Args:
        model_name: Nazwa modelu
        strategy: Strategia chunkowania
        custom_chunk_tokens: Opcjonalny custom chunk size
        
    Returns:
        ChunkConfig z optymalnymi parametrami
    """
    profile = get_model_profile(model_name) or get_default_profile()
    
    # Bazowy chunk size
    base_chunk = profile.safe_chunk_tokens
    
    # Modyfikuj według strategii
    if strategy == ChunkStrategy.CONSERVATIVE:
        chunk_tokens = int(base_chunk * 0.5)  # 50% safe size
        overlap = int(chunk_tokens * 0.1)     # 10% overlap
        max_chunks = 5
    elif strategy == ChunkStrategy.AGGRESSIVE:
        chunk_tokens = int(base_chunk * 1.5)  # 150% safe size
        overlap = int(chunk_tokens * 0.05)    # 5% overlap
        max_chunks = 20
    else:  # BALANCED
        chunk_tokens = base_chunk
        overlap = int(chunk_tokens * 0.08)    # 8% overlap
        max_chunks = 10
    
    # Override z custom
    if custom_chunk_tokens:
        chunk_tokens = custom_chunk_tokens
    
    chunk_chars = int(chunk_tokens * profile.chars_per_token)
    
    return ChunkConfig(
        model=profile,
        chunk_tokens=chunk_tokens,
        chunk_chars=chunk_chars,
        max_chunks_per_pass=max_chunks,
        overlap_tokens=overlap,
        strategy=strategy
    )


# ═══════════════════════════════════════════════════════════════════════════
# SIZE ESTIMATION
# ═══════════════════════════════════════════════════════════════════════════

def estimate_tokens(text: str, model_name: str = "gemini-2.0-flash") -> int:
    """
    Szacuje liczbę tokenów dla tekstu.
    
    Args:
        text: Tekst do oszacowania
        model_name: Nazwa modelu
        
    Returns:
        Szacowana liczba tokenów
    """
    profile = get_model_profile(model_name) or get_default_profile()
    return int(len(text) / profile.chars_per_token)


def estimate_chunks_needed(
    text_length_chars: int,
    model_name: str = "gemini-2.0-flash",
    strategy: ChunkStrategy = ChunkStrategy.BALANCED
) -> int:
    """
    Szacuje liczbę chunków potrzebnych do przetworzenia tekstu.
    """
    config = calculate_chunk_config(model_name, strategy)
    
    if text_length_chars <= config.chunk_chars:
        return 1
    
    effective_chunk = config.chunk_chars - int(config.overlap_tokens * config.model.chars_per_token)
    return max(1, (text_length_chars + effective_chunk - 1) // effective_chunk)


def can_process_in_one_call(
    text_length_chars: int,
    model_name: str = "gemini-2.0-flash"
) -> bool:
    """
    Sprawdza czy tekst można przetworzyć w jednym wywołaniu.
    """
    profile = get_model_profile(model_name) or get_default_profile()
    return text_length_chars <= profile.max_input_chars


# ═══════════════════════════════════════════════════════════════════════════
# COMPARISON TABLE
# ═══════════════════════════════════════════════════════════════════════════

def print_model_comparison():
    """Drukuje tabelę porównawczą modeli."""
    print("\n" + "═" * 100)
    print("🐺 ALFA MODEL LIMITS COMPARISON")
    print("═" * 100)
    
    print(f"\n{'Model':<25} {'Provider':<12} {'Context':<12} {'Safe Chunk':<12} {'Chunk Chars':<12} {'Vision':<8}")
    print("-" * 100)
    
    for name, profile in sorted(ALL_MODELS.items(), key=lambda x: -x[1].context_window):
        # Skip duplicates
        if ":" in name and name.split(":")[0] in ALL_MODELS:
            continue
        
        context = f"{profile.context_window:,}"
        chunk = f"{profile.safe_chunk_tokens:,}"
        chars = f"{profile.safe_chunk_chars:,}"
        vision = "✅" if profile.supports_vision else "❌"
        
        print(f"{name:<25} {profile.provider:<12} {context:<12} {chunk:<12} {chars:<12} {vision:<8}")
    
    print("=" * 100)


def get_limits_summary() -> dict:
    """Zwraca podsumowanie limitów."""
    return {
        "gemini": {
            "gemini-2.0-flash": {
                "context": GEMINI_2_FLASH.context_window,
                "safe_chunk_tokens": GEMINI_2_FLASH.safe_chunk_tokens,
                "safe_chunk_chars": GEMINI_2_FLASH.safe_chunk_chars,
            },
            "gemini-1.5-pro": {
                "context": GEMINI_1_5_PRO.context_window,
                "safe_chunk_tokens": GEMINI_1_5_PRO.safe_chunk_tokens,
                "safe_chunk_chars": GEMINI_1_5_PRO.safe_chunk_chars,
            },
        },
        "deepseek": {
            "deepseek-chat": {
                "context": DEEPSEEK_CHAT.context_window,
                "safe_chunk_tokens": DEEPSEEK_CHAT.safe_chunk_tokens,
                "safe_chunk_chars": DEEPSEEK_CHAT.safe_chunk_chars,
            },
            "deepseek-r1": {
                "context": DEEPSEEK_R1.context_window,
                "safe_chunk_tokens": DEEPSEEK_R1.safe_chunk_tokens,
                "safe_chunk_chars": DEEPSEEK_R1.safe_chunk_chars,
            },
        },
        "ollama": {
            "mistral:7b": {
                "context": MISTRAL_7B.context_window,
                "safe_chunk_tokens": MISTRAL_7B.safe_chunk_tokens,
                "safe_chunk_chars": MISTRAL_7B.safe_chunk_chars,
            },
            "qwen2.5:72b": {
                "context": QWEN_2_5_72B.context_window,
                "safe_chunk_tokens": QWEN_2_5_72B.safe_chunk_tokens,
                "safe_chunk_chars": QWEN_2_5_72B.safe_chunk_chars,
            },
        },
        "recommended": {
            "primary": "gemini-2.0-flash",
            "fallback": "deepseek-chat",
            "local": "qwen2.5:72b",
            "reason": "Gemini 2.0 Flash ma 1M context, jest darmowy i szybki"
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print_model_comparison()
    
    print("\n\n🧮 CHUNK CALCULATIONS:")
    print("-" * 60)
    
    # Test text sizes
    sizes = [
        10_000,      # 10 KB
        100_000,     # 100 KB
        1_000_000,   # 1 MB
        10_000_000,  # 10 MB
        100_000_000, # 100 MB
    ]
    
    for size in sizes:
        print(f"\n📄 Text size: {size:,} chars ({size / 1_000_000:.1f} MB)")
        
        for model in ["gemini-2.0-flash", "deepseek-chat", "mistral:7b"]:
            config = calculate_chunk_config(model)
            chunks = estimate_chunks_needed(size, model)
            one_call = "✅ YES" if can_process_in_one_call(size, model) else "❌ NO"
            
            print(f"   {model:<20} → {chunks:>4} chunks | One call: {one_call}")
    
    print("\n✅ Analysis complete!")
