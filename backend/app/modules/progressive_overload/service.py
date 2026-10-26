"""
app/modules/progressive_overload/service.py
Service layer for workout set logging, history retrieval, progression recommendations, and volume.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlmodel import Session, col, desc, select

from app.modules.exercises.catalog import get_catalog
from app.modules.exercises.service import get_exercise
from app.modules.progressive_overload.algorithms import (
    Recommendation,
    detect_plateau,
    double_progression,
    get_default_increment,
    linear_progression,
    weekly_volume,
)
from app.modules.progressive_overload.models import (
    SessionGroup,
    UnitType,
    WorkoutSet,
    WorkoutSetCreate,
    WorkoutSetRead,
)

LB_TO_KG_FACTOR = 0.45359237


def _convert_weight_to_kg(weight: float, unit: UnitType) -> float:
    if unit == UnitType.LB:
        return round(weight * LB_TO_KG_FACTOR, 2)
    return round(weight, 2)


def log_set(session: Session, data: WorkoutSetCreate, user_id: int) -> WorkoutSet:
    """Validate exercise and log a single workout set in kg."""
    exercise = get_exercise(data.exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise '{data.exercise_id}' not found in catalog",
        )

    weight_kg = _convert_weight_to_kg(data.weight, data.unit)
    performed_at = data.performed_at or datetime.now(timezone.utc)

    workout_set = WorkoutSet(
        user_id=user_id,
        exercise_id=data.exercise_id,
        performed_at=performed_at,
        session_label=data.session_label,
        set_number=data.set_number,
        reps=data.reps,
        weight_kg=weight_kg,
        rpe=data.rpe,
        rir=data.rir,
        notes=data.notes,
    )
    session.add(workout_set)
    session.commit()
    session.refresh(workout_set)
    return workout_set


def log_sets_bulk(session: Session, items: List[WorkoutSetCreate], user_id: int) -> List[WorkoutSet]:
    """Validate and log multiple workout sets in a single transaction."""
    results: List[WorkoutSet] = []
    for item in items:
        exercise = get_exercise(item.exercise_id)
        if not exercise:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Exercise '{item.exercise_id}' not found in catalog",
            )
        weight_kg = _convert_weight_to_kg(item.weight, item.unit)
        performed_at = item.performed_at or datetime.now(timezone.utc)

        workout_set = WorkoutSet(
            user_id=user_id,
            exercise_id=item.exercise_id,
            performed_at=performed_at,
            session_label=item.session_label,
            set_number=item.set_number,
            reps=item.reps,
            weight_kg=weight_kg,
            rpe=item.rpe,
            rir=item.rir,
            notes=item.notes,
        )
        session.add(workout_set)
        results.append(workout_set)

    session.commit()
    for ws in results:
        session.refresh(ws)
    return results


def get_history(
    session: Session,
    exercise_id: str,
    user_id: int,
    limit: int = 50,
    since: Optional[datetime] = None,
) -> List[SessionGroup]:
    """Get history for an exercise grouped by session date, newest first."""
    query = select(WorkoutSet).where(
        WorkoutSet.user_id == user_id,
        WorkoutSet.exercise_id == exercise_id,
    )
    if since:
        query = query.where(WorkoutSet.performed_at >= since)

    query = query.order_by(desc(WorkoutSet.performed_at), WorkoutSet.set_number).limit(limit)
    records = session.exec(query).all()

    # Group sets by session date
    grouped: Dict[str, List[WorkoutSetRead]] = {}
    labels: Dict[str, Optional[str]] = {}

    for ws in records:
        date_str = ws.performed_at.strftime("%Y-%m-%d")
        if date_str not in grouped:
            grouped[date_str] = []
            labels[date_str] = ws.session_label
        grouped[date_str].append(
            WorkoutSetRead(
                id=ws.id,
                user_id=ws.user_id,
                exercise_id=ws.exercise_id,
                performed_at=ws.performed_at,
                session_label=ws.session_label,
                set_number=ws.set_number,
                reps=ws.reps,
                weight_kg=ws.weight_kg,
                rpe=ws.rpe,
                rir=ws.rir,
                notes=ws.notes,
            )
        )

    return [
        SessionGroup(date=d, session_label=labels[d], sets=s_list)
        for d, s_list in grouped.items()
    ]


def get_recommendation(
    session: Session,
    exercise_id: str,
    algorithm: str = "double",
    *,
    user_id: int,
) -> Recommendation:
    """Compute progressive overload recommendation for the next session."""
    exercise = get_exercise(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise '{exercise_id}' not found in catalog",
        )

    history = get_history(session, exercise_id, user_id=user_id, limit=20)
    if not history:
        return Recommendation(
            weight_kg=20.0,
            rep_target="3x8",
            alternative=None,
            reason="No history yet for this exercise. Start with a manageable warm-up weight.",
            plateau_flag=False,
            deload_suggested=False,
        )

    last_session_sets = history[0].sets
    # Prepare session list for plateau detection: list of list of sets (newest first)
    sessions_sets = [group.sets for group in history]
    plateau_flag, deload_suggested = detect_plateau(sessions_sets, window=3)

    increment = get_default_increment(exercise)

    if algorithm.lower() == "linear":
        return linear_progression(
            last_session_sets=last_session_sets,
            weekly_increment_kg=increment,
            prescribed_reps=5,
            plateau_flag=plateau_flag,
            deload_suggested=deload_suggested,
        )
    else:
        rep_range = "6-12" if exercise.is_compound else "10-15"
        return double_progression(
            last_session_sets=last_session_sets,
            rep_range=rep_range,
            increment_kg=increment,
            plateau_flag=plateau_flag,
            deload_suggested=deload_suggested,
        )


def get_weekly_volume_summary(
    session: Session,
    week_start: Optional[date] = None,
    *,
    user_id: int,
) -> Dict[str, Any]:
    """Calculate effective weekly sets per muscle group for the specified or current week (Monday start)."""
    if week_start is None:
        today = date.today()
        # Monday of current week
        week_start = today - timedelta(days=today.weekday())

    catalog = get_catalog()
    week_end = week_start + timedelta(days=7)

    query = select(WorkoutSet).where(
        WorkoutSet.user_id == user_id,
        WorkoutSet.performed_at >= datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc),
        WorkoutSet.performed_at < datetime.combine(week_end, datetime.min.time(), tzinfo=timezone.utc),
    )
    sets = session.exec(query).all()

    volume_data = weekly_volume(sets, catalog, week_start)
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "muscles": volume_data,
    }


import concurrent.futures

from app.modules.progressive_overload.algorithms import (   # noqa: E402
    CONSTANTS_VERSION,
    DIAG_DELOAD_COOLDOWN_SESSIONS,
    DIAG_MANUAL_DELOAD_THRESHOLD,
    DIAG_PLATEAU_WINDOW_DAYS,
    DIAG_WEIGHT_REDUCTION_PCT,
    DiagConfidence,
    DiagnosisResult,
    DiagSessionData,
    DiagSetData,
    DiagStrategy,
    RootCause,
    diagnose_fatigue,
    explain_llm_prose_rejection,
    render_fallback,
    validate_llm_prose,
)
from app.modules.progressive_overload.models import (       # noqa: E402
    ApplyDeloadRequest,
    CancelDeloadRequest,
    DeloadRecord,
    DeloadRecordCreate,
    DeloadRecordRead,
)
from app.modules.rag_core.engine import LLMClient, get_llm_client, get_vector_store  # noqa: E402
from app.modules.user.models import UserProfile             # noqa: E402

# Deload expiry window: if the prescription is never logged within this many days
# the service will auto-expire it and allow a fresh diagnosis.
DELOAD_EXPIRY_DAYS: int = 28


def _round_to_plate_increment(weight_kg: float, unit: str = "kg") -> tuple[float, float, float]:
    """Round target weight to the user's plate increment (2.5 kg for metric, 5 lb for imperial).

    Returns (rounded_weight_kg, plate_increment_kg, weight_match_tolerance_kg).
    The match tolerance is half a plate step (1.25 kg for metric; ~1.134 kg for 5 lb).
    """
    if unit in ("lb", "imperial"):
        increment_lb = 5.0
        plate_inc_kg = round(increment_lb * LB_TO_KG_FACTOR, 3) # ~2.268 kg
        half_step_kg = round((increment_lb / 2.0) * LB_TO_KG_FACTOR, 3) # ~1.134 kg
        weight_lb = weight_kg / LB_TO_KG_FACTOR
        rounded_lb = max(increment_lb, round(weight_lb / increment_lb) * increment_lb)
        rounded_kg = round(rounded_lb * LB_TO_KG_FACTOR, 2)
        return rounded_kg, plate_inc_kg, half_step_kg
    else:
        increment_kg = 2.5
        rounded_kg = max(increment_kg, round(weight_kg / increment_kg) * increment_kg)
        half_step_kg = round(increment_kg / 2.0, 3) # 1.25 kg
        return rounded_kg, increment_kg, half_step_kg


LLM_DIAGNOSIS_TIMEOUT_SECONDS: float = 4.0


def get_approved_strategies(root_cause: RootCause, default_strategy: DiagStrategy) -> List[DiagStrategy]:
    """Return the 2-3 Python-approved strategies for the diagnosed root cause."""
    mapping = {
        RootCause.fatigue_pattern: [
            DiagStrategy.volume_reduction,
            DiagStrategy.weight_reduction,
            DiagStrategy.hold,
        ],
        RootCause.possible_under_recovery: [
            DiagStrategy.weight_reduction,
            DiagStrategy.volume_reduction,
            DiagStrategy.hold,
        ],
        RootCause.insufficient_stimulus: [
            DiagStrategy.progress_load,
            DiagStrategy.hold,
        ],
        RootCause.undetermined_cause: [
            DiagStrategy.hold,
            DiagStrategy.volume_reduction,
        ],
        RootCause.progressing: [
            DiagStrategy.no_action,
        ],
    }
    strategies = mapping.get(root_cause, [default_strategy])
    if default_strategy not in strategies:
        strategies = [default_strategy] + [s for s in strategies if s != default_strategy]
    return strategies


def _word_signals(ev, sessions: Optional[List[Any]] = None) -> dict:
    """Convert FatigueEvidence numeric fields and optional session history
    to explicit, non-overlapping verbal direction labels.
    """
    top_weights = []
    if sessions:
        for s in sessions:
            sets = getattr(s, "sets", [])
            if sets:
                top_weights.append(max((getattr(st, "weight_kg", 0.0) for st in sets), default=0.0))
    if top_weights and len(top_weights) >= 2:
        diff = max(top_weights) - min(top_weights)
        if diff <= 0.5:
            weight_trend = "working weight is flat across sessions"
        elif top_weights[-1] > top_weights[0] + 0.5:
            weight_trend = "working weight is increasing across sessions"
        else:
            weight_trend = "working weight is decreasing across sessions"
    else:
        if ev.slope_pct_per_week >= -0.5 and ev.slope_pct_per_week <= 0.5:
            weight_trend = "working weight is flat across sessions"
        elif ev.slope_pct_per_week > 0.5:
            weight_trend = "working weight is progressing or flat"
        else:
            weight_trend = "working weight is declining or flat"

    slope = ev.slope_pct_per_week
    if slope > 1.0:
        strength_trend = "estimated strength is trending upward across sessions"
    elif slope < -0.5:
        strength_trend = "estimated strength is declining across sessions"
    else:
        strength_trend = "estimated strength is flat across sessions"

    rpe_cov = ev.rpe_coverage_pct
    rpe_trend = ev.slope_rpe_per_session
    if rpe_cov < 40:
        effort_signal = "effort ratings are absent or sparse"
    elif rpe_trend is not None and rpe_trend > 0.3:
        effort_signal = "effort ratings are climbing steadily across sessions"
    elif rpe_trend is not None and rpe_trend < -0.3:
        effort_signal = "effort ratings are falling across sessions"
    else:
        effort_signal = "effort ratings are stable across sessions"

    dropoff = ev.avg_rep_dropoff_pct
    if dropoff is None:
        rep_signal = "rep consistency within sessions is not assessable (single-set data)"
    elif dropoff >= 15:
        rep_signal = "reps are dropping noticeably within sessions"
    elif dropoff >= 5:
        rep_signal = "mild rep dropoff within sessions"
    else:
        rep_signal = "rep counts are stable within sessions"

    return {
        "weight_trend": weight_trend,
        "strength_trend": strength_trend,
        "effort_signal": effort_signal,
        "rep_signal": rep_signal,
        "volume_status": ev.volume_status,
        "noisy": ev.noisy_data,
        "rpe_coverage": "sufficient" if rpe_cov >= 50 else ("sparse" if rpe_cov >= 20 else "absent"),
        "sessions_span": ev.session_span_days,
    }


# Abstract schema illustration from an unrelated domain (endurance cadence)
# to show output format without leaking any strength training / deload phrases for the model to copy.
_ABSTRACT_FORMAT_ILLUSTRATION = """\
FORMAT AND STRUCTURE ILLUSTRATION (Different domain — running cadence):
STRATEGY: hold
EXPLANATION: Cadence measurements remain steady while perceived effort rises, an observation consistent with aerobic fatigue accumulation [1]. Maintaining the current interval volume prevents excessive fatigue while allowing systemic aerobic recovery [1]. Practical factors to evaluate include overnight rest duration, daily nutritional fueling, and running surface conditions.
"""


def generate_diagnosis_explanation(
    result: DiagnosisResult,
    experience_level: str = "intermediate",
    goal: str = "hypertrophy",
    llm_client: Optional[LLMClient] = None,
    vector_store: Optional[Any] = None,
    timeout_seconds: float = LLM_DIAGNOSIS_TIMEOUT_SECONDS,
    sessions: Optional[List[Any]] = None,
) -> tuple[str, DiagStrategy, List[Dict[str, Any]]]:
    """Generate coach explanation prose and bounded strategy choice via RAG + LLM.

    Strict rules:
    - Zero digits or number words in prose.
    - No unsupported CNS/motor unit claims; hedged physiological prose only.
    - No nutrition-deficit claims as a *cause* (no intake data available).
    - If empty RAG or unrelated passages, prompt strictly forbids claiming research support.
    - Contradiction check: prose must not contradict computed metrics (e.g. claiming stable effort when RPE is rising).
    - Validates prose with validate_llm_prose(text, evidence); on failure/timeout falls back to render_fallback().
    - Bounded strategy: LLM picks one from Python-approved strategies; picks outside the set fall back to default.
    - Structured output: (1) pattern sentence, (2) strategy justification, (3) 2-3 confounders to check.
    - Temperature: 0.3 for consistency.
    """
    default_strategy = result.deload_target.strategy
    approved_strategies = get_approved_strategies(result.root_cause, default_strategy)
    fallback_text = render_fallback(result)

    # Low-data / non-prescriptive states use deterministic templates directly
    if result.root_cause in (
        RootCause.insufficient_data,
        RootCause.deloading,
        RootCause.deload_cooldown,
    ):
        return fallback_text, default_strategy, []

    # 1. RAG retrieval (Module 5) with strict relevance filter
    sources: List[Dict[str, Any]] = []
    passages: list = []
    has_rag_passages = False
    context_str = ""
    try:
        store = vector_store or get_vector_store()
        query = f"{experience_level} {goal} {result.root_cause.value} {default_strategy.value} fatigue recovery deload"
        raw_passages = store.search(query, category="exercise", k=3)
        # Filter: only keep passages that directly discuss fatigue, recovery, deload, or periodization
        relevant_keywords = ("deload", "overreach", "fatigue", "volume reduction", "recovery", "periodiz", "supercompensation")
        passages = [p for p in raw_passages if any(k in p.text.lower() for k in relevant_keywords)]
        if passages:
            sources = [{"source": p.source, "page": p.page, "score": round(p.score, 4), "text": p.text} for p in passages]
            context_str = "\n".join(f"[{i+1}] {p.text}" for i, p in enumerate(passages))
            has_rag_passages = True
    except Exception:
        passages = []

    if has_rag_passages:
        research_instruction = (
            "Ground your physiological explanation strictly in these retrieved passages:\n"
            f"{context_str}\n\n"
            "CITATION RULES:\n"
            "- Only cite a passage [1], [2], or [3] immediately after the specific sentence whose "
            "claim is DIRECTLY and explicitly supported by that passage's text.\n"
            "- If no passage directly supports a sentence, write it WITHOUT any citation.\n"
            "- Do NOT cite passages for basic lifter observations or lifestyle factors unless explicitly discussed in the text.\n"
        )
    else:
        research_instruction = (
            "No research passages were found for this query. "
            "You must NOT include any citations ([1], [2], etc.) and "
            "You must NOT claim, cite, or imply any scientific or clinical research support."
        )

    allowed_strategies_str = ", ".join(s.value for s in approved_strategies)
    strat_value = default_strategy.value

    is_gray_zone = (
        result.root_cause == RootCause.undetermined_cause
        or result.evidence.noisy_data
    )

    sigs = _word_signals(result.evidence, sessions=sessions)

    if is_gray_zone:
        system_prompt = (
            "You are an evidence-based strength coach explaining an ambiguous training plateau.\n\n"
            f"{research_instruction}\n\n"
            f"{_ABSTRACT_FORMAT_ILLUSTRATION}\n"
            "STRICT NON-NEGOTIABLE CONSTRAINTS:\n"
            "1. NEVER include any digits (0-9), percentages, or number words "
            "(e.g. zero, one, two, three, four, five, ten, half, quarter). "
            "The token '1RM' and citation tags like [1] are the ONLY allowed tokens containing numbers.\n"
            "2. Do NOT mention central nervous system, CNS, neural fatigue, or motor units.\n"
            "3. Do NOT claim a nutritional deficit is the cause — you have no intake data. "
            "Nutrition adequacy may only appear as a confounder to check.\n"
            "4. Do NOT use the phrases 'deficit', 'you are fatigued', 'you should take a break', or 'take a break'.\n"
            "5. Do NOT copy, mimic, or reuse wording from any example. Write an original explanation tailored to the exact directions provided.\n"
            f"6. The Python prescription is '{strat_value}'. Select only from: [{allowed_strategies_str}]. "
            "Your STRATEGY line must match one of these exactly.\n"
            "7. FIXED STRUCTURE — three sentences only:\n"
            "   Sentence A: What the observed signals are most consistent with (hedged, e.g. 'may reflect', 'is consistent with an ambiguous pattern'). Do NOT assert definite fatigue.\n"
            f"   Sentence B: Why the '{strat_value}' strategy fits this ambiguous pattern specifically without changing volume or load prematurely.\n"
            "   Sentence C: Two or three concrete things the lifter should log or check next (sleep consistency, daily energy intake adequacy, logging exertion per set, technique).\n"
            "8. CITATION RULE: only cite [1]/[2]/[3] after a sentence whose claim is directly supported by that passage. "
            "Omit citations for sentences the passages do not directly support.\n\n"
            "Format output EXACTLY as:\n"
            "STRATEGY: <chosen_strategy>\n"
            "EXPLANATION: <prose>"
        )

        user_message = (
            f"Lifter profile: {experience_level} lifter, goal: {goal}.\n"
            f"Root cause diagnosed by Python: '{result.root_cause.value}'.\n"
            f"Direction labels from data (Observed signals):\n"
            f" - Weight direction: {sigs['weight_trend']}\n"
            f" - Strength (1RM) direction: {sigs['strength_trend']}\n"
            f" - Effort (RPE) direction: {sigs['effort_signal']}\n"
            f" - Intra-session rep direction: {sigs['rep_signal']}\n"
            f"Effort data coverage: {sigs['rpe_coverage']}.\n"
            f"Weekly training volume: {sigs['volume_status']}.\n"
            f"Python prescription: strategy = '{strat_value}'.\n"
            f"Approved options: [{allowed_strategies_str}].\n\n"
            "Write three sentences following the FIXED STRUCTURE. Respect the direction labels above (e.g. if effort is absent, do NOT claim effort is rising)."
        )
    else:
        system_prompt = (
            "You are an evidence-based strength coach explaining a fatigue analysis.\n\n"
            f"{research_instruction}\n\n"
            f"{_ABSTRACT_FORMAT_ILLUSTRATION}\n"
            "STRICT NON-NEGOTIABLE CONSTRAINTS:\n"
            "1. NEVER include any digits (0-9), percentages, or number words "
            "(e.g. zero, one, two, three, four, five, ten, half, quarter). "
            "The token '1RM' and citation tags like [1] are the ONLY allowed tokens containing numbers.\n"
            "2. Do NOT mention central nervous system, CNS, neural fatigue, or motor units. "
            "Use cautious, hedged physiological language (e.g. 'patterns suggest', 'consistent with', 'may reflect').\n"
            "3. Do NOT use the phrases 'deficit', 'you are fatigued', 'you should take a break', or 'take a break'.\n"
            "4. Do NOT claim a nutritional deficit is the cause — you have no intake data.\n"
            "5. Do NOT copy, mimic, or reuse wording from any example. Write original prose tailored to the observed signals.\n"
            f"6. The Python prescription is '{strat_value}'. Your STRATEGY line must be exactly '{strat_value}'.\n"
            "7. FIXED STRUCTURE — three sentences only:\n"
            "   Sentence A: Name the specific signals observed using the exact direction labels provided (words only, no numbers) and what pattern they are consistent with.\n"
            f"   Sentence B: Why the '{strat_value}' strategy fits: explain in your own words how {strat_value} directly addresses the observed pattern without copying generic phrases.\n"
            "   Sentence C: Two or three concrete confounders or lifestyle factors to check next (sleep, stress, nutrition adequacy, technique).\n"
            "8. CITATION RULE: only cite [1]/[2]/[3] after a sentence whose claim is directly supported by that passage. "
            "Omit citations for sentences the passages do not directly support.\n\n"
            "Format output EXACTLY as:\n"
            "STRATEGY: <chosen_strategy>\n"
            "EXPLANATION: <prose>"
        )

        user_message = (
            f"Lifter profile: {experience_level} lifter, goal: {goal}.\n"
            f"Root cause diagnosed by Python: '{result.root_cause.value}'.\n"
            f"Direction labels from data:\n"
            f" - Weight direction: {sigs['weight_trend']}\n"
            f" - Strength (1RM) direction: {sigs['strength_trend']}\n"
            f" - Effort (RPE) direction: {sigs['effort_signal']}\n"
            f" - Intra-session rep direction: {sigs['rep_signal']}\n"
            f"Effort data coverage: {sigs['rpe_coverage']}.\n"
            f"Weekly training volume: {sigs['volume_status']}.\n"
            f"Python prescription: strategy = '{strat_value}'.\n"
            f"Approved options: [{allowed_strategies_str}].\n\n"
            "Write three sentences following the FIXED STRUCTURE. Respect the direction labels above (e.g. if weight is flat, do NOT claim weight is declining; if effort is climbing, do NOT claim effort is stable)."
        )

    client = llm_client or get_llm_client()

    def _call() -> str:
        return client.complete(
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt,
            temperature=0.3,
        )

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_call)
        raw_output = future.result(timeout=timeout_seconds)
    except Exception:
        # Timeout or error -> fallback
        return fallback_text, default_strategy, sources
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if not raw_output or not isinstance(raw_output, str):
        return fallback_text, default_strategy, sources

    raw_output = raw_output.strip()
    chosen_strategy = default_strategy
    prose_explanation = raw_output

    if "STRATEGY:" in raw_output and "EXPLANATION:" in raw_output:
        parts = raw_output.split("EXPLANATION:")
        strat_part = parts[0].replace("STRATEGY:", "").strip().lower()
        prose_explanation = parts[1].strip()

        # Bounded strategy verification: must be in approved_strategies
        for s in approved_strategies:
            if s.value.lower() == strat_part:
                chosen_strategy = s
                break
    elif "EXPLANATION:" in raw_output:
        prose_explanation = raw_output.split("EXPLANATION:")[1].strip()

    # Validate prose — must contain zero unvalidated numbers, valid citation bounds, no forbidden phrases, and no contradictions
    if not validate_llm_prose(prose_explanation, evidence=result.evidence, max_citation_index=len(passages)):
        return fallback_text, default_strategy, sources

    return prose_explanation, chosen_strategy, sources


# Known limit: volume-only deloads (same weight, fewer sets) are NOT detected
# by the weight-drop heuristic below. Heavy/light programming (alternating loads)
# can also produce false positives if the light session falls below 85% of the
# heavy session. Both require explicit manual marking, which is out of scope for v1.
MANUAL_DELOAD_DETECTION_KNOWN_LIMITS = (
    "volume-only deloads and heavy/light programming alternations are not detected"
)


def _is_deload_active(record: DeloadRecord) -> bool:
    """True when the deload record is ongoing (not cancelled, completed, or expired)."""
    now = datetime.now(timezone.utc)
    if record.cancelled_at is not None:
        return False
    if record.completed_at is not None:
        return False
    if record.expires_at is not None:
        exp = record.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            return False
    return True


def _deload_sessions_completed(
    db: Session,
    record: DeloadRecord,
) -> int:
    """Count distinct-date sessions logged at deload weight since applied_at.

    A session counts if:
    - performed_at >= record.applied_at
    - exercise_id == record.exercise_id and user_id == record.user_id
    - The session's max weight_kg is within record.weight_match_tolerance_kg of
      record.target_weight_kg (plate-increment tolerance; lb users need ~1.134 kg).

    Sessions are counted by distinct date (not by set count) to avoid penalising
    users who log multiple sets per session.
    """
    applied = record.applied_at
    if applied.tzinfo is None:
        applied = applied.replace(tzinfo=timezone.utc)

    stmt = select(WorkoutSet).where(
        WorkoutSet.user_id == record.user_id,
        WorkoutSet.exercise_id == record.exercise_id,
    )
    rows = db.exec(stmt).all()

    # Filter rows performed on or after applied_at
    filtered_rows: List[WorkoutSet] = []
    for ws in rows:
        p_at = ws.performed_at
        if p_at.tzinfo is None:
            p_at = p_at.replace(tzinfo=timezone.utc)
        if p_at >= applied:
            filtered_rows.append(ws)

    # Group by date
    by_date: Dict[str, List[WorkoutSet]] = {}
    for ws in filtered_rows:
        d = ws.performed_at.strftime("%Y-%m-%d")
        by_date.setdefault(d, []).append(ws)

    count = 0
    tol = record.weight_match_tolerance_kg
    for sets in by_date.values():
        max_w = max(ws.weight_kg for ws in sets)
        if abs(max_w - record.target_weight_kg) <= tol:
            count += 1
    return count


def _get_active_deload(db: Session, user_id: int, exercise_id: str) -> Optional[DeloadRecord]:
    """Return the currently active DeloadRecord for this user+exercise, or None."""
    stmt = (
        select(DeloadRecord)
        .where(
            DeloadRecord.user_id == user_id,
            DeloadRecord.exercise_id == exercise_id,
            DeloadRecord.cancelled_at.is_(None),   # type: ignore[attr-defined]
            DeloadRecord.completed_at.is_(None),    # type: ignore[attr-defined]
        )
        .order_by(desc(DeloadRecord.applied_at))
        .limit(1)
    )
    record = db.exec(stmt).first()
    if record and _is_deload_active(record):
        return record
    return None


def _detect_manual_deload_cutoff(
    groups: List[SessionGroup],
) -> Optional[datetime]:
    """Return the performed_at of the most recent suspected-manual-deload session.

    Detection rule: a session's max weight_kg < prev session max weight_kg × 0.85.
    Known limit: volume-only deloads (same weight, fewer sets) are NOT detected.
    Heavy/light alternating programmes can produce false positives.

    Returns: the performed_at of the first post-deload session (i.e. where the
    drop occurred), so callers can exclude all sessions BEFORE that point.
    Returns None if no manual deload is suspected.
    """
    if len(groups) < 2:
        return None

    # groups is newest-first; reverse to chronological
    chron = list(reversed(groups))
    for i in range(1, len(chron)):
        prev_max = max(ws.weight_kg for ws in chron[i - 1].sets)
        curr_max = max(ws.weight_kg for ws in chron[i].sets)
        if prev_max > 0 and curr_max < prev_max * DIAG_MANUAL_DELOAD_THRESHOLD:
            # Suspected manual deload at session i; sessions after this are post-deload
            cutoff_date = chron[i].date   # "YYYY-MM-DD"
            return datetime.strptime(cutoff_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return None


def _build_diag_sessions(
    db: Session,
    exercise_id: str,
    user_id: int,
    cooldown_sessions: int = DIAG_DELOAD_COOLDOWN_SESSIONS,
) -> List[DiagSessionData]:
    """Fetch history and assemble DiagSessionData[] for diagnose_fatigue.

    Steps:
    1. Pull the last DIAG_PLATEAU_WINDOW_DAYS of sets.
    2. Group into SessionGroup[]  (chronological, newest first from DB → reversed).
    3. Detect manual-deload cutoff; if found, skip sessions in the pre-cutoff window
       and the first `cooldown_sessions` normal sessions after the deload.
    4. Convert remaining sessions to DiagSessionData using day-offsets from the
       earliest included session.
    """
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=DIAG_PLATEAU_WINDOW_DAYS)
    history: List[SessionGroup] = get_history(
        db, exercise_id, user_id=user_id, since=cutoff_dt, limit=200
    )
    if not history:
        return []

    # history is newest-first; reverse to chronological
    chron = list(reversed(history))

    # Detect manual deload
    manual_cutoff = _detect_manual_deload_cutoff(history)
    if manual_cutoff is not None:
        # Keep only sessions on or after the cutoff date
        chron = [
            g for g in chron
            if datetime.strptime(g.date, "%Y-%m-%d").replace(tzinfo=timezone.utc) >= manual_cutoff
        ]
        # Skip the first `cooldown_sessions` sessions (the deload itself + cool-down)
        chron = chron[cooldown_sessions:]

    if not chron:
        return []

    # Build DiagSessionData with day offsets from earliest included session
    base_date = datetime.strptime(chron[0].date, "%Y-%m-%d").date()
    result: List[DiagSessionData] = []
    for g in chron:
        session_date = datetime.strptime(g.date, "%Y-%m-%d").date()
        day_offset = (session_date - base_date).days
        sets = [
            DiagSetData(
                weight_kg=ws.weight_kg,
                reps=ws.reps,
                rpe=ws.rpe,
            )
            for ws in g.sets
        ]
        result.append(DiagSessionData(day_offset=day_offset, sets=sets))

    return result


def get_diagnosis(
    db: Session,
    exercise_id: str,
    user_id: int = 1,
    experience_level: Optional[str] = None,
    volume_count: Optional[int] = None,
    profile_is_default: Optional[bool] = None,
    unit: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
    vector_store: Optional[Any] = None,
) -> dict:
    """POST /diagnosis — read-only: analyse history, retrieve RAG, generate prose explanation.

    Does NOT create a DeloadRecord. The client must explicitly call
    POST /apply-deload to persist the prescription.
    """
    exercise = get_exercise(exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail=f"Exercise '{exercise_id}' not found")

    profile = None
    try:
        profile = db.exec(select(UserProfile).where(UserProfile.user_id == user_id)).first()
    except Exception:
        pass

    exp = experience_level
    if not exp:
        exp = profile.experience_level.value if profile and hasattr(profile, "experience_level") else "intermediate"

    vol = volume_count
    if vol is None:
        try:
            vol_summary = get_weekly_volume_summary(db, user_id=user_id)
            if exercise and exercise.primary_muscle.value in vol_summary.get("muscles", {}):
                vol = vol_summary["muscles"][exercise.primary_muscle.value]["count"]
            else:
                vol = 12
        except Exception:
            vol = 12

    is_default = profile_is_default
    if is_default is None:
        is_default = (profile is None or (profile.weight_kg == 75.0 and profile.height_cm == 175.0))

    goal = profile.goal.value if profile and hasattr(profile, "goal") else "hypertrophy"

    chosen_unit = unit
    if not chosen_unit:
        if profile and hasattr(profile, "unit_system") and profile.unit_system:
            val = profile.unit_system.value if hasattr(profile.unit_system, "value") else str(profile.unit_system)
            chosen_unit = "lb" if val in ("imperial", "lb") else "kg"
        else:
            chosen_unit = "kg"

    diag_sessions = _build_diag_sessions(db, exercise_id, user_id)
    result = diagnose_fatigue(
        sessions=diag_sessions,
        experience_level=exp,
        volume_count=vol,
        profile_is_default=is_default,
    )

    if result.deload_target.target_weight_kg is not None:
        target_w, _, _ = _round_to_plate_increment(result.deload_target.target_weight_kg, chosen_unit)
        result.deload_target.target_weight_kg = target_w
    if result.deload_target.resume_weight_kg is not None:
        resume_w, _, _ = _round_to_plate_increment(result.deload_target.resume_weight_kg, chosen_unit)
        result.deload_target.resume_weight_kg = resume_w

    explanation, chosen_strategy, sources = generate_diagnosis_explanation(
        result=result,
        experience_level=exp,
        goal=goal,
        llm_client=llm_client,
        vector_store=vector_store,
        sessions=diag_sessions,
    )
    approved_strategies = get_approved_strategies(result.root_cause, result.deload_target.strategy)

    # Check whether an active deload already exists
    active = _get_active_deload(db, user_id, exercise_id)

    return {
        "diagnosis": result,
        "explanation": explanation,
        "chosen_strategy": chosen_strategy.value if hasattr(chosen_strategy, "value") else str(chosen_strategy),
        "approved_strategies": [s.value for s in approved_strategies],
        "sources": sources,
        "active_deload": active,
        "deload_sessions_completed": (
            _deload_sessions_completed(db, active) if active else None
        ),
    }


def apply_deload(
    db: Session,
    request: ApplyDeloadRequest,
    user_id: int = 1,
    experience_level: Optional[str] = None,
    volume_count: Optional[int] = None,
    profile_is_default: Optional[bool] = None,
) -> DeloadRecordRead:
    """POST /apply-deload — server-side recompute + persist.

    Rejects if an active DeloadRecord already exists for this user+exercise.
    The prescription is recomputed fresh from history; client numbers are never trusted.
    """
    exercise = get_exercise(request.exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail=f"Exercise '{request.exercise_id}' not found")

    # Guard: reject if already in a deload
    existing = _get_active_deload(db, user_id, request.exercise_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Active deload record (id={existing.id}) already exists "
                f"for exercise '{request.exercise_id}'. Cancel it before applying a new one."
            ),
        )

    profile = None
    try:
        profile = db.exec(select(UserProfile).where(UserProfile.user_id == user_id)).first()
    except Exception:
        pass

    exp = experience_level
    if not exp:
        exp = profile.experience_level.value if profile and hasattr(profile, "experience_level") else "intermediate"

    vol = volume_count
    if vol is None:
        try:
            vol_summary = get_weekly_volume_summary(db, user_id=user_id)
            if exercise and exercise.primary_muscle.value in vol_summary.get("muscles", {}):
                vol = vol_summary["muscles"][exercise.primary_muscle.value]["count"]
            else:
                vol = 12
        except Exception:
            vol = 12

    is_default = profile_is_default
    if is_default is None:
        is_default = (profile is None or (profile.weight_kg == 75.0 and profile.height_cm == 175.0))

    # Server-side recompute
    diag_sessions = _build_diag_sessions(db, request.exercise_id, user_id)
    result = diagnose_fatigue(
        sessions=diag_sessions,
        experience_level=exp,
        volume_count=vol,
        profile_is_default=is_default,
    )

    # Bounded strategy choice: verify pick is in approved_strategies, else reject
    approved_strategies = get_approved_strategies(result.root_cause, result.deload_target.strategy)
    selected_strategy = result.deload_target.strategy
    if request.strategy:
        matched = False
        for s in approved_strategies:
            if s.value.lower() == request.strategy.lower():
                selected_strategy = s
                matched = True
                break
        if not matched:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Strategy '{request.strategy}' is not allowed for root cause '{result.root_cause.value}'. "
                    f"Approved options: {[s.value for s in approved_strategies]}"
                ),
            )

    # Only persist if a meaningful deload strategy is indicated
    if selected_strategy in (DiagStrategy.no_action, DiagStrategy.hold):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Diagnosis is '{result.root_cause.value}' with strategy "
                f"'{selected_strategy.value}' — no deload prescribed."
            ),
        )

    now = datetime.now(timezone.utc)

    # Determine unit preference (from request or UserProfile)
    chosen_unit = request.unit
    if not chosen_unit:
        if profile and hasattr(profile, "unit_system") and profile.unit_system:
            val = profile.unit_system.value if hasattr(profile.unit_system, "value") else str(profile.unit_system)
            chosen_unit = "lb" if val in ("imperial", "lb") else "kg"
        else:
            chosen_unit = "kg"

    target_w_calc = result.deload_target.target_weight_kg
    target_sets_calc = result.deload_target.target_sets

    # Handle alternative approved strategy adjustments deterministically
    if selected_strategy == DiagStrategy.weight_reduction and result.deload_target.strategy == DiagStrategy.volume_reduction:
        target_w_calc = result.evidence.current_weight_kg * (1.0 - DIAG_WEIGHT_REDUCTION_PCT)
        target_sets_calc = result.evidence.current_sets
    elif selected_strategy == DiagStrategy.volume_reduction and result.deload_target.strategy == DiagStrategy.weight_reduction:
        target_w_calc = result.evidence.current_weight_kg
        target_sets_calc = max(2, result.evidence.current_sets - 1)

    target_weight_kg, plate_inc_kg, tol_kg = _round_to_plate_increment(
        target_w_calc,
        chosen_unit,
    )
    resume_weight_kg, _, _ = _round_to_plate_increment(
        result.deload_target.resume_weight_kg,
        chosen_unit,
    )

    record = DeloadRecord(
        user_id=user_id,
        exercise_id=request.exercise_id,
        strategy=selected_strategy.value,
        root_cause=result.root_cause.value,
        confidence=result.confidence.value,
        target_weight_kg=target_weight_kg,
        target_sets=target_sets_calc,
        target_reps_range=result.deload_target.target_reps_range,
        target_rpe_ceiling=result.deload_target.target_rpe_ceiling,
        resume_weight_kg=resume_weight_kg,
        duration_sessions=result.deload_target.duration_sessions,
        constants_version=CONSTANTS_VERSION,
        unit="lb" if chosen_unit in ("lb", "imperial") else "kg",
        plate_increment_kg=plate_inc_kg,
        weight_match_tolerance_kg=tol_kg,
        profile_is_default=is_default,
        applied_at=now,
        expires_at=now + timedelta(days=DELOAD_EXPIRY_DAYS),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    completed = _deload_sessions_completed(db, record)
    return DeloadRecordRead(
        id=record.id,
        exercise_id=record.exercise_id,
        strategy=record.strategy,
        root_cause=record.root_cause,
        confidence=record.confidence,
        target_weight_kg=record.target_weight_kg,
        target_sets=record.target_sets,
        target_reps_range=record.target_reps_range,
        target_rpe_ceiling=record.target_rpe_ceiling,
        resume_weight_kg=record.resume_weight_kg,
        duration_sessions=record.duration_sessions,
        sessions_completed=completed,
        is_active=_is_deload_active(record),
        applied_at=record.applied_at,
        expires_at=record.expires_at,
        constants_version=record.constants_version,
        unit=record.unit,
        plate_increment_kg=record.plate_increment_kg,
        weight_match_tolerance_kg=record.weight_match_tolerance_kg,
    )


def cancel_deload(
    db: Session,
    request: CancelDeloadRequest,
    user_id: int,
) -> DeloadRecordRead:
    """POST /cancel-deload — marks a deload record as cancelled."""
    record = db.get(DeloadRecord, request.deload_record_id)
    if not record or record.user_id != user_id:
        raise HTTPException(status_code=404, detail="Deload record not found")
    if not _is_deload_active(record):
        raise HTTPException(status_code=409, detail="Deload record is already inactive")

    now = datetime.now(timezone.utc)
    record.cancelled_at = now
    record.cancel_reason = request.reason
    db.add(record)
    db.commit()
    db.refresh(record)

    completed = _deload_sessions_completed(db, record)
    return DeloadRecordRead(
        id=record.id,
        exercise_id=record.exercise_id,
        strategy=record.strategy,
        root_cause=record.root_cause,
        confidence=record.confidence,
        target_weight_kg=record.target_weight_kg,
        target_sets=record.target_sets,
        target_reps_range=record.target_reps_range,
        target_rpe_ceiling=record.target_rpe_ceiling,
        resume_weight_kg=record.resume_weight_kg,
        duration_sessions=record.duration_sessions,
        sessions_completed=completed,
        is_active=False,
        applied_at=record.applied_at,
        expires_at=record.expires_at,
        constants_version=record.constants_version,
        unit=record.unit,
        plate_increment_kg=record.plate_increment_kg,
        weight_match_tolerance_kg=record.weight_match_tolerance_kg,
    )
