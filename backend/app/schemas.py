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


class HealthRead(BaseModel):
    status: str
    provider: str
    llm_model: str
    embed_model: str
    provider_ready: bool
