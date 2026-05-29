"""Notebook overview + suggested starter questions, grounded in the sources.

A small one-shot LLM call over short excerpts of each ready source. Cached by the
caller; this module only does the generation + a fingerprint of the source set.
"""

import hashlib
import json
import re

from ..models import Source
from ..providers import get_chat_llm

_FENCE = re.compile(r"```(?:json)?|```", re.IGNORECASE)
_MAX_SOURCES = 8
_HEAD_CHARS = 900
_MID_CHARS = 700

_PROMPT = """You are given excerpts from the sources in a research notebook.

Write:
1. "summary": 2-3 sentences describing what these sources collectively cover. Be concrete
   and specific to THIS material; do not speculate beyond the excerpts.
2. "questions": exactly 3 starter questions a reader would actually find useful. They must
   probe the SUBSTANCE — findings, methods, results, numbers, comparisons, trade-offs —
   and be clearly answerable from these sources. Do NOT ask about bibliographic metadata
   (title, authors, venue). Each under 90 characters.

Use ONLY the material below. Respond with ONLY a JSON object:
{{"summary": "...", "questions": ["...", "...", "..."]}}

Sources:
{context}

JSON:"""


def _excerpt(md: str) -> str:
    """Head of the document plus a slice from the middle, so questions can probe
    more than the title page."""
    md = (md or "").strip()
    head = md[:_HEAD_CHARS]
    if len(md) > _HEAD_CHARS + _MID_CHARS:
        mid_start = len(md) // 2
        return f"{head}\n…\n{md[mid_start : mid_start + _MID_CHARS]}"
    return head


def fingerprint(sources: list[Source]) -> str:
    parts = sorted(f"{s.id}:{s.char_count}:{s.status}" for s in sources)
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def generate_summary(sources: list[Source]) -> tuple[str, list[str]]:
    excerpts = []
    for s in sources[:_MAX_SOURCES]:
        excerpts.append(f"=== {s.title} ({s.kind}) ===\n{_excerpt(s.parsed_markdown)}")
    context = "\n\n".join(excerpts)

    raw = get_chat_llm().complete(_PROMPT.format(context=context)).text
    text = _FENCE.sub("", raw).strip()
    try:
        obj = json.loads(text)
        summary = str(obj.get("summary", "")).strip()
        questions = [str(q).strip() for q in obj.get("questions", []) if str(q).strip()]
    except (ValueError, AttributeError, TypeError):
        summary, questions = "", []
    return summary, questions[:3]
