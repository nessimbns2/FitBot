"""
backend/tests/test_plateau_llm.py
Unit tests for the LLM explanation layer, validation, timeout fallback,
and bounded strategy selection:
1. Digits in LLM output -> rejected, falls back to Python template
2. Spelled number word in LLM output -> rejected, falls back to Python template
3. Timeout -> caught, falls back to Python template within explicit timeout
4. Clean prose -> passes validation and is returned
5. Empty RAG -> prompt forbids research claims, sources is empty
6. Bounded strategy choice -> valid pick is accepted
7. Out-of-bounds strategy choice -> rejected, falls back to Python default
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, Dict, List
import pytest

from app.modules.progressive_overload.algorithms import (
    DiagConfidence,
    DiagDeloadTarget,
    DiagnosisResult,
    DiagStrategy,
    FatigueEvidence,
    RootCause,
    render_fallback,
)
from app.modules.progressive_overload.service import (
    generate_diagnosis_explanation,
    get_approved_strategies,
)
from app.modules.rag_core.engine import LLMClient


class ScriptedLLMClient(LLMClient):
    """Test LLM client that returns scripted responses or simulates delays."""

    def __init__(self, response_text: str = "", delay_seconds: float = 0.0):
        self.response_text = response_text
        self.delay_seconds = delay_seconds
        self.last_system_prompt: str = ""
        self.last_messages: List[Dict[str, str]] = []

    def complete(self, messages: List[Dict[str, str]], system: str, temperature: float = 1.0) -> str:
        self.last_system_prompt = system
        self.last_messages = messages
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        return self.response_text

    async def stream(self, messages: List[Dict[str, str]], system: str, temperature: float = 1.0) -> AsyncIterator[str]:
        yield self.response_text


class MockPassage:
    def __init__(self, text: str, source: str = "guide.pdf", page: int = 12, score: float = 0.85):
        self.text = text
        self.source = source
        self.page = page
        self.score = score


class MockVectorStore:
    def __init__(self, passages: List[MockPassage] | None = None):
        self.passages = passages or []

    def search(self, query: str, category: str = "exercise", k: int = 3):
        return self.passages[:k]


def _mock_diagnosis_result() -> DiagnosisResult:
    """Create a standard fatigue_pattern diagnosis result."""
    evidence = FatigueEvidence(
        sessions_analysed=4,
        sessions_skipped=0,
        session_span_days=21,
        slope_pct_per_week=0.0,
        slope_rpe_per_day=0.08,
        slope_rpe_per_session=0.56,
        avg_rep_dropoff_pct=18.0,
        rpe_coverage_pct=100.0,
        noisy_data=False,
        noise_ratio=0.01,
        volume_count=14,
        volume_status="in_range",
        current_weight_kg=80.0,
        current_sets=3,
        current_avg_rpe=9.2,
    )
    target = DiagDeloadTarget(
        strategy=DiagStrategy.volume_reduction,
        target_weight_kg=72.5,
        target_sets=2,
        target_reps_range="6-12",
        target_rpe_ceiling=7.0,
        resume_weight_kg=80.0,
        duration_sessions=2,
    )
    return DiagnosisResult(
        plateau_detected=True,
        root_cause=RootCause.fatigue_pattern,
        confidence=DiagConfidence.medium,
        reason="Flat 1RM with rising RPE and rep dropoff.",
        evidence=evidence,
        deload_target=target,
    )


def test_llm_digits_rejected_and_falls_back():
    """LLM text containing digits (e.g. 'Take 2 days off') is rejected and falls back."""
    result = _mock_diagnosis_result()
    fallback = render_fallback(result)
    client = ScriptedLLMClient("STRATEGY: volume_reduction\nEXPLANATION: Take 2 sessions off to recover.")

    explanation, strat, _ = generate_diagnosis_explanation(
        result=result,
        llm_client=client,
        vector_store=MockVectorStore(),
    )
    # Digits are banned -> fallback template used
    assert explanation == fallback
    assert strat == DiagStrategy.volume_reduction


def test_llm_spelled_number_rejected_and_falls_back():
    """LLM text containing spelled number words (e.g. 'three sets') is rejected and falls back."""
    result = _mock_diagnosis_result()
    fallback = render_fallback(result)
    client = ScriptedLLMClient("STRATEGY: volume_reduction\nEXPLANATION: Reduce the workload by three sets this week.")

    explanation, strat, _ = generate_diagnosis_explanation(
        result=result,
        llm_client=client,
        vector_store=MockVectorStore(),
    )
    # Number word "three" is banned -> fallback template used
    assert explanation == fallback
    assert strat == DiagStrategy.volume_reduction


def test_llm_timeout_falls_back():
    """An LLM call exceeding timeout falls back gracefully to Python template."""
    result = _mock_diagnosis_result()
    fallback = render_fallback(result)
    # Client delay 0.5s with timeout 0.1s
    client = ScriptedLLMClient("EXPLANATION: Valid hedged explanation.", delay_seconds=0.5)

    start = time.perf_counter()
    explanation, strat, _ = generate_diagnosis_explanation(
        result=result,
        llm_client=client,
        vector_store=MockVectorStore(),
        timeout_seconds=0.1,
    )
    elapsed = time.perf_counter() - start

    assert explanation == fallback
    assert strat == DiagStrategy.volume_reduction
    assert elapsed < 0.35  # bounded by timeout


def test_llm_clean_prose_passes():
    """Clean, compliant prose without numbers passes validation."""
    result = _mock_diagnosis_result()
    clean_text = (
        "STRATEGY: volume_reduction\n"
        "EXPLANATION: Training patterns reflect accumulating fatigue across recent sessions. "
        "A temporary reduction in overall volume facilitates systemic recovery while preserving strength adaptations."
    )
    client = ScriptedLLMClient(clean_text)

    explanation, strat, _ = generate_diagnosis_explanation(
        result=result,
        llm_client=client,
        vector_store=MockVectorStore(),
    )
    assert "accumulating fatigue" in explanation
    assert strat == DiagStrategy.volume_reduction


def test_empty_rag_forbids_research_claims():
    """When vector store returns no passages, the prompt strictly forbids claiming research support."""
    result = _mock_diagnosis_result()
    client = ScriptedLLMClient("STRATEGY: volume_reduction\nEXPLANATION: Hedged general coaching rationale.")

    explanation, strat, sources = generate_diagnosis_explanation(
        result=result,
        llm_client=client,
        vector_store=MockVectorStore([]),  # empty RAG
    )
    assert sources == []
    # Verify prompt instruction
    assert "No research passages were found" in client.last_system_prompt
    assert "You must NOT claim, cite, or imply any scientific or clinical research support" in client.last_system_prompt


def test_bounded_strategy_selection_accepts_approved():
    """The LLM picks an alternative strategy from the Python-approved set."""
    result = _mock_diagnosis_result()  # default is volume_reduction; approved includes hold and weight_reduction
    client = ScriptedLLMClient(
        "STRATEGY: hold\n"
        "EXPLANATION: Holding the current training load stabilizes performance without introducing excessive deload fatigue."
    )

    explanation, strat, _ = generate_diagnosis_explanation(
        result=result,
        llm_client=client,
        vector_store=MockVectorStore(),
    )
    assert strat == DiagStrategy.hold
    assert "Holding the current training load" in explanation


def test_bounded_strategy_selection_rejects_unapproved():
    """When the LLM suggests an unapproved strategy, code rejects it and falls back to Python's default."""
    result = _mock_diagnosis_result()  # approved: volume_reduction, weight_reduction, hold
    client = ScriptedLLMClient(
        "STRATEGY: progress_load\n"
        "EXPLANATION: Performance indicates adaptation capacity is ready for progressive advancement."
    )

    explanation, strat, _ = generate_diagnosis_explanation(
        result=result,
        llm_client=client,
        vector_store=MockVectorStore(),
    )
    # progress_load is not approved for fatigue_pattern -> falls back to default strategy
    assert strat == DiagStrategy.volume_reduction


