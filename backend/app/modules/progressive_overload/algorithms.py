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
