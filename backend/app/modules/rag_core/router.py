"""
app/modules/rag_core/router.py
Chat endpoints, streaming responses (SSE), and vector search inspection.
"""


import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.core.database import get_session
from app.core.privacy import redact_pii, validate_llm_output
from app.core.rate_limit import limiter
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.models import User
from app.modules.rag_core.engine import (
    LLMUnavailableError,
    SearchResult,
    VectorStore,
    degraded_answer,
    build_prompt,
    get_llm_client,
    get_vector_store,
)
from app.modules.rag_core.router_agent import (
    classify_intent,
    enrich,
    parse_logged_sets,
)
from app.modules.user.service import (
    append_message,
    create_session,
    get_recent_history,
    get_session_or_404,
)

router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    intent: str
    answer: str
    sources: List[Dict[str, Any]]
    pending_action: Optional[Dict[str, Any]] = None
    ai_status: str = "ok"  # "ok" or an LLMUnavailableError reason (degraded answer)


@router.get("/debug/search", summary="Debug vector retrieval (only when DEBUG=true)")
def debug_search(
    q: str = Query(..., description="Query text"),
    category: Optional[str] = Query(None, description="Category: 'nutrition' or 'exercise'"),
    k: int = Query(5, ge=1, le=20),
) -> List[Dict[str, Any]]:
    """Inspect raw vector search results without invoking an LLM. Active only when DEBUG=true."""
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug endpoint is disabled in production settings",
        )

    store = get_vector_store()
    if category:
        results = store.search(q, category=category, k=k)
    else:
        results = store.search_all(q, k=k)

    return [r.to_dict() for r in results]


def _resolve_session_id(
    session: Session,
    session_id: Optional[str],
    first_message: str,
    user_id: int,
) -> str:
    """Return an existing session owned by the user, or create one titled from the first 6 words."""
    if session_id:
        return str(get_session_or_404(session, session_id, user_id).id)

    words = first_message.strip().split()
    title = " ".join(words[:6]) if words else "New Chat"
    new_sess = create_session(session, user_id, title=title)
    return str(new_sess.id)


@dataclass
class _ChatTurn:
    """Everything needed to answer one chat message (shared by the JSON and SSE endpoints)."""

    session_id: str
    intent: str
    system_prompt: str
    llm_messages: List[Dict[str, str]]
    passages: List[SearchResult]
    sources: List[Dict[str, Any]]
    pending_action: Optional[Dict[str, Any]]


def _prepare_turn(session: Session, user: User, req: ChatRequest) -> _ChatTurn:
    """classify -> enrich (exact math) -> retrieve (category-isolated) -> prompt with history."""
    session_id = _resolve_session_id(session, req.session_id, req.message, user.id)  # type: ignore[arg-type]
    # Only the redacted text ever reaches the LLM; the raw message stays in our database.
    safe_message = redact_pii(req.message, known_names=[user.full_name])

    intent = classify_intent(safe_message).name
    enriched = enrich(intent, req.message, session=session, user_id=user.id)  # type: ignore[arg-type]

    store = get_vector_store()
    passages: List[SearchResult] = []
    try:
        if enriched.retrieval_category in ("nutrition", "exercise"):
            passages = store.search(safe_message, category=enriched.retrieval_category, k=5)
        else:
            passages = store.search_all(safe_message, k=5)
    except FileNotFoundError:
        logger.warning("Vector index missing; answering without retrieved passages.")

    pending_action = None
    if intent == "workout_logging":
        pending_act = parse_logged_sets(req.message)
        if pending_act:
            pending_action = pending_act.model_dump()

    # Conversation memory: previous turns of this session (redacted) + the new message.
    history = [
        {"role": m["role"], "content": redact_pii(m["content"], known_names=[user.full_name])}
        for m in get_recent_history(session, session_id, limit=6)
    ]
    history.append({"role": "user", "content": safe_message})

    system_prompt, llm_messages = build_prompt(
        intent=intent,
        facts=enriched.user_facts,
        numbers=enriched.numbers,
        passages=passages,
        history=history,
    )

    sources = [
        {
            "source": p.source,
            "page": p.page,
            "score": round(p.score, 4),
            "text": (p.text[:220] + "...") if len(p.text) > 220 else p.text,
        }
        for p in passages
    ]
    return _ChatTurn(session_id, intent, system_prompt, llm_messages, passages, sources, pending_action)