def test_gray_zone_undetermined_cause_prompt_and_prose():
    """Gray zone (undetermined_cause): computed facts are passed, LLM provides hedged consistency + lifestyle checks."""
    result = _mock_diagnosis_result()
    result.root_cause = RootCause.undetermined_cause
    result.deload_target.strategy = DiagStrategy.hold
    result.evidence.rpe_coverage_pct = 0.0

    client = ScriptedLLMClient(
        "STRATEGY: hold\n"
        "EXPLANATION: Recent flat performance is consistent with technical stagnation or variable recovery habits. "
        "The lifter should monitor sleep consistency, ensure adequate caloric intake, and begin logging perceived exertion."
    )

    explanation, strat, _ = generate_diagnosis_explanation(
        result=result,
        llm_client=client,
        vector_store=MockVectorStore(),
    )

    # Prompt check
    assert "ambiguous training plateau" in client.last_system_prompt
    # New user message format contains verbal signal descriptions
    assert "Observed signals" in client.last_messages[0]["content"]
    assert "Lifter profile" in client.last_messages[0]["content"]
    assert strat == DiagStrategy.hold
    assert "sleep consistency" in explanation


def test_gray_zone_validation_failure_falls_back():
    """Gray zone LLM output with banned digits/words falls back to Python fallback template."""
    result = _mock_diagnosis_result()
    result.root_cause = RootCause.undetermined_cause
    result.deload_target.strategy = DiagStrategy.hold

    # Contains illegal number word 'three' and digit '7'
    client = ScriptedLLMClient(
        "STRATEGY: hold\n"
        "EXPLANATION: Hold load for three sessions at RPE 7 because recovery is variable."
    )

    explanation, strat, _ = generate_diagnosis_explanation(
        result=result,
        llm_client=client,
        vector_store=MockVectorStore(),
    )

    fallback = render_fallback(result)
    assert explanation == fallback
    assert strat == DiagStrategy.hold


