from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Notebook
from ..schemas import NotebookCreate, NotebookRead, NotebookUpdate

router = APIRouter(prefix="/notebooks", tags=["notebooks"])

# Rotating cover palette (oklch hue pairs) matching the DeepNotes design covers.
_COVERS = [
    (152, 168), (32, 18), (210, 225), (18, 350), (270, 285), (48, 35),
]


def _to_read(nb: Notebook) -> NotebookRead:
    return NotebookRead(
        id=nb.id,
        title=nb.title,
        snippet=nb.snippet,
        cover_hue_a=nb.cover_hue_a,
        cover_hue_b=nb.cover_hue_b,
        cover_glyph=nb.cover_glyph,
        source_count=len(nb.sources),
        created_at=nb.created_at,
        updated_at=nb.updated_at,
    )


def _get_or_404(db: Session, notebook_id: str) -> Notebook:
    nb = db.get(Notebook, notebook_id)
    if nb is None:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return nb


@router.get("", response_model=list[NotebookRead])
def list_notebooks(db: Session = Depends(get_db)):
    rows = db.scalars(select(Notebook).order_by(Notebook.updated_at.desc())).all()
    return [_to_read(nb) for nb in rows]


@router.post("", response_model=NotebookRead, status_code=201)
def create_notebook(payload: NotebookCreate, db: Session = Depends(get_db)):
    title = payload.title.strip() or "Untitled notebook"
    hue_a, hue_b = _COVERS[db.query(Notebook).count() % len(_COVERS)]
    nb = Notebook(
        title=title,
        cover_hue_a=hue_a,
        cover_hue_b=hue_b,
        cover_glyph=title[0].upper(),
    )
    db.add(nb)
    db.commit()
    db.refresh(nb)
    return _to_read(nb)


@router.get("/{notebook_id}", response_model=NotebookRead)
def get_notebook(notebook_id: str, db: Session = Depends(get_db)):
    return _to_read(_get_or_404(db, notebook_id))


@router.patch("/{notebook_id}", response_model=NotebookRead)
def update_notebook(
    notebook_id: str, payload: NotebookUpdate, db: Session = Depends(get_db)
):
    nb = _get_or_404(db, notebook_id)
    if payload.title is not None:
        nb.title = payload.title.strip() or nb.title
    if payload.snippet is not None:
        nb.snippet = payload.snippet
    db.commit()
    db.refresh(nb)
    return _to_read(nb)


@router.delete("/{notebook_id}", status_code=204)
def delete_notebook(notebook_id: str, db: Session = Depends(get_db)):
    nb = _get_or_404(db, notebook_id)
    db.delete(nb)
    db.commit()
