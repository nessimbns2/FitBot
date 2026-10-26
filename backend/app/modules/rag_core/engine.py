"""
app/modules/rag_core/engine.py
RAG core engine: VectorStore (category FAISS loader & searcher), LLM clients, and prompt templates.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from app.core.config import settings
from app.modules.rag_core.ingest import FakeEmbedder, SentenceTransformerEmbedder

logger = logging.getLogger(__name__)


# ── Search Result Type ────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    text: str
    source: str
    page: int
    category: str
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "page": self.page,
            "category": self.category,
            "score": round(self.score, 4),
        }


# ── Vector Store ──────────────────────────────────────────────────────────────

class VectorStore:
    """Manages lazy loading and querying of category-specific FAISS indexes."""

    def __init__(
        self,
        vectorstore_dir: Optional[Path] = None,
        embedder: Optional[Any] = None,
    ):
        self.vectorstore_dir = vectorstore_dir or Path(settings.VECTORSTORE_DIR)
        self.embedder = embedder
        self._indexes: Dict[str, faiss.Index] = {}
        self._metadata: Dict[str, List[Dict[str, Any]]] = {}

    def _get_embedder(self):
        if self.embedder is None:
            self.embedder = SentenceTransformerEmbedder(model_name=settings.EMBEDDING_MODEL)
        return self.embedder

    def load_category(self, category: str) -> None:
        """Load index and chunk metadata for a specific category into memory."""
        index_file = self.vectorstore_dir / f"{category}.faiss"
        meta_file = self.vectorstore_dir / f"{category}_chunks.json"

        if not index_file.exists() or not meta_file.exists():
            raise FileNotFoundError(
                f"Vector index for category '{category}' not found at {index_file}. "
                "Please run ingestion first with: python -m app.modules.rag_core.ingest"
            )

        self._indexes[category] = faiss.read_index(str(index_file))
        with open(meta_file, "r", encoding="utf-8") as f:
            self._metadata[category] = json.load(f)

    def search(
        self,
        query: str,
        category: str,
        k: int = 5,
        min_score: float = 0.25,
    ) -> List[SearchResult]:
        """Search within a specific category index. Filter out results below min_score."""
        if category not in self._indexes:
            self.load_category(category)

        index = self._indexes[category]
        metadata = self._metadata[category]

        embedder = self._get_embedder()
        effective_min_score = -1.0 if isinstance(embedder, FakeEmbedder) else min_score
        q_vec = embedder.embed_texts([query])
        faiss.normalize_L2(q_vec)

        scores, indices = index.search(q_vec, min(k, len(metadata)))
        results: List[SearchResult] = []

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(metadata):
                continue
            f_score = float(score)
            if f_score >= effective_min_score:
                item = metadata[idx]
                results.append(
                    SearchResult(
                        text=item["text"],
                        source=item["source"],
                        page=item["page"],
                        category=item["category"],
                        score=f_score,
                    )
                )

        return results

    def search_all(
        self,
        query: str,
        k: int = 5,
        min_score: float = 0.25,
    ) -> List[SearchResult]:
        """Search across both 'nutrition' and 'exercise' categories, merged and sorted by score."""
        results: List[SearchResult] = []
        for cat in ["nutrition", "exercise"]:
            try:
                cat_results = self.search(query, category=cat, k=k, min_score=min_score)
                results.extend(cat_results)
            except FileNotFoundError:
                continue

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]


_GLOBAL_VECTOR_STORE: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _GLOBAL_VECTOR_STORE
    if _GLOBAL_VECTOR_STORE is None:
        _GLOBAL_VECTOR_STORE = VectorStore()
    return _GLOBAL_VECTOR_STORE


def set_vector_store(store: VectorStore) -> None:
    global _GLOBAL_VECTOR_STORE
    _GLOBAL_VECTOR_STORE = store


# ── Prompt Templates (Centralized in app.prompts) ─────────────────────────────
from app.prompts import (
    COACH_PERSONA,
    SAFETY_DISCLAIMER,
    NUTRITION_PROMPT_TEMPLATE,
    EXERCISE_TECHNIQUE_PROMPT_TEMPLATE,
    OVERLOAD_ADVICE_PROMPT_TEMPLATE,
    WORKOUT_LOGGING_PROMPT_TEMPLATE,
    GENERAL_PROMPT_TEMPLATE,
    INTENT_PROMPT_MAP,
)

PROMPT_TEMPLATES: Dict[str, str] = INTENT_PROMPT_MAP



def build_prompt(
    intent: str,
    facts: str,
    numbers: str,
    passages: List[SearchResult],
    history: List[Dict[str, str]],
) -> Tuple[str, List[Dict[str, str]]]:
    """Assemble system prompt and chat messages (keeping last 10 history messages)."""
    template = PROMPT_TEMPLATES.get(intent, GENERAL_PROMPT_TEMPLATE)

    if passages:
        formatted_context = "\n\n".join(
            f"[{i+1}] (Source: {p.source}, Page {p.page})\n{p.text}"
            for i, p in enumerate(passages)
        )
    else:
        formatted_context = "No retrieved context passages available."

    system_prompt = template.format(
        persona=COACH_PERSONA,
        facts=facts.strip() or "Standard profile",
        numbers=numbers.strip() or "None",
        context=formatted_context,
        safety_note=SAFETY_DISCLAIMER,
    )

    # Keep only the last 10 messages of history
    trimmed_history = history[-10:] if len(history) > 10 else list(history)

    return system_prompt, trimmed_history


# ── LLM Client Abstraction ────────────────────────────────────────────────────

class LLMClient(ABC):
    """Abstract interface for LLM calls supporting completion and token streaming."""

    @abstractmethod
    def complete(self, messages: List[Dict[str, str]], system: str, temperature: float = 1.0) -> str:
        pass

    @abstractmethod
    async def stream(
        self, messages: List[Dict[str, str]], system: str
    ) -> AsyncIterator[str]:
        pass


class FakeLLMClient(LLMClient):
    """Test client that yields scripted tokens for predictable, fast assertions."""

    def __init__(self, response_text: str = "This is a verified coach response [1]."):
        self.response_text = response_text

    def complete(self, messages: List[Dict[str, str]], system: str, temperature: float = 1.0) -> str:
        return self.response_text

    async def stream(
        self, messages: List[Dict[str, str]], system: str
    ) -> AsyncIterator[str]:
        words = self.response_text.split(" ")
        for i, word in enumerate(words):
            yield word if i == 0 else f" {word}"


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM provider cannot produce an answer.

    `reason` is a stable machine code (missing_api_key, invalid_api_key, quota_exceeded,
    timeout, blocked, provider_error); `user_message` is safe to show in the UI.
    """

    USER_MESSAGES = {
        "missing_api_key": "The AI service is not configured (no API key). Showing evidence from the documents instead.",
        "invalid_api_key": "The AI service rejected the API key. Showing evidence from the documents instead.",
        "quota_exceeded": "The AI service quota is exhausted for now. Showing evidence from the documents instead.",
        "timeout": "The AI service took too long to answer. Showing evidence from the documents instead.",
        "blocked": "The AI service declined to answer this request.",
        "provider_error": "The AI service is temporarily unavailable. Showing evidence from the documents instead.",
    }

    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason if reason in self.USER_MESSAGES else "provider_error"
        self.user_message = self.USER_MESSAGES[self.reason]
        super().__init__(f"{self.reason}: {detail}" if detail else self.reason)


