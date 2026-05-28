"""Ingestion pipeline: chunk -> embed -> store, with metadata preserved.

Each chunk keeps its char offsets into parsed_markdown plus page/section, persisted
both in Chroma (as node metadata, for retrieval) and SQLite (for the citation drawer).
Chunk id == Chroma node id, so the two stay linked.
"""

import json
import uuid

from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models import Chunk, Source
from ..providers import get_provider
from ..stores.chroma import get_vector_store
from .parse import ParsedDoc, span_at

_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30), reraise=True)
def _embed_and_store(nodes, storage_context, embed_model) -> None:
    # Provider embeddings have their own internal retry; this outer retry guards the
    # whole batch against transient free-tier rate-limit errors with backoff.
    VectorStoreIndex(nodes, storage_context=storage_context, embed_model=embed_model)


def ingest_source(db: Session, source: Source, parsed: ParsedDoc) -> int:
    """Chunk parsed markdown, embed, store vectors + chunk rows. Returns chunk count."""
    base_nodes = _splitter.get_nodes_from_documents([Document(text=parsed.markdown)])

    nodes: list[TextNode] = []
    chunk_rows: list[Chunk] = []
    for i, n in enumerate(base_nodes):
        start = n.start_char_idx or 0
        end = n.end_char_idx if n.end_char_idx is not None else start + len(n.get_content())
        sp = span_at(start, parsed.spans)
        page = sp.page if sp else None
        section = sp.section if sp else None
        cid = uuid.uuid4().hex

        meta = {
            "source_id": source.id,
            "notebook_id": source.notebook_id,
            "page": page if page is not None else -1,  # Chroma rejects None
            "section": section or "",
            "char_offset_start": start,
            "char_offset_end": end,
            "order_index": i,
        }
        node = TextNode(id_=cid, text=n.get_content(), metadata=meta)
        # Embed only the chunk text — keep bookkeeping metadata out of the vector/LLM.
        node.excluded_embed_metadata_keys = list(meta.keys())
        node.excluded_llm_metadata_keys = list(meta.keys())
        nodes.append(node)

        chunk_rows.append(
            Chunk(
                id=cid,
                source_id=source.id,
                notebook_id=source.notebook_id,
                text=n.get_content(),
                order_index=i,
                page=page,
                section=section,
                char_offset_start=start,
                char_offset_end=end,
            )
        )

    storage_context = StorageContext.from_defaults(vector_store=get_vector_store())
    _embed_and_store(nodes, storage_context, get_provider().embedding())

    db.add_all(chunk_rows)
    source.parsed_markdown = parsed.markdown
    source.page_map = json.dumps([[s.start, s.end, s.page] for s in parsed.spans])
    source.char_count = len(parsed.markdown)
    if parsed.num_pages:
        source.pages = parsed.num_pages
    source.status = "ready"
    db.commit()
    return len(chunk_rows)
