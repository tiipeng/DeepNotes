# Local / Sovereign Mode (Ollama)

Run DeepNotes **fully on your own hardware** — no data leaves the server. This is the
sovereignty differentiator: same product, but parsing, embeddings, retrieval, and the
LLM all run locally. Suited to GDPR / public-sector / air-gapped deployments.

It works because the backend talks to models through a **provider abstraction**
(`app/providers/`). Swapping Gemini for Ollama is a config change — no app-logic change.

## Prerequisites

```bash
# 1. Install + run Ollama (https://ollama.com)
ollama serve                       # daemon on http://localhost:11434

# 2. Pull a chat model + an embedding model
ollama pull llama3.1               # or any chat model (e.g. qwen2.5)
ollama pull nomic-embed-text       # embeddings

# 3. Python integration packages (already in requirements.txt)
uv pip install llama-index-llms-ollama llama-index-embeddings-ollama
```

## Configure

Set these in `backend/.env` (or the environment):

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.1
OLLAMA_EMBED_MODEL=nomic-embed-text

# Use storage separate from any cloud-mode install — see note below.
DATABASE_URL=sqlite:///./deepnotes_local.db
CHROMA_DIR=./chroma_local

# GEMINI_API_KEY is not needed and can be left unset.
```

Then run the backend as usual. `GET /health` will report `provider: ollama`.

## Important: embeddings are model-specific

A vector index is only valid for the embedding model that produced it. You **cannot mix**
Gemini and Ollama embeddings in one Chroma collection (different models, different
dimensions). So a deployment commits to one embedding model:

- Keep a **separate `CHROMA_DIR` + `DATABASE_URL`** per provider (as above), **or**
- Re-ingest your sources after switching providers.

Pick the provider before ingesting; everything downstream (ingest + chat) then uses it
consistently.

## Verified

Ran the backend with `LLM_PROVIDER=ollama`, `OLLAMA_LLM_MODEL=qwen2.5-coder:7b-instruct`,
`OLLAMA_EMBED_MODEL=nomic-embed-text`, and **no `GEMINI_API_KEY`**. Ingested a document and
asked a question — got a grounded answer with citations, with all inference on localhost.
No outbound calls to any cloud API.
