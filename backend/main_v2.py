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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.modules.user.router import router as user_router
from app.modules.nutrition.router import router as nutrition_router
from app.modules.exercises.router import router as exercises_router
from app.modules.progressive_overload.router import router as overload_router
from app.modules.rag_core.router import router as chat_router


# ── Rate Limiter ─────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    # --- startup ---
    from app.core.database import init_db
    init_db()
    from app.modules.exercises.catalog import load_catalog
    load_catalog()
    yield
    # --- shutdown ---


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Fitness Coach API",
    description=(
        "A coaching API that combines exact math (TDEE, progressive overload) "
        "with retrieval-augmented answers from a library of PDF guides."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────

app.include_router(user_router)
app.include_router(nutrition_router)
app.include_router(exercises_router)
app.include_router(overload_router)
app.include_router(chat_router)

# ── Health check ─────────────────────────────────────────────────────────────


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Liveness probe — always returns 200 OK when the process is running."""
    return {"status": "ok"}


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main_v2:app", host=host, port=port, reload=False)