def test_contradiction_lint_rejects_stable_effort_when_rising():
    """When RPE slope is rising (>0.3), prose claiming 'stable effort' is rejected and falls back."""
    result = _mock_diagnosis_result()
    result.evidence.slope_rpe_per_session = 0.8  # Rising effort

    client = ScriptedLLMClient(
        "STRATEGY: volume_reduction\n"
        "EXPLANATION: Working weights remain flat alongside stable effort across sessions. "
        "Trimming weekly volume dissipates accumulated fatigue without sacrificing load. "
        "Check sleep consistency, external stress, and daily nutrition adequacy."
    )

    explanation, strat, _ = generate_diagnosis_explanation(
        result=result,
        llm_client=client,
        vector_store=MockVectorStore(),
    )

    fallback = render_fallback(result)
    assert explanation == fallback  # Rejected due to contradiction with rising RPE


def test_contradiction_lint_rejects_declining_weight_when_flat():
    """When 1RM slope is flat, prose claiming 'downward trends in working weight' is rejected and falls back."""
    result = _mock_diagnosis_result()
    result.evidence.slope_pct_per_week = 0.0  # Flat 1RM

    client = ScriptedLLMClient(
        "STRATEGY: volume_reduction\n"
        "EXPLANATION: Observed downward trends in working weight reflect systemic training fatigue. "
        "Trimming weekly volume dissipates accumulated fatigue without sacrificing load. "
        "Check sleep consistency, external stress, and daily nutrition adequacy."
    )

    explanation, strat, _ = generate_diagnosis_explanation(
        result=result,
        llm_client=client,
        vector_store=MockVectorStore(),
    )

    fallback = render_fallback(result)
    assert explanation == fallback  # Rejected due to contradiction with flat weight/1RM


