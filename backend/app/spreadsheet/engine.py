"""Text-to-SQL spreadsheet reasoning over DuckDB tables.

The LLM turns a question into a read-only DuckDB query against the notebook's
XLSX tables; we execute it and phrase a natural-language answer. It also returns an
`evidence_sql` that selects the `__rowid__` of the source rows behind the answer, so
the citation lands on the exact rows (e.g. the GROUP BY rows behind a SUM), not just
the sheet heading. Returns None when the question isn't answerable, so chat falls
back to RAG.
"""

import json
import re

from sqlalchemy.orm import Session

from ..models import Source
from ..providers import get_provider
from .store import notebook_table_schemas, run_select

_SQL_GUARD = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FENCE = re.compile(r"```(?:json|sql)?|```", re.IGNORECASE)
_ROWID = "__rowid__"

_SQL_PROMPT = """You translate a question into DuckDB SQL over the tables below.
Every table also has a "__rowid__" integer column = its source-row index (do not treat
it as data).

Tables:
{schema}

Return a JSON object with two fields:
- "sql": ONE read-only SELECT/WITH query that COMPUTES the answer. Do NOT select
  "__rowid__" here.
- "evidence_sql": a read-only SELECT against a SINGLE table returning "__rowid__" for
  ONLY the source rows that support the SPECIFIC answer (not the whole table). If the
  answer is one group/category, return just that group's rows — self-filter with a
  subquery since you don't know the winner yet. Return null if not applicable.
  Example — "which region has the highest revenue?":
    "evidence_sql": "SELECT \\"__rowid__\\" FROM \\"t\\" WHERE \\"Region\\" = (SELECT \\"Region\\" FROM \\"t\\" GROUP BY \\"Region\\" ORDER BY SUM(\\"Revenue\\") DESC LIMIT 1)"

Rules:
- Use ONLY these tables/columns. Double-quote all identifiers (e.g. "Revenue").
- SELECT/WITH only. No INSERT/UPDATE/DELETE/DDL.
- If the question asks for ANY number/value/aggregate computable from these columns — even
  as one PART of a larger or comparative question — compute that part. Only return
  {{"sql": null}} if the question is not about this tabular data at all.

Respond with ONLY a JSON object: {{"sql": "<query>", "evidence_sql": "<query or null>"}}.

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
        cols = ", ".join(f'"{n}" {t}' for n, t in s["columns"] if n != _ROWID)
        lines.append(
            f'Table "{s["table"]}" (from {s["source_title"]}, sheet "{s["sheet"]}", '
            f'{s["rows"]} rows): {cols}'
        )
    return "\n".join(lines)


def _extract_plan(raw: str) -> tuple[str | None, str | None]:
    """Return (sql, evidence_sql) from the model's JSON (or a bare SELECT fallback)."""
    text = _FENCE.sub("", raw).strip()
    try:
        obj = json.loads(text)
        sql = obj.get("sql")
        ev = obj.get("evidence_sql")
        sql = sql.strip() if isinstance(sql, str) and sql.strip() else None
        ev = ev.strip() if isinstance(ev, str) and ev.strip() else None
        return sql, ev
    except (ValueError, AttributeError):
        return (text if _SQL_GUARD.match(text) else None), None


def _sheet_span(source: Source, sheet: str) -> tuple[int, int]:
    """Char offsets of a sheet's section in the source's parsed markdown."""
    try:
        spans = json.loads(source.page_map or "[]")
    except (ValueError, TypeError):
        spans = []
    for row in spans:
        section = row[3] if len(row) > 3 else None
        if section == sheet:
            return int(row[0]), int(row[1])
    return 0, 0


def _row_spans(markdown: str, sheet_start: int, sheet_end: int) -> list[tuple[int, int]]:
    """Char span of each rendered data row in a sheet's markdown table, in row order
    (index == __rowid__). The first two table rows (header, separator) are skipped."""
    spans: list[tuple[int, int]] = []
    pos = sheet_start
    table_row = 0
    for line in markdown[sheet_start:sheet_end].splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("|"):
            if table_row >= 2:  # data rows follow header + separator
                spans.append((pos, pos + len(line.rstrip("\n"))))
            table_row += 1
        pos += len(line)
    return spans


