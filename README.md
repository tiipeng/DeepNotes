# DeepNotes

A self-hosted, source-grounded research notebook — a NotebookLM-style tool that chats **only**
with the documents you give it. Every answer is grounded in your own uploaded sources, and every
claim links back to the **exact passage** it came from: click a citation and a reading pane opens
the source with the cited sentence highlighted. If the answer isn't in your sources, DeepNotes
says so instead of guessing. Originals are discarded after parsing, the whole stack runs on your
own hardware, and the model provider is swappable (hosted Gemini by default, or a fully-local
Ollama path), so your documents never have to leave a machine you control.

---

## 1. Features

**Notebooks & sources**
- Create many notebooks; each owns its own set of sources, scoped independently.
- Toggle which sources are "in chat" — unchecking a source removes it from **both** the
  retrieval and the spreadsheet-query paths.
- Supported source types (all flow through the same parse → chunk → embed → cite pipeline):

  | Type | How it's ingested |
  |---|---|
  | **PDF** (text or **scanned/image-only**) | Docling; OCR fallback (RapidOCR) only when a page has no text layer |
  | **DOCX, PPTX** | Docling |
  | **TXT, Markdown** | read directly |
  | **XLSX** | each sheet → a queryable table (see *Spreadsheet reasoning*) + a markdown rendering for retrieval |
  | **Web page** (by URL) | main-article extraction via trafilatura (nav/ads stripped, headings kept) |
  | **YouTube** (by URL) | transcript pulled and grouped into timestamped blocks |
  | **Audio** (`.mp3 / .wav / .m4a`) | transcribed locally with Whisper (faster-whisper) |

- Limits (per notebook): **10 MB** per file (**50 MB** for audio), **10 sources**, **~200 pages** total.

**Grounded chat with verifiable citations**
- Answers are generated strictly from the in-scope sources. When retrieval finds nothing
  relevant, a factual question returns *"I couldn't find an answer to that in your sources."* —
  it does not fall back on the model's own knowledge.
- Citations are clickable. The drawer opens the source with the cited span highlighted and
  scrolled into view, plus the surrounding context:
  - **Documents (PDF/DOCX/PPTX/web):** resolved to a page and/or section heading.
  - **YouTube / audio:** resolved to a timestamp (`[mm:ss]`).
  - **Spreadsheets:** resolved to the **exact source rows** behind a computed figure.

**Spreadsheet reasoning (differentiator)**
- XLSX sheets become real tables in DuckDB. A factual question is turned into a read-only SQL
  query (text-to-SQL), executed, and phrased back in natural language with the result table and
  the SQL shown.
- Citations are **row-level**: a second "evidence" query identifies the source rows behind the
  number, and the citation opens the drawer on exactly those rows (e.g. the 12 rows a regional
  `SUM` aggregates over).
- The SQL engine is sandboxed (see *Design decisions*), so it cannot read host files.

**Intent routing**
Each message is classified (a cheap LLM call, with a greeting fast-path) and routed:
- **factual** — strict grounded retrieval; spreadsheet reasoning runs first when the notebook has
  tables; for mixed notebooks a table figure and document prose are merged into one cited answer.
  This is the only path that can return the "not found" refusal.
- **synthesis** ("summarize", "overview", "main points") — broad retrieval across the sources;
  never refuses.
- **meta** ("what can I ask", "give me an example prompt") — suggests prompts grounded in what the
  sources actually contain.
- **conversational** ("hello", "thanks") — a brief, friendly reply; no retrieval, no refusal.

**Experience**
- **Streaming** answers (token-by-token over SSE); citation chips and follow-up suggestions attach
  once the answer completes.
- **Persistent overview** — a grounded summary of the notebook, always visible at the top of the
  chat (cached; regenerated when the source set changes).
- **Suggested questions** — grounded starter questions up front, and 2–3 contextual follow-ups
  after each answer.
- **Notes** — save an answer or a cited passage into the notebook.
- **Threads** — multiple conversations per notebook, isolated and switchable.
- **Answers follow the question's language** (e.g. a German question gets a German answer);
  citations and source content are unchanged.
