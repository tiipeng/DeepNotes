# DeepNotes — Ultraplan

A self-hosted, data-sovereign NotebookLM clone. **Chat with your sources**: the AI answers *only* from uploaded documents, and every claim links back — clickably — to the exact passage it came from. Built thin on open-source; custom code is UI + citation glue + wiring.

This plan synthesizes `/docs/PLAN.md`, `/docs/BUILD_PROMPT.md`, `/docs/DESIGN_PROMPT.md`, and the **DeepNotes** design handoff bundle (Claude Design export). It is the single source of truth for the build.

---

## 0. Guiding principles

1. **Maximize OSS, minimize custom logic.** Parsing, chunking, retrieval, citations, audio are all delegated to libraries. Our code = UI + citation highlighting + wiring.
2. **Grounded chat with verifiable citations is the heart of the product.** No answer without a citation is a bug. If the answer isn't in the sources, say so — never fall back on world knowledge.
3. **Contract first.** Lock the data model + API shape before building features. The chunk metadata (source id, page/section, char offsets) is sacred — never lose it.
4. **Thin vertical slices.** Run it and commit after every phase. If a later phase reveals an earlier phase dropped metadata, fix the earlier phase — don't paper over it.
5. **Spike before building.** Prove the risky citation core works on day one (Phase 0 gate) before scaffolding an app around it.
6. **Provider abstraction for sovereignty.** LLM/embeddings sit behind an interface so a local Ollama model can be swapped in without touching app logic.

---

## 1. Architecture

```
┌─────────────────────────────────────────────┐        ┌──────────────────────────────────────────────┐
│  FRONTEND  (Next.js 14 App Router, TS)         │        │  BACKEND  (Python + FastAPI)                    │
│  Tailwind + shadcn/ui · DeepNotes design       │  HTTP  │  OSS heavy-lifting lives here                   │
│                                                 │ <────> │                                                 │
│  • Dashboard (notebook grid)                    │  JSON  │  • Docling     → parse PDF/DOCX/PPTX/XLSX/URL    │
│  • Notebook 3-col (Sources · Chat · Studio)     │  /SSE  │  • LlamaIndex  → CitationQueryEngine (RAG)       │
│  • Citation drawer (highlight + scroll)         │        │  • Chroma      → vector store (local)            │
│  • Notes / Studio panel                         │        │  • SQLite      → metadata (notebooks/sources/…)  │
└─────────────────────────────────────────────┘        │  • Provider abstraction → Gemini | Ollama        │
   Deploy: Vercel or local                                │  • DuckDB/pandas → XLSX structured reasoning      │
                                                          │  • Podcastfy   → audio overview (stretch)        │
                                                          └──────────────────────────────────────────────┘
                                                             Deploy: container (HF Spaces / Render / Cloud Run)
                                                             NOTE: cannot run on Vercel functions (250MB/10s)
```

**Why two services:** the backend's parsing + RAG stack is heavy (Docling, torch deps) and long-running — it can't fit Vercel's serverless limits. Keep it a separate container. Default deployment for the demo is **local** (show `localhost`).

---

## 2. Stack & dependencies

| Concern | Choice | Notes |
|---|---|---|
| Frontend | Next.js 14 (App Router, TypeScript) | shadcn/ui + Tailwind |
| Styling | Tailwind + DeepNotes design tokens | port the bundle's CSS variables (§4) |
| Fonts | Newsreader (serif), Geist (sans), JetBrains Mono | via `next/font/google` |
| Backend | Python 3.11 + FastAPI + Uvicorn | |
| Parsing | **Docling** (`docling`) | PDF, DOCX, PPTX, XLSX, HTML, OCR → Markdown/JSON w/ provenance |
| RAG + citations | **LlamaIndex** (`llama-index`) + `CitationQueryEngine` | built-in source attribution |
| Vector store | **Chroma** (`chromadb`) local, zero-config | pgvector/Supabase only if explicitly set up |
| Metadata DB | **SQLite** via SQLAlchemy (local default) | Postgres/Supabase optional later |
| LLM | **Gemini** `gemini-2.5-flash` | key in `backend/.env`. NOTE: `gemini-2.0-flash` is blocked for new keys (verified in Phase 0) |
| Embeddings | **Gemini** `gemini-embedding-001` | NOTE: `text-embedding-004` 404s for this key (verified in Phase 0) |
| Spreadsheet reasoning | DuckDB / pandas over parsed tables | differentiator |
| Audio (stretch) | **Podcastfy** (`podcastfy`) | 2-host overview |
| Local/sovereign mode | **Ollama** provider (documented; impl if time) | no data leaves server |

