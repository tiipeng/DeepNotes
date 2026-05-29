"""Runtime chat-model configuration.

The chat (generation) model is selectable at runtime (bring-your-own-key) and stored as
a JSON override over the .env defaults in the single-row `app_settings` table. Embeddings
are NOT governed here — they stay pinned to `llm_provider` so the vector store / citations
never break when the chat model changes.
"""

import json

from .config import get_settings
from .db import SessionLocal
from .models import AppSetting

# Keys overridable at runtime (from the Settings UI). gemini_api_key is included because it
# powers embeddings AND Gemini chat; changing it only swaps the account/key, not the embedding
# MODEL, so the existing vector store stays valid.
_KEYS = (
    "chat_provider",
    "chat_model",
    "gemini_api_key",
    "openrouter_api_key",
    "openrouter_base_url",
    "openai_compatible_base_url",
    "openai_compatible_api_key",
    "ollama_base_url",
)

_cache: dict | None = None


def _defaults() -> dict:
    s = get_settings()
    return {k: getattr(s, k) for k in _KEYS}


def _load() -> dict:
    cfg = _defaults()
    db = SessionLocal()
    try:
        row = db.get(AppSetting, "default")
        if row and row.data:
            try:
                cfg.update({k: v for k, v in json.loads(row.data).items() if k in _KEYS})
            except (ValueError, TypeError):
                pass
    finally:
        db.close()
    return cfg


def chat_config() -> dict:
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache


def gemini_key() -> str:
    """Effective Gemini API key — runtime override (Settings UI) or the .env value."""
    return chat_config().get("gemini_api_key") or ""


def update_chat_config(patch: dict) -> dict:
    """Persist a runtime override (only known keys) and refresh the cache."""
    global _cache
    clean = {k: v for k, v in patch.items() if k in _KEYS and v is not None}
    db = SessionLocal()
    try:
        row = db.get(AppSetting, "default")
        current = {}
        if row and row.data:
            try:
                current = json.loads(row.data)
            except (ValueError, TypeError):
                current = {}
        current.update(clean)
        if row is None:
            row = AppSetting(id="default", data=json.dumps(current))
            db.add(row)
        else:
            row.data = json.dumps(current)
        db.commit()
    finally:
        db.close()
    _cache = None  # force reload on next read
    # The embedding provider is cached and built with the Gemini key; rebuild it so a
    # key change takes effect for embeddings (lazy import avoids a circular import).
    if "gemini_api_key" in clean:
        try:
            from .providers.factory import get_provider

            get_provider.cache_clear()
        except Exception:
            pass
    return chat_config()