- **Bring your own chat model** — choose the model that generates answers (Google Gemini,
  OpenRouter's 200+ models, any OpenAI-compatible endpoint, or local Ollama) and paste your
  own key in Settings. Embeddings stay pinned to one model, so switching the chat model never
  invalidates your vector store or citations.

---

## 2. How to use it

1. **Create a notebook** from the dashboard.
2. **Add sources** — upload a file (PDF, DOCX, PPTX, TXT, XLSX, audio) or paste a web/YouTube URL.
   Each source shows a "processing…" state while it parses in the background, then flips to ready.
3. **Read the overview** that appears at the top, and click a suggested starter question — or type
   your own.
4. **Ask questions.** The answer streams in with inline `⟦n⟧` citations.
5. **Click a citation** to open the source drawer with the exact passage highlighted (page/section
   for documents, timestamp for audio/video, the source rows for spreadsheets).
6. **Save notes**, follow up with the suggested questions, or **start a new thread** for a separate
   line of inquiry. Uncheck a source to exclude it from answers.

---

## 3. Running it locally

### Prerequisites
- **Python 3.12**, **Node 18+** with **pnpm**
- A **Gemini API key** (free tier) — <https://aistudio.google.com/apikey>.
  ([`uv`](https://github.com/astral-sh/uv) recommended for the Python env.)
- No system packages required: OCR (RapidOCR/onnxruntime), audio decoding (PyAV), and Whisper
  (CTranslate2) are pip-installed; models download on first use.

### Backend (FastAPI, port 8000)
```bash
cd backend
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt          # or: pip install -r requirements.txt
cp .env.example .env                         # then put your GEMINI_API_KEY in .env
uvicorn app.main:app --reload --port 8000
```
Health check: `curl localhost:8000/health`

**Environment variables** (`backend/.env` — see `.env.example`, no real values committed):

| Key | Purpose | Default |
|---|---|---|
| `LLM_PROVIDER` | `gemini` (hosted) or `ollama` (local) | `gemini` |
| `GEMINI_API_KEY` | **required** when provider is gemini | — |
| `GEMINI_LLM_MODEL` / `GEMINI_EMBED_MODEL` | model names | `gemini-2.5-flash` / `gemini-embedding-001` |
| `OLLAMA_BASE_URL` / `OLLAMA_LLM_MODEL` / `OLLAMA_EMBED_MODEL` | used only when provider is ollama | `http://localhost:11434` / `llama3.1` / `nomic-embed-text` |
| `CHAT_PROVIDER` / `CHAT_MODEL` | chat (generation) model — `gemini` / `openrouter` / `openai_compatible` / `ollama` (also settable in-app via Settings) | `gemini` / *(provider default)* |
| `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL` | for `CHAT_PROVIDER=openrouter` | — / `https://openrouter.ai/api/v1` |
| `OPENAI_COMPATIBLE_BASE_URL` / `OPENAI_COMPATIBLE_API_KEY` | for `CHAT_PROVIDER=openai_compatible` (OpenAI, vLLM, your own endpoint) | — |
| `DATABASE_URL` | SQLite metadata DB | `sqlite:///./deepnotes.db` |
| `CHROMA_DIR` | Chroma vector store dir | `./chroma` |
| `TABLES_PATH` | DuckDB file for XLSX tables | `./tables.duckdb` |
| `CORS_ORIGINS` | comma-separated allowed origins | `http://localhost:3000` |

### Frontend (Next.js, port 3000)
```bash
cd frontend
pnpm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
pnpm dev                                      # http://localhost:3000
```

### First-run notes
- The **first PDF parse** downloads Docling's layout models (one-time).
- The **first scanned PDF** downloads RapidOCR models; the **first audio file** downloads the
  Whisper model (`base`, ~140 MB).
- On Apple Silicon the parser runs on CPU (MPS is deliberately avoided — it lacks the float64 the
  layout model needs); on a CUDA box it uses the GPU automatically.

---

## 4. Architecture

```
┌─────────────────────────────┐         ┌──────────────────────────────────────────────┐
│ FRONTEND — Next.js 14 (TS)   │  HTTP   │ BACKEND — Python · FastAPI                     │
│ App Router · Tailwind        │ <─────> │                                                │
│  • Dashboard (notebooks)     │  JSON   │  Ingestion (background threadpool)             │
│  • Notebook: Sources/Chat/   │  + SSE  │    Docling · RapidOCR · trafilatura ·          │
│    Studio                    │ stream  │    youtube-transcript-api · faster-whisper     │
│  • Citation drawer           │         │  RAG: LlamaIndex CitationQueryEngine           │
└─────────────────────────────┘         │  Spreadsheet: DuckDB text-to-SQL (sandboxed)   │
   Deploy: Vercel or any host            │  Provider: Gemini (default) | Ollama           │
                                         │                                                │
                                         │   SQLite (metadata)   Chroma (vectors)         │
                                         │   DuckDB (XLSX tables)                          │
                                         └──────────────────────────────────────────────┘
                                            Deploy: a container (cannot run on serverless
                                            functions — Docling/torch/Whisper are too heavy)
```

### Why two services
The frontend is a thin Next.js app. The backend is a separate FastAPI service because the
heavy lifting — Docling parsing (with a torch layout model), OCR, Whisper transcription,
embeddings, and the vector store — exceeds typical serverless function limits (size and
execution time). Keeping it a standalone container also makes the data-sovereignty story real:
the whole pipeline can run on hardware you control.

### Ingestion pipeline
```
source → parse → chunk → embed → store
```
- **parse** — dispatched by type: Docling for PDF/DOCX/PPTX (OCR fallback only when a paged doc
  comes back with essentially no text), trafilatura for web, youtube-transcript-api for YouTube,
  faster-whisper for audio, pandas/openpyxl for XLSX. Every parser emits **one canonical markdown
  document plus an aligned span index** (`[start, end, page, section]`), so a character offset
  always resolves to a page/section (or a timestamp/sheet for AV/spreadsheets). This shared
  coordinate system is what makes citations work *identically* across every source type.
- **chunk** — LlamaIndex `SentenceSplitter` (512 tokens, 64 overlap); each chunk keeps its char
  offsets + page/section.
- **embed & store** — vectors go to Chroma (chunk id == vector id); chunk metadata goes to SQLite.
- Ingestion runs on a **background worker** (FastAPI `BackgroundTasks` → threadpool), so a long
  parse/transcription never blocks the API event loop; the source row moves `parsing → ready`
  (or `error` with a reason) and the UI polls for it.

### Citation mechanism
Retrieval and answering use LlamaIndex's `CitationQueryEngine`, which cites at ~sentence
granularity (48-token citation units). Because those sub-chunks don't carry reliable per-chunk
offsets, each cited snippet is **relocated** against the source markdown via a fixed fallback
chain (`rag/locate.py`):

1. exact substring match →
2. whitespace-normalized match (mapped back to original offsets) →
3. the parent chunk's span (so the drawer never shows nothing).

The page and section are then resolved from the **cited offset itself** (not the parent chunk's
start), so they're accurate regardless of chunk size. The drawer slices the markdown into
pre / highlight / post (~700 chars of context each side). Source-internal reference markers (a
document's own `[12]`/`[4, 9]`) are stripped so only real DeepNotes citations render as chips.

For **spreadsheets**, citations don't use that text chain: a `__rowid__` column plus an LLM
"evidence" query map a computed figure back to the exact source rows, and the drawer highlights
those rows.

### Storage — what's kept, what's discarded
- **SQLite** — durable metadata: notebooks, sources, chunks (with offsets/page/section),
  messages, citations, notes, cached notebook summaries, and table_data (XLSX sheet → DuckDB
  table mapping).
- **Chroma** — the embedding vectors.
- **DuckDB** — the actual XLSX table data for SQL reasoning.
- **Original uploaded files are discarded after parsing** — only the parsed markdown, embeddings,
  and metadata are retained. SQLite/Chroma split keeps relational metadata queryable while
  delegating vector search to a purpose-built store.

### Provider abstraction
A small provider interface returns LlamaIndex-compatible LLM + embedding objects, so the RAG and
spreadsheet layers are identical regardless of backend. `LLM_PROVIDER=gemini` (default) uses
hosted Gemini; `LLM_PROVIDER=ollama` routes everything — generation **and** embeddings — to a
local Ollama daemon for fully-local operation (requires Ollama running with the configured models
pulled). The **chat (generation) model is selected independently** of embeddings via
`CHAT_PROVIDER`/`CHAT_MODEL` (or the in-app Settings panel) — Gemini, OpenRouter, any
OpenAI-compatible endpoint, or Ollama, with the user's own key. Embeddings stay pinned to
`LLM_PROVIDER` on purpose: the vector store is a single fixed-dimension collection, so swapping
the *embedding* model would invalidate every stored vector — only the chat model is hot-swappable.

### Key tables (high level)
`notebooks` · `sources` · `chunks` · `messages` · `citations` · `notes` · `notebook_summaries`
· `table_data`.

---

## 5. Tech stack

- **Frontend:** TypeScript, Next.js 14 (App Router), Tailwind CSS.
- **Backend:** Python 3.12, FastAPI, SQLAlchemy.
- **Parsing / ingestion:** Docling (PDF/DOCX/PPTX), RapidOCR (onnxruntime) for scanned PDFs,
  trafilatura (web), youtube-transcript-api, faster-whisper (CTranslate2) for audio,
  pandas/openpyxl (XLSX).
- **RAG / retrieval:** LlamaIndex (`CitationQueryEngine`, `SentenceSplitter`), Chroma vector store.
- **Spreadsheet reasoning:** DuckDB (text-to-SQL).
- **Models:** Gemini `gemini-2.5-flash` + `gemini-embedding-001` (default), behind a provider
  abstraction that also supports local Ollama.

---

## 6. Design decisions & trade-offs

- **OSS-first.** Parsing, chunking, retrieval, and citation are delegated to mature libraries
  (Docling, LlamaIndex, Chroma, DuckDB); the custom code is the citation-offset glue, the
  per-type extractors, the intent router, and the UI — not a reinvented RAG stack.
- **One coordinate system for citations.** Building a single markdown + span index per source
  (rather than per-type special cases) is what lets click-to-highlight work the same for a PDF, a
  web page, a YouTube transcript, and a spreadsheet.
- **Per-offset page/section resolution.** Page and section come from the cited sentence's offset,
  not the parent chunk — so citations stay accurate even with large chunks.
- **DuckDB sandbox for text-to-SQL.** The LLM-generated query runs on a connection opened with
  `enable_external_access=false` + `lock_configuration=true`, so file-reading SQL functions
  (`read_text`, `read_csv`, `glob`, `ATTACH`) are blocked and the setting can't be re-enabled
  mid-query. The `SELECT`/`WITH` prefix check is only a coarse first filter; the sandbox is the
  real guard.
- **Local-default storage.** SQLite + Chroma + DuckDB on local files keep the dev/self-host path
  trivial; the storage layer is intentionally swappable later.
- **Strict grounding.** The "not found" refusal is reserved exclusively for the factual path;
  conversational/meta/synthesis never show it, so the product feels like an assistant without
  weakening the grounding guarantee.

---

## 7. Limitations & known issues

This is a working prototype, not a hardened product. Honestly:

- **Single-user, no auth.** There is no authentication, no user accounts, and no multi-tenancy —
  every notebook is visible to anyone who can reach the API. Do not expose it publicly as-is.
- **Not hardened for scale.** SQLite + local Chroma + a single DuckDB file are fine for one user;
  concurrent ingestion of two XLSX files can contend on the DuckDB write lock, and there is no
  job queue beyond in-process background tasks.
- **No automated tests / CI yet.**
- **Free-tier model limits.** With hosted Gemini, heavy use can hit rate limits; ingestion has
  retry/backoff on embeddings but chat does not.
- **Synthesis answers can over-cite.** "Summarize" / broad questions may attach many citation
  chips (sparse-citation tuning is applied to the factual path, not yet to synthesis).
- **Cross-source merge is heuristic.** Mixed table+prose questions work by computing the table
  part and merging it with retrieved prose; very complex multi-table comparisons may not fully
  combine.
- **Web-page *file* uploads aren't wired** — add web pages by **URL** (an uploaded `.html` file is
  not supported).
- **Historical messages aren't retro-cleaned** — the source-internal reference stripping applies
  to new answers; messages generated before it remain as stored.
- **"Audio Overview" (podcast) is a placeholder** ("Soon") in the Studio panel — not implemented.
- The local **Ollama** path is implemented via the provider abstraction but is exercised far less
  than the default Gemini path.

---

## 8. Roadmap

The path from prototype to product:

- **Auth & multi-tenancy** — user accounts and per-notebook ownership.
- **Hosted deployment** — containerized backend + managed stores (e.g. Postgres + pgvector), a
  real ingestion queue, and observability.
- **Audio Overview** — the deferred two-host "podcast" generation.
- **Full local mode** — harden and validate the Ollama provider for fully air-gapped use.
- **Tests & CI** — coverage for the citation/offset logic and the SQL sandbox, run in CI.

---

## Project structure

```
backend/
  app/
    main.py · config.py · db.py · models.py · schemas.py
    providers/   gemini · ollama · factory        (LLM/embedding abstraction)
    ingest/      parse (Docling/OCR/web/YouTube/audio) · pipeline (chunk→embed→store)
    rag/         engine (CitationQueryEngine, streaming) · locate (offset resolver)
                 · assist (intent router) · summary (overview)
    spreadsheet/ store (xlsx→duckdb) · engine (text-to-SQL, row citations)
    stores/      chroma
    routers/     notebooks · sources · chat · notes
frontend/
  app/           dashboard · notebook/[id] · globals.css (design tokens)
  components/     TopBar · icons
  lib/            api client · types
docs/            planning + audit notes (DUE_DILIGENCE · SECURITY_VERIFICATION · QA_REPORT · …)
```
