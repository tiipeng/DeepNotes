import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..models import Citation, Message, Notebook, Source
from ..rag.assist import (
    classify_intent,
    conversational_prompt,
    follow_up_questions,
    meta_prompt,
)
from ..providers import get_provider
from ..rag.engine import _DISP_COMPLETE as _DISP
from ..rag.engine import answer_question, stream_answer, stream_plain
from ..schemas import (
    ChatRequest,
    ChatResponse,
    CitationOut,
    MessageRead,
    TableResult,
    ThreadRead,
)
from ..spreadsheet.engine import answer_with_tables

router = APIRouter(tags=["chat"])


def _get_notebook(db: Session, notebook_id: str) -> Notebook:
    nb = db.get(Notebook, notebook_id)
    if nb is None:
        raise HTTPException(404, "Notebook not found")
    return nb


def _resolve_source_ids(nb: Notebook, payload: ChatRequest) -> list[str]:
    if payload.source_ids is not None:
        return payload.source_ids
    return [s.id for s in nb.sources if s.checked and s.status == "ready"]


def _persist_citations(db: Session, message_id: str, citations: list[dict]) -> None:
    for c in citations:
        db.add(
            Citation(
                message_id=message_id,
                source_id=c["source_id"],
                chunk_id=c["chunk_id"],
                display_index=c["display_index"],
                page=c["page"],
                section=c["section"],
                char_offset_start=c["char_offset_start"],
                char_offset_end=c["char_offset_end"],
                snippet=c["snippet"],
            )
        )


def _citation_out(c: Citation, db: Session) -> CitationOut:
    src = db.get(Source, c.source_id)
    return CitationOut(
        display_index=c.display_index,
        source_id=c.source_id,
        chunk_id=c.chunk_id,
        source_title=src.title if src else "(deleted source)",
        source_authors=src.authors if src else None,
        source_venue=src.venue if src else None,
        source_kind=src.kind if src else "pdf",
        page=c.page,
        section=c.section,
        char_offset_start=c.char_offset_start,
        char_offset_end=c.char_offset_end,
        snippet=c.snippet,
    )


def _consume(subgen) -> dict:
    final = None
    for kind, data in subgen:
        if kind != "token":
            final = data
    return final or {"answer": "", "grounded": False, "citations": []}


@router.post("/notebooks/{notebook_id}/chat", response_model=ChatResponse)
def chat(notebook_id: str, payload: ChatRequest, db: Session = Depends(get_db)):
    """Non-streaming sibling of /chat/stream — same intent routing, collected up front."""
    nb = _get_notebook(db, notebook_id)
    source_ids = _resolve_source_ids(nb, payload)
    intent = classify_intent(payload.question, bool(source_ids))
    db.add(Message(notebook_id=notebook_id, role="user", text=payload.question, thread_id=payload.thread_id))

    follow = lambda ans: follow_up_questions(nb.sources, payload.question, ans)  # noqa: E731

    # conversational / meta — plain helpful reply, no retrieval, no refusal
    if intent in ("conversational", "meta"):
        prompt = (
            conversational_prompt(payload.question, nb.sources)
            if intent == "conversational"
            else meta_prompt(payload.question, nb.sources)
        )
        text = get_provider().llm().complete(prompt).text.strip()
        assistant = Message(notebook_id=notebook_id, role="assistant", text=text, thread_id=payload.thread_id)
        db.add(assistant)
        db.commit()
        return ChatResponse(
            message_id=assistant.id, answer_markdown=text, grounded=False,
            citations=[], intent=intent, follow_ups=follow(text),
        )

    # factual — spreadsheet reasoning first
    if intent == "factual":
        table = answer_with_tables(db, notebook_id, payload.question, source_ids)
        if table:
            table_out = TableResult(
                source_title=table["source_title"], sql=table["sql"],
                columns=table["columns"], rows=table["rows"], truncated=table["truncated"],
            )
            assistant = Message(
                notebook_id=notebook_id, role="assistant", text=table["answer"],
                table_json=table_out.model_dump_json(), thread_id=payload.thread_id,
            )
            db.add(assistant)
            db.flush()
            _persist_citations(db, assistant.id, table["citations"])
            db.commit()
            return ChatResponse(
                message_id=assistant.id, answer_markdown=table["answer"], grounded=True,
                citations=[CitationOut(**c) for c in table["citations"]],
                table_result=table_out, intent="factual", follow_ups=follow(table["answer"]),
            )
        result = answer_question(db, source_ids, payload.question)
    else:  # synthesis
        result = _consume(stream_answer(db, source_ids, payload.question, "synthesis"))

    assistant = Message(notebook_id=notebook_id, role="assistant", text=result["answer"], thread_id=payload.thread_id)
    db.add(assistant)
    db.flush()
    _persist_citations(db, assistant.id, result["citations"])
    db.commit()
    return ChatResponse(
        message_id=assistant.id,
        answer_markdown=result["answer"],
        grounded=result["grounded"],
        citations=[CitationOut(**c) for c in result["citations"]],
        intent=intent,
        follow_ups=follow(result["answer"]),
    )


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _word_chunks(text: str, size: int = 6):
    words = text.split(" ")
    for i in range(0, len(words), size):
        yield (" " if i else "") + " ".join(words[i : i + size])


