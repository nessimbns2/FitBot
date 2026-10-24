"""
app/modules/rag_core/router.py
Chat endpoints, streaming responses (SSE), and vector search inspection.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.modules.rag_core.engine import (
    SearchResult,
    VectorStore,
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
    get_or_create_default_profile,
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
    user_id: int = 1,
) -> str:
    """Ensure a valid ChatSession exists, creating one with title from first 6 words if needed."""
    if session_id:
        return session_id

    words = first_message.strip().split()
    title = " ".join(words[:6]) if words else "New Chat"
    new_sess = create_session(session, title=title)
    return str(new_sess.id)


@router.post("", response_model=ChatResponse, summary="Send a chat message")
def chat_endpoint(
    req: ChatRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ChatResponse:
    """Full RAG chat pipeline: classify -> enrich -> retrieve -> prompt -> LLM -> persist."""
    user_id = 1
    session_id = _resolve_session_id(session, req.session_id, req.message, user_id=user_id)

    # 1. Classify intent
    intent_res = classify_intent(req.message)
    intent = intent_res.name

    # 2. Enrich context with deterministic math
    enriched = enrich(intent, req.message, session=session, user_id=user_id)

    # 3. Retrieve relevant passages
    store = get_vector_store()
    passages: List[SearchResult] = []
    if enriched.retrieval_category in ("nutrition", "exercise"):
        try:
            passages = store.search(req.message, category=enriched.retrieval_category, k=5)
        except Exception:
            passages = []
    else:
        passages = store.search_all(req.message, k=5)

    # 4. Check for workout logging pending action
    pending_action = None
    if intent == "workout_logging":
        pending_act = parse_logged_sets(req.message)
        if pending_act:
            pending_action = pending_act.model_dump()

    # 5. Build prompt and execute LLM completion
    system_prompt, history_messages = build_prompt(
        intent=intent,
        facts=enriched.user_facts,
        numbers=enriched.numbers,
        passages=passages,
        history=[{"role": "user", "content": req.message}],
    )

    client = get_llm_client()
    answer = client.complete(messages=[{"role": "user", "content": req.message}], system=system_prompt)

    # 6. Format sources
    sources_data = [
        {
            "source": p.source,
            "page": p.page,
            "score": round(p.score, 4),
            "text": (p.text[:220] + "...") if len(p.text) > 220 else p.text,
        }
        for p in passages
    ]


    # 7. Persist messages
    append_message(session, session_id=session_id, role="user", content=req.message)
    append_message(
        session,
        session_id=session_id,
        role="assistant",
        content=answer,
        sources=sources_data if sources_data else None,
    )

    return ChatResponse(
        session_id=session_id,
        intent=intent,
        answer=answer,
        sources=sources_data,
        pending_action=pending_action,
    )


@router.post("/stream", summary="Streaming SSE chat response")
async def chat_stream_endpoint(
    req: ChatRequest,
    session: Annotated[Session, Depends(get_session)],
):
    """Server-Sent Events streaming endpoint yielding meta, sources, tokens, pending_action, done."""
    user_id = 1
    session_id = _resolve_session_id(session, req.session_id, req.message, user_id=user_id)

    # 1. Classify & Enrich
    intent_res = classify_intent(req.message)
    intent = intent_res.name
    enriched = enrich(intent, req.message, session=session, user_id=user_id)

    # 2. Retrieve
    store = get_vector_store()
    passages: List[SearchResult] = []
    if enriched.retrieval_category in ("nutrition", "exercise"):
        try:
            passages = store.search(req.message, category=enriched.retrieval_category, k=5)
        except Exception:
            passages = []
    else:
        passages = store.search_all(req.message, k=5)

    sources_data = [
        {
            "source": p.source,
            "page": p.page,
            "score": round(p.score, 4),
            "text": (p.text[:220] + "...") if len(p.text) > 220 else p.text,
        }
        for p in passages
    ]


    # 3. Pending action
    pending_action = None
    if intent == "workout_logging":
        pending_act = parse_logged_sets(req.message)
        if pending_act:
            pending_action = pending_act.model_dump()

    # 4. Prompt
    system_prompt, _ = build_prompt(
        intent=intent,
        facts=enriched.user_facts,
        numbers=enriched.numbers,
        passages=passages,
        history=[{"role": "user", "content": req.message}],
    )

    client = get_llm_client()

    async def event_generator() -> AsyncIterator[Dict[str, str]]:
        try:
            # Event 1: meta
            yield {
                "event": "meta",
                "data": json.dumps({"session_id": session_id, "intent": intent}),
            }

            # Event 2: sources
            yield {
                "event": "sources",
                "data": json.dumps(sources_data),
            }

            # Event 3: tokens
            full_response_parts: List[str] = []
            async for token in client.stream(
                messages=[{"role": "user", "content": req.message}],
                system=system_prompt,
            ):
                full_response_parts.append(token)
                yield {
                    "event": "token",
                    "data": json.dumps({"token": token}),
                }

            full_answer = "".join(full_response_parts)

            # Event 4: pending_action (if logging)
            if pending_action:
                yield {
                    "event": "pending_action",
                    "data": json.dumps(pending_action),
                }

            # Event 5: done
            yield {
                "event": "done",
                "data": json.dumps({"status": "complete"}),
            }

            # Persist messages in DB
            append_message(session, session_id=session_id, role="user", content=req.message)
            append_message(
                session,
                session_id=session_id,
                role="assistant",
                content=full_answer,
                sources=sources_data if sources_data else None,
            )

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": "An error occurred while generating response."}),
            }

    return EventSourceResponse(event_generator())
