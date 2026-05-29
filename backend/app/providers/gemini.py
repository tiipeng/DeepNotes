from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.llms.google_genai import GoogleGenAI

from ..config import get_settings
from .base import ModelProvider


class GeminiProvider(ModelProvider):
    name = "gemini"

    def __init__(self) -> None:
        from ..runtime import gemini_key

        s = get_settings()
        key = gemini_key() or s.gemini_api_key  # runtime override (Settings UI) or .env
        if not key:
            raise RuntimeError("Gemini API key is not set (backend/.env or Settings)")
        self._llm = GoogleGenAI(model=s.gemini_llm_model, api_key=key)
        self._embed = GoogleGenAIEmbedding(model_name=s.gemini_embed_model, api_key=key)

    def llm(self):
        return self._llm

    def embedding(self):
        return self._embed
