from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Provider selection: "gemini" (default) or "ollama" (local sovereignty mode).
    # NOTE: this governs the EMBEDDING model + the *default* chat model. The chat
    # (generation) model can be overridden independently via chat_provider/chat_model
    # (bring-your-own-key) without affecting the pinned embedding space.
    llm_provider: str = "gemini"

    # Gemini — models verified available for this key in Phase 0.
    gemini_api_key: str = ""
    gemini_llm_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"

    # ---- Chat (generation) model — selectable, bring-your-own-key ----
    # Providers: "gemini" (default) | "openrouter" | "openai_compatible" | "ollama".
    # Embeddings are NOT affected by this (they stay pinned to llm_provider above),
    # so swapping the chat model never invalidates the vector store / citations.
    chat_provider: str = "gemini"
    chat_model: str = ""  # empty -> the provider's default model
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openai_compatible_base_url: str = ""  # OpenAI, vLLM, LM Studio, or "your own endpoint"
    openai_compatible_api_key: str = ""

    # Ollama (local mode) — path present, wired only when llm_provider="ollama".
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.1"
    ollama_embed_model: str = "nomic-embed-text"

    # Audio transcription (faster-whisper). "base" balances speed/quality on CPU.
    whisper_model: str = "base"

    database_url: str = "sqlite:///./deepnotes.db"
    chroma_dir: str = "./chroma"
    tables_path: str = "./tables.duckdb"  # DuckDB file for XLSX spreadsheet reasoning
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
