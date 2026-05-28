"""SQLAlchemy models — the durable data contract (ULTRAPLAN §4).

Chunk metadata (source_id, page/section, char offsets) is sacred: it is what makes
click-to-highlight citations possible. Never drop it during ingestion.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Notebook(Base):
    __tablename__ = "notebooks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, default="")
    cover_hue_a: Mapped[int] = mapped_column(Integer, default=152)
    cover_hue_b: Mapped[int] = mapped_column(Integer, default=168)
    cover_glyph: Mapped[str] = mapped_column(String(2), default="N")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    sources: Mapped[list["Source"]] = relationship(
        back_populates="notebook", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="notebook", cascade="all, delete-orphan"
    )
    notes: Mapped[list["Note"]] = relationship(
        back_populates="notebook", cascade="all, delete-orphan"
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    notebook_id: Mapped[str] = mapped_column(ForeignKey("notebooks.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String)  # pdf | txt | url | docx | pptx | xlsx
    title: Mapped[str] = mapped_column(String)
    authors: Mapped[str | None] = mapped_column(String, nullable=True)
    venue: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="parsing")  # parsing|ready|error
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked: Mapped[bool] = mapped_column(Boolean, default=True)  # included in chat
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    parsed_markdown: Mapped[str] = mapped_column(Text, default="")  # reading-pane content
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    notebook: Mapped["Notebook"] = relationship(back_populates="sources")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    notebook_id: Mapped[str] = mapped_column(ForeignKey("notebooks.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String, nullable=True)
    char_offset_start: Mapped[int] = mapped_column(Integer, default=0)
    char_offset_end: Mapped[int] = mapped_column(Integer, default=0)
    # Embedding vector itself lives in Chroma, keyed by this row's id.

    source: Mapped["Source"] = relationship(back_populates="chunks")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    notebook_id: Mapped[str] = mapped_column(ForeignKey("notebooks.id", ondelete="CASCADE"))
    thread_id: Mapped[str] = mapped_column(String, default="default")
    role: Mapped[str] = mapped_column(String)  # user | assistant
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    notebook: Mapped["Notebook"] = relationship(back_populates="messages")
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    chunk_id: Mapped[str | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
    display_index: Mapped[int] = mapped_column(Integer)  # the [n] shown in the answer
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String, nullable=True)
    char_offset_start: Mapped[int] = mapped_column(Integer, default=0)
    char_offset_end: Mapped[int] = mapped_column(Integer, default=0)
    snippet: Mapped[str] = mapped_column(Text, default="")

    message: Mapped["Message"] = relationship(back_populates="citations")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    notebook_id: Mapped[str] = mapped_column(ForeignKey("notebooks.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text, default="")
    tag: Mapped[str | None] = mapped_column(String, nullable=True)
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    notebook: Mapped["Notebook"] = relationship(back_populates="notes")


class TableData(Base):
    """XLSX differentiator — structured table rows for real spreadsheet reasoning."""

    __tablename__ = "table_data"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    sheet_name: Mapped[str] = mapped_column(String)
    columns_json: Mapped[str] = mapped_column(Text, default="[]")
    rows_ref: Mapped[str | None] = mapped_column(String, nullable=True)  # parquet/duckdb path
