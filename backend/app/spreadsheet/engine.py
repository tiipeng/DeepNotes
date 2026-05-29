"""Text-to-SQL spreadsheet reasoning over DuckDB tables.

The LLM turns a question into a read-only DuckDB query against the notebook's
XLSX tables; we execute it and phrase a natural-language answer. Returns None when
the question isn't answerable from the tables, so chat falls back to RAG.
"""

import json
import re

from sqlalchemy.orm import Session

from ..models import Source
from ..providers import get_provider
from .store import notebook_table_schemas, run_select

_SQL_GUARD = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FENCE = re.compile(r"```(?:json|sql)?|```", re.IGNORECASE)

_SQL_PROMPT = """You translate a question into ONE read-only DuckDB SQL query over the tables below.

Tables:
{schema}

Rules:
- Use ONLY these tables/columns. Double-quote all identifiers (e.g. "Revenue").
- SELECT/WITH only. No INSERT/UPDATE/DELETE/DDL.
- If the question CANNOT be answered from these tables, return null for sql.

Respond with ONLY a JSON object: {{"sql": "<query>"}} or {{"sql": null}}.

Question: {question}
JSON:"""

_NL_PROMPT = """Answer the question in one or two sentences using ONLY the query result.
State the concrete numbers. Do not invent anything.

Question: {question}
SQL: {sql}
Result columns: {columns}
Result rows: {rows}

Answer:"""


def _schema_text(schemas: list[dict]) -> str:
    lines = []
    for s in schemas:
        cols = ", ".join(f'"{n}" {t}' for n, t in s["columns"])
        lines.append(
            f'Table "{s["table"]}" (from {s["source_title"]}, sheet "{s["sheet"]}", '
            f'{s["rows"]} rows): {cols}'
        )
    return "\n".join(lines)


def _extract_sql(raw: str) -> str | None:
    text = _FENCE.sub("", raw).strip()
    try:
        obj = json.loads(text)
        sql = obj.get("sql")
        return sql.strip() if isinstance(sql, str) and sql.strip() else None
    except (ValueError, AttributeError):
        # Fallback: a bare SELECT/WITH the model returned without JSON.
        return text if _SQL_GUARD.match(text) else None


def _sheet_span(source: Source, sheet: str) -> tuple[int, int]:
    """Char offsets of a sheet's section in the source's parsed markdown (for the
    drawer). parse_xlsx stores one span per sheet as [start, end, page, sheet]."""
    try:
        spans = json.loads(source.page_map or "[]")
    except (ValueError, TypeError):
        spans = []
    for row in spans:
        section = row[3] if len(row) > 3 else None
        if section == sheet:
            return int(row[0]), int(row[1])
    return 0, 0


def _table_citations(db: Session, schemas: list[dict], sql: str) -> list[dict]:
    """One citation per table the SQL actually referenced, pointing at the
    originating source + sheet so the answer stays clickable/grounded."""
    used = [s for s in schemas if s["table"] in sql] or schemas
    out: list[dict] = []
    for i, s in enumerate(used, start=1):
        src = db.get(Source, s["source_id"])
        if src is None:
            continue
        start, end = _sheet_span(src, s["sheet"])
        # Highlight the sheet heading; the drawer renders the table rows around it.
        heading = f"## {s['sheet']}"
        h_end = min(end, start + len(heading)) if end > start else start
        out.append(
            {
                "display_index": i,
                "source_id": src.id,
                "chunk_id": None,
                "source_title": src.title,
                "source_authors": src.authors,
                "source_venue": src.venue,
                "source_kind": src.kind,
                "page": None,
                "section": s["sheet"],
                "char_offset_start": start,
                "char_offset_end": h_end,
                "snippet": src.parsed_markdown[start:h_end] or heading,
            }
        )
    return out


def answer_with_tables(
    db: Session, notebook_id: str, question: str, source_ids: list[str] | None = None
) -> dict | None:
    schemas = notebook_table_schemas(db, notebook_id, source_ids)
    if not schemas:
        return None

    llm = get_provider().llm()
    raw = llm.complete(_SQL_PROMPT.format(schema=_schema_text(schemas), question=question)).text
    sql = _extract_sql(raw)
    if not sql or not _SQL_GUARD.match(sql):  # read-only guard
        return None

    try:
        columns, rows = run_select(sql)
    except Exception:
        return None  # malformed query -> fall back to RAG

    preview = rows[:50]
    nl = llm.complete(
        _NL_PROMPT.format(
            question=question, sql=sql, columns=columns, rows=preview[:20]
        )
    ).text.strip()

    citations = _table_citations(db, schemas, sql)
    # Append clickable [n] markers so the spreadsheet answer is grounded like RAG.
    if citations:
        nl = f"{nl} " + "".join(f"[{c['display_index']}]" for c in citations)

    return {
        "answer": nl,
        "sql": sql,
        "columns": columns,
        "rows": preview,
        "truncated": len(rows) > len(preview),
        "source_title": schemas[0]["source_title"],
        "citations": citations,
    }