def _evidence_rowids(evidence_sql: str | None) -> list[int] | None:
    if not evidence_sql or not _SQL_GUARD.match(evidence_sql):
        return None
    try:
        cols, rows = run_select(evidence_sql)
    except Exception:
        return None
    if _ROWID not in cols:
        return None
    i = cols.index(_ROWID)
    rowids = sorted({int(r[i]) for r in rows if r[i] is not None})
    return rowids[:500]


def _base_citation(src: Source, sheet: str, idx: int, start: int, end: int) -> dict:
    return {
        "display_index": idx,
        "source_id": src.id,
        "chunk_id": None,
        "source_title": src.title,
        "source_authors": src.authors,
        "source_venue": src.venue,
        "source_kind": src.kind,
        "page": None,
        "section": sheet,
        "char_offset_start": start,
        "char_offset_end": end,
        "snippet": src.parsed_markdown[start:end],
    }


def _row_citation(src: Source, sheet: str, rowids: list[int]) -> dict | None:
    """A citation spanning the contributing source rows in the sheet's markdown table."""
    s_start, s_end = _sheet_span(src, sheet)
    if s_end <= s_start:
        return None
    spans = _row_spans(src.parsed_markdown, s_start, s_end)
    hit = [spans[r] for r in rowids if 0 <= r < len(spans)]
    if not hit:
        return None
    start = min(h[0] for h in hit)
    end = max(h[1] for h in hit)
    return _base_citation(src, sheet, 1, start, end)


def _sheet_citation(src: Source, sheet: str, idx: int) -> dict:
    """Fallback: point at the sheet heading when row evidence isn't available."""
    start, end = _sheet_span(src, sheet)
    heading = f"## {sheet}"
    h_end = min(end, start + len(heading)) if end > start else start
    c = _base_citation(src, sheet, idx, start, h_end)
    c["snippet"] = c["snippet"] or heading
    return c


def _citations(db: Session, schemas: list[dict], sql: str, rowids: list[int] | None,
               evidence_sql: str | None) -> list[dict]:
    """Prefer row-level citations from the evidence query (single table); otherwise
    fall back to one sheet-level citation per table the answer SQL referenced."""
    if rowids:
        ev_tables = [s for s in schemas if s["table"] in (evidence_sql or "")]
        if len(ev_tables) == 1:
            src = db.get(Source, ev_tables[0]["source_id"])
            if src is not None:
                row_cite = _row_citation(src, ev_tables[0]["sheet"], rowids)
                if row_cite is not None:
                    return [row_cite]

    used = [s for s in schemas if s["table"] in sql] or schemas
    out: list[dict] = []
    for i, s in enumerate(used, start=1):
        src = db.get(Source, s["source_id"])
        if src is not None:
            out.append(_sheet_citation(src, s["sheet"], i))
    return out


def answer_with_tables(
    db: Session, notebook_id: str, question: str, source_ids: list[str] | None = None
) -> dict | None:
    schemas = notebook_table_schemas(db, notebook_id, source_ids)
    if not schemas:
        return None

    llm = get_provider().llm()
    raw = llm.complete(_SQL_PROMPT.format(schema=_schema_text(schemas), question=question)).text
    sql, evidence_sql = _extract_plan(raw)
    if not sql or not _SQL_GUARD.match(sql):  # read-only guard
        return None

    try:
        columns, rows = run_select(sql)
    except Exception:
        return None  # malformed query -> fall back to RAG

    rowids = _evidence_rowids(evidence_sql)

    preview = rows[:50]
    nl = llm.complete(
        _NL_PROMPT.format(
            question=question, sql=sql, columns=columns, rows=preview[:20]
        )
    ).text.strip()

    citations = _citations(db, schemas, sql, rowids, evidence_sql)
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
