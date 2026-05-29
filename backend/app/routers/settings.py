from fastapi import APIRouter

from ..config import get_settings
from ..providers import active_chat_label
from ..runtime import chat_config, gemini_key, update_chat_config
from ..schemas import SettingsRead, SettingsUpdate

router = APIRouter(tags=["settings"])


def _read() -> SettingsRead:
    cfg = chat_config()
    s = get_settings()
    return SettingsRead(
        chat_provider=cfg.get("chat_provider", "gemini"),
        chat_model=cfg.get("chat_model", ""),
        openrouter_base_url=cfg.get("openrouter_base_url", ""),
        openai_compatible_base_url=cfg.get("openai_compatible_base_url", ""),
        ollama_base_url=cfg.get("ollama_base_url", ""),
        has_openrouter_key=bool(cfg.get("openrouter_api_key")),
        has_openai_compatible_key=bool(cfg.get("openai_compatible_api_key")),
        has_gemini_key=bool(gemini_key() or s.gemini_api_key),
        embedding_provider=s.llm_provider,
        active_chat=active_chat_label(),
    )


@router.get("/settings", response_model=SettingsRead)
def get_chat_settings():
    return _read()


@router.put("/settings", response_model=SettingsRead)
def put_chat_settings(payload: SettingsUpdate):
    # Only non-None fields are applied; empty string clears a value.
    update_chat_config(payload.model_dump(exclude_none=True))
    return _read()
