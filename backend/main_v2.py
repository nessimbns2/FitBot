"""
backend/main_v2.py
Fitness Coach — FastAPI application entrypoint.

Run locally:
    fastapi dev backend/main_v2.py
    # or
    uvicorn backend.main_v2:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.rate_limit import limiter
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.router import router as auth_router
from app.modules.user.router import router as user_router
from app.modules.nutrition.router import router as nutrition_router
from app.modules.exercises.router import router as exercises_router
from app.modules.progressive_overload.router import router as overload_router
from app.modules.rag_core.router import router as chat_router


# ── Lifespan ─────────────────────────────────────────────────────────────────


def _warm_up_vector_store() -> None:
    try:
        from app.modules.rag_core.engine import get_vector_store

        store = get_vector_store()
        for category in ("nutrition", "exercise"):
            store.search("warm up", category=category, k=1)
    except Exception:  # noqa: BLE001 — warm-up is best effort; requests still work lazily
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    # --- startup ---
    from app.core.database import init_db
    init_db()
    from app.modules.exercises.catalog import load_catalog
    load_catalog()
    if not settings.is_sqlite:
        # Warm up the embedding model + FAISS indexes in the background so the first
        # chat message doesn't pay the cold-start cost (~10-30 s on Windows).
        import threading

        threading.Thread(target=_warm_up_vector_store, daemon=True).start()
    yield
    # --- shutdown ---


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Fitness Coach API",
    description=(
        "A coaching API that combines exact math (TDEE, progressive overload) "
        "with retrieval-augmented answers from a library of PDF guides."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────

# Public: register / login. Everything else requires a valid bearer token.
app.include_router(auth_router)

_auth_required = [Depends(get_current_user)]
app.include_router(user_router, dependencies=_auth_required)
app.include_router(nutrition_router, dependencies=_auth_required)
app.include_router(exercises_router, dependencies=_auth_required)
app.include_router(overload_router, dependencies=_auth_required)
app.include_router(chat_router, dependencies=_auth_required)

# ── Health check ─────────────────────────────────────────────────────────────


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Liveness probe — always returns 200 OK when the process is running."""
    return {"status": "ok"}


@app.get("/api/health/ready", tags=["health"])
def readiness_check() -> dict:
    """Readiness probe: database reachable, LLM key configured, vector indexes present."""
    from pathlib import Path

    from sqlalchemy import text

    from app.core.database import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unreachable"

    vector_dir = Path(settings.VECTORSTORE_DIR)
    indexes = {cat: (vector_dir / f"{cat}.faiss").exists() for cat in ("nutrition", "exercise")}
    return {
        "database": database,
        "database_engine": "sqlite" if settings.is_sqlite else "postgresql",
        "llm_configured": bool(settings.LLM_API_KEY.strip()),
        "vector_indexes": indexes,
    }


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main_v2:app", host=host, port=port, reload=False)

