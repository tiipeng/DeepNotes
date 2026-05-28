"""Text-to-SQL spreadsheet reasoning over DuckDB tables.

The LLM turns a question into a read-only DuckDB query against the notebook's
XLSX tables; we execute it and phrase a natural-language answer. Returns None when
the question isn't answerable from the tables, so chat falls back to RAG.
"""

import json
import re

from sqlalchemy.orm import Session

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


def answer_with_tables(db: Session, notebook_id: str, question: str) -> dict | None:
    schemas = notebook_table_schemas(db, notebook_id)
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

    return {
        "answer": nl,
        "sql": sql,
        "columns": columns,
        "rows": preview,
        "truncated": len(rows) > len(preview),
        "source_title": schemas[0]["source_title"],
    }