**Flag before installing anything not in this list.** Each new dependency gets justified against "does an existing lib already solve this?"

---

## 3. Design system (extracted from the DeepNotes bundle)

The design medium is HTML/CSS/JS prototypes. We recreate them **pixel-perfectly** in React/Next — match the visual output, not the prototype's internal structure. The final design (after the user's "less commercial" edit) removed: Upgrade button, Library icon, brand subtitle, avatars, Beta tags, version chrome, dashboard search lozenge. Build the **toned-down** state: wordmark + central search + a single "Settings" link.

### 3.1 Palette (warm-neutral foundation, forest accent) — port verbatim as CSS vars / Tailwind theme

```
--bg #FAF8F4   --bg-2 #F4F0E8   --bg-3 #ECE6D8
--surface #FFFFFF   --surface-2 #FBFAF6
--border #E6E0D2   --border-2 #DAD2BE   --border-3 #C9BFA6
--ink #1A1815   --ink-2 #3A352D   --muted #6B6862   --muted-2 #94908A   --faint #B6B2A8
--accent #1F4D3F (forest)   --accent-ink #163A2F
--accent-soft rgba(31,77,63,.08)   --accent-soft-2 rgba(31,77,63,.16)
--highlight #FFE6A8   --highlight-2 #F4D77A   (citation highlight)
radii: 6 / 10 / 14 / 18px   ·   shadows: card / pop / drawer (see styles.css)
```

Accent is theme-able (forest default; ember/ink-blue/graphite/violet offered). Notebook covers use `oklch()` gradients from per-notebook `hueA/hueB` + a serif glyph letter.

### 3.2 Typography
- **Serif (Newsreader):** display headings, card titles, answer prose (17px/1.65), drawer prose, empty-state title.
- **Sans (Geist):** all UI chrome, body, buttons, labels.
- **Mono (JetBrains Mono):** page counts, quotas, `⌘K`, section markers, citation numerals.

### 3.3 Screens & components to build
1. **Dashboard** — header ("Your notebooks"), filter chips (All/Recent/Shared/Archive), `+ New notebook` dashed tile + notebook cards (gradient cover, glyph, title, snippet, `N sources · edited`).
2. **Notebook view** — 3-column grid `320px / 1fr / 320px`, min-height 760px:
   - **Left · Sources:** "Add source" dashed CTA, "Select all" + "N of M in chat", source rows (checkbox · PDF/URL icon + kind · title + authors·venue·year·`Np`), selected-state highlight, footer quota bar ("74 / 230 pages indexed").
   - **Center · Chat:** byline ("Grounded in N sources"), serif answer prose with inline `⟦n⟧` citation chips, "Sources" row of cited cards, message tools (Copy / Save as note / Pin / Rerun), sticky composer (attach · input · "N sources" scope chip · send). **Empty state:** striped mark, "Ask anything across your sources.", 3 suggested questions.
   - **Right · Studio:** Audio Overview card (ungenerated CTA ↔ generated player w/ waveform), Notes section (note cards: tag · title · body · edited).
3. **Citation drawer (signature interaction)** — 620px panel slides from right over a blurred scrim. Header: cite number, kind/venue/page, title, authors. Toolbar: section marker, "Jump to next mention", "All highlights · N". Body: 3 stacked "pages" (prev faint · **current**, with the **cited passage `<mark>`-highlighted in yellow and scrolled to center** · next faint). Footer: "⌘↵ Insert as quoted note" + "Save as note". On open: `scrollIntoView({block:'center'})` on the highlight.

### 3.4 Frontend styling decision
Port the bundle's `styles.css` design tokens into `globals.css` + `tailwind.config` `theme.extend`, and recreate each `dn-*` component as a typed React component. Use shadcn/ui only for primitives that benefit (Dialog/Drawer mechanics, Button, Checkbox) — the editorial look comes from our tokens, not shadcn defaults. This keeps it pixel-accurate while staying idiomatic Next.

---

## 4. Data model (contract — get sign-off before Phase 1)

