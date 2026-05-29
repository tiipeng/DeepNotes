"""Pydantic request/response schemas (ULTRAPLAN §5).

Notebook + Source are implemented for Phase 1. Chat/Citation/Note schemas are added
alongside their endpoints in Phases 3/5 so the wire contract never drifts from the code.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class NotebookCreate(BaseModel):
    title: str


class NotebookUpdate(BaseModel):
    title: str | None = None
    snippet: str | None = None


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    notebook_id: str
    kind: str
    title: str
    authors: str | None = None
    venue: str | None = None
    year: int | None = None
    pages: int | None = None
    status: str
    error_msg: str | None = None
    checked: bool
    char_count: int
    created_at: datetime


class SourcePatch(BaseModel):
    checked: bool | None = None


class SourceContent(BaseModel):
    id: str
    title: str
    kind: str
    pages: int | None = None
    parsed_markdown: str
    sections: list[str] = []


class PassageRead(BaseModel):
    source_id: str
    title: str
    kind: str
    authors: str | None = None
    venue: str | None = None
    page: int | None = None
    section: str | None = None
    pre: str
    highlight: str
    post: str


class NotebookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    snippet: str
    cover_hue_a: int
    cover_hue_b: int
    cover_glyph: str
    source_count: int
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    question: str
    # If omitted, the backend uses all checked + ready sources in the notebook.
    source_ids: list[str] | None = None
    thread_id: str = "default"


class CitationOut(BaseModel):
    display_index: int
    source_id: str
    chunk_id: str | None = None
    # Denormalized source fields so the frontend renders chips + drawer with no extra calls.
    source_title: str
    source_authors: str | None = None
    source_venue: str | None = None
    source_kind: str
    page: int | None = None
    section: str | None = None
    char_offset_start: int
    char_offset_end: int
    snippet: str


class TableResult(BaseModel):
    source_title: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool = False


class ChatResponse(BaseModel):
    message_id: str
    answer_markdown: str
    grounded: bool
    citations: list[CitationOut]
    table_result: TableResult | None = None
    intent: str = "factual"
    follow_ups: list[str] = []


class ThreadRead(BaseModel):
    thread_id: str
    title: str
    message_count: int
    updated_at: datetime


class MessageRead(BaseModel):
    id: str
    role: str
    text: str
    created_at: datetime
    citations: list[CitationOut] = []
    table_result: TableResult | None = None


class NoteCreate(BaseModel):
    title: str
    body: str = ""
    tag: str | None = None
    source_id: str | None = None


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    notebook_id: str
    title: str
    body: str
    tag: str | None = None
    source_id: str | None = None
    created_at: datetime


class NotebookSummaryRead(BaseModel):
    summary: str
    suggested_questions: list[str] = []
    ready: bool  # whether the notebook has any ready sources to ground a summary


class SearchHit(BaseModel):
    notebook_id: str
    notebook_title: str
    kind: str  # "notebook" | source kind (pdf/xlsx/url/audio/…)
    label: str  # the matched title


class SettingsRead(BaseModel):
    chat_provider: str
    chat_model: str
    openrouter_base_url: str
    openai_compatible_base_url: str
    ollama_base_url: str
    # keys are never returned; only whether one is set
    has_openrouter_key: bool
    has_openai_compatible_key: bool
    has_gemini_key: bool
    embedding_provider: str  # pinned (governs the vector space) — informational
    active_chat: str
    providers: list[str] = ["gemini", "openrouter", "openai_compatible", "ollama"]


class SettingsUpdate(BaseModel):
    chat_provider: str | None = None
    chat_model: str | None = None
    openrouter_api_key: str | None = None
    openrouter_base_url: str | None = None
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: str | None = None
    ollama_base_url: str | None = None


class HealthRead(BaseModel):
    status: str
    provider: str
    llm_model: str
    embed_model: str
    provider_ready: bool
