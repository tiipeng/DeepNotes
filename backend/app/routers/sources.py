import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..ingest.parse import parse_document, parse_plain_text, resolve_at
from ..ingest.pipeline import ingest_source
from ..models import Chunk, Notebook, Source
from ..schemas import PassageRead, SourceContent, SourcePatch, SourceRead
from ..spreadsheet.store import drop_tables, ingest_tables, parse_xlsx
from ..stores.chroma import delete_source as chroma_delete_source

router = APIRouter(tags=["sources"])

# Free-tier limits (ULTRAPLAN §9)
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_SOURCES = 10
MAX_PAGES_TOTAL = 200
EXT_KIND = {
    ".pdf": "pdf", ".txt": "txt", ".md": "txt",
    ".docx": "docx", ".pptx": "pptx", ".xlsx": "xlsx", ".html": "url",
}


def _get_notebook(db: Session, notebook_id: str) -> Notebook:
    nb = db.get(Notebook, notebook_id)
    if nb is None:
        raise HTTPException(404, "Notebook not found")
    return nb


def _get_source(db: Session, source_id: str) -> Source:
    s = db.get(Source, source_id)
    if s is None:
        raise HTTPException(404, "Source not found")
    return s


@router.get("/notebooks/{notebook_id}/sources", response_model=list[SourceRead])
def list_sources(notebook_id: str, db: Session = Depends(get_db)):
    nb = _get_notebook(db, notebook_id)
    return [SourceRead.model_validate(s) for s in sorted(nb.sources, key=lambda x: x.created_at)]


@router.post("/notebooks/{notebook_id}/sources", response_model=SourceRead, status_code=201)
async def add_source(
    notebook_id: str,
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    nb = _get_notebook(db, notebook_id)
    if len(nb.sources) >= MAX_SOURCES:
        raise HTTPException(400, f"Notebook is at the {MAX_SOURCES}-source limit")
    if not file and not url:
        raise HTTPException(400, "Provide a file or a url")

    tmp_path: str | None = None
    plain_text: str | None = None

    if file:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in EXT_KIND:
            raise HTTPException(400, f"Unsupported file type {ext!r}")
        data = await file.read()
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(400, f"File exceeds {MAX_FILE_BYTES // (1024*1024)} MB limit")
        kind = EXT_KIND[ext]
        src_title = title or Path(file.filename).stem
        if kind == "txt":
            plain_text = data.decode("utf-8", errors="replace")
        else:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                f.write(data)
                tmp_path = f.name
    else:
        kind = "url"
        src_title = title or url

    source = Source(notebook_id=notebook_id, kind=kind, title=src_title, status="parsing")
    db.add(source)
    db.commit()
    db.refresh(source)

    try:
        if plain_text is not None:
            parsed = parse_plain_text(plain_text)
        elif kind == "xlsx":
            parsed = parse_xlsx(tmp_path)
        else:
            parsed = parse_document(tmp_path or url)

        existing_pages = sum(s.pages or 0 for s in nb.sources if s.id != source.id)
        if existing_pages + (parsed.num_pages or 0) > MAX_PAGES_TOTAL:
            raise HTTPException(400, f"Would exceed the {MAX_PAGES_TOTAL}-page total budget")

        ingest_source(db, source, parsed)
        if kind == "xlsx":
            ingest_tables(db, source, tmp_path)  # structured tables for SQL reasoning
    except HTTPException:
        source.status = "error"
        db.commit()
        raise
    except Exception as e:
        source.status = "error"
        source.error_msg = str(e)[:500]
        db.commit()
        # Readable message for the client; the raw cause is kept in error_msg.
        raise HTTPException(422, "Couldn't read this file — it may be corrupted, password-protected, or empty.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)  # discard original — keep only parsed markdown + vectors

    db.refresh(source)
    return SourceRead.model_validate(source)


@router.patch("/sources/{source_id}", response_model=SourceRead)
def patch_source(source_id: str, payload: SourcePatch, db: Session = Depends(get_db)):
    s = _get_source(db, source_id)
    if payload.checked is not None:
        s.checked = payload.checked
        db.commit()
        db.refresh(s)
    return SourceRead.model_validate(s)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: str, db: Session = Depends(get_db)):
    s = _get_source(db, source_id)
    chroma_delete_source(source_id)  # remove vectors
    drop_tables(source_id)  # remove DuckDB tables (if any)
    db.delete(s)
    db.commit()


_CTX = 700  # chars of context shown on each side of the highlight


@router.get("/sources/{source_id}/passage", response_model=PassageRead)
def source_passage(source_id: str, start: int, end: int, db: Session = Depends(get_db)):
    """Slice parsed_markdown into pre / highlight / post for the citation drawer."""
    s = _get_source(db, source_id)
    md = s.parsed_markdown
    start = max(0, min(start, len(md)))
    end = max(start, min(end, len(md)))

    pre = md[max(0, start - _CTX):start]
    if start - _CTX > 0:  # avoid starting mid-word
        sp = pre.find(" ")
        if sp != -1:
            pre = pre[sp + 1:]
    post = md[end:end + _CTX]

    # page + section from the highlight's exact offset (chunk fallback).
    chunk = (
        db.query(Chunk)
        .filter(Chunk.source_id == source_id, Chunk.char_offset_start <= start)
        .order_by(Chunk.char_offset_start.desc())
        .first()
    )
    page, section = resolve_at(s.page_map, start)
    if page is None:
        page = chunk.page if chunk else s.pages
    if section is None:
        section = chunk.section if chunk else None
    return PassageRead(
        source_id=s.id,
        title=s.title,
        kind=s.kind,
        authors=s.authors,
        venue=s.venue,
        page=page,
        section=section,
        pre=pre,
        highlight=md[start:end],
        post=post,
    )


@router.get("/sources/{source_id}/content", response_model=SourceContent)
def source_content(source_id: str, db: Session = Depends(get_db)):
    s = _get_source(db, source_id)
    seen: list[str] = []
    for c in sorted(s.chunks, key=lambda x: x.order_index):
        if c.section and c.section not in seen:
            seen.append(c.section)
    return SourceContent(
        id=s.id, title=s.title, kind=s.kind, pages=s.pages,
        parsed_markdown=s.parsed_markdown, sections=seen,
    )
