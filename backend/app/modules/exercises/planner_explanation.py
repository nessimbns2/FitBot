"""Explain catalog-backed plan facts using exercise-only retrieved evidence."""
from __future__ import annotations

import json
import logging
from pathlib import PurePosixPath

from fastapi import HTTPException

from app.core.privacy import redact_pii, validate_llm_output
from app.modules.exercises.catalog import get_catalog
from app.modules.exercises.planner_schemas import (
    EvidenceSource, ExplanationRequest, ExplanationResponse, GeneratedExplanation,
)
from app.modules.rag_core.engine import get_llm_client, get_vector_store
from app.modules.user.models import UserProfile
from app.prompts.planner_explanation import PLANNER_EXPLANATION_SYSTEM

logger = logging.getLogger(__name__)


def explain_routine(request: ExplanationRequest, profile: UserProfile, *, store=None, llm=None) -> ExplanationResponse:
    catalog = get_catalog()
    weekly_sets: dict[str, int] = {}
    named_movements = []
    days = []
    for day_index, day in enumerate(request.routine.days, 1):
        entries = []
        for entry in day.exercises:
            exercise = catalog.get(entry.exercise_id)
            if exercise is None:
                raise HTTPException(422, f"Unknown exercise in routine: {entry.exercise_id}")
            low, _, high = entry.rep_range.partition("-")
            if int(low) < 1 or int(high or low) < int(low):
                raise HTTPException(422, "Repetition ranges must be positive and ordered.")
            muscle = exercise.primary_muscle.value
            weekly_sets[muscle] = weekly_sets.get(muscle, 0) + entry.sets
            entries.append({"name": exercise.name, "primary_muscle": muscle,
                            "movement": exercise.movement_pattern.value, "sets": entry.sets, "reps": entry.rep_range})
            named_movements.append(f"{exercise.name} ({exercise.movement_pattern.value})")
        days.append({"day": day_index, "exercises": entries})
    summary = f"{len(days)} training days, {sum(weekly_sets.values())} planned sets. Counts below assign each set to its primary muscle only."
    result = ExplanationResponse(plan_summary=summary, weekly_sets=weekly_sets, mode="unavailable",
                                 message="Exercise guides are unavailable. The plan facts above are calculated from your routine.")
    try:
        query = f"{profile.goal.value} {profile.experience_level.value} exercise selection and movement balance: " + "; ".join(dict.fromkeys(named_movements))[:1800]
        retrieved = (store or get_vector_store()).search(query, category="exercise", k=8)
        # Diverse pages avoid presenting several neighbouring chunks as distinct evidence.
        passages, seen = [], set()
        for passage in retrieved:
            key = (passage.source, passage.page)
            if passage.category == "exercise" and key not in seen:
                passages.append(passage); seen.add(key)
            if len(passages) == 4: break
        # Never pass another category's evidence into a workout explanation.
        passages = [p for p in passages if p.category == "exercise"]
    except Exception as error:
        logger.warning("Planner retrieval unavailable: %s", type(error).__name__)
        return result
    if not passages:
        return result
    result.sources = [EvidenceSource(id=i, source=PurePosixPath(p.source.replace("\\", "/")).name,
                                     page=p.page, excerpt=redact_pii(p.text[:900])) for i, p in enumerate(passages, 1)]
    result.mode = "retrieved_guides"
    result.message = "Relevant guide excerpts are available below. An AI explanation could not be generated."
    try:
        payload = {"PLAN_DATA": {"goal": profile.goal.value, "experience": profile.experience_level.value,
                                 "days": days, "primary_muscle_weekly_sets": weekly_sets},
                   "REFERENCE_DATA": [s.model_dump() for s in result.sources]}
        answer = (llm or get_llm_client()).complete(
            messages=[{"role": "user", "content": json.dumps(payload)}],
            system=PLANNER_EXPLANATION_SYSTEM, temperature=.2,
        ).strip()
        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = GeneratedExplanation.model_validate_json(answer)
        valid_ids = {s.id for s in result.sources}
        for section in parsed.sections:
            if not set(section.citations).issubset(valid_ids):
                raise ValueError("Unknown reference ID")
            section.text = validate_llm_output(section.text)
            section.title = validate_llm_output(section.title)
            if not section.text or not section.title:
                raise ValueError("Empty explanation")
        result.sections = parsed.sections
        result.mode = "rag"
        result.message = "Explanation based on the exercise guides. Review the cited excerpts; this is educational guidance."
    except Exception as error:
        # Retrieval and the deterministic facts stay useful when the provider is
        # unavailable or returns malformed JSON/unrecognised citations.
        logger.warning("Planner explanation unavailable: %s", type(error).__name__)
    return result
