from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Provider selection: "gemini" (default) or "ollama" (local sovereignty mode).
    llm_provider: str = "gemini"

    # Gemini — models verified available for this key in Phase 0.
    gemini_api_key: str = ""
    gemini_llm_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"

    # Ollama (local mode) — path present, wired only when llm_provider="ollama".
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.1"
    ollama_embed_model: str = "nomic-embed-text"

    database_url: str = "sqlite:///./deepnotes.db"
    chroma_dir: str = "./chroma"
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
