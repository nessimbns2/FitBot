"""
backend/tests/test_rag.py
Tests for Phase 5 (Ingestion & Retrieval), Phase 6 (Router Agent, Engine & Chat), and Phase 7 (Retrieval-backed endpoints).
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest
import pypdf

from app.core.config import settings
from app.modules.rag_core.engine import (
    FakeEmbedder,
    FakeLLMClient,
    SearchResult,
    VectorStore,
    build_prompt,
    get_vector_store,
    set_llm_client,
    set_vector_store,
)
from app.modules.rag_core.ingest import (
    Chunk,
    build_category_index,
    run_ingest,
    split_text_into_chunks,
)
from app.modules.rag_core.router_agent import (
    classify_intent,
    enrich,
    extract_exercises,
    parse_logged_sets,
)


# ── Phase 5.1: Ingestion Pipeline Tests ───────────────────────────────────────

def test_chunking_size_and_overlap():
    text = (
        "Paragraph one with enough sentences to form a coherent thought on training principles. "
        "It emphasizes progressive overload and proper volume tracking.\n\n"
        "Paragraph two discusses nutrition, specifically protein intake and caloric balance. "
        "Athletes need sufficient amino acids for muscle repair and recovery.\n\n"
        "Paragraph three covers hydration and electrolyte management for peak physical performance."
    )
    chunks = split_text_into_chunks(text, target_size=150, overlap=30)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) > 0


def test_ingestion_manifest_validation_error():
    with TemporaryDirectory() as tmp_docs, TemporaryDirectory() as tmp_vs:
        docs_path = Path(tmp_docs)
        vs_path = Path(tmp_vs)

        # Write a PDF that is not in manifest
        fake_pdf = docs_path / "UnregisteredGuide.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 dummy content")

        manifest_file = docs_path / "manifest.json"
        manifest_file.write_text(json.dumps({"Other.pdf": "nutrition"}))

        with pytest.raises(ValueError, match="missing from manifest.json"):
            run_ingest(docs_dir=docs_path, vectorstore_dir=vs_path, embedder=FakeEmbedder())


def test_ingestion_pipeline_and_idempotency():
    with TemporaryDirectory() as tmp_docs, TemporaryDirectory() as tmp_vs:
        docs_path = Path(tmp_docs)
        vs_path = Path(tmp_vs)

        # Create a valid tiny PDF using pypdf
        writer = pypdf.PdfWriter()
        page = writer.add_blank_page(width=72, height=72)
        # Add a text annotation or stream
        test_pdf_path = docs_path / "TestNutrition.pdf"
        with open(test_pdf_path, "wb") as f:
            writer.write(f)

        manifest = {"TestNutrition.pdf": "nutrition"}
        (docs_path / "manifest.json").write_text(json.dumps(manifest))

        embedder = FakeEmbedder()
        res1 = run_ingest(docs_dir=docs_path, vectorstore_dir=vs_path, embedder=embedder)
        assert "nutrition" in res1["categories_rebuilt"]

        # Run 2: without changes, should skip
        res2 = run_ingest(docs_dir=docs_path, vectorstore_dir=vs_path, embedder=embedder)
        assert res2["files_processed"] == 0

        # Run 3: rebuild=True forces rebuild
        res3 = run_ingest(docs_dir=docs_path, vectorstore_dir=vs_path, rebuild=True, embedder=embedder)
        assert res3["files_processed"] == 1


# ── Phase 5.2: Retrieval & Vector Store Tests ─────────────────────────────────

@pytest.fixture
def mock_vector_store():
    with TemporaryDirectory() as tmp_vs:
        vs_path = Path(tmp_vs)
        embedder = FakeEmbedder()

        # Build dummy nutrition index
        nutr_chunks = [
            Chunk("n1", "Protein intake should be 2.0 grams per kg for hypertrophy.", "NutrGuide.pdf", 5, "nutrition"),
            Chunk("n2", "Hydration target is 35 ml per kg of body weight daily.", "NutrGuide.pdf", 8, "nutrition"),
        ]
        build_category_index(nutr_chunks, embedder, "nutrition", vs_path)

        # Build dummy exercise index
        ex_chunks = [
            Chunk("e1", "Keep elbows tucked at 45 degrees during barbell bench press.", "ExerciseGuide.pdf", 12, "exercise"),
            Chunk("e2", "Squat to parallel or below while keeping chest proud.", "ExerciseGuide.pdf", 15, "exercise"),
        ]
        build_category_index(ex_chunks, embedder, "exercise", vs_path)

        store = VectorStore(vectorstore_dir=vs_path, embedder=embedder)
        yield store


def test_vectorstore_category_isolation(mock_vector_store):
    """Nutrition query must only return category='nutrition'."""
    results = mock_vector_store.search("protein intake", category="nutrition", k=5, min_score=-1.0)
    assert len(results) > 0
    for r in results:
        assert r.category == "nutrition"
        assert "NutrGuide" in r.source


def test_vectorstore_search_all(mock_vector_store):
    """search_all queries both categories and returns merged results."""
    results = mock_vector_store.search_all("bench press and protein", k=4, min_score=-1.0)
    assert len(results) == 4
    categories = {r.category for r in results}
    assert "nutrition" in categories
    assert "exercise" in categories


def test_vectorstore_missing_index_raises():
    with TemporaryDirectory() as empty_dir:
        store = VectorStore(vectorstore_dir=Path(empty_dir), embedder=FakeEmbedder())
        with pytest.raises(FileNotFoundError, match="Vector index for category 'nutrition' not found"):
            store.search("test", category="nutrition")


# ── Phase 6.1: LLM Engine & Prompt Templates ──────────────────────────────────

def test_prompt_template_blocks_and_truncation():
    passages = [
        SearchResult(text="Sample passage text", source="Guide.pdf", page=1, category="nutrition", score=0.85)
    ]
    history = [{"role": "user", "content": f"msg {i}"} for i in range(20)]

    system, trimmed_hist = build_prompt(
        intent="nutrition",
        facts="Age 30, Male, 80kg",
        numbers="Target: 2500 kcal",
        passages=passages,
        history=history,
    )

    assert "USER FACTS" in system
    assert "CALCULATED NUMBERS" in system
    assert "CONTEXT" in system
    assert "[1] (Source: Guide.pdf, Page 1)" in system
    assert "not constitute medical" in system
    # History must be truncated to last 10 messages
    assert len(trimmed_hist) == 10
    assert trimmed_hist[-1]["content"] == "msg 19"


@pytest.mark.asyncio
async def test_fake_llm_client_streaming():
    fake = FakeLLMClient(response_text="Hello fitness world")
    tokens = []
    async for tok in fake.stream(messages=[], system=""):
        tokens.append(tok)
    assert "".join(tokens) == "Hello fitness world"


# ── Phase 6.2: Intent Router & Context Enricher ───────────────────────────────

def test_intent_classification():
    assert classify_intent("How much protein should I eat for cutting?").name == "nutrition"
    assert classify_intent("What is my TDEE and calorie deficit?").name == "nutrition"
    assert classify_intent("How do I fix elbow flare on bench press?").name == "exercise_technique"
    assert classify_intent("I hit a plateau on squat, how do I overload?").name == "overload_advice"
    assert classify_intent("Logged bench press 80kg 3x8 rpe 8").name == "workout_logging"


def test_extract_exercise_aliases():
    assert "barbell-bench-press" in extract_exercises("I did bench press today")
    assert "barbell-back-squat" in extract_exercises("My back squat feels heavy")
    assert "overhead-barbell-press" in extract_exercises("How to improve OHP form?")


def test_parse_logged_sets_no_database_write():
    action = parse_logged_sets("Bench 80kg 3x8 rpe 8")
    assert action is not None
    assert action.action_type == "log_workout"
    assert len(action.sets) == 3
    assert action.sets[0].weight == 80.0
    assert action.sets[0].reps == 8
    assert action.sets[0].rpe == 8.0
    assert action.sets[0].rir == 2


def test_context_enrichment_includes_numbers(session):
    enriched = enrich("nutrition", "What are my macros?", session=session)
    assert enriched.retrieval_category == "nutrition"
    assert "Target Calories" in enriched.numbers
    assert "Protein:" in enriched.numbers


# ── Phase 6.3: Chat API Endpoints ─────────────────────────────────────────────

def test_api_chat_pipeline_and_persistence(client, mock_vector_store):
    set_vector_store(mock_vector_store)
    set_llm_client(FakeLLMClient("Your target is 2500 kcal [1]."))

    payload = {"message": "How many calories should I eat?"}
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "nutrition"
    assert "session_id" in data
    assert "Your target is 2500 kcal" in data["answer"]

    # Verify session messages persisted in DB
    sess_id = data["session_id"]
    msg_res = client.get(f"/api/user/sessions/{sess_id}/messages")
    assert msg_res.status_code == 200
    msgs = msg_res.json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_api_chat_rejects_overlong_messages(client):
    long_msg = "a" * 2001
    res = client.post("/api/chat", json={"message": long_msg})
    assert res.status_code == 422


def test_api_debug_search_guardrail(client):
    """When DEBUG=false (default), /api/chat/debug/search returns 404."""
    settings.DEBUG = False
    res = client.get("/api/chat/debug/search?q=protein")
    assert res.status_code == 404

    settings.DEBUG = True
    res_debug = client.get("/api/chat/debug/search?q=protein")
    assert res_debug.status_code == 200
    settings.DEBUG = False


# ── Phase 7: Retrieval-backed Module Endpoints ────────────────────────────────

def test_api_nutrition_ask_category_isolation(client, mock_vector_store):
    set_vector_store(mock_vector_store)
    set_llm_client(FakeLLMClient("Eat 2.0g protein [1]."))

    res = client.post("/api/nutrition/ask", json={"question": "What is my protein target?"})
    assert res.status_code == 200
    data = res.json()
    assert len(data["sources"]) > 0
    # Every source must be from nutrition
    for s in data["sources"]:
        assert "NutrGuide" in s["source"]


def test_api_nutrition_ask_503_on_missing_index(client):
    with TemporaryDirectory() as empty_dir:
        set_vector_store(VectorStore(vectorstore_dir=Path(empty_dir), embedder=FakeEmbedder()))
        res = client.post("/api/nutrition/ask", json={"question": "What are my macros?"})
        assert res.status_code == 503
        assert "Vector index for category 'nutrition' not found" in res.json()["detail"]


def test_api_nutrition_plan_with_guidance(client, mock_vector_store):
    set_vector_store(mock_vector_store)
    set_llm_client(FakeLLMClient("Timing guidance [1]."))

    payload = {"meals_per_day": 4, "include_guidance": True}
    res = client.post("/api/nutrition/plan", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "guidance" in data
    # Numeric fields are unaltered
    assert data["macros"]["target_kcal"] > 0
    assert len(data["meals"]) == 4


def test_api_exercise_form_cue_with_pain_warning(client, mock_vector_store):
    set_vector_store(mock_vector_store)
    set_llm_client(FakeLLMClient("Keep your core tight."))

    res = client.post(
        "/api/exercises/form-cue",
        json={"exercise_id": "barbell-bench-press", "question": "I have shoulder pain when pressing"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "barbell-bench-press" == data["exercise_id"]
    assert "NOTICE" in data["extra_guidance"]
    assert "qualified physical therapist" in data["extra_guidance"]


def test_api_exercise_body_type_guidance(client, mock_vector_store):
    set_vector_store(mock_vector_store)
    set_llm_client(FakeLLMClient("Mesomorph training guidance."))

    res = client.get("/api/exercises/body-type-guidance")
    assert res.status_code == 200
    data = res.json()
    assert "somatotype" in data
    assert "guidance" in data
