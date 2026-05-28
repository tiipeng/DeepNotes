# Build a self-hosted, scalable NotebookLM clone

## Your role & the prime directive
You are building a self-hosted NotebookLM clone. **Maximize use of existing open-source libraries — write as little custom logic as possible.** If a library already solves a problem (parsing, chunking, retrieval, citations, audio), use it. Do not reinvent it.

The single most important feature is **grounded chat with verifiable citations**: every answer must come only from the user's sources, and the user must be able to click a citation and land on the exact passage it came from. Treat this as the heart of the product.

The attached mockup screenshot is the visual target — match its layout, palette and the citation interaction.

## Before writing ANY code (plan mode)
1. Read this entire spec.
2. Propose: the data model + API contract (see "Contract first" below), the file/folder structure, and the phases. **Wait for my confirmation before coding.**
3. List every dependency you intend to install. Flag anything not named in this spec and ask first.

## Contract first
Before building features, nail down and show me:
- The **data model**: notebooks, sources, chunks (each chunk MUST carry: source id, page/section, char offsets), chat messages, citations.
- The **API shape** between frontend and backend (endpoints, request/response schemas).
This contract is what keeps the build coherent. Get my sign-off on it before Phase 1.

## Architecture (use exactly this unless you flag a blocker)
- **Frontend:** Next.js 14 (App Router, TypeScript), Tailwind CSS, shadcn/ui. Deployable to Vercel.
- **Backend:** Python + FastAPI (the OSS heavy-lifting lives here). Deployable as a container (HF Spaces / Render / Cloud Run). NOTE: the backend can NOT run on Vercel functions (250 MB / 10s limits) — keep it a separate service.
- **Document parsing:** Docling (`pip install docling`) — PDF, DOCX, PPTX, XLSX, HTML, OCR, layout, tables → clean Markdown/JSON.
- **RAG + citations:** LlamaIndex — use its citation query engine so source attribution is built-in.
- **Vector store:** Chroma (local, zero-config) as default. pgvector/Supabase only if I say it's set up.
- **LLM + embeddings:** <FILL IN: Gemini (free tier) or Claude> via API, key from `.env`. **Put this behind a provider abstraction** so a local Ollama model can be swapped in later without touching app logic. Never hardcode keys.
- **Audio Overview (stretch only):** Podcastfy (`pip install podcastfy`).

## MVP scope — MUST have
1. **Notebooks:** create multiple; each owns its own sources.
2. **Source management:** upload PDF + TXT, add a URL. Also accept DOCX/PPTX/XLSX (Docling parses them anyway — table-stakes parity). List sources per notebook.
3. **Ingestion pipeline:** Docling parse -> chunk -> embed -> store. **Every chunk retains source metadata (source id, page/section, char offset).** Do not lose it. Process sources serially (respect free-tier LLM rate limits; add retry with backoff).
4. **Grounded chat:** question -> retrieve top-k chunks -> LLM answers ONLY from those chunks -> inline citation markers [1], [2].
5. **Citation UX:** clicking a marker opens the source and scrolls to / highlights the cited passage. This is the signature feature.
6. **Strict grounding:** if the answer isn't in the sources, say so. Never fall back on the model's own world knowledge.

## Differentiators (after MVP)
- **Spreadsheet reasoning:** treat uploaded XLSX as queryable structured data (real aggregation/filtering over tables), not flattened text. This is a concrete feature NotebookLM does poorly.
- **Sovereignty / local mode:** thanks to the provider abstraction, document the path to run fully local via Ollama (no data leaves the server). Implement if time allows; otherwise document it in the README.

## Stretch scope — ONLY after MVP runs end-to-end
- Audio Overview via Podcastfy (2-host podcast, playable in UI).
- Notes panel (save snippets / responses).
- Auto-generated notebook summary + suggested starter questions.

## Limits to enforce
- Max file size 10 MB (reject larger with a clear message).
- Max 5–10 sources per notebook; ~200 pages total.
- Store only parsed Markdown + embeddings + metadata; discard original files after parsing (keep only what the citation view needs).

## Non-negotiables
- Don't reinvent parsing, chunking, retrieval, or citations — delegate.
- No answer without a citation. A response that doesn't cite is a bug.
- Secrets in `.env` only. Provide `.env.example`. Never commit keys.
- Prefer simple over clever. No premature auth/multi-tenancy/scaling unless I ask.

## Build in phases — run it and commit after each
- **Phase 0 — Spike (throwaway):** a tiny script: one PDF -> Docling -> LlamaIndex -> answer with citations, printing the source spans to the terminal. Prove the risky core works BEFORE building the app. Report results, then stop for my go/no-go.
- **Phase 1 — Contract + Scaffold:** data model + API contract implemented; Next.js + FastAPI skeleton talking; health-check. Run, show me, commit.
- **Phase 2 — Ingestion:** upload -> parse -> chunk -> embed -> store, metadata preserved. Verify by ingesting a test file and printing stored chunks. Commit.
- **Phase 3 — Grounded chat:** retrieval + answer with inline [n] citations. Verify with a real question AND a question whose answer is NOT in the sources (must say "not found"). Commit.
- **Phase 4 — Citation UX:** click citation -> open source -> highlight passage. Commit.
- **Phase 5 (differentiator):** spreadsheet reasoning. Commit.
- **Phase 6 (stretch):** audio, notes, summaries.

After every phase: actually run it, confirm it works, commit before moving on. If a later phase reveals Phase 2 lost metadata, fix Phase 2 first — don't paper over it.

## Definition of done (MVP)
I can: create a notebook, upload 2–3 PDFs, ask a question, get an answer grounded only in those PDFs with inline citations, click a citation, and land on the exact passage.

## How to handle uncertainty
- Blocker or ambiguous decision? **Stop and ask me.** Don't build on a guess.
- Want a dependency not listed here? Ask first.
- Tempted by a feature not in scope? Note it as "possible later" and move on.
