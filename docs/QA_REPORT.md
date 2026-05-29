# DeepNotes — QA Pass (logic + UX/UI)

**Method:** Live app driven over Tailscale (`100.114.191.71` — frontend `:3100`, backend `:8100`).
Logic exercised through the real chat/stream API and the actual citation pipeline; UI driven with
Playwright + system Chrome (real clicks, screenshots, viewport resizing). This is a find-problems
pass — nothing was fixed.

**Test notebook:** "QA — Mixed" with 4 live sources — PDF (a 3-page sleep/memory paper), XLSX
(`sales.xlsx`), a web article (Wikipedia: Retrieval-augmented generation), and a YouTube video
(3Blue1Brown — neural networks). Plus throwaway notebooks for empty / error / delete / backend-down.

---

## Prioritized issues

### BLOCKER
None found. Core flows (grounded RAG, refusal discipline, scoping, citations, streaming) hold up.

### MAJOR

**M1 — Long / front-loaded inputs misroute to "conversational" (intent classifier truncates the question).**
- **Did:** Sent a long message whose factual question sits at the end after a chatty preamble: `"I was reading a lot about deep learning and I keep wondering, …(×30)… so what is multi-head attention?"`
- **Happened:** `intent=conversational` → a chatty "It sounds like you're diving deep…" reply; the actual question was never answered or grounded.
- **Should:** Route `factual` and either answer from sources or refuse.
- **Root cause:** `assist.classify_intent` classifies on `q[:500]` only — anything past 500 chars is invisible to the router, so a question after a long preamble is judged on the preamble alone.
- **Severity:** Major (silent wrong-mode answer to a legitimate question; defeats the Sprint-3 router for long/multi-part prompts).

**M2 — 3-column layout overflows on any window narrower than ~1000px.**
- **Did:** Resized the notebook view to 820px wide.
- **Happened:** `document.scrollWidth = 1088` vs `clientWidth = 820` → horizontal scrollbar; the Studio column is clipped ("Audio o…", "Save an ans…") and the top bar's right controls (health pill, Settings) are pushed off-screen. See `screenshots 10_narrow_820`.
- **Should:** Collapse/reflow gracefully (stack columns or hide Studio) with no horizontal scroll.
- **Root cause:** `.dn-three-col` is a fixed `320px 1fr 320px` grid and `.dn-topbar` a fixed `280px 1fr 280px` grid; neither has a responsive breakpoint.
- **Severity:** Major (looks broken on laptops <1000px, split-screen, tablets).

**M3 — Cross-source (table + prose) questions silently refuse.**
- **Did:** In the mixed notebook asked `"How does total West region revenue compare to the sources' findings on sleep spindles?"` (spans the XLSX and the PDF).
- **Happened:** `intent=factual`, `grounded=false` → *"I couldn't find an answer to that in your sources."*
- **Should:** Combine the table value with the prose finding (or at least answer the part it can). Both pieces exist in the notebook.
- **Why it matters:** Directly contradicts the "a notebook can mix PDF + XLSX + web + YouTube" promise — the natural mixed question reads as a grounding failure. (Known architectural gap: chat routes to exactly one path — table OR RAG — never both.)
- **Severity:** Major (on-mission capability gap; not a quick fix).

### MINOR

**m4 — Synthesis / broad answers over-cite.**
- **Did:** `"tell me more"` (routed to synthesis).
- **Happened:** **15** citation chips in one answer.
- **Should:** Sparse, claim-level citing like the factual path now does (factual "what is a transformer" produces ~4). The Sprint-3 density tuning didn't fully take on the synthesis template / broad top_k=20.
- **Severity:** Minor (readability).

**m5 — Source-internal bracketed references leak into answers as text.**
- **Did:** Synthesis/RAG answers drawn from the Wikipedia source.
- **Happened:** Strings like `[64, 139]` and `[51, 267]` appear in the prose — these are the *source's own* reference markers, not DeepNotes citations. They render as plain text and look like broken/duplicate citation chips.
- **Should:** Strip or neutralize source-internal `[n]`/`[n, m]` markers so only real DeepNotes citations render as chips.
- **Severity:** Minor (looks buggy; erodes trust in the citation UI).

**m6 — Deleting a source leaves dangling, clickable citations in prior answers.**
- **Did:** Asked a question (got 2 citations), deleted the cited source, reopened the notebook, clicked the citation chip.
- **Happened:** Chip still renders and is clickable; drawer opens titled **"(deleted source)"**, shows the stored snippet as the highlight but **no surrounding context** (the live `/passage` call 404s); "Open original" still shown. See `30_stale_citation`.
- **Should:** Either visually mark/disable citations whose source was removed, or note "source removed from this notebook." Current behavior is graceful (no crash) but misleading.
- **Severity:** Minor (data-integrity/UX edge; orphaned `Citation` rows persist after source delete).

**m7 — "Open original" button in the citation drawer is dead and misleading.**
- **Did:** Opened the citation drawer for any source.
- **Happened:** "Open original" button present with no handler; and originals are **discarded after parsing** by design, so it can never work.
- **Should:** Remove it, or hide it (no original is retained).
- **Severity:** Minor (dead control; contradicts the sovereignty "originals discarded" design).

