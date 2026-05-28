# Design a high-fidelity visual mockup: a NotebookLM-style "chat with your sources" app

You are a senior product designer. Produce a **high-fidelity, non-functional visual mockup** as a single self-contained React + Tailwind artifact. This is a visual reference for engineering — it does not need to work, it needs to look like the finished product. Use realistic mock content, never lorem ipsum.

## Visual craft (this is the point — don't ship a generic template)
- Clean, modern, confident. Avoid the default "AI app" look.
- Commit to and apply consistently: a restrained color palette (1 accent + neutrals), one type scale, consistent spacing rhythm, subtle depth/borders. Light mode as primary.
- Desktop-first, ~1280px wide. Show micro-detail: icons, static hover/selected states, thoughtful empty states.

## Screens (all in ONE artifact, switchable via top tabs)
1. **Notebook dashboard** — a grid of notebook cards (title, source count, last-edited, a colored cover accent) plus one "＋ New notebook" card.

2. **Notebook view — the core screen. Three columns:**
   - **Left · Sources:** an "Add source" action at the top, then a list of 4–5 realistic sources (PDF and URL icons, real-sounding titles e.g. research papers, page counts). Each source has a checkbox to include/exclude it from the chat. Show one source as "selected".
   - **Center · Chat:** a scrollable conversation. Show a user question and an assistant answer that contains **inline citation chips** rendered as small clickable pills (e.g. a superscript ⟦1⟧ ⟦2⟧), with a "Sources" row beneath the answer. Also include the empty-state variant: a friendly prompt with 3 suggested starter questions. A sticky input box pinned to the bottom.
   - **Right · Studio:** an "Audio Overview" card (a generate button, plus the generated state with a simple audio player), and a "Notes" section showing 1–2 saved note cards.

3. **Citation open state — the signature interaction:** show what happens when a user clicks a citation chip. The source opens (reading pane or side modal) with the **exact cited passage highlighted and scrolled into view**. Make this unmistakable — it's the feature that defines the product.

## Constraints
- One self-contained artifact. Mock data only — no API calls, no backend, no real file handling.
- Content must feel real: believable paper titles, a genuinely grounded-sounding answer whose claims map to the citation chips.
- Don't annotate inside the UI. Put any rationale in text outside the artifact.

## Deliverable
Render the artifact, then give me a 3–4 line summary of the design decisions (palette, typeface, layout rationale) that I can paste straight into the engineering handoff.
