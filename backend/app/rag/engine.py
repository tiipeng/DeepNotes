"""Grounded chat: retrieve over selected sources -> CitationQueryEngine -> answer
with inline [n] markers, mapped to denormalized CitationOut records.
"""

import logging
import re

from llama_index.core import PromptTemplate, Settings, VectorStoreIndex
from llama_index.core.query_engine import CitationQueryEngine
from llama_index.core.vector_stores import (
    FilterCondition,
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from sqlalchemy.orm import Session

from ..ingest.parse import resolve_at
from ..models import Chunk, Source
from ..providers import get_provider
from ..stores.chroma import get_vector_store
from .locate import locate_span

NOT_FOUND = "I couldn't find an answer to that in your sources."

_QA_TEMPLATE = PromptTemplate(
    "You are answering strictly from the provided sources, each labeled 'Source N:'.\n"
    "Rules:\n"
    "- Use ONLY information in these sources. Do not use outside knowledge.\n"
    "- Cite every claim with the matching source number(s) in square brackets, e.g. [1] "
    "or [1][2], placed immediately after the claim.\n"
    "- If the sources do not contain the answer, reply with exactly this sentence and "
    f"nothing else: {NOT_FOUND}\n\n"
    "Sources:\n{context_str}\n\n"
    "Question: {query_str}\n"
    "Answer: "
)

_REFINE_TEMPLATE = PromptTemplate(
    "Refine the existing answer using ONLY the sources below, keeping [n] citations.\n"
    "If the sources add nothing, return the existing answer unchanged.\n"
    f"If nothing answers the question, reply exactly: {NOT_FOUND}\n\n"
    "Existing answer: {existing_answer}\n\n"
    "Sources:\n{context_msg}\n\n"
    "Question: {query_str}\n"
    "Refined Answer: "
)

_CITE_RE = re.compile(r"\[(\d+)\]")
_SOURCE_PREFIX = re.compile(r"^\s*Source\s+\d+:\s*", re.IGNORECASE)

log = logging.getLogger("deepnotes.citations")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


def _strip_prefix(text: str) -> str:
    return _SOURCE_PREFIX.sub("", text).strip()


def _build_engine(source_ids: list[str], top_k: int = 8) -> CitationQueryEngine:
    provider = get_provider()
    Settings.llm = provider.llm()
    Settings.embed_model = provider.embedding()

    index = VectorStoreIndex.from_vector_store(
        get_vector_store(), embed_model=provider.embedding()
    )
    filters = MetadataFilters(
        filters=[
            MetadataFilter(key="source_id", value=sid, operator=FilterOperator.EQ)
            for sid in source_ids
        ],
        condition=FilterCondition.OR,
    )
    return CitationQueryEngine.from_args(
        index,
        llm=provider.llm(),
        similarity_top_k=top_k,
        filters=filters,
        citation_chunk_size=48,  # ~1 sentence per cited unit (tight, no heading graze)
        citation_chunk_overlap=0,
        citation_qa_template=_QA_TEMPLATE,
        citation_refine_template=_REFINE_TEMPLATE,
    )


def _build_citations(db: Session, answer: str, source_nodes) -> list[dict]:
    cited_ns = sorted({int(m) for m in _CITE_RE.findall(answer)})
    out: list[dict] = []
    for n in cited_ns:
        if n - 1 >= len(source_nodes):
            continue
        node = source_nodes[n - 1].node
        meta = node.metadata or {}
        sid = meta.get("source_id")
        source = db.get(Source, sid) if sid else None
        if source is None:
            continue

        cited_text = _strip_prefix(node.get_content())
        p_start = int(meta.get("char_offset_start", 0))
        p_end = int(meta.get("char_offset_end", 0))
        start, end, method = locate_span(cited_text, source.parsed_markdown, p_start, p_end)
        log.info(
            "locate_span [%d] source=%s method=%s span=%d..%d (%d chars) cited=%d chars",
            n, sid, method, start, end, end - start, len(cited_text),
        )

        # Resolve page + section from the cited sentence's offset (chunk-size
        # independent), falling back to the chunk's metadata if no page_map.
        page, section = resolve_at(source.page_map, start)
        if page is None:
            meta_page = meta.get("page")
            page = None if meta_page in (None, -1, "-1") else int(meta_page)
        if section is None:
            section = meta.get("section") or None
        chunk = (
            db.query(Chunk)
            .filter_by(source_id=sid, char_offset_start=p_start)
            .first()
        )

        out.append(
            {
                "display_index": n,
                "source_id": sid,
                "chunk_id": chunk.id if chunk else None,
                "source_title": source.title,
                "source_authors": source.authors,
                "source_venue": source.venue,
                "source_kind": source.kind,
                "page": page,
                "section": section,
                "char_offset_start": start,
                "char_offset_end": end,
                "snippet": source.parsed_markdown[start:end],
            }
        )
    return out


def _renumber(answer: str, citations: list[dict]) -> tuple[str, list[dict]]:
    """Remap the engine's internal citation numbers (e.g. [7][29][112]) to clean
    sequential [1][2][3] in order of first appearance, in both the answer text and
    the citation records."""
    order: list[int] = []
    for m in _CITE_RE.finditer(answer):
        n = int(m.group(1))
        if n not in order:
            order.append(n)
    remap = {old: i + 1 for i, old in enumerate(order)}
    new_answer = _CITE_RE.sub(lambda m: f"[{remap.get(int(m.group(1)), m.group(1))}]", answer)
    for c in citations:
        c["display_index"] = remap.get(c["display_index"], c["display_index"])
    citations.sort(key=lambda c: c["display_index"])
    return new_answer, citations


def answer_question(db: Session, source_ids: list[str], question: str) -> dict:
    if not source_ids:
        return {"answer": NOT_FOUND, "grounded": False, "citations": []}

    engine = _build_engine(source_ids)
    resp = engine.query(question)
    answer = str(resp).strip()
    grounded = NOT_FOUND.lower() not in answer.lower()
    citations = _build_citations(db, answer, resp.source_nodes) if grounded else []
    # An answer with no resolvable citations isn't truly grounded.
    if grounded and not citations:
        grounded = False
    if grounded:
        answer, citations = _renumber(answer, citations)
    return {"answer": answer, "grounded": grounded, "citations": citations}
