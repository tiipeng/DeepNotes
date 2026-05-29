"""Intent classification + non-retrieval assistant replies.

The chat router classifies each message into one of four intents and routes it. Only
the 'factual' path uses strict grounded RAG (and may refuse with "not found");
'meta'/'conversational' are helpful replies grounded in what the sources contain but
never show the refusal; 'synthesis' summarizes broadly across the sources.
"""

import json
import re

from ..models import Source
from ..providers import get_provider

_FENCE = re.compile(r"```(?:json)?|```", re.IGNORECASE)

# Fast path: obvious greetings/thanks/identity — skip the classifier LLM call.
_GREETING = re.compile(
    r"^\s*(hi|hello|hey+|yo|sup|howdy|hiya|good\s+(morning|afternoon|evening)|"
    r"thanks?|thank\s+you|thx|ty|cheers|"
    r"who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do)\b[\s!.?]*$",
    re.IGNORECASE,
)

_INTENT_PROMPT = """Classify the user's message for a "chat with your documents" assistant
into exactly ONE label:
- factual: a specific question to answer from the documents (incl. data/number/table lookups).
- synthesis: asks to summarize, give an overview, or list the main points/key takeaways.
- meta: asks for help using the tool — example prompts, what they can ask, what's in here,
  "suggest questions".
- conversational: greeting, thanks, small talk, or who/what are you.

Reply with ONLY the label (one word).

Message: {q}
Label:"""


def _for_classify(q: str, budget: int = 1400) -> str:
    """A slice the classifier can judge intent from. The real question usually sits at
    the END of a long message (after pasted context / preamble), so keep both the head
    and the tail rather than a blind first-N-chars cut."""
    q = q.strip()
    if len(q) <= budget:
        return q
    head = budget // 3
    tail = budget - head
    return f"{q[:head]} […] {q[-tail:]}"


def classify_intent(question: str, has_sources: bool) -> str:
    q = question.strip()
    if not q:
        return "conversational"
    if _GREETING.match(q):
        return "conversational"
    try:
        raw = get_provider().llm().complete(_INTENT_PROMPT.format(q=_for_classify(q))).text
    except Exception:
        return "factual"  # safe default: strict grounded path
    label = raw.strip().lower().split()[0].strip(".:") if raw.strip() else "factual"
    if label not in {"factual", "synthesis", "meta", "conversational"}:
        return "factual"
    return label


def _titles(sources: list[Source]) -> str:
    ready = [s for s in sources if s.status == "ready"]
    return "\n".join(f"- {s.title} ({s.kind})" for s in ready) or "(no sources yet)"


def _excerpts(sources: list[Source], per: int = 700, limit: int = 6) -> str:
    ready = [s for s in sources if s.status == "ready"][:limit]
    return "\n\n".join(
        f"=== {s.title} ===\n{(s.parsed_markdown or '').strip()[:per]}" for s in ready
    ) or "(no sources yet)"


def conversational_prompt(question: str, sources: list[Source]) -> str:
    return (
        "You are DeepNotes, an assistant that answers strictly from a user's own uploaded "
        "sources, with clickable citations. Reply to the message below in 1-2 warm, brief "
        "sentences, then orient the user toward what they can do with THIS notebook. Do not "
        "invent source content; only reference the titles listed. No citations.\n\n"
        f"Sources in this notebook:\n{_titles(sources)}\n\n"
        f"Message: {question}\nReply:"
    )


def meta_prompt(question: str, sources: list[Source]) -> str:
    return (
        "You are DeepNotes, helping the user get the most out of their notebook. They are "
        "asking for guidance (e.g. example prompts / what they can ask), NOT a factual "
        "lookup. Using ONLY what the sources below actually contain, give a brief helpful "
        "reply: 1 short orienting sentence, then 3-4 concrete example prompts they could ask, "
        "as a bullet list. Keep prompts answerable from these sources. No citations, and "
        "never say you couldn't find an answer.\n\n"
        f"Sources:\n{_excerpts(sources)}\n\n"
        f"Request: {question}\nReply:"
    )


_FOLLOWUP_PROMPT = """Based ONLY on the sources below and the exchange that just happened,
suggest {n} natural follow-up questions the user could ask next that are clearly answerable
from these sources. Keep each under 90 characters. Do not repeat the question just asked.

Sources:
{excerpts}

Just asked: {question}
Answer given: {answer}

Respond with ONLY a JSON array of strings."""


def follow_up_questions(
    sources: list[Source], question: str, answer: str, n: int = 3
) -> list[str]:
    ready = [s for s in sources if s.status == "ready"]
    if not ready:
        return []
    prompt = _FOLLOWUP_PROMPT.format(
        n=n, excerpts=_excerpts(sources), question=question[:400], answer=answer[:800]
    )
    try:
        raw = get_provider().llm().complete(prompt).text
        text = _FENCE.sub("", raw).strip()
        items = json.loads(text)
        out = [str(x).strip() for x in items if str(x).strip()]
        return out[:n]
    except Exception:
        return []
