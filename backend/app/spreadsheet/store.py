"""XLSX → DuckDB tables (the spreadsheet-reasoning differentiator).

Each sheet becomes a real DuckDB table queried with SQL — actual aggregation/
filtering over structured data, not flattened text. We also build a per-sheet
markdown rendering so the XLSX still participates in RAG / the reading pane.
"""

import json
import re

import duckdb
import pandas as pd
from sqlalchemy.orm import Session

from ..config import get_settings
from ..ingest.parse import ParsedDoc, Span
from ..models import Source, TableData

_MAX_RENDER_ROWS = 200  # cap markdown rendering for huge sheets


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_") or "sheet"


def _table_name(source_id: str, sheet: str) -> str:
    return f"t_{source_id}_{_slug(sheet)}"


def _df_to_markdown(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = "\n".join(
        "| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |"
        for row in df.head(_MAX_RENDER_ROWS).itertuples(index=False)
    )
    return f"{head}\n{sep}\n{body}"


def parse_xlsx(path: str) -> ParsedDoc:
    """Build a markdown + span index from an XLSX (one section per sheet) for RAG."""
    xls = pd.ExcelFile(path)
    parts: list[str] = []
    spans: list[Span] = []
    pos = 0
    for sheet in xls.sheet_names:
        df = xls.parse(sheet)
        if df.empty:
            continue
        piece = f"## {sheet}\n\n{_df_to_markdown(df)}\n\n"
        start = pos
        parts.append(piece)
        pos += len(piece)
        spans.append(Span(start, pos, None, sheet))
    return ParsedDoc(markdown="".join(parts), spans=spans, num_pages=0)


def ingest_tables(db: Session, source: Source, path: str) -> int:
    """Load each non-empty sheet into a DuckDB table; record TableData rows."""
    con = duckdb.connect(get_settings().tables_path)
    try:
        xls = pd.ExcelFile(path)
        n = 0
        for sheet in xls.sheet_names:
            df = xls.parse(sheet)
            if df.empty:
                continue
            df.columns = [str(c) for c in df.columns]
            tname = _table_name(source.id, sheet)
            con.execute(f'DROP TABLE IF EXISTS "{tname}"')
            con.register("df_tmp", df)
            con.execute(f'CREATE TABLE "{tname}" AS SELECT * FROM df_tmp')
            con.unregister("df_tmp")
            cols = [{"name": str(c), "type": str(df[c].dtype)} for c in df.columns]
            db.add(
                TableData(
                    source_id=source.id,
                    sheet_name=sheet,
                    columns_json=json.dumps(cols),
                    rows_ref=tname,
                )
            )
            n += 1
        db.commit()
        return n
    finally:
        con.close()


def drop_tables(source_id: str) -> None:
    """Drop a source's DuckDB tables (on source delete)."""
    import os

    path = get_settings().tables_path
    if not os.path.exists(path):
        return
    con = duckdb.connect(path)
    try:
        prefix = f"t_{source_id}_"
        names = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        for name in names:
            if name.startswith(prefix):
                con.execute(f'DROP TABLE IF EXISTS "{name}"')
    finally:
        con.close()


def notebook_table_schemas(db: Session, notebook_id: str) -> list[dict]:
    """Schemas for the checked+ready XLSX tables in a notebook (for the LLM prompt)."""
    rows = (
        db.query(TableData, Source)
        .join(Source, TableData.source_id == Source.id)
        .filter(
            Source.notebook_id == notebook_id,
            Source.checked.is_(True),
            Source.status == "ready",
        )
        .all()
    )
    if not rows:
        return []
    con = duckdb.connect(get_settings().tables_path, read_only=True)
    try:
        schemas = []
        for td, src in rows:
            info = con.execute(f'PRAGMA table_info("{td.rows_ref}")').fetchall()
            cols = [(r[1], r[2]) for r in info]  # (name, type)
            count = con.execute(f'SELECT count(*) FROM "{td.rows_ref}"').fetchone()[0]
            schemas.append(
                {
                    "table": td.rows_ref,
                    "source_title": src.title,
                    "sheet": td.sheet_name,
                    "columns": cols,
                    "rows": count,
                }
            )
        return schemas
    finally:
        con.close()


def _coerce(v):
    if v is None or isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def run_select(sql: str) -> tuple[list[str], list[list]]:
    con = duckdb.connect(get_settings().tables_path, read_only=True)
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [[_coerce(c) for c in r] for r in cur.fetchall()]
        return cols, rows
    finally:
        con.close()
