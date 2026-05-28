from ..config import get_settings
from .base import ModelProvider


class OllamaProvider(ModelProvider):
    """Local sovereignty mode — no data leaves the server.

    Requires a running Ollama daemon plus:
        uv pip install llama-index-llms-ollama llama-index-embeddings-ollama
    Activated via LLM_PROVIDER=ollama. The integration packages are intentionally
    optional so the default Gemini install stays lean.
    """

    name = "ollama"

    def __init__(self) -> None:
        s = get_settings()
        try:
            from llama_index.embeddings.ollama import OllamaEmbedding
            from llama_index.llms.ollama import Ollama
        except ImportError as e:
            raise RuntimeError(
                "Ollama provider needs: uv pip install "
                "llama-index-llms-ollama llama-index-embeddings-ollama"
            ) from e
        self._llm = Ollama(
            model=s.ollama_llm_model, base_url=s.ollama_base_url, request_timeout=300.0
        )
        self._embed = OllamaEmbedding(
            model_name=s.ollama_embed_model, base_url=s.ollama_base_url
        )

    def llm(self):
        return self._llm

    def embedding(self):
        return self._embed