def _persist_turn(session: Session, user: User, turn: _ChatTurn, user_message: str, answer: str) -> None:
    append_message(session, session_id=turn.session_id, user_id=user.id, role="user", content=user_message)  # type: ignore[arg-type]
    append_message(
        session,
        session_id=turn.session_id,
        user_id=user.id,  # type: ignore[arg-type]
        role="assistant",
        content=answer,
        sources=turn.sources or None,
    )


@router.post("", response_model=ChatResponse, summary="Send a chat message")
@limiter.limit("20/minute")
def chat_endpoint(
    request: Request,
    req: ChatRequest,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> ChatResponse:
    """Full RAG chat pipeline: classify -> enrich -> retrieve -> prompt -> LLM -> validate -> persist."""
    turn = _prepare_turn(session, user, req)

    ai_status = "ok"
    try:
        raw_answer = get_llm_client().complete(messages=turn.llm_messages, system=turn.system_prompt)
        answer = validate_llm_output(raw_answer)
        if not answer:
            raise LLMUnavailableError("blocked")
    except LLMUnavailableError as err:
        logger.warning("LLM unavailable for chat: %s", err)
        ai_status = err.reason
        answer = degraded_answer(err, turn.passages)

    _persist_turn(session, user, turn, req.message, answer)

    return ChatResponse(
        session_id=turn.session_id,
        intent=turn.intent,
        answer=answer,
        sources=turn.sources,
        pending_action=turn.pending_action,
        ai_status=ai_status,
    )


@router.post("/stream", summary="Streaming SSE chat response")
@limiter.limit("20/minute")
async def chat_stream_endpoint(
    request: Request,
    req: ChatRequest,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
):
    """Server-Sent Events streaming endpoint yielding meta, sources, tokens, pending_action, done."""
    turn = _prepare_turn(session, user, req)
    client = get_llm_client()

    async def event_generator() -> AsyncIterator[Dict[str, str]]:
        parts: List[str] = []
        ai_status = "ok"

        yield {"event": "meta", "data": json.dumps({"session_id": turn.session_id, "intent": turn.intent})}
        yield {"event": "sources", "data": json.dumps(turn.sources)}

        try:
            async for token in client.stream(messages=turn.llm_messages, system=turn.system_prompt):
                parts.append(token)
                yield {"event": "token", "data": json.dumps({"token": token})}
        except LLMUnavailableError as err:
            logger.warning("LLM unavailable for streamed chat: %s", err)
            ai_status = err.reason
            if not parts:
                fallback = degraded_answer(err, turn.passages)
                parts.append(fallback)
                yield {"event": "token", "data": json.dumps({"token": fallback})}
        except Exception as exc:  # noqa: BLE001 — never leave the client hanging
            logger.error("Chat streaming failed: %s", exc, exc_info=True)
            ai_status = "provider_error"
            if not parts:
                fallback = degraded_answer(LLMUnavailableError("provider_error"), turn.passages)
                parts.append(fallback)
                yield {"event": "token", "data": json.dumps({"token": fallback})}

        if turn.pending_action:
            yield {"event": "pending_action", "data": json.dumps(turn.pending_action)}

        answer = validate_llm_output("".join(parts), fallback="".join(parts))
        try:
            _persist_turn(session, user, turn, req.message, answer)
        except Exception as db_err:  # noqa: BLE001
            logger.error("Failed to persist chat turn: %s", db_err)

        yield {"event": "done", "data": json.dumps({"status": "complete", "ai_status": ai_status})}

    return EventSourceResponse(event_generator())
