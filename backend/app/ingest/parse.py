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
    title: str | None = None  # a better title discovered during parsing (e.g. article/video title)


@lru_cache(maxsize=2)
def _converter(ocr: bool = False) -> DocumentConverter:
    # Resolve compute device once: CUDA on GPU servers, CPU otherwise. MPS is
    # deliberately avoided on Apple Silicon — it lacks float64 and crashes Docling's
    # RT-DETR layout model. Do not switch this to MPS.
    device = AcceleratorDevice.CUDA if torch.cuda.is_available() else AcceleratorDevice.CPU
    opts = PdfPipelineOptions()
    opts.accelerator_options = AcceleratorOptions(device=device)
    opts.do_ocr = ocr  # OCR is slow; only enabled as a fallback for no-text-layer PDFs
    if ocr:
        # RapidOCR (onnxruntime) — portable across CPU/Linux/CUDA, no system tesseract.
        from docling.datamodel.pipeline_options import RapidOcrOptions

        opts.ocr_options = RapidOcrOptions()
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def _build(doc) -> ParsedDoc:
    """Docling document -> canonical markdown + aligned page/section spans."""
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


def _needs_ocr(parsed: ParsedDoc) -> bool:
    """True when a paged document came back with essentially no text layer
    (scanned / image-only PDF) — the signal to retry with OCR."""
    if not parsed.num_pages:  # URLs / non-paged content: never OCR
        return False
    return len(parsed.markdown.strip()) < 50 * parsed.num_pages


def parse_plain_text(text: str) -> ParsedDoc:
    return ParsedDoc(markdown=text, spans=[Span(0, len(text), None, None)], num_pages=0)


def parse_markdown_sections(markdown: str, num_pages: int = 0, title: str | None = None) -> ParsedDoc:
    """Build page/section spans from markdown headings — one span per section, so any
    char offset resolves to the heading it lives under. Shared by URL / YouTube / audio
    sources so their citations work exactly like PDF citations."""
    spans: list[Span] = []
    section: str | None = None
    seg_start = 0
    pos = 0
    for line in markdown.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("#"):
            if pos > seg_start:
                spans.append(Span(seg_start, pos, None, section))
            section = stripped.lstrip("#").strip() or section
            seg_start = pos
        pos += len(line)
    if pos > seg_start:
        spans.append(Span(seg_start, pos, None, section))
    if not spans:
        spans = [Span(0, len(markdown), None, None)]
    return ParsedDoc(markdown=markdown, spans=spans, num_pages=num_pages, title=title)


_YT_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be")


def is_youtube(url: str) -> bool:
    from urllib.parse import urlparse

    try:
        return (urlparse(url).hostname or "").lower() in _YT_HOSTS
    except Exception:
        return False


def _youtube_id(url: str) -> str | None:
    from urllib.parse import parse_qs, urlparse

    u = urlparse(url)
    host = (u.hostname or "").lower()
    if host in ("youtu.be", "www.youtu.be"):
        return u.path.lstrip("/").split("/")[0] or None
    if u.path.startswith(("/shorts/", "/embed/", "/v/")):
        return u.path.split("/")[2] if len(u.path.split("/")) > 2 else None
    return (parse_qs(u.query).get("v") or [None])[0]


def _youtube_title(url: str) -> str | None:
    import json
    import urllib.parse
    import urllib.request

    try:
        api = "https://www.youtube.com/oembed?url=" + urllib.parse.quote(url, safe="") + "&format=json"
        with urllib.request.urlopen(api, timeout=10) as r:
            return json.load(r).get("title")
    except Exception:
        return None


def _fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def parse_youtube(url: str) -> ParsedDoc:
    """Pull a YouTube transcript and ingest it as a normal source. Transcript is
    grouped into ~30s blocks each headed by its timestamp, so citations point into
    the transcript at a time offset."""
    from youtube_transcript_api import YouTubeTranscriptApi

    vid = _youtube_id(url)
    if not vid:
        raise ValueError("Not a valid YouTube URL.")
    try:
        fetched = YouTubeTranscriptApi().fetch(vid)
    except Exception:
        raise ValueError("No transcript available for this video (captions may be disabled).")

    segs = [
        (float(getattr(s, "start", 0.0)), str(getattr(s, "text", "")).strip())
        for s in fetched
    ]
    segs = [s for s in segs if s[1]]
    if not segs:
        raise ValueError("This video's transcript is empty.")

    title = _youtube_title(url) or f"YouTube video {vid}"
    parts = [f"## {title}\n\n"]
    block: list[str] = []
    block_start = segs[0][0]
    for start, text in segs:
        if start - block_start >= 30 and block:
            parts.append(f"## [{_fmt_ts(block_start)}]\n\n{' '.join(block)}\n\n")
            block = []
            block_start = start
        block.append(text)
    if block:
        parts.append(f"## [{_fmt_ts(block_start)}]\n\n{' '.join(block)}\n\n")

    return parse_markdown_sections("".join(parts), title=title)


@lru_cache(maxsize=1)
def _whisper_model():
    from faster_whisper import WhisperModel

    from ..config import get_settings

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute = "float16" if device == "cuda" else "int8"
    return WhisperModel(get_settings().whisper_model, device=device, compute_type=compute)


def parse_audio(path: str) -> ParsedDoc:
    """Transcribe an audio file with Whisper and ingest like any source. Transcript is
    grouped into ~30s blocks headed by their timestamp so citations point into the audio."""
    segments, _info = _whisper_model().transcribe(path, vad_filter=True)
    parts: list[str] = []
    block: list[str] = []
    block_start: float | None = None
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        if block_start is None:
            block_start = seg.start
        if seg.start - block_start >= 30 and block:
            parts.append(f"## [{_fmt_ts(block_start)}]\n\n{' '.join(block)}\n\n")
            block = []
            block_start = seg.start
        block.append(text)
    if block:
        parts.append(f"## [{_fmt_ts(block_start or 0)}]\n\n{' '.join(block)}\n\n")
    md = "".join(parts)
    if not md.strip():
        raise ValueError("No speech detected in the audio.")
    return parse_markdown_sections(md)


def parse_url(url: str) -> ParsedDoc:
    """Robust article extraction: main content only (nav/ads/boilerplate stripped),
    headings preserved as markdown sections for citation metadata."""
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError("Couldn't fetch the URL (unreachable or blocked).")
    md = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        favor_recall=True,
    )
    if not md or len(md.strip()) < 50:
        raise ValueError("No readable article content found at this URL.")
    title = None
    try:
        meta = trafilatura.extract_metadata(downloaded)
        title = (meta.title or None) if meta else None
    except Exception:
        title = None
    if title:
        md = f"## {title}\n\n{md}"
    return parse_markdown_sections(md, title=title)


def parse_document(source: str | Path) -> ParsedDoc:
    """Parse a file path or URL via Docling into markdown + page/section spans.

    Fast path is text-layer extraction (no OCR). If a paged document comes back with
    no usable text (scanned / image-only PDF), retry once with OCR enabled."""
    parsed = _build(_converter(ocr=False).convert(str(source)).document)
    if _needs_ocr(parsed):
        parsed = _build(_converter(ocr=True).convert(str(source)).document)
    return parsed


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
