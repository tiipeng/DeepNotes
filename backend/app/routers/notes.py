from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Note, Notebook
from ..schemas import NoteCreate, NoteRead

router = APIRouter(tags=["notes"])


@router.get("/notebooks/{notebook_id}/notes", response_model=list[NoteRead])
def list_notes(notebook_id: str, db: Session = Depends(get_db)):
    nb = db.get(Notebook, notebook_id)
    if nb is None:
        raise HTTPException(404, "Notebook not found")
    return [
        NoteRead.model_validate(n)
        for n in sorted(nb.notes, key=lambda x: x.created_at, reverse=True)
    ]


@router.post("/notebooks/{notebook_id}/notes", response_model=NoteRead, status_code=201)
def create_note(notebook_id: str, payload: NoteCreate, db: Session = Depends(get_db)):
    if db.get(Notebook, notebook_id) is None:
        raise HTTPException(404, "Notebook not found")
    note = Note(
        notebook_id=notebook_id,
        title=payload.title.strip()[:200] or "Untitled note",
        body=payload.body,
        tag=payload.tag,
        source_id=payload.source_id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteRead.model_validate(note)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: str, db: Session = Depends(get_db)):
    n = db.get(Note, note_id)
    if n is None:
        raise HTTPException(404, "Note not found")
    db.delete(n)
    db.commit()