SQLite for metadata; Chroma for vectors (keyed by `chunk.id`). Originals discarded after parsing — keep only parsed markdown + embeddings + metadata.

```
notebook
  id (uuid) · title · snippet · cover_hue_a · cover_hue_b · cover_glyph
  created_at · updated_at
  (source_count derived)

source
  id (uuid) · notebook_id (fk) · kind (pdf|txt|url|docx|pptx|xlsx)
  title · authors · venue · year · pages
  status (parsing|ready|error) · error_msg
  checked (bool — included in chat)  · char_count
  parsed_markdown (TEXT — the reading-pane content)
  created_at

chunk                       ← METADATA IS SACRED
  id (uuid) · source_id (fk) · notebook_id (fk)
  text · order_index
  page · section (heading)
  char_offset_start · char_offset_end   (into source.parsed_markdown)
  (embedding lives in Chroma, id == chunk.id)

message
  id (uuid) · notebook_id (fk) · thread_id · role (user|assistant)
  text · created_at

citation
  id (uuid) · message_id (fk) · source_id (fk) · chunk_id (fk)
  display_index (n)  · page · section
  char_offset_start · char_offset_end   (highlight range in source)
  snippet (the highlighted passage text)

note
  id (uuid) · notebook_id (fk) · title · body · tag · source_id? · created_at

table_data  (XLSX differentiator)
  id · source_id (fk) · sheet_name · columns(json) · rows(parquet/duckdb ref)
```

Every chunk **must** retain `source_id`, `page/section`, and `char_offset_start/end`. This is what makes click-to-highlight possible.

---

## 5. API contract (FastAPI)

```
GET    /health

GET    /notebooks                         → [notebook]
POST   /notebooks            {title}       → notebook
GET    /notebooks/{id}                     → notebook + sources + messages
PATCH  /notebooks/{id}       {title}       → notebook
DELETE /notebooks/{id}

GET    /notebooks/{id}/sources             → [source]
POST   /notebooks/{id}/sources            (multipart file | {url})  → source (status=parsing→ready)
PATCH  /sources/{id}        {checked}      → source   (toggle include-in-chat)
DELETE /sources/{id}
GET    /sources/{id}/content               → {parsed_markdown, pages, sections}   (reading pane)
GET    /sources/{id}/passage?start=&end=   → {pre, highlight, post, page, section} (drawer)

POST   /notebooks/{id}/chat  {question, source_ids[]}
       → { answer_markdown,
           citations: [ {display_index, source_id, chunk_id, title, authors,
                         venue, page, section, char_offset_start, char_offset_end,
                         snippet} ] }
       (MVP: JSON. Polish: SSE stream tokens, then citations payload.)
GET    /notebooks/{id}/messages            → [message + citations]

GET    /notebooks/{id}/notes    · POST · DELETE /notes/{id}

# differentiator / stretch
POST   /notebooks/{id}/query-table  {question}     → structured table answer (XLSX)
POST   /notebooks/{id}/audio                        → {job_id}
GET    /audio/{job_id}                              → {status, url}
GET    /notebooks/{id}/summary                      → {summary, suggested_questions[]}
```

The chat response shape is designed so the frontend can render the answer with `⟦n⟧` chips and, on click, hand the citation's offsets straight to the drawer — mapping cleanly onto the design's `CITED_PASSAGES` (pre / highlight / post / page / section).

---

## 6. Citation pipeline (the crux)

```
upload → Docling parse (markdown + provenance: page, section, bbox)
       → keep source.parsed_markdown as canonical text
       → chunk (Docling/LlamaIndex node parser), each node tagged with
            metadata = {source_id, page, section, char_offset_start, char_offset_end}
       → embed (Gemini text-embedding-004) → Chroma (id == chunk.id)

ask    → retrieve top-k over CHECKED sources only (Chroma filter by source_id)
       → LlamaIndex CitationQueryEngine → answer with [n] markers, each n ↔ a source node
       → strict-grounding system prompt: "answer ONLY from context; if absent, say not found"
       → map each [n] → chunk → source + char offsets → citation record

click  → frontend hits /sources/{id}/passage with the citation's offsets
       → backend slices parsed_markdown into {pre, highlight, post}
       → drawer renders, <mark>-highlights `highlight`, scrollIntoView(center)
```

