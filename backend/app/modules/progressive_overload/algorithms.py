"""
app/modules/progressive_overload/algorithms.py
Pure, deterministic progression algorithms, plateau detection, and volume tracking.
No database, no FastAPI, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from app.modules.exercises.catalog import Exercise, MovementPattern, MuscleGroup


# ── Editable Constants ────────────────────────────────────────────────────────

DEFAULT_INCREMENT_UPPER_COMPOUND = 2.5
DEFAULT_INCREMENT_LOWER_COMPOUND = 5.0
DEFAULT_INCREMENT_ISOLATION = 1.25

DEFAULT_RPE_CEILING = 8.5
EFFECTIVE_SET_MIN_RPE = 6.0

VOLUME_MIN_IN_RANGE = 10
VOLUME_MAX_IN_RANGE = 20


@dataclass(frozen=True)
class Recommendation:
    weight_kg: float
    rep_target: str
    alternative: Optional[str]
    reason: str
    plateau_flag: bool
    deload_suggested: bool


def epley_1rm(weight_kg: float, reps: int) -> float:
    """Epley formula for estimated 1-Rep Max: weight * (1 + reps / 30)."""
    if reps <= 0 or weight_kg <= 0:
        return 0.0
    if reps == 1:
        return weight_kg
    return weight_kg * (1.0 + reps / 30.0)


def parse_rep_range(rep_range: Union[str, Tuple[int, int]]) -> Tuple[int, int]:
    """Parse '6-12' -> (6, 12)."""
    if isinstance(rep_range, tuple):
        return rep_range
    parts = rep_range.split("-")
    if len(parts) == 2:
        return int(parts[0].strip()), int(parts[1].strip())
    val = int(parts[0].strip())
    return val, val


def get_default_increment(exercise: Exercise) -> float:
    """Determine default weight increment based on movement pattern and compound nature."""
    if not exercise.is_compound or exercise.movement_pattern == MovementPattern.ISOLATION:
        return DEFAULT_INCREMENT_ISOLATION

    lower_patterns = {MovementPattern.SQUAT, MovementPattern.HINGE, MovementPattern.LUNGE}
    lower_muscles = {MuscleGroup.QUADS, MuscleGroup.HAMSTRINGS}

    if exercise.movement_pattern in lower_patterns or exercise.primary_muscle in lower_muscles:
        return DEFAULT_INCREMENT_LOWER_COMPOUND
    return DEFAULT_INCREMENT_UPPER_COMPOUND


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def double_progression(
    last_session_sets: List[Any],
    rep_range: Union[str, Tuple[int, int]],
    increment_kg: float,
    rpe_ceiling: float = DEFAULT_RPE_CEILING,
    plateau_flag: bool = False,
    deload_suggested: bool = False,
) -> Recommendation:
    """Double progression rule:
    1. If every working set reached the top of the rep range at or below the RPE ceiling,
       advance weight by increment_kg and reset reps to the bottom of the range.
    2. Otherwise, keep the same weight and add 1 rep to the weakest set,
       with an alternative of weight + increment at bottom of range.
    """
    if not last_session_sets:
        min_reps, _ = parse_rep_range(rep_range)
        return Recommendation(
            weight_kg=20.0,
            rep_target=f"3x{min_reps}",
            alternative=None,
            reason="No history found. Start with a light manageable weight.",
            plateau_flag=False,
            deload_suggested=False,
        )

    min_reps, max_reps = parse_rep_range(rep_range)
    num_sets = len(last_session_sets)
    base_weight = float(_get_val(last_session_sets[0], "weight_kg", 0.0))

    all_hit_top = True
    min_reps_achieved = 999

    for s in last_session_sets:
        reps = int(_get_val(s, "reps", 0))
        rpe = _get_val(s, "rpe", None)
        if reps < min_reps_achieved:
            min_reps_achieved = reps

        if reps < max_reps or (rpe is not None and float(rpe) > rpe_ceiling):
            all_hit_top = False

    if all_hit_top:
        new_weight = round(base_weight + increment_kg, 2)
        return Recommendation(
            weight_kg=new_weight,
            rep_target=f"{num_sets}x{min_reps}",
            alternative=None,
            reason=f"Completed all {num_sets} sets at {max_reps} reps! Increase weight by {increment_kg} kg.",
            plateau_flag=plateau_flag,
            deload_suggested=deload_suggested,
        )
    else:
        target_reps = min_reps_achieved + 1
        alt_weight = round(base_weight + increment_kg, 2)
        alt_str = f"{alt_weight} kg for {num_sets}x{min_reps}"
        reason = (
            f"Last session: {base_weight} kg for {num_sets}x{min_reps_achieved}. "
            f"Target: {base_weight} kg for {num_sets}x{target_reps}, or {alt_str}."
        )
        return Recommendation(
            weight_kg=base_weight,
            rep_target=f"{num_sets}x{target_reps}",
            alternative=alt_str,
            reason=reason,
            plateau_flag=plateau_flag,
            deload_suggested=deload_suggested,
        )


def linear_progression(
    last_session_sets: List[Any],
    weekly_increment_kg: float,
    prescribed_reps: int = 5,
    plateau_flag: bool = False,
    deload_suggested: bool = False,
) -> Recommendation:
    """Linear progression: add weekly_increment_kg when all sets hit prescribed reps, hold otherwise."""
    if not last_session_sets:
        return Recommendation(
            weight_kg=20.0,
            rep_target=f"3x{prescribed_reps}",
            alternative=None,
            reason="No history found. Start with an empty bar or manageable weight.",
            plateau_flag=False,
            deload_suggested=False,
        )

    num_sets = len(last_session_sets)
    base_weight = float(_get_val(last_session_sets[0], "weight_kg", 0.0))

    all_completed = True
    for s in last_session_sets:
        reps = int(_get_val(s, "reps", 0))
        if reps < prescribed_reps:
            all_completed = False
            break

    if all_completed:
        new_weight = round(base_weight + weekly_increment_kg, 2)
        return Recommendation(
            weight_kg=new_weight,
            rep_target=f"{num_sets}x{prescribed_reps}",
            alternative=None,
            reason=f"All {num_sets} sets completed at {prescribed_reps} reps. Increased weight by {weekly_increment_kg} kg.",
            plateau_flag=plateau_flag,
            deload_suggested=deload_suggested,
        )
    else:
        return Recommendation(
            weight_kg=base_weight,
            rep_target=f"{num_sets}x{prescribed_reps}",
            alternative=None,
            reason=f"Missed prescribed reps ({prescribed_reps}). Hold weight at {base_weight} kg.",
            plateau_flag=plateau_flag,
            deload_suggested=deload_suggested,
        )


def detect_plateau(
    sessions: List[List[Any]],
    window: int = 3,
) -> Tuple[bool, bool]:
    """Check if estimated 1RM has not improved over the last `window` sessions (newest first).
    Returns (plateau_flag, deload_suggested).
    """
    if len(sessions) < window:
        return False, False

    # Take the window of sessions
    recent_sessions = sessions[:window]

    max_1rms: List[float] = []
    avg_rpes: List[float] = []

    for sess in recent_sessions:
        best_1rm = 0.0
        rpe_sum = 0.0
        rpe_count = 0
        for s in sess:
            weight = float(_get_val(s, "weight_kg", 0.0))
            reps = int(_get_val(s, "reps", 0))
            rpe = _get_val(s, "rpe", None)

            est = epley_1rm(weight, reps)
            if est > best_1rm:
                best_1rm = est

            if rpe is not None:
                rpe_sum += float(rpe)
                rpe_count += 1

        max_1rms.append(best_1rm)
        avg_rpes.append(rpe_sum / rpe_count if rpe_count > 0 else 0.0)

    # recent_sessions is newest first: index 0 is most recent, index -1 is oldest in window
    # Plateau: newest 1RM <= oldest 1RM in the window
    newest_1rm = max_1rms[0]
    oldest_1rm = max_1rms[-1]
    is_plateau = newest_1rm <= oldest_1rm

    # Deload suggested: plateau AND RPE is trending up (newest average RPE > oldest average RPE)
    deload_suggested = is_plateau and (avg_rpes[0] > avg_rpes[-1] and avg_rpes[0] >= 8.5)

    return is_plateau, deload_suggested


def weekly_volume(
    sets: List[Any],
    catalog: Dict[str, Exercise],
    week_start: date,
) -> Dict[str, Dict[str, Any]]:
    """Calculate effective weekly sets (RPE >= 6.0) per muscle group for the week [week_start, week_start + 7 days).
    Returns dict: {muscle_name: {"count": int, "status": "below" | "in_range" | "above"}}.
    """
    week_end = week_start + timedelta(days=7)
    counts = {m.value: 0 for m in MuscleGroup}

    for s in sets:
        performed_at = getattr(s, "performed_at", s.get("performed_at") if isinstance(s, dict) else None)
        if isinstance(performed_at, datetime):
            p_date = performed_at.date()
        elif isinstance(performed_at, str):
            p_date = datetime.fromisoformat(performed_at).date()
        elif isinstance(performed_at, date):
            p_date = performed_at
        else:
            continue

        if not (week_start <= p_date < week_end):
            continue

        rpe = getattr(s, "rpe", s.get("rpe") if isinstance(s, dict) else None)
        # Check if effective set (RPE >= 6.0 or None defaults to effective)
        if rpe is not None and rpe < EFFECTIVE_SET_MIN_RPE:
            continue

        ex_id = getattr(s, "exercise_id", s.get("exercise_id") if isinstance(s, dict) else None)
        ex = catalog.get(ex_id)
        if ex:
            counts[ex.primary_muscle.value] += 1

    result: Dict[str, Dict[str, Any]] = {}
    for muscle, cnt in counts.items():
        if cnt < VOLUME_MIN_IN_RANGE:
            status = "below"
        elif cnt <= VOLUME_MAX_IN_RANGE:
            status = "in_range"
        else:
            status = "above"

        result[muscle] = {
            "count": cnt,
            "status": status,
        }

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# ── Plateau Diagnosis System ──────────────────────────────────────────────────
# Pure Python — no DB, no LLM, no FastAPI.
# All constants are heuristics; bump CONSTANTS_VERSION when any threshold changes.
# ═══════════════════════════════════════════════════════════════════════════════

import re as _re
from enum import Enum as _Enum


# ── Constants ─────────────────────────────────────────────────────────────────

DIAG_PLATEAU_WINDOW_DAYS: int = 28
DIAG_MIN_SESSION_SPAN_DAYS: int = 0  # Relaxed to 0 for interactive testing (was 14)
DIAG_MIN_SESSIONS: int = 3
DIAG_SESSION_GAP_DAYS_IGNORE: int = 10
DIAG_MIN_RPE_COVERAGE: float = 0.50
DIAG_RPE_CEILING: float = 9.5            # RPE slope unreliable at or above this
DIAG_NOISE_RATIO_THRESHOLD: float = 0.05 # regression residual RMSE / mean 1RM
DIAG_EPLEY_MAX_REPS: int = 12            # sets with reps > this excluded from Epley
DIAG_FLOAT_TOL: float = 1e-6
DIAG_WEIGHT_TOL: float = 0.01

DIAG_PROGRESS_THRESHOLD_PCT_PER_WEEK: Dict[str, float] = {
    "beginner":     1.5,
    "intermediate": 0.5,
    "advanced":     0.2,
}
DIAG_DECLINING_THRESHOLD_PCT_PER_WEEK: float = -0.5

# RPE slope threshold expressed in per-day units so it can be compared directly
# to the OLS regression output (x-axis = days, y-axis = RPE).
# Value derivation: 0.5 RPE/session ÷ 7 days/session = 0.0714 RPE/day.
# Equivalent to a 2.5-point RPE increase over a 5-week window at weekly cadence.
DIAG_RPE_FATIGUE_SLOPE_MIN_PER_DAY: float = 0.5 / 7.0   # ≈ 0.0714 RPE/day

DIAG_REP_DROPOFF_THRESHOLD: float = 0.15

# Prescription weight-cut constants (Fix 2 & 3 mentor v1.1)
DIAG_RPE_CAP_ACHIEVABLE_THRESHOLD: float = 8.5   # trigger: avg_rpe > this → apply weight cut
DIAG_RPE_GAP_CUT_SCALE: float = 0.033            # % weight cut per RPE point above deload ceiling
DIAG_RPE_GAP_CUT_MAX: float = 0.10               # cap: never cut more than 10% regardless of gap
DIAG_WEIGHT_REDUCTION_PCT: float = 0.10
DIAG_DELOAD_DURATION_SESSIONS: Dict[str, int] = {
    "beginner": 1, "intermediate": 2, "advanced": 3,
}
DIAG_DELOAD_RPE_CEILING: float = 7.0
DIAG_DELOAD_COOLDOWN_SESSIONS: int = 3
DIAG_MANUAL_DELOAD_THRESHOLD: float = 0.85  # weight < prev × 0.85 → suspected manual deload
DIAG_VOLUME_BELOW: int = 10
DIAG_VOLUME_ABOVE: int = 20
CONSTANTS_VERSION: str = "v1.1"


# ── Enums ──────────────────────────────────────────────────────────────────────

class RootCause(str, _Enum):
    progressing             = "progressing"
    fatigue_pattern         = "fatigue_pattern"
    possible_under_recovery = "possible_under_recovery"
    insufficient_stimulus   = "insufficient_stimulus"
    undetermined_cause      = "undetermined_cause"
    insufficient_data       = "insufficient_data"
    deloading               = "deloading"
    deload_cooldown         = "deload_cooldown"


class DiagStrategy(str, _Enum):
    volume_reduction = "volume_reduction"
    weight_reduction = "weight_reduction"
    progress_load    = "progress_load"
    hold             = "hold"
    no_action        = "no_action"


class DiagConfidence(str, _Enum):
    high   = "high"
    medium = "medium"
    low    = "low"


# ── Input / Output Data Structures ────────────────────────────────────────────

@dataclass
class DiagSetData:
    """One logged set, pre-converted to kg."""
    weight_kg: float
    reps: int
    rpe: Optional[float] = None       # None when not logged


@dataclass
class DiagSessionData:
    """One training session inside the analysis window.
    day_offset = calendar days since the earliest session in the window (so index 0 = day 0).
    """
    day_offset: int
    sets: List[DiagSetData]


@dataclass
class FatigueEvidence:
    sessions_analysed: int
    sessions_skipped: int                 # high-rep sessions excluded from 1RM calc
    session_span_days: int
    slope_pct_per_week: float
    slope_rpe_per_day: Optional[float]    # x-axis = days; None when can't use RPE
    slope_rpe_per_session: Optional[float]# derived display value; threshold comparison uses per-day
    avg_rep_dropoff_pct: Optional[float]  # mean of last 2 sessions; None for single-set sessions
    rpe_coverage_pct: float
    noisy_data: bool
    noise_ratio: float
    volume_count: int
    volume_status: str                    # "below" | "in_range" | "above"
    current_weight_kg: float             # top-set weight, most recent qualifying session
    current_sets: int                    # set count, most recent qualifying session
    current_avg_rpe: Optional[float]


@dataclass
class PrescriptionNote:
    """Python-rendered coach note. Never passed through the LLM."""
    text: str


@dataclass
class DiagDeloadTarget:
    strategy: DiagStrategy
    target_weight_kg: Optional[float] = None
    target_sets: Optional[int] = None
    target_reps_range: Optional[str] = None
    target_rpe_ceiling: Optional[float] = None
    resume_weight_kg: Optional[float] = None
    duration_sessions: Optional[int] = None
    prescription_note: Optional[PrescriptionNote] = None


@dataclass
class DiagnosisResult:
    plateau_detected: bool
    root_cause: RootCause
    confidence: DiagConfidence
    reason: str
    evidence: FatigueEvidence
    deload_target: DiagDeloadTarget
    profile_is_default: bool = False


# ── Internal Math ─────────────────────────────────────────────────────────────

def _diag_linreg_slope(xs: List[float], ys: List[float]) -> float:
    """OLS slope. Returns 0.0 when degenerate."""
    n = len(xs)
    if n < 2:
        return 0.0
    xm = sum(xs) / n
    ym = sum(ys) / n
    num = sum((xs[i] - xm) * (ys[i] - ym) for i in range(n))
    den = sum((xs[i] - xm) ** 2 for i in range(n))
    return num / den if abs(den) > DIAG_FLOAT_TOL else 0.0


def _diag_plain_epley(weight_kg: float, reps: int) -> Optional[float]:
    """Plain Epley 1RM. Returns None for sets outside valid range (reps > EPLEY_MAX or w <= 0)."""
    if reps <= 0 or weight_kg <= 0 or reps > DIAG_EPLEY_MAX_REPS:
        return None
    if reps == 1:
        return float(weight_kg)
    return weight_kg * (1.0 + reps / 30.0)


def _diag_session_best_1rm(session: DiagSessionData) -> Optional[float]:
    candidates = [_diag_plain_epley(s.weight_kg, s.reps) for s in session.sets]
    valid = [c for c in candidates if c is not None]
    return max(valid) if valid else None


def _diag_noise_ratio(
    days: List[float],
    best_1rms: List[float],
    slope_kg_per_day: float,
) -> float:
    """RMSE of regression residuals divided by mean 1RM. Uses residuals, NOT raw CV."""
    n = len(days)
    mean_1rm = sum(best_1rms) / n
    if mean_1rm <= DIAG_FLOAT_TOL:
        return 0.0
    xm = sum(days) / n
    intercept = mean_1rm - slope_kg_per_day * xm
    residuals = [best_1rms[i] - (slope_kg_per_day * days[i] + intercept) for i in range(n)]
    rmse = (sum(r ** 2 for r in residuals) / n) ** 0.5
    return rmse / mean_1rm


def _diag_rpe_data(
    sessions: List[DiagSessionData],
) -> Tuple[float, List[Tuple[float, float]]]:
    """Returns (coverage_fraction, [(day_offset, avg_rpe), ...]) for sessions that have RPE."""
    total_sets = sum(len(s.sets) for s in sessions)
    sets_with_rpe = sum(1 for s in sessions for st in s.sets if st.rpe is not None)
    coverage = sets_with_rpe / total_sets if total_sets > 0 else 0.0
    rpe_by_day: List[Tuple[float, float]] = []
    for s in sessions:
        rpes = [st.rpe for st in s.sets if st.rpe is not None]
        if rpes:
            rpe_by_day.append((float(s.day_offset), sum(rpes) / len(rpes)))
    return coverage, rpe_by_day


def _diag_rep_dropoff(session: DiagSessionData) -> Optional[float]:
    """Rep drop from first to last set using only same-weight sets.
    Returns None for single-set sessions (no dropoff computable).
    """
    if len(session.sets) <= 1:
        return None
    groups: Dict[float, List[int]] = {}
    for st in session.sets:
        key = round(st.weight_kg, 2)
        groups.setdefault(key, []).append(st.reps)
    # Use the group with the most sets; tiebreak by heaviest weight
    top_weight = max(groups, key=lambda w: (len(groups[w]), w))
    reps = groups[top_weight]
    if len(reps) <= 1:
        return None
    first, last = reps[0], reps[-1]
    return (first - last) / first if first > 0 else None


def _diag_mean_last2_rep_dropoff(sessions: List[DiagSessionData]) -> Optional[float]:
    """Mean rep dropoff over the last 2 sessions (or 1 if only 1 session exists).

    Using 2 sessions reduces noise from a single outlier set while still
    weighting recent fatigue evidence heavily.

    Returns None when no session in the tail has multi-set data (single-set
    sessions cannot produce a meaningful dropoff value). Callers MUST handle
    None explicitly — never default-to-zero, as that masks a no-signal state.
    """
    tail = sessions[-2:] if len(sessions) >= 2 else sessions
    drops = [_diag_rep_dropoff(s) for s in tail]
    valid = [d for d in drops if d is not None]
    return (sum(valid) / len(valid)) if valid else None


def _diag_volume_status(count: int) -> str:
    if count < DIAG_VOLUME_BELOW:
        return "below"
    if count > DIAG_VOLUME_ABOVE:
        return "above"
    return "in_range"


def _diag_round_to_increment(weight_kg: float, increment: float = 2.5) -> float:
    return round(round(weight_kg / increment) * increment, 2)


def _diag_default_rep_range(exercise_type: str) -> str:
    return {"compound": "6-12", "isolation": "10-15", "strength": "3-6"}.get(exercise_type, "6-12")


def _diag_default_increment(exercise_type: str) -> float:
    return {"compound": 2.5, "isolation": 1.25, "strength": 5.0}.get(exercise_type, 2.5)


# ── Confidence ────────────────────────────────────────────────────────────────

_CONF_ORDER = [DiagConfidence.low, DiagConfidence.medium, DiagConfidence.high]


def _diag_base_confidence(
    root_cause: RootCause,
    n: int,
    rpe_coverage: float,
    span: int,
    noisy: bool,
    can_use_rpe: bool,
) -> DiagConfidence:
    if root_cause in (
        RootCause.insufficient_data,
        RootCause.deloading,
        RootCause.deload_cooldown,
    ):
        return DiagConfidence.low

    if noisy:
        return DiagConfidence.low

    if rpe_coverage < DIAG_MIN_RPE_COVERAGE:
        return DiagConfidence.low

    if root_cause == RootCause.undetermined_cause:
        # Plateau confirmed but cause ambiguous — cap at medium even with great data
        if n >= DIAG_MIN_SESSIONS and span >= DIAG_MIN_SESSION_SPAN_DAYS and can_use_rpe:
            return DiagConfidence.medium
        return DiagConfidence.low

    if root_cause == RootCause.progressing:
        if n >= 4 and span >= 21 and not noisy:
            return DiagConfidence.high
        return DiagConfidence.medium

    # fatigue_pattern, possible_under_recovery, insufficient_stimulus
    if (
        n >= 4
        and rpe_coverage >= 0.75
        and span >= 21
        and not noisy
    ):
        return DiagConfidence.high
    if (
        n >= DIAG_MIN_SESSIONS
        and rpe_coverage >= DIAG_MIN_RPE_COVERAGE
        and span >= DIAG_MIN_SESSION_SPAN_DAYS
        and not noisy
    ):
        return DiagConfidence.medium
    return DiagConfidence.low


def _diag_adjust_confidence_volume(
    base: DiagConfidence,
    root_cause: RootCause,
    volume_status: str,
) -> DiagConfidence:
    """Apply volume adjustment: at most +1 tier, capped at medium.

    Volume is a supporting signal — it can close the gap from low to medium
    but cannot substitute for the data quality required for high confidence.
    Rule: never raises to high; never lowers an already-high base.
    """
    idx = _CONF_ORDER.index(base)
    medium_idx = _CONF_ORDER.index(DiagConfidence.medium)

    if root_cause == RootCause.fatigue_pattern and volume_status == "above":
        # Raise at most 1 tier, cap at medium; never lower an existing high
        new_idx = min(idx + 1, medium_idx)
        idx = max(idx, new_idx)
    elif root_cause == RootCause.insufficient_stimulus and volume_status == "below":
        new_idx = min(idx + 1, medium_idx)
        idx = max(idx, new_idx)
    elif root_cause == RootCause.fatigue_pattern and volume_status == "below":
        idx = max(idx - 1, 0)

    return _CONF_ORDER[idx]


# ── Prescription ──────────────────────────────────────────────────────────────

def _diag_prescription(
    root_cause: RootCause,
    current_weight_kg: float,
    current_sets: int,
    current_avg_rpe: Optional[float],
    experience_level: str,
    noisy_data: bool,
    exercise_type: str = "compound",
) -> DiagDeloadTarget:
    exp = experience_level if experience_level in DIAG_DELOAD_DURATION_SESSIONS else "intermediate"
    rep_range = _diag_default_rep_range(exercise_type)
    increment = _diag_default_increment(exercise_type)
    duration = DIAG_DELOAD_DURATION_SESSIONS[exp]

    # Fix (mentor): cap at hold when data is noisy — don't prescribe deload from noisy data
    if noisy_data and root_cause in (
        RootCause.fatigue_pattern,
        RootCause.possible_under_recovery,
        RootCause.insufficient_stimulus,
    ):
        return DiagDeloadTarget(
            strategy=DiagStrategy.hold,
            target_weight_kg=current_weight_kg,
            target_sets=current_sets,
            target_reps_range=rep_range,
            target_rpe_ceiling=8.5,
            resume_weight_kg=current_weight_kg,
            duration_sessions=2,
            prescription_note=PrescriptionNote(
                "Data quality too inconsistent to prescribe a deload. "
                "Log more consistent sessions before applying any protocol change."
            ),
        )

    if root_cause == RootCause.fatigue_pattern:
        # Fix (mentor v1.1): size the weight cut from the RPE gap, not a fixed 5%.
        # gap = avg_rpe − DIAG_DELOAD_RPE_CEILING (the target RPE for the deload).
        # scale: DIAG_RPE_GAP_CUT_SCALE % per RPE point, capped at DIAG_RPE_GAP_CUT_MAX.
        if current_avg_rpe is not None and current_avg_rpe > DIAG_RPE_CAP_ACHIEVABLE_THRESHOLD:
            rpe_gap = current_avg_rpe - DIAG_DELOAD_RPE_CEILING
            cut_pct = min(rpe_gap * DIAG_RPE_GAP_CUT_SCALE, DIAG_RPE_GAP_CUT_MAX)
            target_w = _diag_round_to_increment(
                current_weight_kg * (1.0 - cut_pct)
            )
            cut_pct_int = round(cut_pct * 100)
            note = PrescriptionNote(
                f"RPE gap: {rpe_gap:.1f} points above deload ceiling ({DIAG_DELOAD_RPE_CEILING}). "
                f"Weight cut {cut_pct_int}% (gap × {DIAG_RPE_GAP_CUT_SCALE * 100:.1f}%/point, "
                f"cap {int(DIAG_RPE_GAP_CUT_MAX * 100)}%) → {target_w} kg "
                f"to make RPE ≤ {DIAG_DELOAD_RPE_CEILING} achievable."
            )
        else:
            target_w = current_weight_kg
            note = PrescriptionNote(
                "Volume reduced. If this weight still exceeds RPE "
                f"{DIAG_DELOAD_RPE_CEILING}, drop by one increment."
            )
        return DiagDeloadTarget(
            strategy=DiagStrategy.volume_reduction,
            target_weight_kg=target_w,
            target_sets=max(2, current_sets - 1),
            target_reps_range=rep_range,
            target_rpe_ceiling=DIAG_DELOAD_RPE_CEILING,
            resume_weight_kg=current_weight_kg,
            duration_sessions=duration,
            prescription_note=note,
        )

    if root_cause == RootCause.possible_under_recovery:
        target_w = _diag_round_to_increment(
            current_weight_kg * (1.0 - DIAG_WEIGHT_REDUCTION_PCT)
        )
        return DiagDeloadTarget(
            strategy=DiagStrategy.weight_reduction,
            target_weight_kg=target_w,
            target_sets=current_sets,
            target_reps_range=rep_range,
            target_rpe_ceiling=DIAG_DELOAD_RPE_CEILING,
            resume_weight_kg=current_weight_kg,
            duration_sessions=duration,
        )

    if root_cause == RootCause.insufficient_stimulus:
        target_w = _diag_round_to_increment(current_weight_kg + increment)
        return DiagDeloadTarget(
            strategy=DiagStrategy.progress_load,
            target_weight_kg=target_w,
            target_sets=current_sets,
            target_reps_range=rep_range,
            target_rpe_ceiling=8.5,
            resume_weight_kg=target_w,
        )

    if root_cause == RootCause.undetermined_cause:
        return DiagDeloadTarget(
            strategy=DiagStrategy.hold,
            target_weight_kg=current_weight_kg,
            target_sets=current_sets,
            target_reps_range=rep_range,
            target_rpe_ceiling=8.5,
            resume_weight_kg=current_weight_kg,
            duration_sessions=2,
        )

    # progressing, insufficient_data, deloading, deload_cooldown
    return DiagDeloadTarget(strategy=DiagStrategy.no_action)


# ── Main Diagnosis Function ───────────────────────────────────────────────────

def _empty_evidence(volume_count: int, volume_status: str) -> FatigueEvidence:
    return FatigueEvidence(
        sessions_analysed=0,
        sessions_skipped=0,
        session_span_days=0,
        slope_pct_per_week=0.0,
        slope_rpe_per_day=None,
        slope_rpe_per_session=None,
        avg_rep_dropoff_pct=None,
        rpe_coverage_pct=0.0,
        noisy_data=False,
        noise_ratio=0.0,
        volume_count=volume_count,
        volume_status=volume_status,
        current_weight_kg=0.0,
        current_sets=0,
        current_avg_rpe=None,
    )


def diagnose_fatigue(
    sessions: List[DiagSessionData],
    experience_level: str,
    volume_count: int,
    profile_is_default: bool = False,
    exercise_type: str = "compound",
) -> DiagnosisResult:
    """Pure-Python plateau diagnosis state machine.

    Args:
        sessions: Pre-filtered sessions within PLATEAU_WINDOW_DAYS, sorted ascending
                  by day_offset. Gaps already handled by caller (split at gaps > 10 days,
                  use most recent sub-window). Deload sessions excluded by caller.
        experience_level: "beginner" | "intermediate" | "advanced"
        volume_count: Weekly effective sets for exercise's primary muscle (from weekly_volume()).
        profile_is_default: True when user has never customised their profile.
        exercise_type: "compound" | "isolation" | "strength"
    """
    # Fix (mentor): default profile → use intermediate thresholds, cap confidence at medium
    effective_exp = "intermediate" if profile_is_default else experience_level
    if effective_exp not in DIAG_PROGRESS_THRESHOLD_PCT_PER_WEEK:
        effective_exp = "intermediate"

    volume_status = _diag_volume_status(volume_count)

    # ── Step 0: Bodyweight exclusion ──────────────────────────────────────────
    if sessions and all(st.weight_kg <= 0 for s in sessions for st in s.sets):
        return DiagnosisResult(
            plateau_detected=False,
            root_cause=RootCause.insufficient_data,
            confidence=DiagConfidence.low,
            reason="Bodyweight exercises (weight_kg = 0) are excluded in v1.",
            evidence=_empty_evidence(volume_count, volume_status),
            deload_target=DiagDeloadTarget(strategy=DiagStrategy.no_action),
            profile_is_default=profile_is_default,
        )

    # ── Step 1: Data sufficiency ───────────────────────────────────────────────
    n = len(sessions)
    span = (sessions[-1].day_offset - sessions[0].day_offset) if n >= 2 else 0

    if n < DIAG_MIN_SESSIONS or span < DIAG_MIN_SESSION_SPAN_DAYS:
        reason = (
            f"Only {n} session(s) spanning {span} days — need "
            f"≥{DIAG_MIN_SESSIONS} sessions over ≥{DIAG_MIN_SESSION_SPAN_DAYS} days."
        )
        return DiagnosisResult(
            plateau_detected=False,
            root_cause=RootCause.insufficient_data,
            confidence=DiagConfidence.low,
            reason=reason,
            evidence=_empty_evidence(volume_count, volume_status),
            deload_target=DiagDeloadTarget(strategy=DiagStrategy.no_action),
            profile_is_default=profile_is_default,
        )

    # ── Current session stats (top-set weight, set count, last avg RPE) ───────
    last_sess = sessions[-1]
    current_weight_kg = max((st.weight_kg for st in last_sess.sets), default=0.0)
    current_sets = len(last_sess.sets)
    last_rpes = [st.rpe for st in last_sess.sets if st.rpe is not None]
    current_avg_rpe: Optional[float] = (sum(last_rpes) / len(last_rpes)) if last_rpes else None

    # ── Step 2: 1RM trend — skip sessions with no qualifying sets ─────────────
    days_x_all = [float(s.day_offset) for s in sessions]
    best_1rms_raw = [_diag_session_best_1rm(s) for s in sessions]

    # Fix 5 (mentor): sessions where every set exceeds DIAG_EPLEY_MAX_REPS are
    # skipped (not qualifying), not treated as an error. Re-check n and span
    # after filtering; if the window shrinks below minimums → insufficient_data.
    qualifying = [
        (s, float(rm), day)
        for s, rm, day in zip(sessions, best_1rms_raw, days_x_all)
        if rm is not None
    ]
    sessions_skipped = len(sessions) - len(qualifying)

    if len(qualifying) < DIAG_MIN_SESSIONS:
        reason = (
            f"Only {len(qualifying)} qualifying session(s) after skipping "
            f"{sessions_skipped} high-rep session(s) "
            f"(all sets > {DIAG_EPLEY_MAX_REPS} reps)."
        )
        return DiagnosisResult(
            plateau_detected=False,
            root_cause=RootCause.insufficient_data,
            confidence=DiagConfidence.low,
            reason=reason,
            evidence=_empty_evidence(volume_count, volume_status),
            deload_target=DiagDeloadTarget(strategy=DiagStrategy.no_action),
            profile_is_default=profile_is_default,
        )

    sessions = [q[0] for q in qualifying]
    best_1rms_f: List[float] = [q[1] for q in qualifying]
    days_x: List[float] = [q[2] for q in qualifying]
    n = len(sessions)
    span = int(days_x[-1] - days_x[0])

    if span < DIAG_MIN_SESSION_SPAN_DAYS:
        return DiagnosisResult(
            plateau_detected=False,
            root_cause=RootCause.insufficient_data,
            confidence=DiagConfidence.low,
            reason=(
                f"Qualifying session span {span}d < {DIAG_MIN_SESSION_SPAN_DAYS}d minimum "
                f"(after skipping {sessions_skipped} high-rep session(s))."
            ),
            evidence=_empty_evidence(volume_count, volume_status),
            deload_target=DiagDeloadTarget(strategy=DiagStrategy.no_action),
            profile_is_default=profile_is_default,
        )

    # Recompute current session stats from the last qualifying session
    last_sess = sessions[-1]
    current_weight_kg = max((st.weight_kg for st in last_sess.sets), default=0.0)
    current_sets = len(last_sess.sets)
    last_rpes = [st.rpe for st in last_sess.sets if st.rpe is not None]
    current_avg_rpe = (sum(last_rpes) / len(last_rpes)) if last_rpes else None

    mean_1rm = sum(best_1rms_f) / n

    slope_kg_per_day = _diag_linreg_slope(days_x, best_1rms_f)
    slope_kg_per_week = slope_kg_per_day * 7.0
    slope_pct_per_week = (slope_kg_per_week / mean_1rm * 100.0) if mean_1rm > DIAG_FLOAT_TOL else 0.0

    # ── Step 3: Noise check (regression residuals — NOT raw CV) ───────────────
    nr = _diag_noise_ratio(days_x, best_1rms_f, slope_kg_per_day)
    noisy_data = nr > DIAG_NOISE_RATIO_THRESHOLD

    # ── Step 4: RPE data (x-axis = days to match 1RM regression) ─────────────
    rpe_coverage, rpe_by_day = _diag_rpe_data(sessions)
    # can_use_rpe: sufficient coverage AND last session not at ceiling
    can_use_rpe = (
        rpe_coverage >= DIAG_MIN_RPE_COVERAGE
        and len(rpe_by_day) >= 2
        and (current_avg_rpe is None or current_avg_rpe < DIAG_RPE_CEILING)
    )

    slope_rpe_per_day: Optional[float] = None
    slope_rpe_per_session: Optional[float] = None
    if can_use_rpe:
        rpe_days = [r[0] for r in rpe_by_day]
        rpe_vals = [r[1] for r in rpe_by_day]
        slope_rpe_per_day = _diag_linreg_slope(rpe_days, rpe_vals)
        # Convert to per-session for threshold comparison (threshold is 0.5/session)
        avg_days_per_sess = span / (n - 1)
        slope_rpe_per_session = slope_rpe_per_day * avg_days_per_sess

    # ── Step 5: Rep dropoff (mean of last 2 sessions; None handled explicitly) ─
    mean_last2_dropoff = _diag_mean_last2_rep_dropoff(sessions)

    # ── Step 6: Plateau detection ─────────────────────────────────────────────
    threshold_pct = DIAG_PROGRESS_THRESHOLD_PCT_PER_WEEK[effective_exp]
    is_declining = slope_pct_per_week < DIAG_DECLINING_THRESHOLD_PCT_PER_WEEK - DIAG_FLOAT_TOL
    plateau_detected = slope_pct_per_week <= threshold_pct + DIAG_FLOAT_TOL

    # ── Step 7: Root cause ────────────────────────────────────────────────────
    root_cause: RootCause
    reason: str

    if not plateau_detected:
        root_cause = RootCause.progressing
        reason = (
            f"1RM trending at {slope_pct_per_week:.2f}%/week, above "
            f"{threshold_pct}% threshold for {effective_exp}."
        )
    else:
        # Both FLAT and DECLINING cases handled below
        if can_use_rpe and slope_rpe_per_day is not None:
            rpe_d = slope_rpe_per_day  # compare per-day to per-day threshold

            if is_declining:
                # Fix 1 (mentor): define declining branches when RPE is usable
                if rpe_d >= DIAG_RPE_FATIGUE_SLOPE_MIN_PER_DAY - DIAG_FLOAT_TOL:
                    # Declining 1RM + rising RPE → clear fatigue signal
                    root_cause = RootCause.fatigue_pattern
                    reason = "1RM declining and RPE rising — consistent with fatigue pattern."
                elif rpe_d < -DIAG_FLOAT_TOL:
                    # Declining 1RM + falling RPE → contradictory, can't classify
                    root_cause = RootCause.undetermined_cause
                    reason = (
                        "1RM declining but RPE also falling — contradictory signal, "
                        "cause undetermined."
                    )
                else:
                    # Declining 1RM + flat RPE (0 ≤ rpe_d < threshold) → fatigue pattern
                    root_cause = RootCause.fatigue_pattern
                    reason = "1RM declining with stable RPE — consistent with fatigue pattern."
            else:
                # Flat 1RM
                if rpe_d >= DIAG_RPE_FATIGUE_SLOPE_MIN_PER_DAY - DIAG_FLOAT_TOL:
                    # Rep dropoff: mean of last 2 sessions; must not default to 0 when None
                    if mean_last2_dropoff is not None:
                        if mean_last2_dropoff >= DIAG_REP_DROPOFF_THRESHOLD - DIAG_FLOAT_TOL:
                            root_cause = RootCause.fatigue_pattern
                            reason = (
                                "Flat 1RM, rising RPE, and rep drop-off — "
                                "consistent with fatigue pattern."
                            )
                        else:
                            root_cause = RootCause.possible_under_recovery
                            reason = (
                                "Flat 1RM and rising RPE without rep drop-off — "
                                "consistent with possible under-recovery."
                            )
                    else:
                        # All sessions single-set: dropoff uncomputable; rising RPE → under-recovery
                        root_cause = RootCause.possible_under_recovery
                        reason = (
                            "Flat 1RM and rising RPE; rep drop-off uncomputable "
                            "(single-set sessions) — classifying as possible under-recovery."
                        )
                elif rpe_d < -DIAG_FLOAT_TOL:
                    root_cause = RootCause.insufficient_stimulus
                    reason = (
                        "Flat 1RM with falling RPE at same load — "
                        "load may be insufficient to drive adaptation."
                    )
                else:
                    # Gray zone: 0 ≤ rpe_d < DIAG_RPE_FATIGUE_SLOPE_MIN_PER_DAY
                    root_cause = RootCause.undetermined_cause
                    reason = (
                        f"Flat 1RM with RPE slope {rpe_d:.4f}/day "
                        f"(gray zone 0–{DIAG_RPE_FATIGUE_SLOPE_MIN_PER_DAY:.4f}) — cause undetermined."
                    )
        else:
            # Cannot use RPE
            if is_declining:
                root_cause = RootCause.fatigue_pattern
                reason = (
                    "1RM declining — consistent with fatigue pattern "
                    "(insufficient RPE data to disambiguate cause)."
                )
            else:
                root_cause = RootCause.undetermined_cause
                reason = "Flat 1RM with insufficient RPE data to classify cause."

    # Fix 1 (mentor v1.1): noisy_data overrides root_cause to undetermined_cause.
    # The data is too inconsistent for any specific cause classification.
    # The original signal is preserved in the reason string for transparency.
    if noisy_data and root_cause not in (
        RootCause.insufficient_data, RootCause.progressing,
        RootCause.deloading, RootCause.deload_cooldown,
    ):
        reason = (
            f"Noise ratio {nr * 100:.1f}% > {DIAG_NOISE_RATIO_THRESHOLD * 100:.0f}% threshold — "
            "data too inconsistent for root-cause classification. "
            f"(Pre-noise signal: {reason})"
        )
        root_cause = RootCause.undetermined_cause



    # ── Step 8: Confidence ────────────────────────────────────────────────────
    confidence = _diag_base_confidence(
        root_cause, n, rpe_coverage, span, noisy_data, can_use_rpe
    )
    confidence = _diag_adjust_confidence_volume(confidence, root_cause, volume_status)

    # Fix 6 (mentor): default profile caps confidence at medium
    if profile_is_default and confidence == DiagConfidence.high:
        confidence = DiagConfidence.medium

    # ── Step 9: Prescription ──────────────────────────────────────────────────
    deload_target = _diag_prescription(
        root_cause,
        current_weight_kg,
        current_sets,
        current_avg_rpe,
        effective_exp,
        noisy_data,
        exercise_type,
    )

    evidence = FatigueEvidence(
        sessions_analysed=n,
        sessions_skipped=sessions_skipped,
        session_span_days=span,
        slope_pct_per_week=slope_pct_per_week,
        slope_rpe_per_day=slope_rpe_per_day,
        slope_rpe_per_session=slope_rpe_per_session,
        avg_rep_dropoff_pct=(mean_last2_dropoff * 100.0) if mean_last2_dropoff is not None else None,
        rpe_coverage_pct=rpe_coverage * 100.0,
        noisy_data=noisy_data,
        noise_ratio=nr,
        volume_count=volume_count,
        volume_status=volume_status,
        current_weight_kg=current_weight_kg,
        current_sets=current_sets,
        current_avg_rpe=current_avg_rpe,
    )

    return DiagnosisResult(
        plateau_detected=plateau_detected,
        root_cause=root_cause,
        confidence=confidence,
        reason=reason,
        evidence=evidence,
        deload_target=deload_target,
        profile_is_default=profile_is_default,
    )


# ── Validator ─────────────────────────────────────────────────────────────────

# Fix 5 (mentor): word boundaries via regex prevent punctuation/hyphen bypass.
# "one" IS banned. "1RM" is allowed via explicit removal before digit scan.
_BANNED_NUMBER_WORDS: frozenset = frozenset({
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty",
    "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand",
    "percent", "percentage", "half", "quarter", "twice", "double", "third",
})

# Prose-level forbidden claims: strings that indicate the LLM over-specified
# a cause it cannot know (e.g. nutrition intake) or suggested an action
# inconsistent with Python's prescription. Matched case-insensitively as substrings.
_FORBIDDEN_PROSE_PHRASES: tuple = (
    "deficit",
    "you are fatigued",
    "you should take a break",
    "take a break",
)


def check_prose_contradictions(text: str, evidence: Optional[FatigueEvidence] = None) -> Optional[str]:
    """Check if LLM prose directly contradicts computed FatigueEvidence metrics.
    Returns a description of the first contradiction found, or None if consistent.
    """
    if evidence is None:
        return None
    lowered = text.lower()

    # 1. Effort contradictions
    if evidence.slope_rpe_per_session is not None:
        if evidence.slope_rpe_per_session > 0.3:
            # Effort is rising; reject claims that effort is stable or falling
            bad_phrases = [
                "stable effort", "effort ratings are stable", "effort was stable",
                "effort remained stable", "stable effort ratings", "effort ratings relatively stable",
                "effort is falling", "falling effort", "effort ratings easing", "effort easing",
            ]
            for phrase in bad_phrases:
                if phrase in lowered:
                    return f"contradiction: RPE slope is rising ({evidence.slope_rpe_per_session:+.2f}/session) but prose claims '{phrase}'"
        elif evidence.slope_rpe_per_session < -0.3:
            # Effort is falling; reject claims that effort is rising/climbing
            bad_phrases = [
                "effort is climbing", "climbing effort", "effort rising", "effort ratings climbing",
                "rising effort", "effort ratings climbing steadily",
            ]
            for phrase in bad_phrases:
                if phrase in lowered:
                    return f"contradiction: RPE slope is falling ({evidence.slope_rpe_per_session:+.2f}/session) but prose claims '{phrase}'"

    # 2. Strength / 1RM trend contradictions
    # slope_pct_per_week: >= -0.5 means flat or progressing (not declining)
    if evidence.slope_pct_per_week >= -0.5:
        # 1RM is not declining; reject claims that 1RM/working weight is declining or downward
        bad_phrases = [
            "declining working weight", "downward trends in working weight",
            "working weight and estimated strength trending downward",
            "declining working weights", "strength trending downward",
            "working weight is declining", "downward trend in working weight",
        ]
        for phrase in bad_phrases:
            if phrase in lowered:
                return f"contradiction: 1RM slope is not declining ({evidence.slope_pct_per_week:+.2f}%/wk) but prose claims '{phrase}'"
    else:
        # 1RM is declining (< -0.5%); reject claims that strength is progressing/improving/upward
        bad_phrases = [
            "strength is improving", "trending upward", "strength estimates trending upward",
            "progress indicates proper response", "proper response",
        ]
        for phrase in bad_phrases:
            if phrase in lowered:
                return f"contradiction: 1RM slope is declining ({evidence.slope_pct_per_week:+.2f}%/wk) but prose claims '{phrase}'"

    # 3. Rep dropoff contradictions
    if evidence.avg_rep_dropoff_pct is not None:
        if evidence.avg_rep_dropoff_pct >= 15.0:
            bad_phrases = ["rep counts stable", "stable reps", "rep counts are stable", "reps remained stable"]
            for phrase in bad_phrases:
                if phrase in lowered:
                    return f"contradiction: rep dropoff is {evidence.avg_rep_dropoff_pct:.1f}% but prose claims '{phrase}'"
        elif evidence.avg_rep_dropoff_pct < 5.0:
            bad_phrases = ["reps dropping noticeably", "reps dropping within", "rep dropoff", "rep drop-off"]
            for phrase in bad_phrases:
                if phrase in lowered:
                    return f"contradiction: rep dropoff is low ({evidence.avg_rep_dropoff_pct:.1f}%) but prose claims '{phrase}'"

    return None


def explain_llm_prose_rejection(
    text: str,
    evidence: Optional[FatigueEvidence] = None,
    max_citation_index: Optional[int] = None,
) -> Optional[str]:
    """Return a human-readable string describing the FIRST rule that rejects
    *text*, or None if the prose passes all checks.

    Designed for diagnostic reporting; not used in the hot path.
    """
    # Contradiction lint against computed metrics
    contradiction = check_prose_contradictions(text, evidence)
    if contradiction:
        return contradiction

    # Validate citation indices against passages sent to LLM
    citation_matches = _re.findall(r'\[([\d,\s]+)\]', text)
    if citation_matches:
        for cgroup in citation_matches:
            for num_str in _re.split(r'[,\s]+', cgroup.strip()):
                if num_str.isdigit():
                    num = int(num_str)
                    if max_citation_index is not None:
                        if max_citation_index == 0:
                            return f"citation [{num}] present but no research passages were provided"
                        if num > max_citation_index or num < 1:
                            return f"citation [{num}] exceeds available passages ({max_citation_index})"

    # Strip allowed tokens first (single and multi-citations like [1] or [1, 2], and 1RM / one-rep maximum)
    cleaned = _re.sub(r'\[[\d,\s]+\]', '', text)
    cleaned = _re.sub(r'\bone[-\s]rep(?:\s+maximum)?\b', '', cleaned, flags=_re.IGNORECASE)
    cleaned = _re.sub(r'\b1RM\b', '', cleaned, flags=_re.IGNORECASE)

    if _re.search(r'(?<![A-Za-z])\d(?![A-Za-z])', cleaned):
        m = _re.search(r'(?<![A-Za-z])\d(?![A-Za-z])', cleaned)
        return f"bare digit '{m.group()}' found"

    for word in _BANNED_NUMBER_WORDS:
        if _re.search(rf'\b{_re.escape(word)}\b', cleaned, flags=_re.IGNORECASE):
            return f"banned number word '{word}' found"

    lowered = text.lower()
    for phrase in _FORBIDDEN_PROSE_PHRASES:
        if phrase.lower() in lowered:
            return f"forbidden phrase '{phrase}' found"

    return None  # passes


def validate_llm_prose(
    text: str,
    evidence: Optional[FatigueEvidence] = None,
    max_citation_index: Optional[int] = None,
) -> bool:
    """Returns True when LLM prose passes all content rules.

    Allowed: [n] citation tags (indices within 1..max_citation_index), the token "1RM", and "one-rep maximum".
    Banned: bare digits, number words, forbidden claim phrases, invalid citation indices, or factual contradictions.
    """
    if check_prose_contradictions(text, evidence) is not None:
        return False

    # Check citation indices
    citation_matches = _re.findall(r'\[([\d,\s]+)\]', text)
    if citation_matches:
        for cgroup in citation_matches:
            for num_str in _re.split(r'[,\s]+', cgroup.strip()):
                if num_str.isdigit():
                    num = int(num_str)
                    if max_citation_index is not None:
                        if max_citation_index == 0:
                            return False
                        if num > max_citation_index or num < 1:
                            return False

    cleaned = _re.sub(r'\[[\d,\s]+\]', '', text)          # strip [1], [2], [1, 2]...
    cleaned = _re.sub(r'\bone[-\s]rep(?:\s+maximum)?\b', '', cleaned, flags=_re.IGNORECASE)
    cleaned = _re.sub(r'\b1RM\b', '', cleaned, flags=_re.IGNORECASE)  # allow "1RM"
    # Word-boundary digit scan (handles punctuation and hyphens correctly)
    if _re.search(r'(?<![A-Za-z])\d(?![A-Za-z])', cleaned):
        return False
    for word in _BANNED_NUMBER_WORDS:
        if _re.search(rf'\b{_re.escape(word)}\b', cleaned, flags=_re.IGNORECASE):
            return False
    # Forbidden prose phrases (substring, case-insensitive)
    lowered = text.lower()
    for phrase in _FORBIDDEN_PROSE_PHRASES:
        if phrase.lower() in lowered:
            return False
    return True


# ── Per-Strategy Fallback Templates ──────────────────────────────────────────
# Python-rendered; used when LLM output fails validation or times out.
# No field that could be None is included in templates that don't use it.

def render_fallback(result: DiagnosisResult) -> str:
    """Render a deterministic coach message from the DiagnosisResult.
    No numbers are hardcoded here — all come from result fields.
    """
    t = result.deload_target
    s = t.strategy

    if s == DiagStrategy.no_action:
        if result.root_cause == RootCause.progressing:
            # Fix 5 (mentor): separate message for progressing — not "insufficient data"
            return (
                f"Good progress — 1RM trending at "
                f"{result.evidence.slope_pct_per_week:.1f}%/week. "
                "Continue current protocol."
            )
        return "Insufficient data or active deload. Continue current protocol and log more sessions."

    if s == DiagStrategy.volume_reduction:
        base = (
            f"Pattern consistent with fatigue. Target: "
            f"{t.target_weight_kg} kg × {t.target_sets} sets × "
            f"{t.target_reps_range} @ RPE ≤ {t.target_rpe_ceiling} "
            f"for {t.duration_sessions} session(s), then resume at {t.resume_weight_kg} kg."
        )
    elif s == DiagStrategy.weight_reduction:
        base = (
            f"Pattern consistent with under-recovery. Target: "
            f"{t.target_weight_kg} kg × {t.target_sets} sets × "
            f"{t.target_reps_range} @ RPE ≤ {t.target_rpe_ceiling} "
            f"for {t.duration_sessions} session(s), then resume at {t.resume_weight_kg} kg."
        )
    elif s == DiagStrategy.progress_load:
        base = (
            f"Stimulus appears insufficient. Target: "
            f"{t.target_weight_kg} kg × {t.target_sets} sets × "
            f"{t.target_reps_range} @ RPE ≤ {t.target_rpe_ceiling}."
        )
    elif s == DiagStrategy.hold:
        base = (
            f"Cause unclear — hold protocol for {t.duration_sessions} session(s): "
            f"{t.target_weight_kg} kg × {t.target_sets} sets × "
            f"{t.target_reps_range} @ RPE ≤ {t.target_rpe_ceiling}."
        )
    else:
        base = "Continue current protocol."

    # Append Python-rendered note separately (never through LLM)
    if t.prescription_note:
        base += f" Note: {t.prescription_note.text}"
    return base
