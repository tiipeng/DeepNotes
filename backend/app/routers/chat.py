from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Citation, Message, Notebook, Source
from ..rag.engine import answer_question
from ..schemas import ChatRequest, ChatResponse, CitationOut, MessageRead

router = APIRouter(tags=["chat"])


def _get_notebook(db: Session, notebook_id: str) -> Notebook:
    nb = db.get(Notebook, notebook_id)
    if nb is None:
        raise HTTPException(404, "Notebook not found")
    return nb


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

    if payload.source_ids is not None:
        source_ids = payload.source_ids
    else:
        source_ids = [s.id for s in nb.sources if s.checked and s.status == "ready"]

    result = answer_question(db, source_ids, payload.question)

    db.add(Message(notebook_id=notebook_id, role="user", text=payload.question))
    assistant = Message(notebook_id=notebook_id, role="assistant", text=result["answer"])
    db.add(assistant)
    db.flush()  # assign assistant.id before linking citations

    for c in result["citations"]:
        db.add(
            Citation(
                message_id=assistant.id,
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
    db.commit()

    return ChatResponse(
        message_id=assistant.id,
        answer_markdown=result["answer"],
        grounded=result["grounded"],
        citations=[CitationOut(**c) for c in result["citations"]],
    )


@router.get("/notebooks/{notebook_id}/messages", response_model=list[MessageRead])
def list_messages(notebook_id: str, db: Session = Depends(get_db)):
    nb = _get_notebook(db, notebook_id)
    out: list[MessageRead] = []
    for m in sorted(nb.messages, key=lambda x: x.created_at):
        cites = sorted(
            (_citation_out(c, db) for c in m.citations),
            key=lambda x: x.display_index,
        )
        out.append(
            MessageRead(
                id=m.id, role=m.role, text=m.text, created_at=m.created_at, citations=cites
            )
        )
    return out