**m8 — Ingestion-error message leaks the internal temp filename.**
- **Did:** Uploaded a corrupt `.pdf`.
- **Happened:** Source row shows `COULDN'T PROCESS` (good) with reason *"Input document tmpr49tifi7.pdf is not valid."* — exposing the server's temp filename instead of the user's filename. See `21_error`.
- **Should:** Show the original filename (or a clean reason).
- **Severity:** Minor (polish / mild info leak).

**m9 — Esc does not close the citation drawer.**
- **Did:** Opened the drawer, pressed Escape.
- **Happened:** Drawer stayed open (`drawerClosedByEsc=false`).
- **Should:** Esc closes it (standard for a modal/drawer). Close affordances (scrim click, ✕) do work.
- **Severity:** Minor (interaction nicety; the spec explicitly lists Esc).

**m10 — German question → English answer (inconsistent language mirroring).**
- **Did:** `"Was ist Retrieval-Augmented Generation?"`
- **Happened:** Correct, grounded answer (5 citations) — but in **English**. (Earlier sprints answered a German question in German.)
- **Should:** Mirror the user's language consistently.
- **Severity:** Minor.

### POLISH

- **p11 — Pluralization:** header pill reads **"1 sources"** (and composer scope "1 sources") — no singular form. (`21_error`, `01_dashboard`).
- **p12 — YouTube sources are indistinguishable from web pages** — both show kind `URL` with the link icon. A YouTube glyph/label would help users tell them apart.
- **p13 — TTFT for factual is ~3–4s** because the intent-classifier LLM call runs *serially before* retrieval. Covered by the "Searching your sources…" indicator, but it adds a noticeable beat vs. the old direct path.
- **p14 — Whitespace-only message** returns a raw SSE `error` event ("Ask a question to get started."). The composer already blocks sending it, so impact is low, but the API path is reachable directly.
- **p15 — "New notebook" button/card stays visually enabled during the backend-down state** (`loadError`); clicking can't succeed.

---

## What's solid (passed)

- **Intent routing — core cases:** `hello`→conversational (no refusal), `give me an example prompt`→meta with grounded prompt ideas, `summarize this`→synthesis, factual→grounded, `capital of France`→refusal. The **"not found" refusal appears ONLY on the factual path** in every case tested — never on conversational/meta/synthesis. Emoji-only → conversational; bare `?` → meta (sensible).
- **Grounding discipline:** genuinely-absent facts refuse; partial/answerable facts answer. No hallucinated answers observed.
- **Source scoping (the big one):** unchecking a source removes it from **both** RAG and table queries — verified: unchecked XLSX → table question returns "not found"; unchecked web → RAG question on that topic returns "not found"; re-checking restores both.
- **Citation precision:** across PDF + web + YouTube, **24/24 cited spans resolved by exact match (100%, 0 parent-fallback)**, median span ~196 chars (sentence-level). **XLSX row-level citations land on exactly the right rows** (East-region query → highlight = 12 East rows, 0 others, exact offset). YouTube citations carry timestamp sections (`[mm:ss]`); web carry heading sections.
- **Citation drawer:** highlight centered in view with real surrounding context; page + section header matches the highlighted text; works for every source type; open feels snappy. (`05_drawer`, `07`)
- **Streaming feel:** clear "Searching your sources…" → streamed prose → citation chips + follow-ups attach on completion. No layout jump observed, **no console or page JS errors** across all flows.
- **Sprint-3 UI is native, not bolted-on:** the persistent Overview block, starter chips, and follow-up chips match the cream/forest serif aesthetic; conversational/meta replies render as normal assistant prose (byline "DeepNotes"), with the muted "not found" styling correctly reserved for the genuine refusal. (`02`, `04`)
- **Follow-ups & summary are grounded & answerable** (e.g. "What generates sleep spindles?"); clicking a suggestion sends it; overview regenerates on source change and reflects all sources without inventing content.
- **Edge states are clear & on-brand:** 0-source (composer disabled, no overview, "Add a source to begin"), ingestion failure ("couldn't process" + reason), backend-down (banner + retry). (`20`, `21`, `23`)
- **Interaction safety:** send disabled mid-stream; "New thread" disabled mid-stream; no double-submit; thread switch guarded during streaming; can't chat in a 0-source notebook.

---

## Single highest-priority fix

**M1 — the intent classifier's 500-char truncation / long-input misroute.** It's a correctness defect in the
feature shipped this very sprint: a legitimate factual question placed after any sizeable preamble (pasted
context, multi-part prompt) is silently answered in the wrong mode instead of being grounded or refused —
quietly undermining the router's whole purpose and the product's grounding promise. It's also a cheap fix
(classify on a smarter slice / the whole message, or heuristically locate the question). Fix this first;
the narrow-window layout overflow (M2) is the top UX fix right behind it, and cross-source answering (M3)
is the top capability gap.

---

### Appendix — repro environment
- Screenshots saved under `/tmp/dnqa/*.png` during the run (dashboard, overview, streaming, answered,
  drawer, narrow-820, hello, empty, error, backend-down, stale-citation).
- Citation ratio + scoping measured against the real pipeline (`app.rag.engine` internals and the live
  `/chat/stream`, `/sources/{id}/passage`, `PATCH /sources/{id}` endpoints).
- QA notebooks created: "QA — Mixed", "QA — Empty", "QA — Error", "QA — Delete" (test artifacts; safe to delete).
