# DeepNotes

A self-hosted, data-sovereign **"chat with your sources"** workspace — a NotebookLM-style
tool where the AI answers **only** from your uploaded documents, and **every claim links
back, clickably, to the exact passage it came from.**

The signature interaction: ask a question → get a grounded answer with inline `⟦n⟧`
citations → click one → a reading pane slides in with the cited sentence **highlighted and
scrolled into view**. If the answer isn't in your sources, it says so — it never falls back
on the model's own knowledge.

Built thin on open source: the custom code is UI, citation-offset glue, and wiring;
everything heavy (parsing, chunking, retrieval, citations) is delegated to libraries.

---

## What it does

- **Notebooks** — create many; each owns its own sources.
- **Sources** — upload PDF / TXT / DOCX / PPTX / XLSX (or add a URL); toggle which are
  in scope for chat. Originals are discarded after parsing — only parsed markdown +
  embeddings + metadata are kept.
- **Grounded chat** — retrieval over the selected sources → answer with inline `[n]`
  citations → strict "not found" when the sources don't cover it.
- **Click-to-source** — citations resolve to the **exact** passage (page + section
  accurate), highlighted in a reading drawer.
- **Spreadsheet reasoning** *(differentiator)* — XLSX is queried as real structured data
  via SQL, not flattened text.
- **Local/sovereign mode** *(differentiator)* — run fully on your own hardware via Ollama;
  no data leaves the server.

---

## Architecture

```
┌──────────────────────────────────────┐        ┌────────────────────────────────────────────┐
│ FRONTEND — Next.js 14 (App Router, TS) │  HTTP  │ BACKEND — Python + FastAPI                    │
│ Tailwind · DeepNotes design tokens     │ <────> │ (the OSS heavy-lifting lives here)            │
│                                         │  JSON  │                                              │
│  • Dashboard (notebook grid)            │        │  Docling      → parse PDF/DOCX/PPTX/XLSX/URL  │
│  • Notebook (Sources · Chat · Studio)   │        │  LlamaIndex   → CitationQueryEngine (RAG)     │
│  • Citation drawer (highlight + scroll) │        │  Chroma       → vector store                  │
└──────────────────────────────────────┘        │  SQLite       → notebooks/sources/chunks/…    │
   Deploy: Vercel or local                        │  DuckDB       → XLSX text-to-SQL reasoning     │
                                                   │  Provider abstraction → Gemini | Ollama       │
                                                   └────────────────────────────────────────────┘
                                                      Deploy: container (HF Spaces / Render / …)
                                                      NOTE: can't run on Vercel functions (250MB/10s)
```

### The citation pipeline (the heart of the product)

```
upload → Docling parse (markdown + aligned page/section index)
       → chunk (offsets preserved) → embed → Chroma (chunk.id == vector id) + SQLite metadata

ask    → retrieve top-k over CHECKED sources → CitationQueryEngine → answer with [n]
       → each [n] resolved to an exact span via locate_span:
            exact substring → whitespace-normalized → parent-chunk fallback (never nothing)
       → page + section resolved per-offset (chunk-size independent)

click  → /sources/{id}/passage slices parsed_markdown into pre/highlight/post
       → drawer highlights the cited sentence and scrolls it to center
```

---

## The 5 challenges → open-source solution

| Challenge | Solution | Custom code |
|---|---|---|
| **Citations / grounding** | LlamaIndex `CitationQueryEngine` + `locate_span` offset resolver | offset glue + drawer |
| **Document parsing** | Docling (PDF, DOCX, PPTX, XLSX, HTML, OCR → markdown w/ provenance) | none |
| **Chunking** | LlamaIndex `SentenceSplitter` (char offsets retained) | page/section span index |
| **Spreadsheet reasoning** | DuckDB + LLM text-to-SQL | routing + result UI |
| **Scope discipline** | thin vertical slices, one risk proven at a time | the build plan |

---

## Tech stack

**Frontend:** Next.js 14 · TypeScript · Tailwind · Geist / Newsreader / JetBrains Mono.
**Backend:** Python 3.12 · FastAPI · SQLAlchemy (SQLite) · Docling · LlamaIndex · Chroma · DuckDB.
**Models:** Gemini `gemini-2.5-flash` + `gemini-embedding-001` (default), behind a provider
abstraction so a local **Ollama** model swaps in via config.