**Risk to validate in Phase 0:** that Docling provenance + LlamaIndex node metadata give *usable* char spans we can re-locate in `parsed_markdown`. If offsets don't round-trip cleanly, fall back to exact-substring search of the cited node text within the source markdown to recover the highlight range. This is the single highest-risk piece — hence the spike gate.

> **Phase 0 result (✅ validated):** SentenceSplitter nodes round-trip perfectly (`md[start:end] == node.text`). **Caveat:** `CitationQueryEngine` sub-splits a retrieved node into citation chunks `[1][2]…` whose `start_char_idx` still points at the *parent* node, not the sub-chunk. So for highlighting, **locate each citation chunk's text by substring search in the source markdown** (exact match hit 100% in the spike; keep a whitespace-normalized fallback). Don't trust the citation node's `start_char_idx` for the precise span.

> **Locked-in offset resolution (confirmed) — `locate_span(cited_text, parsed_markdown, parent_chunk)`:**
> 1. **Exact substring** match in `parsed_markdown` → use that range.
> 2. **Whitespace-normalized** match (collapse runs of whitespace on both sides, map back to original offsets) → use that range. Prevents silent highlight failures on whitespace differences.
> 3. **Fallback to the parent chunk's full span** (`chunk.char_offset_start/end`) → highlight the whole retrieved chunk rather than showing nothing.
> `CitationOut` is **denormalized** (carries `source_title/authors/venue/kind`) so the frontend renders chips + drawer with zero extra round-trips; the `citations` table stays normalized via `source_id`/`chunk_id`.

---

## 7. Repository structure

```
DeepNotes/
  docs/            PLAN.md · BUILD_PROMPT.md · DESIGN_PROMPT.md · ULTRAPLAN.md
  frontend/        Next.js 14 app
    app/           (dashboard) · notebook/[id] · layout · globals.css
    components/    dashboard/ · notebook/ (sources, chat, studio) · citation-drawer · ui (shadcn)
    lib/           api client · types (mirror the contract)
    tailwind.config.ts   (DeepNotes tokens)
  backend/
    .env (gitignored, has GEMINI_API_KEY) · .env.example
    app/
      main.py            FastAPI app + routes
      models.py          SQLAlchemy models (§4)
      schemas.py         Pydantic request/response (§5)
      ingest/            docling parse · chunk · embed · store
      rag/               citation_query_engine · retrieval · grounding prompt
      providers/         llm.py (Gemini|Ollama abstraction) · embeddings.py
      stores/            chroma.py · db.py
      spreadsheet/       duckdb table reasoning (differentiator)
      audio/             podcastfy wrapper (stretch)
    spike.py             Phase 0 throwaway
    requirements.txt
  README.md          architecture diagram · OSS→challenge map · setup · limits
```

Housekeeping at start: keep `docs/` at root, move the stray `.env` to `backend/.env`, remove the duplicated docs inside `backend/`.

---

## 8. Phased build plan (run + commit after each)

### Phase 0 — Spike (throwaway) · **GO/NO-GO GATE**
`spike.py`: one PDF → Docling → LlamaIndex `CitationQueryEngine` (Gemini) → print answer + `[n]` markers + each cited node's source/page/char-span to the terminal.
→ **Verify:** are the spans usable to re-locate the passage in the parsed markdown? **Yes → project is feasible. No → replan now** (substring-recovery fallback or different chunker). Report results, stop for sign-off.

### Phase 1 — Contract + Scaffold
Data model (§4) + Pydantic schemas (§5) implemented. FastAPI skeleton + Next.js skeleton talking; `GET /health` green from the browser. Provider abstraction stubbed (Gemini live, Ollama interface present). `.env.example` committed.
→ **Verify:** frontend fetches `/health`; create + list a notebook end-to-end. Commit.

### Phase 2 — Ingestion
`upload → Docling parse → chunk → embed → store`, metadata preserved. Serial processing, retry + backoff for Gemini rate limits. Discard originals; keep parsed markdown + embeddings + metadata. Enforce limits (§9).
→ **Verify:** ingest a test PDF, print stored chunks with their `{source_id, page, section, offsets}`. Commit.

### Phase 3 — Grounded chat
Retrieval over **checked** sources → `CitationQueryEngine` → answer with inline `[n]`. Strict grounding prompt.
→ **Verify:** a real question returns grounded answer + citations; a question whose answer is **not** in the sources returns "not found." Commit.

