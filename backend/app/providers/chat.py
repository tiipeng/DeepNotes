"""Chat (generation) LLM resolver — bring-your-own-key, selectable provider.

Returns a LlamaIndex LLM for the *generation* step only (answers, intent routing,
text-to-SQL, summaries). Embeddings are resolved separately via get_provider().embedding()
and stay pinned to llm_provider, so changing the chat model never touches the vector space.

Providers: gemini (default) | openrouter | openai_compatible | ollama.
"""

import json

from ..config import get_settings
from ..runtime import chat_config

_cache: dict = {}


def _build(provider: str, model: str, cfg: dict):
    s = get_settings()
    if provider == "gemini":
        from llama_index.llms.google_genai import GoogleGenAI

        if not s.gemini_api_key:
            raise ValueError("Gemini API key is not set (GEMINI_API_KEY in backend/.env).")
        return GoogleGenAI(model=model or s.gemini_llm_model, api_key=s.gemini_api_key)

    if provider == "openrouter":
        from llama_index.llms.openai_like import OpenAILike

        key = cfg.get("openrouter_api_key") or ""
        if not key:
            raise ValueError("OpenRouter API key is not set. Add it in Settings.")
        if not model:
            raise ValueError("Choose an OpenRouter model (e.g. 'anthropic/claude-3.5-sonnet').")
        return OpenAILike(
            model=model,
            api_base=cfg.get("openrouter_base_url") or "https://openrouter.ai/api/v1",
            api_key=key,
            is_chat_model=True,
            is_function_calling_model=False,
            context_window=131072,
            timeout=120.0,
            max_retries=2,
        )

    if provider == "openai_compatible":
        from llama_index.llms.openai_like import OpenAILike

        base = cfg.get("openai_compatible_base_url") or ""
        if not base:
            raise ValueError("Set the OpenAI-compatible base URL in Settings (e.g. https://api.openai.com/v1).")
        if not model:
            raise ValueError("Choose a model name in Settings.")
        return OpenAILike(
            model=model,
            api_base=base,
            api_key=cfg.get("openai_compatible_api_key") or "none",
            is_chat_model=True,
            is_function_calling_model=False,
            context_window=131072,
            timeout=120.0,
            max_retries=2,
        )

    if provider == "ollama":
        from llama_index.llms.ollama import Ollama

        return Ollama(
            model=model or s.ollama_llm_model,
            base_url=cfg.get("ollama_base_url") or s.ollama_base_url,
            request_timeout=300.0,
        )

    raise ValueError(f"Unknown chat provider: {provider!r}")


def get_chat_llm():
    cfg = chat_config()
    provider = (cfg.get("chat_provider") or "gemini").lower()
    model = (cfg.get("chat_model") or "").strip()
    sig = json.dumps(cfg, sort_keys=True)  # any settings change -> rebuild
    if sig not in _cache:
        _cache.clear()
        _cache[sig] = _build(provider, model, cfg)
    return _cache[sig]


def active_chat_label() -> str:
    cfg = chat_config()
    provider = (cfg.get("chat_provider") or "gemini").lower()
    model = (cfg.get("chat_model") or "").strip()
    if provider == "gemini" and not model:
        model = get_settings().gemini_llm_model
    return f"{provider} · {model}" if model else provider
