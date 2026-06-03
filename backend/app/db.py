from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate() -> None:
    """Add columns introduced after initial schema. Idempotent — safe to re-run."""
    from sqlalchemy import text

    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE sources ADD COLUMN guide_json TEXT",
            # Speeds up per-thread message loading (thread switching) and thread listing.
            "CREATE INDEX IF NOT EXISTS ix_messages_notebook_thread "
            "ON messages (notebook_id, thread_id, created_at)",
        ]:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass  # column already exists
        conn.commit()


def init_db() -> None:
    from . import models  # noqa: F401  (register mappers before create_all)

    Base.metadata.create_all(bind=engine)
    _migrate()
