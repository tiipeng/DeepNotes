from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.llms.google_genai import GoogleGenAI

from ..config import get_settings
from .base import ModelProvider


class GeminiProvider(ModelProvider):
    name = "gemini"

    def __init__(self) -> None:
        s = get_settings()
        if not s.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in backend/.env")
        self._llm = GoogleGenAI(model=s.gemini_llm_model, api_key=s.gemini_api_key)
        self._embed = GoogleGenAIEmbedding(
            model_name=s.gemini_embed_model, api_key=s.gemini_api_key
        )

    def llm(self):
        return self._llm

    def embedding(self):
        return self._embed
