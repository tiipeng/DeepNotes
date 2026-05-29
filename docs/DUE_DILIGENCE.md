# DeepNotes — Technical & Product Due Diligence

**Reviewer stance:** skeptical technical investor running diligence before a funding decision. The job is to find what's wrong, what's missing, and whether the thing holds up — not to flatter it.

**Date:** 2026-05-29
**What was reviewed:** the running application (backend `:8100`, frontend `:3100`), driven live over the local/Tailscale network, plus a full read of the codebase.
**Method:** I did not take the README's word for anything. I ingested real hard documents, computed ground truth independently, ran adversarial queries, measured citation resolution from the server's own logger, and probed the security boundary directly against the live code paths.

> **TL;DR.** The core technical claims are *real and verified* — citation precision, grounding discipline, and spreadsheet reasoning all genuinely work, and the engineering taste is evident. But this is a **single-user prototype**, not a product: no authentication, no tests, an event loop that freezes for 26 seconds on a single upload, a text-to-SQL engine that will read any file on the host, and the headline "every claim is clickable" promise quietly breaks on the one feature that's supposed to be the differentiator. **I would not write a priced round today.** I'd consider a small founder bet conditioned on the milestones in §7.

---

## 1. What I actually did (evidence, not vibes)

| Test | Result |
|---|---|
| Ingest hard **two-column PDF** (BERT paper, 16pp, tables) | Parsed in **15s**; reading order correct; 35 headings; tables captured |
| Ingest **100-page PDF** (GPT-4 report, 5MB, 296k chars) | Parsed in **44s**; succeeded |
| Ingest **scanned/image-only PDF** | Accepted as `status:ready`, **`char_count:0`** — silently useless |
| Ingest **messy XLSX** (3 sheets, blank rows, mixed types, weird headers) | Parsed in **0.65s**; empty sheet skipped; 2 DuckDB tables |
| **Text-to-SQL vs independent ground truth** (5 questions) | **5/5 correct**, incl. a deliberate VARCHAR-coercion trap and date math |
| **Citation hit/fallback ratio** (12 questions, 57 citations) | **57/57 exact (100%)**, 0 fallbacks, median highlight 138 chars |
| **Citation drawer precision** (`/passage`) | **4/4 exact**, correct page **and** section |
| **Adversarial chat** (out-of-scope, hallucination bait, German, very-long, ambiguous) | Refused correctly where it should; answered German with citations |
| **Security: file-read via text-to-SQL** | **Exfiltrated the live `GEMINI_API_KEY`, `/etc/passwd`, and a filesystem glob** |
| **Event-loop blocking** under upload | `/health` latency went **0.9ms → 25.8s** during one ingest |
| Edge cases (oversized, unsupported, empty Q, 0-source, dup, delete-mid-convo) | Mixed — see §2 |

---

## 2. The product, exercised for real

### 2a. Citations / grounding — **genuinely works** ✅
This is the heart of the pitch, and it holds up better than most RAG products I've seen.