def classify_llm_error(exc: Exception) -> LLMUnavailableError:
    """Map a provider/SDK exception to an LLMUnavailableError with a stable reason."""
    if isinstance(exc, LLMUnavailableError):
        return exc
    name = type(exc).__name__
    text = str(exc).lower()
    if name in ("DeadlineExceeded", "TimeoutError", "ReadTimeout", "ConnectTimeout") or "timed out" in text or "deadline" in text:
        return LLMUnavailableError("timeout", name)
    if name in ("ResourceExhausted", "TooManyRequests") or "429" in text or "quota" in text:
        return LLMUnavailableError("quota_exceeded", name)
    if name in ("Unauthenticated", "PermissionDenied") or "api key not valid" in text or "api_key_invalid" in text:
        return LLMUnavailableError("invalid_api_key", name)
    return LLMUnavailableError("provider_error", name)


def degraded_answer(err: LLMUnavailableError, passages: List[SearchResult]) -> str:
    """Answer built only from retrieved evidence when the LLM cannot be reached."""
    if not passages:
        return err.user_message
    excerpts = "\n".join(
        f"- {' '.join(p.text.split())[:280]}… *(Source: {p.source}, p. {p.page})*"
        for p in passages[:3]
    )
    return f"⚠️ {err.user_message}\n\n{excerpts}"



