# Projektplan — Self-hosted NotebookLM-Klon

## Produktvision
Ein self-hosted, datensouveräner NotebookLM-Klon: "Chat mit deinen Quellen", bei dem die KI ausschließlich aus den hochgeladenen Dokumenten antwortet und jede Aussage klickbar zur exakten Stelle in der Quelle zurückverweist. Dünn auf Open-Source gebaut, aber so architektiert, dass es zu einem echten Produkt skalierbar ist.

## Leitprinzip
Maximal Open-Source nutzen, minimal selbst implementieren. Eigener Code = UI + Citation-Highlighting + Verdrahtung. Alles Schwere wird an Bibliotheken delegiert.

---

## Stack
- **Frontend:** Next.js 14 (App Router, TS) + Tailwind + shadcn/ui → Vercel oder lokal
- **Backend:** Python + FastAPI → Container-Host (HF Spaces / Render / Cloud Run) oder lokal
- **Parsing:** Docling (PDF, DOCX, PPTX, XLSX, HTML, OCR — alles in einer Lib)
- **RAG + Citations:** LlamaIndex (CitationQueryEngine)
- **Vektorstore:** Chroma lokal (oder pgvector/Supabase)
- **DB/Storage:** Supabase Free oder lokal — nur geparstes Markdown + Embeddings + Metadaten speichern, nicht die Originale
- **LLM/Embeddings:** Gemini (Free-Tier) oder Claude, hinter einer Abstraktion (Ollama später einsteckbar)
- **Audio (Stretch):** Podcastfy

## Die 5 Herausforderungen — Lösung
| Challenge | Lösung | OSS-Anteil |
|---|---|---|
| Citations / Grounding | LlamaIndex + eigenes Highlight-Glue | ~80% |
| Document Parsing | Docling | 100% |
| Chunking | Docling / LlamaIndex | 100% |
| Audio Overview | Podcastfy (Stretch) | 100% |
| Scope-Disziplin | du | 0% |

## Limits (Free-Tier-tauglich)
- Max. Dateigröße: 10 MB (großzügig: 20)
- Max. Quellen pro Notebook: 5–10
- Max. Seiten gesamt: ~200
- Erlaubte Typen: PDF, TXT, URL + DOCX/PPTX/XLSX als Parität
- Ingestion seriell, nicht parallel (Gemini-Rate-Limits + Retry/Backoff)
- Originaldateien nach Parsing verwerfen, nur Markdown + Embeddings + Metadaten behalten

## Deployment
- **Default: lokal** für die Demo (im Loom localhost zeigen — legitim, spart Free-Tier-Schmerz)
- **Optionaler Live-Link:** Frontend→Vercel, Python-Backend→Container-Host (Vercel kann das Backend NICHT hosten: 250 MB / 10s-Limit), Supabase optional
- Supabase Free: 500 MB DB, 1 GB Storage, pausiert nach 7 Tagen Inaktivität → vor Abgabe unpausieren

## Differentiator (statt MS-Formate — die kann NotebookLM längst)
1. **Datensouveränität / Self-Hosted + Ollama-Modus** (Skalierungs-Wette, passt zur Consulting-Positionierung, DSGVO/Public-Sector)
2. **Echtes Spreadsheet-Reasoning** über XLSX (konkretes, demobares Extra-Feature; echte NotebookLM-Schwäche)

---

## Fahrplan — Step by Step

### Phase A — Vorbereitung (~30 Min, lokal)
1. Monorepo anlegen: `/frontend`, `/backend`, `/docs`
2. Gemini-API-Key besorgen, `.env.example` anlegen, `.env` in `.gitignore`
3. Handover-Dateien nach `/docs`: BUILD_PROMPT.md, DESIGN_PROMPT.md, PLAN.md

### Phase B — Design (~30–45 Min, Claude-Chat mit Artifacts)
4. DESIGN_PROMPT in Claude-Chat → Hi-Fi-Mockup
5. 1–2 Iterationen bis Layout + Citation-Interaktion sitzen
6. Screenshot(s) speichern (visuelles Ziel für Claude Code)
> Checkpoint: UI steht und ist erklärbar.

### Phase C — Spike (~30 Min, Claude Code) — kritischer Gate
7. BUILD_PROMPT + Mockup-Screenshot an Claude Code, Plan-Mode an
8. Plan lesen + absegnen, Dependencies prüfen
9. Phase 0: Wegwerf-Skript, eine PDF → Docling → LlamaIndex → Antwort mit Citations + Source-Spans im Terminal
> Go/No-Go: Brauchbare Spans? Ja → Projekt machbar. Nein → jetzt umplanen.

### Phase D — MVP in dünnen Scheiben (Claude Code, phasenweise)
10. Phase 1 — Contract + Scaffold: Datenmodell + API-Form, FE+BE-Skelett, Healthcheck → run → commit
11. Phase 2 — Ingestion: Upload→Parse→Chunk→Embed→Store, Metadaten prüfen → commit
12. Phase 3 — Grounded Chat: Retrieval + Inline-[n]-Citations; "nicht gefunden"-Fall testen → commit
13. Phase 4 — Citation-UX: Klick → Quelle öffnen → Highlight + Scroll → commit
> Checkpoint: Definition of Done. Notebook → PDFs hoch → fragen → Citation klicken → exakte Stelle. Ab hier alles Bonus.

### Phase E — Differentiator + Stretch (nur wenn MVP läuft)
14. Spreadsheet-Reasoning (XLSX als abfragbare Daten) → commit
15. Office-Parität absichern (docx/pptx via Docling)
16. Souveränitäts-Abstraktion: LLM-Layer Ollama-fähig bauen, im README dokumentieren
17. Audio (Podcastfy) + Notizen-Panel — nur falls Zeit; eher weglassen als halbfertig

### Phase F — Polish & Abgabe
18. README: Architektur-Diagramm, OSS→Challenge-Mapping, Setup, Limits, Differentiator, "so würde ich skalieren"
19. Loom: Design → Plan → Spike (Gate-Moment) → Build → Citation-Demo (Höhepunkt) → Differentiator → Architektur-Entscheidungen erklären
20. Repo aufräumen: .env.example, Secrets raus, frisch klonen + Setup testen
21. E-Mail-Antwort mit Repo-Link + Loom-Link

## Definition of Done (MVP)
Notebook anlegen → 2–3 PDFs hochladen → Frage stellen → Antwort ausschließlich aus den Quellen mit Inline-Citations → Citation klicken → exakte Stelle in der Quelle.

## Kritische Stellen, an denen Projekte kippen
- **Spike-Gate (Schritt 9)** nicht überspringen — erspart tagelange Sackgassen
- **Scope-Versuchung (Phase E)** — jedes Extra gegen "macht das den Loom besser?" prüfen