@router.post("/notebooks/{notebook_id}/chat/stream")
def chat_stream(notebook_id: str, payload: ChatRequest):
    """Server-sent events: 'token' deltas as the answer streams, then a 'done'
    event carrying message_id + resolved citations (+ table_result)."""

    def gen():
        db = SessionLocal()
        try:
            nb = db.get(Notebook, notebook_id)
            if nb is None:
                yield _sse({"type": "error", "detail": "Notebook not found"})
                return
            if not payload.question.strip():
                yield _sse({"type": "error", "detail": "Ask a question to get started."})
                return

            source_ids = _resolve_source_ids(nb, payload)
            db.add(Message(notebook_id=notebook_id, role="user", text=payload.question, thread_id=payload.thread_id))
            db.commit()

            # Route by intent. Only the 'factual' path uses strict grounded RAG and may
            # refuse with NOT_FOUND; meta/conversational/synthesis never show the refusal.
            intent = classify_intent(payload.question, bool(source_ids))

            def _suggest(answer: str) -> list[str]:
                return follow_up_questions(nb.sources, payload.question, answer)

            # --- conversational / meta: plain helpful reply, no retrieval, no refusal ---
            if intent in ("conversational", "meta"):
                prompt = (
                    conversational_prompt(payload.question, nb.sources)
                    if intent == "conversational"
                    else meta_prompt(payload.question, nb.sources)
                )
                final = None
                for kind, data in stream_plain(prompt):
                    if kind == "token":
                        yield _sse({"type": "token", "delta": data})
                    else:
                        final = data
                assistant = Message(
                    notebook_id=notebook_id, role="assistant", text=final["answer"],
                    thread_id=payload.thread_id,
                )
                db.add(assistant)
                db.commit()
                yield _sse({
                    "type": "done", "message_id": assistant.id,
                    "answer_markdown": final["answer"], "grounded": False,
                    "citations": [], "table_result": None, "intent": intent,
                    "follow_ups": _suggest(final["answer"]),
                })
                return

            # --- factual: spreadsheet reasoning first, then strict grounded RAG ---
            if intent == "factual":
                table = answer_with_tables(db, notebook_id, payload.question, source_ids)
                if table:
                    display = _DISP.sub("", table["answer"]).strip()
                    for w in _word_chunks(display):
                        yield _sse({"type": "token", "delta": w})
                    table_out = TableResult(
                        source_title=table["source_title"], sql=table["sql"],
                        columns=table["columns"], rows=table["rows"], truncated=table["truncated"],
                    )
                    assistant = Message(
                        notebook_id=notebook_id, role="assistant", text=table["answer"],
                        table_json=table_out.model_dump_json(), thread_id=payload.thread_id,
                    )
                    db.add(assistant)
                    db.flush()
                    _persist_citations(db, assistant.id, table["citations"])
                    db.commit()
                    yield _sse({
                        "type": "done", "message_id": assistant.id,
                        "answer_markdown": table["answer"], "grounded": True,
                        "citations": table["citations"], "table_result": table_out.model_dump(),
                        "intent": "factual", "follow_ups": _suggest(table["answer"]),
                    })
                    return

            # factual (no table) or synthesis -> streamed RAG
            mode = "synthesis" if intent == "synthesis" else "factual"
            final = None
            for kind, data in stream_answer(db, source_ids, payload.question, mode):
                if kind == "token":
                    yield _sse({"type": "token", "delta": data})
                else:
                    final = data
            assistant = Message(
                notebook_id=notebook_id, role="assistant", text=final["answer"], thread_id=payload.thread_id,
            )
            db.add(assistant)
            db.flush()
            _persist_citations(db, assistant.id, final["citations"])
            db.commit()
            yield _sse({
                "type": "done", "message_id": assistant.id,
                "answer_markdown": final["answer"], "grounded": final["grounded"],
                "citations": final["citations"], "table_result": None, "intent": intent,
                "follow_ups": _suggest(final["answer"]),
            })
        except Exception:
            db.rollback()
            yield _sse({"type": "error", "detail": "Something went wrong answering that. Please try again."})
        finally:
            db.close()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/notebooks/{notebook_id}/threads", response_model=list[ThreadRead])
def list_threads(notebook_id: str, db: Session = Depends(get_db)):
    """Conversation threads in a notebook, derived from messages. Title is the first
    user question; ordered by most-recent activity."""
    nb = _get_notebook(db, notebook_id)
    groups: dict[str, list[Message]] = {}
    for m in nb.messages:
        groups.setdefault(m.thread_id or "default", []).append(m)
    threads: list[ThreadRead] = []
    for tid, msgs in groups.items():
        msgs.sort(key=lambda x: x.created_at)
        first_user = next((m for m in msgs if m.role == "user"), None)
        title = (first_user.text.strip()[:60] if first_user else "New thread") or "New thread"
        threads.append(
            ThreadRead(
                thread_id=tid,
                title=title,
                message_count=len(msgs),
                updated_at=msgs[-1].created_at,
            )
        )
    threads.sort(key=lambda t: t.updated_at, reverse=True)
    return threads


@router.get("/notebooks/{notebook_id}/messages", response_model=list[MessageRead])
def list_messages(notebook_id: str, thread_id: str | None = None, db: Session = Depends(get_db)):
    nb = _get_notebook(db, notebook_id)
    msgs = sorted(nb.messages, key=lambda x: x.created_at)
    if thread_id is not None:
        msgs = [m for m in msgs if (m.thread_id or "default") == thread_id]
    out: list[MessageRead] = []
    for m in msgs:
        cites = sorted(
            (_citation_out(c, db) for c in m.citations),
            key=lambda x: x.display_index,
        )
        table_result = (
            TableResult(**json.loads(m.table_json)) if m.table_json else None
        )
        out.append(
            MessageRead(
                id=m.id, role=m.role, text=m.text, created_at=m.created_at,
                citations=cites, table_result=table_result,
            )
        )
    return out