### Phase 4 — Citation UX (signature)
Frontend renders `⟦n⟧` chips + Sources row. Click → fetch passage → **drawer opens, highlights the exact passage in yellow, scrolls to center.** Matches the design drawer (header/toolbar/3-page body/footer).
→ **Verify (Definition of Done):** create notebook → upload 2–3 PDFs → ask → grounded answer w/ inline citations → click → land on exact passage. Commit.

### Phase 5 — Full frontend per DeepNotes design
Dashboard (cards + covers + filters), notebook 3-col polish, Studio panel (notes CRUD), empty state + suggested questions, composer scope chip, quota bar, theme tokens + fonts, accent theming. Pixel-match the bundle.
→ **Verify:** visually compare against the design's screens; click through all flows in the browser. Commit.

### Phase 6 — Differentiators
- **Spreadsheet reasoning:** parse XLSX tables into DuckDB; route table questions to real aggregation/filtering (not flattened text).
- **Sovereignty:** finish the Ollama provider path; document local mode in README.
→ **Verify:** an aggregation question over an uploaded XLSX returns a computed answer. Commit.

### Phase 7 — Stretch (only if MVP solid)
Audio Overview via Podcastfy (2-host, playable in Studio); notes-from-answer; auto summary + suggested starters. Prefer dropping over shipping half-finished.

### Phase 8 — Polish & handoff
README (architecture diagram, OSS→challenge mapping, setup, limits, differentiator, "how I'd scale it"), secrets scrub, fresh-clone setup test, optional live link (FE→Vercel, BE→container), Loom: Design → Plan → Spike gate → Build → **Citation demo (climax)** → Differentiator → architecture rationale.

---

## 9. Limits to enforce
- Max file size **10 MB** (reject larger with a clear message).
- Max **5–10 sources** per notebook; **~200 pages** total.
- Allowed types: PDF, TXT, URL + DOCX/PPTX/XLSX parity.
- Ingestion **serial**, not parallel (free-tier rate limits + retry/backoff).
- Store only parsed markdown + embeddings + metadata; **discard originals** after parsing.

## 10. Non-negotiables
- Don't reinvent parsing/chunking/retrieval/citations — delegate.
- **No answer without a citation.** Strict grounding; "not found" when absent.
- Secrets in `.env` only; `.env.example` provided; never commit keys.
- Simple over clever. No premature auth/multi-tenancy/scaling unless asked.

## 11. Differentiators (vs vanilla NotebookLM)
1. **Data sovereignty / self-hosted + Ollama local mode** — the scaling bet (GDPR / public sector).
2. **Real spreadsheet reasoning** over XLSX — queryable structured data, a concrete NotebookLM weakness.

## 12. Risks & gates
- **Phase 0 spike gate** — ✅ PASSED. Citation core proven: grounded answer + inline `[n]` + all citations relocate in markdown; out-of-sources question correctly refused ("None of the sources are helpful").
- **Scope creep (Phases 6–7)** — measure every extra against "does it make the demo better?"
- **Offset round-tripping** (§6) — ✅ resolved: substring search of citation-chunk text (not node `start_char_idx`).
- **Docling on Apple Silicon** — must force CPU (`AcceleratorOptions(device=CPU)`); MPS lacks float64 and crashes the RT-DETR layout model. Set `do_ocr=False` for text-layer PDFs (faster, skips RapidOCR model downloads).
- **Gemini rate limits** — serial ingest + backoff; cache embeddings.

---

## 13. Decisions (confirmed)
1. **Metadata DB:** ✅ **SQLite** (local default) + Chroma for vectors. Postgres/Supabase swappable later.
2. **Frontend styling:** ✅ **Port the bundle's CSS tokens into Tailwind + recreate components** for pixel-accuracy.
3. **Differentiator priority:** ✅ **Spreadsheet reasoning (XLSX) ships first**; Ollama sovereignty mode after.
4. **Chat transport:** JSON response for MVP, SSE streaming as Phase 5 polish.
5. **LLM/embeddings:** Gemini `gemini-2.5-flash` + `gemini-embedding-001` (verified working in Phase 0; the originally-planned `2.0-flash`/`text-embedding-004` are unavailable for this key).
