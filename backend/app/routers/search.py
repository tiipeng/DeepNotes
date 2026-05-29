from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Notebook, Source
from ..schemas import SearchHit

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[SearchHit])
def search(q: str = "", db: Session = Depends(get_db)):
    """Lightweight global search over notebook titles + source titles."""
    term = q.strip().lower()
    if not term:
        return []
    hits: list[SearchHit] = []
    titles = {nb.id: nb.title for nb in db.query(Notebook).all()}
    for nb_id, title in titles.items():
        if term in (title or "").lower():
            hits.append(SearchHit(notebook_id=nb_id, notebook_title=title, kind="notebook", label=title))
    for s in db.query(Source).all():
        if term in (s.title or "").lower():
            hits.append(
                SearchHit(
                    notebook_id=s.notebook_id,
                    notebook_title=titles.get(s.notebook_id, ""),
                    kind=s.kind,
                    label=s.title,
                )
            )
    return hits[:25]
