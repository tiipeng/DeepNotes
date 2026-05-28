"""Resolve a cited passage to exact char offsets in the source markdown.

Phase 0 finding: CitationQueryEngine's citation sub-chunks don't carry reliable
per-chunk offsets, so we relocate the cited text by search. Fallback chain (locked in):
  1. exact substring match
  2. whitespace-normalized match, mapped back to original offsets
  3. the parent chunk's full span (never show nothing)
"""

import re

_WS = re.compile(r"\s+")


def _norm_map(s: str) -> tuple[str, list[int]]:
    """Collapse whitespace runs to single spaces; track each kept char's original index."""
    chars: list[str] = []
    idx: list[int] = []
    prev_space = False
    for i, ch in enumerate(s):
        if ch.isspace():
            if prev_space:
                continue
            chars.append(" ")
            idx.append(i)
            prev_space = True
        else:
            chars.append(ch)
            idx.append(i)
            prev_space = False
    return "".join(chars), idx


def locate_span(
    cited_text: str,
    markdown: str,
    parent_start: int,
    parent_end: int,
) -> tuple[int, int, str]:
    """Return (start, end, method) where method is the resolution path taken:
    'exact' | 'normalized' | 'parent_fallback' | 'empty'."""
    cited = cited_text.strip()
    if cited:
        # 1. exact substring
        i = markdown.find(cited)
        if i != -1:
            return i, i + len(cited), "exact"

        # 2. whitespace-normalized
        norm_md, idx_map = _norm_map(markdown)
        norm_cited = _WS.sub(" ", cited).strip()
        if norm_cited:
            p = norm_md.find(norm_cited)
            if p != -1:
                start = idx_map[p]
                end = idx_map[p + len(norm_cited) - 1] + 1
                return start, end, "normalized"

        # 3. fallback: parent chunk span
        return parent_start, parent_end, "parent_fallback"

    return parent_start, parent_end, "empty"