class GeminiLLMClient(LLMClient):
    """Google Gemini LLM client with multi-model fallback, request timeout and typed errors."""

    # Tried in order after the configured model. Verified available with the project key
    # (Oct 2026); retired models (gemini-2.5-*) answer 404 and slow ones only burn the budget.
    FALLBACK_MODELS = [
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-flash-lite-latest",
    ]
    # Below this many seconds left in the call budget, don't start another model attempt.
    MIN_ATTEMPT_SECONDS = 2.0

    def __init__(self, model_name: str = "gemini-3.5-flash-lite", api_key: Optional[str] = None):
        if model_name in ("gemini-2.0-flash", "gemini-2.5-flash"):
            model_name = "gemini-3.5-flash-lite"
        self.model_name = model_name
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self.timeout = settings.LLM_TIMEOUT_SECONDS

    def _get_client(self, model_override: Optional[str] = None):
        target_model = model_override or self.model_name
        if target_model in ("gemini-2.0-flash", "gemini-2.5-flash"):
            target_model = "gemini-3.5-flash-lite"

        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        return genai.GenerativeModel(model_name=target_model)

    def _models_to_try(self) -> List[str]:
        return [self.model_name] + [m for m in self.FALLBACK_MODELS if m != self.model_name]

    @staticmethod
    def _build_prompt(messages: List[Dict[str, str]], system: str) -> str:
        prompt_parts = [f"SYSTEM: {system}\n\n"]
        for m in messages:
            role = "USER" if m.get("role") == "user" else "ASSISTANT"
            prompt_parts.append(f"{role}: {m.get('content')}\n")
        prompt_parts.append("ASSISTANT: ")
        return "".join(prompt_parts)

    def _ensure_key(self) -> None:
        if not (self.api_key or "").strip():
            raise LLMUnavailableError("missing_api_key")

    def _attempts(self):
        """Yield (model, per-attempt timeout) while the overall call budget lasts.

        LLM_TIMEOUT_SECONDS bounds the WHOLE call, fallbacks included, so a user never
        waits N models x timeout.
        """
        deadline = time.monotonic() + self.timeout
        for model in self._models_to_try():
            remaining = deadline - time.monotonic()
            if remaining < self.MIN_ATTEMPT_SECONDS:
                return
            yield model, remaining

    def complete(self, messages: List[Dict[str, str]], system: str, temperature: float = 1.0) -> str:
        self._ensure_key()
        full_prompt = self._build_prompt(messages, system)
        last_error: Optional[LLMUnavailableError] = None

        for model, budget in self._attempts():
            try:
                client = self._get_client(model)
                response = client.generate_content(
                    full_prompt, generation_config={"temperature": max(0.0, min(2.0, temperature))}, request_options={"timeout": budget}
                )
                text = _response_text(response)
                if text:
                    return text
                last_error = LLMUnavailableError("blocked", model)
            except Exception as exc:  # noqa: BLE001 — every SDK error is classified below
                last_error = classify_llm_error(exc)
                logger.warning("Gemini model %s failed: %s", model, last_error)
                if last_error.reason in ("missing_api_key", "invalid_api_key"):
                    break

        raise last_error or LLMUnavailableError("timeout")

    async def stream(
        self, messages: List[Dict[str, str]], system: str
    ) -> AsyncIterator[str]:
        self._ensure_key()
        full_prompt = self._build_prompt(messages, system)
        last_error: Optional[LLMUnavailableError] = None

        for model, budget in self._attempts():
            streamed_any = False
            try:
                client = self._get_client(model)
                # The Gemini SDK is blocking: run it in the threadpool so one streamed answer
                # never freezes the event loop (and every other request) while it is generated.
                response = await run_in_threadpool(
                    client.generate_content, full_prompt, stream=True, request_options={"timeout": budget}
                )
                async for chunk in iterate_in_threadpool(iter(response)):
                    text = _response_text(chunk)
                    if text:
                        streamed_any = True
                        yield text
                if streamed_any:
                    return
                last_error = LLMUnavailableError("blocked", model)
            except Exception as exc:  # noqa: BLE001
                last_error = classify_llm_error(exc)
                logger.warning("Gemini streaming with %s failed: %s", model, last_error)
                if streamed_any:
                    # Part of the answer was already sent: stop rather than restart on another model.
                    return
                if last_error.reason in ("missing_api_key", "invalid_api_key"):
                    break

        raise last_error or LLMUnavailableError("timeout")


def _response_text(response: Any) -> str:
    """Extract text from a Gemini response/chunk without raising on blocked candidates."""
    try:
        text = response.text
        if text:
            return text
    except (AttributeError, ValueError):
        pass
    try:
        parts = response.candidates[0].content.parts
        return "".join(getattr(p, "text", "") or "" for p in parts)
    except (AttributeError, IndexError, TypeError):
        return ""


_ACTIVE_LLM_CLIENT: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _ACTIVE_LLM_CLIENT
    if _ACTIVE_LLM_CLIENT is None:
        if settings.LLM_PROVIDER.lower() == "gemini":
            _ACTIVE_LLM_CLIENT = GeminiLLMClient(
                model_name=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
            )
        else:
            _ACTIVE_LLM_CLIENT = FakeLLMClient()
    return _ACTIVE_LLM_CLIENT


def set_llm_client(client: LLMClient) -> None:
    global _ACTIVE_LLM_CLIENT
    _ACTIVE_LLM_CLIENT = client
