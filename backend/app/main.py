from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routers import chat, notebooks, notes, settings as settings_router, sources
from .runtime import chat_config
from .schemas import HealthRead


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="DeepNotes API", version="0.1.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notebooks.router)
app.include_router(sources.router)
app.include_router(chat.router)
app.include_router(notes.router)
app.include_router(settings_router.router)


@app.get("/health", response_model=HealthRead)
def health():
    s = get_settings()
    cfg = chat_config()
    provider = (cfg.get("chat_provider") or "gemini").lower()
    model = (cfg.get("chat_model") or "").strip()
    if not model:
        model = s.gemini_llm_model if provider == "gemini" else (
            s.ollama_llm_model if provider == "ollama" else ""
        )
    return HealthRead(
        status="ok",
        provider=provider,  # the active CHAT provider
        llm_model=model or provider,
        embed_model=s.gemini_embed_model if s.llm_provider == "gemini" else s.ollama_embed_model,
        provider_ready=bool(s.gemini_api_key) if s.llm_provider == "gemini" else True,
    )
