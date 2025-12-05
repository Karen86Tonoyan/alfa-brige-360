"""
ALFA_SEAT — Model Registry
Central registry for all AI model adapters.
"""

import logging
from typing import Dict, Any, Optional

from .adapters.gpt import GPTAdapter
from .adapters.claude import ClaudeAdapter
from .adapters.gemini import GeminiAdapter
from .adapters.deepseek import DeepSeekAdapter
from .adapters.ollama import OllamaAdapter

logger = logging.getLogger("ALFA.Seat.Registry")


# ═══════════════════════════════════════════════════════════════════════════
# MODEL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Cloud Models
    "gpt": {
        "name": "GPT-4 Turbo",
        "instance": GPTAdapter(),
        "type": "cloud",
        "provider": "OpenAI"
    },
    "claude": {
        "name": "Claude 3.5 Sonnet",
        "instance": ClaudeAdapter(),
        "type": "cloud",
        "provider": "Anthropic"
    },
    "gemini": {
        "name": "Gemini 2.0 Flash",
        "instance": GeminiAdapter(),
        "type": "cloud",
        "provider": "Google"
    },
    "deepseek": {
        "name": "DeepSeek R1",
        "instance": DeepSeekAdapter(),
        "type": "cloud",
        "provider": "DeepSeek"
    },
    
    # Local Models (Ollama)
    "ollama_mistral": {
        "name": "Mistral (Ollama)",
        "instance": OllamaAdapter("mistral"),
        "type": "local",
        "provider": "Ollama"
    },
    "ollama_codellama": {
        "name": "CodeLlama (Ollama)",
        "instance": OllamaAdapter("codellama"),
        "type": "local",
        "provider": "Ollama"
    },
    "ollama_deepseek": {
        "name": "DeepSeek-R1 (Ollama)",
        "instance": OllamaAdapter("deepseek-r1:7b"),
        "type": "local",
        "provider": "Ollama"
    },
}


def get_model(model_id: str) -> Optional[Dict[str, Any]]:
    """Get model by ID."""
    return MODEL_REGISTRY.get(model_id)


def get_adapter(model_id: str):
    """Get model adapter instance."""
    model = MODEL_REGISTRY.get(model_id)
    if model:
        return model["instance"]
    return None


def list_models() -> Dict[str, dict]:
    """List all models with metadata (without instances)."""
    return {
        model_id: {
            "name": info["name"],
            "type": info["type"],
            "provider": info["provider"]
        }
        for model_id, info in MODEL_REGISTRY.items()
    }


def register_model(
    model_id: str,
    name: str,
    instance,
    model_type: str = "custom",
    provider: str = "custom"
) -> None:
    """Register a new model."""
    MODEL_REGISTRY[model_id] = {
        "name": name,
        "instance": instance,
        "type": model_type,
        "provider": provider
    }
    logger.info(f"Registered model: {model_id} ({name})")


async def check_model_health(model_id: str) -> bool:
    """Check if model is healthy."""
    adapter = get_adapter(model_id)
    if adapter:
        return await adapter.health_check()
    return False
