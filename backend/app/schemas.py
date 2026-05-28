"""Pydantic request/response schemas (ULTRAPLAN §5).

Notebook + Source are implemented for Phase 1. Chat/Citation/Note schemas are added
alongside their endpoints in Phases 3/5 so the wire contract never drifts from the code.
"""

from datetime import datetime

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


class ChatResponse(BaseModel):
    message_id: str
    answer_markdown: str
    grounded: bool
    citations: list[CitationOut]


class MessageRead(BaseModel):
    id: str
    role: str
    text: str
    created_at: datetime
    citations: list[CitationOut] = []


class HealthRead(BaseModel):
    status: str
    provider: str
    llm_model: str
    embed_model: str
    provider_ready: bool
