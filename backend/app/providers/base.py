"""Provider abstraction (ULTRAPLAN §0 principle 6 — sovereignty).

A provider returns LlamaIndex-compatible LLM + embedding objects so the RAG layer
(CitationQueryEngine, VectorStoreIndex) is identical regardless of backend. Swapping
Gemini for a local Ollama model is a config change, not an app-logic change.
"""

from abc import ABC, abstractmethod

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.llms.llm import LLM


class ModelProvider(ABC):
    name: str

    @abstractmethod
    def llm(self) -> LLM: ...

    @abstractmethod
    def embedding(self) -> BaseEmbedding: ...
