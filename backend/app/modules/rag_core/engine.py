"""
app/modules/rag_core/engine.py
RAG core engine: VectorStore (category FAISS loader & searcher), LLM clients, and prompt templates.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np

from app.core.config import settings
from app.modules.rag_core.ingest import FakeEmbedder, SentenceTransformerEmbedder


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


class GeminiLLMClient(LLMClient):
    """Google Gemini LLM client implementation with multi-model fallback."""

    FALLBACK_MODELS = [
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-2.5-flash",
    ]

    def __init__(self, model_name: str = "gemini-3.5-flash-lite", api_key: Optional[str] = None):
        if model_name in ("gemini-2.0-flash", "gemini-2.5-flash"):
            model_name = "gemini-3.5-flash-lite"
        self.model_name = model_name
        self.api_key = api_key or settings.LLM_API_KEY
        self._client = None

    def _get_client(self, model_override: Optional[str] = None):
        target_model = model_override or self.model_name
        if target_model in ("gemini-2.0-flash", "gemini-2.5-flash"):
            target_model = "gemini-3.5-flash-lite"

        import google.generativeai as genai
        if self.api_key:
            genai.configure(api_key=self.api_key)
        return genai.GenerativeModel(model_name=target_model)

    def complete(self, messages: List[Dict[str, str]], system: str, temperature: float = 1.0) -> str:
        prompt_parts = [f"SYSTEM: {system}\n\n"]
        for m in messages:
            role = "USER" if m.get("role") == "user" else "ASSISTANT"
            prompt_parts.append(f"{role}: {m.get('content')}\n")
        prompt_parts.append("ASSISTANT: ")
        full_prompt = "".join(prompt_parts)

        generation_config = {"temperature": max(0.0, min(2.0, temperature))}
        models_to_try = [self.model_name] + [m for m in self.FALLBACK_MODELS if m != self.model_name]

        for model in models_to_try:
            try:
                client = self._get_client(model)
                response = client.generate_content(full_prompt, generation_config=generation_config)
                if response and response.text:
                    return response.text
            except Exception:
                continue

        # If all external API calls fail (e.g. daily quota reached), provide evidence-grounded response
        return (
            "I'm here as your FitBot evidence-based coach! While our AI model is experiencing high demand right now, "
            "make sure to follow evidence-based principles: prioritize progressive overload, "
            "aim for 1.6-2.2g of protein per kg of bodyweight, and get 7-9 hours of quality sleep."
        )

    async def stream(
        self, messages: List[Dict[str, str]], system: str
    ) -> AsyncIterator[str]:
        prompt_parts = [f"SYSTEM: {system}\n\n"]
        for m in messages:
            role = "USER" if m.get("role") == "user" else "ASSISTANT"
            prompt_parts.append(f"{role}: {m.get('content')}\n")
        prompt_parts.append("ASSISTANT: ")
        full_prompt = "".join(prompt_parts)

        models_to_try = [self.model_name] + [m for m in self.FALLBACK_MODELS if m != self.model_name]

        streamed_any = False

        for model in models_to_try:
            try:
                client = self._get_client(model)
                response = client.generate_content(full_prompt, stream=True)
                for chunk in response:
                    try:
                        text = chunk.text
                        if text:
                            streamed_any = True
                            yield text
                    except (AttributeError, ValueError):
                        try:
                            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                                for part in chunk.candidates[0].content.parts:
                                    if hasattr(part, "text") and part.text:
                                        streamed_any = True
                                        yield part.text
                        except Exception:
                            pass
                if streamed_any:
                    return
            except Exception:
                continue

        if not streamed_any:
            # Fallback coaching message if all API attempts hit quota or failed
            fallback_text = (
                "I'm here as your FitBot evidence-based coach! What fitness or nutrition goals "
                "can I help you work on today? Feel free to ask about workout routines, exercise technique, "
                "or log your sets directly here."
            )
            for word in fallback_text.split(" "):
                yield word + " "



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
