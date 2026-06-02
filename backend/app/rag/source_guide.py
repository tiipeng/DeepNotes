"""Per-source guide: a short summary + 5 questions answerable from this source alone."""

import json
import re

from ..models import Source
from ..providers import get_chat_llm

_FENCE = re.compile(r"```(?:json)?|```", re.IGNORECASE)
_MAX_CHARS = 4000  # head + mid slice sent to the LLM

_PROMPT = """You are given an excerpt from a single source document.

Write a JSON object with exactly two keys:
1. "summary": 2-3 sentences describing what this source is about. Be specific to the content.
2. "questions": a list of exactly 5 questions a reader can answer using ONLY this source.
   Make them specific and substantive — about facts, figures, methods, findings, or key claims.
   Each question must be under 90 characters.

Respond with ONLY the JSON object (no markdown fences, no extra text):
{{"summary": "...", "questions": ["...", "...", "...", "...", "..."]}}

Source title: {title}
---
{content}
---
JSON:"""


def generate_source_guide(source: Source) -> tuple[str, list[str]]:
    md = (source.parsed_markdown or "").strip()
    if len(md) > _MAX_CHARS:
        half = _MAX_CHARS // 2
        mid = len(md) // 2
        md = md[:half] + "\n…\n" + md[mid : mid + half]

    raw = get_chat_llm().complete(_PROMPT.format(title=source.title, content=md)).text
    text = _FENCE.sub("", raw).strip()
    try:
        obj = json.loads(text)
        summary = str(obj.get("summary", "")).strip()
        questions = [str(q).strip() for q in obj.get("questions", []) if str(q).strip()]
    except (ValueError, AttributeError, TypeError):
        summary, questions = "", []
    return summary, questions[:5]