- **Citation precision is real.** Across 12 questions on the two-column BERT PDF, all **57** citations resolved via *exact substring match* (the server's own `deepnotes.citations` logger: `method=exact` 57/57, `parent_fallback` 0). Median highlight span 138 chars — one sentence, not a whole paragraph.
- **The drawer lands exactly.** For a fresh answer, all 4 citations had `snippet == /passage.highlight`, with correct page **and** section (e.g. p4 §3.1 *Pre-training BERT*, p6 §4.1 *GLUE*, p1 *Abstract*). The signature "click → highlighted passage scrolled into view" is not a mock; the offset coordinate system (one markdown, char offsets everywhere, `page_map` resolution) is well-designed and accurate.
- **Refusal discipline is strong.** "What is the capital of France?" → *not found*. "What does this paper say about quantum computing?" (plausible-but-absent bait) → *not found*, no fabricated bridge. Whitespace-only question → *not found*. 0-source notebook → *not found*. No hallucinations observed.
- **Multilingual works.** A German question returned a correct German answer with 5 citations.
- **Robust to noise.** A 600-word rambling question still extracted the real ask and answered with one citation.

> Caveat (latent, not observed): `locate.py` uses `markdown.find(cited)` — the **first** occurrence. For a sentence that appears verbatim more than once (repeated table cells, boilerplate), it will highlight the wrong instance. The parent offset is available but unused for disambiguation. Not triggered in my tests, but it's a correctness landmine with zero tests guarding it.

### 2b. Spreadsheet reasoning — **the strongest part, but it breaks two promises** ⚠️
Credit first: this is **better than NotebookLM** at what it does, and it survived traps I expected it to fail.

- 5/5 correct vs. independently computed ground truth, including:
  - The **VARCHAR trap**: I made `Salary (USD)` mixed-type (`120000` … `'70,000'`), which DuckDB types as `VARCHAR`. A naive `MAX()` returns lexicographic `'95000'` (Bob). The model wrote `CAST(REPLACE("Salary (USD)", ',', '') AS BIGINT)` and correctly returned **Alice / 120000**.
  - **Date math**: avg tenure → `AVG(DATE_DIFF('day', TRY_CAST("Start" AS DATE), CURRENT_DATE)/365.25)` = 4.96y (verified ✓), correctly ignoring the null row.
  - **Honest emptiness**: "employees earning over 200000" → empty result → "there are no employees…" (no fabrication). "profit margin" (no such column) → correctly returned `sql:null` → fell back to RAG → *not found*.

But:

- **[SERIOUS] Spreadsheet answers carry ZERO citations** and still report `grounded:true`. The single most-marketed feature ("every claim links back, clickably") **does not apply to the differentiator.** You get a number + the SQL, but no click-to-source, no drawer. The two headline features are mutually exclusive.
  > **✅ FIXED & RE-VERIFIED (2026-05-29).** `answer_with_tables` now builds a citation per referenced table, pointing at the originating source + sheet, and appends clickable `[n]` markers. Re-test: "Which region had the highest total revenue?" → *"The West region had the highest total revenue. [1]"*, `grounded:true`, **1 citation** (source *sales*, sheet *Sales*), table result still present, and `/passage` opens the drawer on the sheet with its rows in context.
- **[SERIOUS] The differentiator ignores per-request scoping.** With `source_ids:[]` (user deselected *everything*), a table question **still answered** `grounded:true`. `answer_with_tables` runs first on every message and filters only by `checked`, ignoring the chat-time `source_ids`. "Scope discipline" is one of the five advertised pillars; it's violated by the marquee feature.
  > **✅ FIXED & RE-VERIFIED (2026-05-29).** `chat.py` now resolves the in-scope `source_ids` *before* routing, and `notebook_table_schemas` filters by them (empty list ⇒ no tables). Re-test: same question with `source_ids:[]` → `grounded:false`, no table, *"I couldn't find an answer…"*.
- **[SERIOUS] No cross-source synthesis.** "Compare BERT's GLUE score (PDF) with total Marketing spend (spreadsheet)" → *not found*. The router picks **one** path (table *or* prose), never both. For a "chat with all your sources" tool, you cannot ask a question that spans a document and a spreadsheet.
- It is, architecturally, a **thin wrapper over LLM text-to-SQL**. It's done well, but it's a feature, not a moat — every BI/analytics tool is shipping the same thing.

### 2c. Parsing — solid, with one silent hole
- Two-column reading order, headings, and tables all parsed correctly; 100pp in 44s on CPU is fine.
- **[SERIOUS] OCR is disabled** (`parse.py:51 do_ocr=False`) while the README's parsing table advertises "OCR → markdown w/ provenance." A **scanned/image-only PDF is accepted, marked `ready`, and contributes nothing** (`char_count:0`, no warning). Scanned contracts, invoices, and old reports — a huge share of the real-world documents a sovereignty-focused buyer (legal/healthcare/public-sector) actually has — are silently useless.

### 2d. Edge cases
| Case | Behavior | Verdict |
|---|---|---|
| Oversized (11MB) | `400 File exceeds 10 MB limit` | ✅ clean |
| Unsupported `.zip` | `400 Unsupported file type '.zip'` | ✅ clean |
| **Empty question `""`** | `200` — **fabricated a generic summary** | ⚠️ no input validation, wasted LLM call |
| 0-source notebook | clean *not found* | ✅ |
| **Duplicate upload** | silently creates a 2nd identical source (+dup DuckDB table, +dup vectors) | ⚠️ no dedup |
| **Delete source mid-conversation** | history degrades to "(deleted source)", but the citation is **still clickable → `/passage` 404** (dead drawer); answer keeps `[n]` markers | ⚠️ |

---

## 3. Security — the part that fails diligence

### [BLOCKER] Arbitrary file read / secret exfiltration via text-to-SQL
> **✅ FIXED & RE-VERIFIED (2026-05-29).** DuckDB connections are now opened with `config={"enable_external_access": False, "lock_configuration": True}` (`spreadsheet/store.py::_connect`), applied to every connection. Re-running the exact attacks against the live `run_select`: `read_text('.env')` → **PermissionException (blocked)**, `/etc/passwd` → **blocked**, `glob(...)` → **blocked**, and a stacked `SET enable_external_access=true` → **blocked** (configuration locked). Legit queries and XLSX ingestion still work. The regex remains only a coarse first filter; the real guard is now at the engine level. *(Rotate the previously-exposed key regardless — see below.)* The remainder of this section documents the as-found state.

The "read-only guard" (`spreadsheet/engine.py`) is a regex that only checks the query *starts with* `select`/`with`. `read_only=True` on the DuckDB connection protects the *database file*, **not the filesystem.** Run directly against the live `run_select`:

```
SELECT content FROM read_text('.../backend/.env')
  → ['GEMINI_API_KEY=AIza…  (the real key, in plaintext)']
SELECT content[1:80] FROM read_text('/etc/passwd')   → leaked
SELECT file FROM glob('.../backend/*')                → full directory listing
SELECT 1; DROP TABLE IF EXISTS nope;                  → stacked statement executed
```

The only thing standing between a user and any file on the host is the LLM's willingness to emit such SQL. In my end-to-end attempts **Gemini declined** (returned `sql:null`) — a useful *accidental* gate, but not a control. It collapses under: (a) the **Ollama "sovereignty mode"** (llama3.1, far more compliant) — which is *the deployment that has the org's secrets on the same box*; (b) prompt injection via document/sheet/column names that flow into the SQL prompt; (c) any future prompt/model change. A "sovereign, runs-on-your-own-hardware" product whose query engine can read `/etc/passwd` is a contradiction in terms. **This is a hard blocker for both hosted and on-prem.**
*Action: run DuckDB in a sandboxed process with `enable_external_access=false` / file functions disabled; allowlist tables/columns; parse-validate the SQL AST instead of regex-prefixing.*

### [BLOCKER] No authentication or authorization — at all
No user model, no login, no session, no API key, no notebook ownership (`models.py` has no `User`). Every endpoint is fully open; anyone who can reach the API can read, query, and **delete** every notebook. CORS is scoped, but there's nothing to protect because there's no auth. **This is single-tenant-only and cannot be exposed beyond one trusted user without a data-model and security rewrite.**

### Lower-severity
- **[SERIOUS]** Raw exception strings returned to the client on ingest failure (`sources.py:112 f"Ingestion failed: {e}"`) — info disclosure.
- **[MINOR]** The live `GEMINI_API_KEY` is now exposed (via the exfil path and in my logs). **Rotate it.** (Secrets are correctly gitignored — only `.env.example` is tracked.)
- **[MINOR]** `MAX_FILE_BYTES` is enforced *after* `await file.read()` loads the whole upload into memory — a 2GB upload is fully buffered before rejection.

---

## 4. Architecture & code quality

### Solid
- Clean separation (routers / ingest / rag / spreadsheet / providers / stores).
- **Provider abstraction is genuinely good** — Gemini↔Ollama really is a config swap.
- The citation offset/coordinate design is the best-thought-out part and is empirically accurate.
- The README's "How I'd scale this" section shows the author *knows* the gaps (async ingest, multi-tenancy, managed stores). Self-aware — a positive founder signal.

### Fragile / won't survive scale
- **[BLOCKER, proven] Blocking ingestion freezes the whole server.** `add_source` is `async def` but does blocking Docling/embedding work on the event loop. Measured: during one upload, `/health` went from **0.9ms to 25.8s**. One user = a slow upload; *any* concurrency = the service stalls. There is no worker queue (the README plans one; it isn't built), and no status polling on the frontend, so "parsing→ready" only reconciles on manual reload.
- **[SERIOUS] Global mutable state race.** `rag/engine.py:67` sets the process-global `Settings.llm` / `Settings.embed_model` per request, under sync routes run in a threadpool. Masked today (one provider); corrupts behavior the moment provider selection becomes per-tenant.
- **[SERIOUS] DuckDB single-file contention.** A writer (`ingest_tables`) opening during a reader (`run_select`) on the same file will hit a lock error under two concurrent users.
- **[SERIOUS] Non-atomic writes** across Chroma → SQLite → DuckDB. A crash mid-ingest orphans vectors/tables with no reconciliation or GC; the source is stranded in `parsing`.
- **[SERIOUS] No retry/rate-limit handling on inference.** Retry exists only on the embedding batch. A transient 429 during chat → unhandled 500 → leaked exception.
- **Triple datastore** (SQLite + Chroma + DuckDB) on local files: three consistency boundaries, none transactional, none hosted-ready.

### [BLOCKER] Zero automated tests, zero CI
There is **no test of any kind** anywhere — no `tests/`, no `pytest`, no `.github/`. The load-bearing, fragile logic (offset relocation, page/section resolution, citation renumbering, the SQL guard) is entirely unverified. For a product whose entire value is *citation accuracy*, shipping it with no regression net is the single clearest "prototype, not product" tell. (The `first-occurrence` highlight bug in §2a is exactly the kind of thing a test would catch.)

### Tech-debt / correctness misc
- **[SERIOUS]** `tenacity` is imported (`ingest/pipeline.py:15`) but **not in `requirements.txt`** — present transitively today; a clean install could break ingestion at import time.
- **[MINOR]** Frontend swallows errors: `ask()` has no `catch` (a failed question vanishes silently); list errors look identical to an empty account; toggle reverts silently.
- **[MINOR]** UI ships non-functional shells — "Generate audio overview (~12 min two-host conversation)", notes, threads, copy/pin/save, ⌘K, "Open original". The README *honestly* labels these "Deferred (stretch)," but in a live demo the un-labelled CTAs read as working features — a credibility risk in an eval. (Audio overview is, pointedly, NotebookLM's flagship.)
- **[MINOR]** `/health` reports `provider_ready:true` unconditionally for Ollama (never pings the daemon). DuckDB table-name slug collisions possible. `notebook.updated_at`/`snippet`/`source_count` drift (not touched on source add). Next 14.2 sync `params` access breaks on the Next 15 upgrade.

---

## 5. Product assessment

**Real value prop vs NotebookLM (honest version).** NotebookLM is free, Google-hosted, polished, has audio overviews and a massive context window, and is improving fast. DeepNotes cannot win on polish, price, or features. It has exactly **two** things NotebookLM structurally cannot offer:
1. **Data sovereignty** — self-hosted / air-gapped, originals discarded after parse (verified true), fully-local Ollama mode. This is the *only* defensible wedge.
2. **Real spreadsheet reasoning** — SQL-grade aggregation/filtering, verified better than NotebookLM's text-flattening for numeric/tabular questions.

**Is the spreadsheet differentiator compelling or a gimmick?** Compelling *for a niche* (finance/ops/analysts), genuinely well-executed — but it's a commoditizing feature (text-to-SQL is becoming table stakes), and right now it **breaks the citation and scoping promises** that are the rest of the product's identity. As shipped it's a strong demo, not a moat.

**Who is the user, and would they switch?** A consumer/prosumer will not leave free, polished NotebookLM. The only realistic buyer is someone who **cannot legally/technically use cloud tools**: legal, healthcare, public sector, defense, regulated finance. That's the wedge — and it's a go-to-market motion (compliance, procurement, SOC2), not a tech advantage. Today the product cannot serve that buyer: no auth, no multi-tenancy, no OCR for their scanned documents, no reliability, and a query engine that reads arbitrary host files.

**What's missing to be paid/relied-on daily:** auth + multi-tenancy; OCR; reliability under concurrency; the differentiator shipped *with* citations and cross-source synthesis; document management/export; observability; and removing or finishing the implied-but-absent features.

**Biggest product risks:** (1) the only durable wedge (sovereignty) is a slow regulated-sales GTM, and none of the compliance scaffolding exists; (2) low technical moat — it's a thin, well-made wrapper over OSS that the incumbents are commoditizing; (3) feature-parity theater (audio CTA) erodes trust in a real evaluation.

---

## 6. The full finding list, ranked

### BLOCKERS (must fix before any deployment beyond one trusted user)
1. ~~**Arbitrary file read / secret exfiltration via text-to-SQL** (proven — leaked the live API key).~~ **✅ FIXED & re-verified 2026-05-29** (DuckDB `enable_external_access=false` + `lock_configuration=true`). §3
2. **No authentication / authorization / multi-tenancy** — everything is open. §3
3. **Event loop freezes on ingest** (proven — 0.9ms → 25.8s) — no concurrency survives. §4
4. **Zero tests / zero CI** on citation-accuracy-critical logic. §4

### SERIOUS
5. ~~Spreadsheet answers have **no citations** (`grounded:true`, 0 cites) — differentiator breaks the headline promise.~~ **✅ FIXED & re-verified 2026-05-29.** §2b
6. ~~Spreadsheet path **ignores per-request `source_ids`** scoping.~~ **✅ FIXED & re-verified 2026-05-29.** §2b
7. **No cross-source (table+prose) synthesis.** §2b
8. **OCR disabled** — scanned PDFs silently accepted as empty. §2c
9. Global `Settings` mutation race; DuckDB single-file lock contention. §4
10. Non-atomic writes across the three datastores; no GC/reconciliation. §4
11. No retry/rate-limit on inference → 500s + leaked exceptions. §4
12. Raw exception strings leaked to client. §3
13. `tenacity` missing from `requirements.txt`. §4

### MINOR
14. Empty-string question is answered (no validation). §2d
15. Duplicate uploads create identical sources (dup tables/vectors). §2d
16. Stale citations clickable after delete → `/passage` 404. §2d
17. `locate.py` first-occurrence `find()` — latent mis-highlight. §2a
18. Frontend silently swallows errors (`ask()` no catch). §4
19. UI ships non-functional feature shells (audio/notes/threads/…). §4
20. `MAX_FILE_BYTES` checked after full in-memory read. §3
21. `/health` Ollama readiness is fake; table-name slug collisions; notebook metadata drift; Next 15 `params` break. §4
22. Rotate the exposed `GEMINI_API_KEY`. §3

---

## 7. Verdict & funding decision

**This is an impressive solo-built prototype and a credible founder/CTO signal — not a fundable company yet.** The engineering taste is real: the citation system works, the spreadsheet reasoning beat traps I expected to break it, sovereignty is genuinely implemented, and the author demonstrably understands the gaps. But there is **no moat** (a thin, commoditizing OSS wrapper), the only defensibility is a GTM (sovereignty) with none of its scaffolding built, and the artifact is **single-user-demo grade** with a real security hole.

**Decision: I would not write a priced seed round today.** I would offer at most a **small pre-seed / angel check as a bet on the founder**, or pass and stay in close contact — gated on the milestones below. The bar to clear is not "make the demo nicer"; it's "prove a person with a sovereignty constraint will pay, and prove the system can be trusted with their data."

**Conditions / milestones before a real check:**
1. **Security baseline:** sandbox the SQL engine (no filesystem/network), and add auth + multi-tenancy with row-level ownership.
2. **Prove the wedge:** one paid pilot with a genuinely sovereignty-constrained buyer (a law firm, hospital, or agency) using it on real documents. This is the single most important *business* milestone — it's the only thing that separates this from "a nicer self-hosted NotebookLM clone."
3. **Make the differentiator whole:** spreadsheet answers **with** citations, respecting scope, plus cross-source synthesis. This is the actual unique value — it must be bulletproof, not a demo.
4. **Reliability:** background ingestion worker, concurrency that doesn't freeze, and a test+CI suite on the citation/SQL core.
5. **OCR** (the target buyer's documents are scanned), and remove/finish the implied-but-absent features.

**The single most important thing to fix next:** **sandbox the text-to-SQL execution and restore the citation guarantee on spreadsheet answers.** The file-read hole is a hard deployment blocker that directly *negates the sovereignty pitch* (a "data never leaves your server" product whose query engine reads any file on that server), and the citation-less spreadsheet path quietly dismantles the central promise on the exact feature meant to differentiate it. Fix those two and the product is at least *internally coherent*; until then it argues against itself.

---

### Appendix — reproduction notes
- Tests were run live against `:8100`. I created a throwaway notebook **"DD Test"** (delete it to clean up) and left a few probe messages in the existing **"Q4 Sales Analysis"** notebook (harmless).
- Test assets: messy XLSX with computed ground truth, a two-column PDF (ACL BERT), a 100-page PDF (GPT-4 report), and a synthetic scanned/image-only PDF.
- The citation ratio came from the app's own `deepnotes.citations` logger (`method=exact|normalized|parent_fallback`), not estimation.
- The file-read exfiltration was executed against the real `app.spreadsheet.store.run_select` code path, not a mock.
