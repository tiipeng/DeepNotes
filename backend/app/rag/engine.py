"""Grounded chat: retrieve over selected sources -> CitationQueryEngine -> answer
with inline [n] markers, mapped to denormalized CitationOut records.
"""

import logging
import re

from llama_index.core import PromptTemplate, Settings, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
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
from ..providers import get_chat_llm, get_provider
from ..stores.chroma import get_vector_store
from .locate import locate_span

NOT_FOUND = "I couldn't find an answer to that in your sources."

_QA_TEMPLATE = PromptTemplate(
    "You are answering strictly from the provided sources, each labeled 'Source N:'.\n"
    "Rules:\n"
    "- Use ONLY information in these sources. Do not use outside knowledge.\n"
    "- Cite sparingly, the way a careful writer does: place a [n] after a KEY claim or at "
    "the end of a sentence — not after every clause. At most one citation per sentence, and "
    "only the single most relevant source. Do not stack multiple numbers unless truly needed.\n"
    "- Write the answer in the same language as the question.\n"
    "- If the sources do not contain the answer, reply with exactly this sentence (in "
    f"English) and nothing else: {NOT_FOUND}\n\n"
    "Sources:\n{context_str}\n\n"
    "Question: {query_str}\n"
    "Answer: "
)

_SYNTH_TEMPLATE = PromptTemplate(
    "You are synthesizing an overview from the user's sources, each labeled 'Source N:'.\n"
    "Write a clear, well-structured synthesis that addresses the request using ONLY these "
    "sources. Cover the main points across them; do not use outside knowledge. Cite key "
    "claims with a single [n] at the end of the sentence — sparingly, the most relevant "
    "source only. Write the overview in the same language as the request.\n\n"
    "Sources:\n{context_str}\n\n"
    "Request: {query_str}\n"
    "Overview: "
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

_COMBINED_TEMPLATE = PromptTemplate(
    "Answer the question using the sources below, each labeled 'Source N:'. Source 1 is a "
    "figure computed from the user's spreadsheet; the others are document excerpts. Use "
    "ONLY this information, combine the spreadsheet figure with the documents as the "
    "question requires, and cite key claims with a single [n] (sparingly, most relevant "
    "source only). Do not use outside knowledge. Answer in the same language as the question.\n\n"
    "Sources:\n{context_str}\n\n"
    "Question: {query_str}\n"
    "Answer: "
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
    Settings.llm = get_chat_llm()
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
        llm=get_chat_llm(),
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


_BRACKET = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")


def _finalize_citations(answer: str, valid: dict[int, dict]) -> tuple[str, list[dict]]:
    """Strip source-internal reference markers (e.g. the document's own '[64, 139]' or a
    '[38]' that maps to no retrieved chunk) so only real DeepNotes citations render as
    chips, then renumber the survivors to clean sequential [1][2][3]. `valid` maps the
    model's original [n] -> resolved citation dict."""
    # 1. remove any bracket token that isn't a single, resolvable citation index
    def _strip(m: re.Match) -> str:
        body = m.group(0).strip("[] ")
        if "," in body:
            return ""  # comma-form is always a source-internal reference
        return m.group(0) if int(body) in valid else ""

    cleaned = _BRACKET.sub(_strip, answer)
    # 2. renumber the surviving markers in order of first appearance
    order: list[int] = []
    for m in _CITE_RE.finditer(cleaned):
        n = int(m.group(1))
        if n in valid and n not in order:
            order.append(n)
    remap = {old: i + 1 for i, old in enumerate(order)}
    new_answer = _CITE_RE.sub(lambda m: f"[{remap[int(m.group(1))]}]" if int(m.group(1)) in remap else "", cleaned)
    new_answer = re.sub(r"\s+([.,;:)])", r"\1", new_answer)
    new_answer = re.sub(r"[ \t]{2,}", " ", new_answer).strip()
    citations = [{**valid[old], "display_index": i} for old, i in remap.items()]
    citations.sort(key=lambda c: c["display_index"])
    return new_answer, citations


# ---------------------------------------------------------------------------
# Streaming path
#
# CitationQueryEngine's response synthesizer buffers GoogleGenAI into one chunk,
# so we can't stream through it. Instead we replicate its citation sub-chunking
# (same 48-token units → same sentence-level highlight precision) and stream a
# direct LLM call, resolving citations after the prose completes.
# ---------------------------------------------------------------------------

_cite_splitter = SentenceSplitter(chunk_size=48, chunk_overlap=0)
_DISP_COMPLETE = re.compile(r"\[\d+\]")
_DISP_PARTIAL = re.compile(r"\[\d*\Z")  # a trailing, not-yet-closed marker


def _strip_for_display(buf: str) -> tuple[str, str]:
    """Remove complete [n] markers; hold back a trailing partial marker that may
    finish in the next token. Returns (emit_now, hold_back)."""
    buf = _DISP_COMPLETE.sub("", buf)
    m = _DISP_PARTIAL.search(buf)
    if m:
        return buf[: m.start()], buf[m.start() :]
    return buf, ""


def stream_plain(prompt: str):
    """Stream a plain LLM reply (no retrieval, no citations) — for conversational/meta
    intents. Yields ('token', delta) then ('done', {...}) like stream_answer."""
    raw = ""
    for resp in get_chat_llm().stream_complete(prompt):
        delta = resp.delta or ""
        if delta:
            raw += delta
            yield ("token", delta)
    yield ("done", {"answer": raw.strip(), "grounded": False, "citations": []})


def _retrieve_citation_chunks(source_ids: list[str], question: str, top_k: int = 8) -> list[dict]:
    provider = get_provider()
    Settings.llm = get_chat_llm()
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
    retriever = index.as_retriever(similarity_top_k=top_k, filters=filters)
    chunks: list[dict] = []
    for nws in retriever.retrieve(question):
        meta = nws.node.metadata or {}
        for piece in _cite_splitter.split_text(nws.node.get_content()):
            chunks.append(
                {
                    "text": piece,
                    "source_id": meta.get("source_id"),
                    "p_start": int(meta.get("char_offset_start", 0)),
                    "p_end": int(meta.get("char_offset_end", 0)),
                    "page": meta.get("page"),
                    "section": meta.get("section"),
                }
            )
    return chunks


def _citation_from_chunk(db: Session, n: int, chunk: dict) -> dict | None:
    source = db.get(Source, chunk["source_id"])
    if source is None:
        return None
    cited = _strip_prefix(chunk["text"])
    start, end, _ = locate_span(cited, source.parsed_markdown, chunk["p_start"], chunk["p_end"])
    page, section = resolve_at(source.page_map, start)
    if page is None:
        page = None if chunk["page"] in (None, -1, "-1") else int(chunk["page"])
    if section is None:
        section = chunk["section"] or None
    return {
        "display_index": n,
        "source_id": source.id,
        "chunk_id": None,
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


def stream_answer(db: Session, source_ids: list[str], question: str, mode: str = "factual"):
    """Generator yielding ('token', delta) as prose streams, then ('done', result)
    where result = {answer, grounded, citations}. Display tokens have [n] markers
    stripped; citations are resolved from the full answer once it completes.

    mode='factual' = strict pinpoint RAG (may refuse with NOT_FOUND).
    mode='synthesis' = broad retrieval + overview template (never refuses)."""
    synthesis = mode == "synthesis"
    if not source_ids:
        yield ("token", NOT_FOUND)
        yield ("done", {"answer": NOT_FOUND, "grounded": False, "citations": []})
        return

    top_k = 20 if synthesis else 8
    chunks = _retrieve_citation_chunks(source_ids, question, top_k=top_k)
    if not chunks:
        yield ("token", NOT_FOUND)
        yield ("done", {"answer": NOT_FOUND, "grounded": False, "citations": []})
        return

    context = "\n\n".join(f"Source {i + 1}:\n{c['text']}" for i, c in enumerate(chunks))
    template = _SYNTH_TEMPLATE if synthesis else _QA_TEMPLATE
    prompt = template.format(context_str=context, query_str=question)

    raw = ""
    hold = ""
    for resp in get_chat_llm().stream_complete(prompt):
        delta = resp.delta or ""
        if not delta:
            continue
        raw += delta
        emit, hold = _strip_for_display(hold + delta)
        if emit:
            yield ("token", emit)
    tail = _DISP_COMPLETE.sub("", hold)
    if tail:
        yield ("token", tail)

    answer = raw.strip()
    grounded = NOT_FOUND.lower() not in answer.lower()
    citations: list[dict] = []
    if grounded:
        valid: dict[int, dict] = {}
        for n in sorted({int(m) for m in _CITE_RE.findall(answer)}):
            if n - 1 < len(chunks):
                c = _citation_from_chunk(db, n, chunks[n - 1])
                if c:
                    valid[n] = c
        if not valid:
            grounded = False
        else:
            answer, citations = _finalize_citations(answer, valid)
    yield ("done", {"answer": answer, "grounded": grounded, "citations": citations})


def stream_combined(db: Session, rag_source_ids: list[str], question: str, table: dict):
    """Merge spreadsheet evidence (a computed figure) with RAG prose into ONE grounded
    answer. The table result is injected as 'Source 1' (cited via its row citation);
    document chunks follow as Source 2.. So a mixed-notebook question like 'compare the
    West total with what the paper says about X' answers and cites BOTH source types."""
    rag_chunks = _retrieve_citation_chunks(rag_source_ids, question, top_k=8) if rag_source_ids else []
    table_text = _DISP_COMPLETE.sub("", table["answer"]).strip()
    table_cite = table["citations"][0] if table.get("citations") else None

    parts = [f"Source 1:\n[Computed from the spreadsheet] {table_text}"]
    for i, c in enumerate(rag_chunks, start=2):
        parts.append(f"Source {i}:\n{c['text']}")
    context = "\n\n".join(parts)
    prompt = _COMBINED_TEMPLATE.format(context_str=context, query_str=question)

    raw, hold = "", ""
    for resp in get_chat_llm().stream_complete(prompt):
        delta = resp.delta or ""
        if not delta:
            continue
        raw += delta
        emit, hold = _strip_for_display(hold + delta)
        if emit:
            yield ("token", emit)
    tail = _DISP_COMPLETE.sub("", hold)
    if tail:
        yield ("token", tail)

    # Combined path never hard-refuses (it always has the computed figure); citations are
    # resolved where present, answer prose is always kept.
    answer = raw.strip()
    valid: dict[int, dict] = {}
    for n in sorted({int(m) for m in _CITE_RE.findall(answer)}):
        if n == 1 and table_cite:
            valid[1] = dict(table_cite)
        elif n >= 2 and (n - 2) < len(rag_chunks):
            c = _citation_from_chunk(db, n, rag_chunks[n - 2])
            if c:
                valid[n] = c
    citations: list[dict] = []
    if valid:
        answer, citations = _finalize_citations(answer, valid)
    yield ("done", {"answer": answer, "grounded": bool(citations), "citations": citations})


def answer_question(db: Session, source_ids: list[str], question: str) -> dict:
    if not source_ids:
        return {"answer": NOT_FOUND, "grounded": False, "citations": []}

    engine = _build_engine(source_ids)
    resp = engine.query(question)
    answer = str(resp).strip()
    grounded = NOT_FOUND.lower() not in answer.lower()
    citations: list[dict] = []
    if grounded:
        built = _build_citations(db, answer, resp.source_nodes)
        valid = {c["display_index"]: c for c in built}
        if not valid:
            grounded = False
        else:
            answer, citations = _finalize_citations(answer, valid)
    return {"answer": answer, "grounded": grounded, "citations": citations}