---

## Setup

**Prerequisites:** Python 3.12, Node 18+ (pnpm), and a [Gemini API key](https://aistudio.google.com/apikey)
(free tier). [`uv`](https://github.com/astral-sh/uv) recommended for the Python env.

### Backend

```bash
cd backend
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env          # then put your GEMINI_API_KEY in .env
uvicorn app.main:app --reload --port 8000
```
Health check: `curl localhost:8000/health`

### Frontend

```bash
cd frontend
pnpm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
pnpm dev                       # http://localhost:3000
```

Open `http://localhost:3000`, create a notebook, add a couple of PDFs, and ask away.

> First backend run downloads Docling's layout models (one-time). On Apple Silicon the
> parser auto-selects CPU (MPS lacks float64); on a CUDA box it auto-selects the GPU.

---

## Differentiators

### 1. Spreadsheet reasoning
Upload an `.xlsx` and ask aggregation/filtering questions ("which region had the highest
revenue?", "total units of X"). Each sheet becomes a DuckDB table; the LLM generates a
**read-only** SQL query, it runs, and you get the computed answer plus the result table and
the SQL. Real `GROUP BY/SUM`, not flattened text — a concrete NotebookLM weakness.

### 2. Sovereignty / local mode
Run everything — parsing, embeddings, retrieval, LLM — on your own hardware via Ollama, so
no data leaves the server (GDPR / public-sector / air-gapped). Same grounded-citation
experience. See **[docs/LOCAL_MODE.md](docs/LOCAL_MODE.md)**.

---

## Limits (free-tier friendly)

- Max file size **10 MB**; max **10 sources** per notebook; ~**200 pages** total.
- Ingestion is serial with retry/backoff (respects free-tier rate limits).
- Originals discarded after parsing — only markdown + embeddings + metadata retained.

---

## How I'd scale this

The current build is deliberately simple (local SQLite + Chroma, synchronous ingest). The
architecture is shaped so the obvious next steps don't require rewrites:

- **Async ingestion** — move upload→parse→embed off the request path into a worker queue
  (Celery / Cloud Tasks); the `status: parsing→ready` field is already in the model.
- **Managed vector + metadata stores** — Chroma → pgvector / Qdrant / Pinecone; SQLite →
  Postgres. The provider-abstraction pattern generalizes to a vector-store abstraction.
- **Multi-tenancy** — add org/user scoping + auth + row-level security; retrieval already
  filters by source/notebook metadata.
- **Cost & privacy routing** — the provider abstraction already lets you route per
  tenant: premium cloud models for some, fully-local Ollama for sensitive data.
- **UX** — stream chat responses; cache embeddings; the per-citation resolution path is
  already instrumented (`deepnotes.citations` logger) for observability.

---

## Project structure

```
backend/
  app/
    main.py · config.py · db.py · models.py · schemas.py
    providers/   gemini · ollama · factory   (LLM/embedding abstraction)
    ingest/      parse (docling) · pipeline (chunk→embed→store)
    rag/         engine (CitationQueryEngine) · locate (offset resolver)
    spreadsheet/ store (xlsx→duckdb) · engine (text-to-SQL)
    stores/      chroma
    routers/     notebooks · sources · chat
  spike.py · make_test_pdf.py · make_test_xlsx.py   (Phase-0 spike + test data)
frontend/
  app/           (dashboard) · notebook/[id] · globals.css (design tokens)
  components/     TopBar · icons
  lib/            api client · types
docs/            ULTRAPLAN.md · LOCAL_MODE.md · BUILD_PROMPT.md · DESIGN_PROMPT.md · PLAN.md
```

---

## Status

Built and verified: grounded chat with click-to-exact-passage citations, ingestion with
preserved page/section metadata, spreadsheet reasoning, and local/sovereign mode. Deferred
(stretch): audio overview, notes, auto-summaries. See **[docs/ULTRAPLAN.md](docs/ULTRAPLAN.md)**
for the full plan and the phase-by-phase record.

The UI implements the **DeepNotes** design (warm-cream + forest editorial aesthetic);
design tokens are ported verbatim from the design handoff into the Tailwind theme.
