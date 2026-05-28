"""Chroma vector store — one persistent collection, keyed by chunk id.

Retrieval is scoped per notebook (and per selected source) via metadata filters,
so a single collection serves every notebook. Phase 3 builds a VectorStoreIndex
from this same store for the CitationQueryEngine.
"""

from functools import lru_cache

import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore

from ..config import get_settings

_COLLECTION = "deepnotes"


@lru_cache(maxsize=1)
def _client() -> "chromadb.api.ClientAPI":
    return chromadb.PersistentClient(path=get_settings().chroma_dir)


def get_collection():
    return _client().get_or_create_collection(_COLLECTION)


def get_vector_store() -> ChromaVectorStore:
    return ChromaVectorStore(chroma_collection=get_collection())


def delete_source(source_id: str) -> None:
    """Remove every vector belonging to a source (on source delete)."""
    get_collection().delete(where={"source_id": source_id})
