from functools import lru_cache

from ..config import get_settings
from .base import ModelProvider


@lru_cache
def get_provider() -> ModelProvider:
    name = get_settings().llm_provider.lower()
    if name == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider()
    if name == "ollama":
        from .ollama import OllamaProvider

        return OllamaProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {name!r} (expected 'gemini' or 'ollama')")
