"""Docling parsing → canonical markdown + an aligned page/section index.

We build the markdown ourselves from Docling's document items (in reading order)
instead of using export_to_markdown(), so that every character offset maps cleanly
to a page number and section heading. Chunk offsets index into this same markdown,
which is also what the citation reading-pane renders — one consistent coordinate system.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import torch
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

try:  # import location varies across docling versions
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
except ImportError:  # pragma: no cover
    from docling.datamodel.pipeline_options import AcceleratorDevice, AcceleratorOptions

_HEADING_LABELS = {"section_header", "title"}


@dataclass
class Span:
    start: int
    end: int
    page: int | None
    section: str | None


@dataclass
class ParsedDoc:
    markdown: str
    spans: list[Span]
    num_pages: int


@lru_cache(maxsize=1)
def _converter() -> DocumentConverter:
    # Resolve compute device once: CUDA on GPU servers, CPU otherwise. MPS is
    # deliberately avoided on Apple Silicon — it lacks float64 and crashes Docling's
    # RT-DETR layout model. Do not switch this to MPS.
    device = AcceleratorDevice.CUDA if torch.cuda.is_available() else AcceleratorDevice.CPU
    opts = PdfPipelineOptions()
    opts.accelerator_options = AcceleratorOptions(device=device)
    opts.do_ocr = False  # text-layer docs: skip OCR (faster, no model downloads)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def parse_plain_text(text: str) -> ParsedDoc:
    return ParsedDoc(markdown=text, spans=[Span(0, len(text), None, None)], num_pages=0)


def parse_document(source: str | Path) -> ParsedDoc:
    """Parse a file path or URL via Docling into markdown + page/section spans."""
    doc = _converter().convert(str(source)).document

    parts: list[str] = []
    spans: list[Span] = []
    pos = 0
    section: str | None = None

    for item, _level in doc.iterate_items():
        text = (getattr(item, "text", None) or "").strip()
        if not text:
            # Tables/figures have no .text; include table markdown best-effort.
            export = getattr(item, "export_to_markdown", None)
            if export is not None:
                try:
                    text = export(doc).strip()
                except Exception:
                    text = ""
            if not text:
                continue

        label = getattr(getattr(item, "label", None), "value", "")
        prov = getattr(item, "prov", None)
        page = prov[0].page_no if prov else None

        if label in _HEADING_LABELS:
            section = text
            piece = f"## {text}\n\n"
        else:
            piece = f"{text}\n\n"

        start = pos
        parts.append(piece)
        pos += len(piece)
        spans.append(Span(start, pos, page, section))

    markdown = "".join(parts)
    pages = getattr(doc, "pages", None)
    num_pages = len(pages) if pages else max((s.page or 0 for s in spans), default=0)
    return ParsedDoc(markdown=markdown, spans=spans, num_pages=num_pages)


def span_at(offset: int, spans: list[Span]) -> Span | None:
    """The page/section span containing a character offset."""
    for s in spans:
        if s.start <= offset < s.end:
            return s
    return spans[-1] if spans else None


def resolve_at(page_map_json: str, offset: int) -> tuple[int | None, str | None]:
    """Resolve (page, section) for an arbitrary char offset from a stored page_map
    JSON ([[start, end, page, section], ...]). Used at citation time so page AND
    section reflect the cited sentence's exact offset, not the parent chunk's start.
    Tolerates the older 3-tuple format (section omitted)."""
    import json

    try:
        spans = json.loads(page_map_json or "[]")
    except (ValueError, TypeError):
        return None, None
    nearest: tuple[int | None, str | None] = (None, None)
    for row in spans:
        start, end, page = row[0], row[1], row[2]
        section = row[3] if len(row) > 3 else None
        if start <= offset < end:
            return page, section
        if start <= offset:
            nearest = (page, section)
    return nearest
