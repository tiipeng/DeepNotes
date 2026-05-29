import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..models import Citation, Message, Notebook, Source
from ..rag.engine import _DISP_COMPLETE as _DISP
from ..rag.engine import answer_question, stream_answer
from ..schemas import ChatRequest, ChatResponse, CitationOut, MessageRead, TableResult
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


@router.post("/notebooks/{notebook_id}/chat", response_model=ChatResponse)
def chat(notebook_id: str, payload: ChatRequest, db: Session = Depends(get_db)):
    nb = _get_notebook(db, notebook_id)
    source_ids = _resolve_source_ids(nb, payload)

    # Spreadsheet reasoning first: if in-scope sources have XLSX tables and the
    # question is answerable via SQL, compute it. Otherwise fall back to grounded RAG.
    table = answer_with_tables(db, notebook_id, payload.question, source_ids)

    db.add(Message(notebook_id=notebook_id, role="user", text=payload.question, thread_id=payload.thread_id))

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
            message_id=assistant.id, answer_markdown=table["answer"],
            grounded=True, citations=[CitationOut(**c) for c in table["citations"]],
            table_result=table_out,
        )

    result = answer_question(db, source_ids, payload.question)
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

            # Spreadsheet path (computed up front, then streamed for a consistent feel).
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
                })
                return

            # Grounded RAG streaming path.
            final = None
            for kind, data in stream_answer(db, source_ids, payload.question):
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
                "citations": final["citations"], "table_result": None,
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
