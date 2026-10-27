"""Content similarity and per-user supervised preference learning.

Hard constraints always precede ranking. An impression without explicit feedback
is never a negative example. Only real feedback enters a user's model; no seed,
global user data, or provider-generated labels are used.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
from fastapi import HTTPException
from sqlmodel import Session, select

from app.modules.exercises.catalog import Difficulty, Equipment, Exercise, MovementPattern, MuscleGroup, get_catalog
from app.modules.exercises.models import ExercisePreferenceModel, ExerciseRecommendation, SavedRoutine
from app.modules.user.models import ExperienceLevel, Goal, UserProfile
from app.modules.exercises.training_rules import eligible, replacement_role_matches

FEATURE_VERSION = "exercise-preferences-v2-explicit-feedback"
MIN_EXAMPLES = 30
MIN_CLASS = 5
MIN_EXERCISES = 8
POSITIVE = {"accepted", "liked"}


def content_vector(exercise: Exercise) -> np.ndarray:
    """Weighted one-hot/multi-hot vector; cosine is a similarity, not confidence."""
    return np.array([
        *[math.sqrt(4) * (exercise.primary_muscle == m) for m in MuscleGroup],
        *[(m in exercise.secondary_muscles) for m in MuscleGroup],
        *[math.sqrt(3) * (exercise.movement_pattern == m) for m in MovementPattern],
        *[(exercise.equipment == e) for e in Equipment],
        *[(exercise.difficulty == d) for d in Difficulty],
        float(exercise.is_compound),
    ], dtype=float)


def preference_features(source: Exercise, candidate: Exercise, profile: UserProfile, similarity: float) -> dict[str, float]:
    # Fixed, bounded numeric features; identifiers and sensitive biometrics excluded.
    return {
        "similarity": similarity,
        "same_movement": float(source.movement_pattern == candidate.movement_pattern),
        "same_equipment": float(source.equipment == candidate.equipment),
        "compound": float(candidate.is_compound),
        **{f"muscle_{m.value}": float(candidate.primary_muscle == m) for m in MuscleGroup},
        **{f"equipment_{e.value}": float(candidate.equipment == e) for e in Equipment},
        **{f"movement_{m.value}": float(candidate.movement_pattern == m) for m in MovementPattern},
        **{f"difficulty_{d.value}": float(candidate.difficulty == d) for d in Difficulty},
        **{f"goal_{g.value}": float(profile.goal == g) for g in Goal},
        **{f"experience_{e.value}": float(profile.experience_level == e) for e in ExperienceLevel},
    }


def feedback_examples(db: Session, user_id: int) -> list[ExerciseRecommendation]:
    rows = db.exec(select(ExerciseRecommendation).where(
        ExerciseRecommendation.user_id == user_id,
        ExerciseRecommendation.feedback.is_not(None),
    ).order_by(ExerciseRecommendation.feedback_at, ExerciseRecommendation.id)).all()
    # Repeated views/clicks on the same pair do not artificially grow the dataset.
    latest = {(r.source_exercise_id, r.exercise_id): r for r in rows}
    return sorted((r for r in latest.values() if r.feedback in POSITIVE | {"disliked"}), key=lambda r: (r.feedback_at, r.id))


def learning_status(db: Session, user_id: int) -> dict:
    examples = feedback_examples(db, user_id)
    positives = sum(r.feedback in POSITIVE for r in examples)
    negatives = len(examples) - positives
    unique = len({r.exercise_id for r in examples})
    neutral = len(db.exec(select(ExerciseRecommendation).where(
        ExerciseRecommendation.user_id == user_id, ExerciseRecommendation.feedback == "replaced",
    )).all())
    model = db.get(ExercisePreferenceModel, user_id)
    active = bool(model and model.parameters.get("version") == FEATURE_VERSION)
    return {
        "examples": len(examples), "positive": positives, "negative": negatives, "neutral_replacements": neutral,
        "unique_exercises": unique, "minimum_examples": MIN_EXAMPLES,
        "minimum_per_class": MIN_CLASS, "minimum_exercises": MIN_EXERCISES,
        "can_train": len(examples) >= MIN_EXAMPLES and min(positives, negatives) >= MIN_CLASS and unique >= MIN_EXERCISES,
        "active": active, "method": "personalized_logistic_regression" if active else "content_similarity",
        "trained_at": model.trained_at if active else None,
        "metrics": model.metrics if active else None,
    }


def predict_preference(parameters: dict, features: dict[str, float]) -> float:
    score = parameters["intercept"] + sum(weight * features.get(key, 0) for key, weight in parameters["weights"].items())
    return 1 / (1 + math.exp(-max(-40, min(40, score))))


def recommend_alternatives(db: Session, user_id: int, profile: UserProfile, source_id: str,
                           equipment: list[Equipment], excluded: list[str]) -> dict:
    catalog = get_catalog()
    source = catalog.get(source_id)
    if source is None:
        raise HTTPException(404, "Exercise not found.")
    model = db.get(ExercisePreferenceModel, user_id)
    personalized = bool(model and model.parameters.get("version") == FEATURE_VERSION)
    original = content_vector(source)
    ranked = []
    for candidate in catalog.values():
        if candidate.id == source_id or candidate.id in excluded or candidate.equipment not in equipment:
            continue
        if candidate.primary_muscle != source.primary_muscle:
            continue
        if not eligible(candidate, equipment, profile.experience_level) or not replacement_role_matches(source, candidate):
            continue
        vector = content_vector(candidate)
        similarity = float(np.dot(original, vector) / (np.linalg.norm(original) * np.linalg.norm(vector)))
        features = preference_features(source, candidate, profile, similarity)
        preference = predict_preference(model.parameters, features) if personalized else None
        # A learned preference never overrides eligibility; similarity remains dominant.
        rank = .8 * similarity + .2 * preference if preference is not None else similarity
        reasons = [f"Same primary muscle: {candidate.primary_muscle.value}."]
        if candidate.movement_pattern == source.movement_pattern:
            reasons.append("Same movement pattern.")
        reasons.append(f"Uses {candidate.equipment.value}; suitable for your experience level.")
        ranked.append((rank, candidate.id, candidate, similarity, features, preference, " ".join(reasons)))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    alternatives = []
    for _, _, candidate, similarity, features, preference, reason in ranked[:3]:
        record = ExerciseRecommendation(user_id=user_id, source_exercise_id=source_id, exercise_id=candidate.id,
                                        similarity=similarity, features=features)
        db.add(record)
        alternatives.append({"recommendation_id": record.id, "exercise": candidate,
                             "similarity": round(similarity, 4), "preference_score": round(preference, 4) if preference is not None else None,
                             "reason": reason})
    db.commit()
    return {"source_exercise_id": source_id, "alternatives": alternatives,
            "method": "personalized_logistic_regression" if personalized else "content_similarity",
            "message": "" if len(alternatives) == 3 else "Fewer than three exercises meet your equipment, muscle and experience constraints."}


def record_feedback(db: Session, user_id: int, recommendation_id: str, action: str) -> ExerciseRecommendation:
    record = db.get(ExerciseRecommendation, recommendation_id)
    if record is None or record.user_id != user_id:
        raise HTTPException(404, "Recommendation not found.")
    if action == "accepted":
        routine = db.exec(select(SavedRoutine).where(SavedRoutine.user_id == user_id)).first()
        if not routine or not any(
            ex.get("exercise_id") == record.exercise_id
            for day in routine.routine.get("days", []) for ex in day.get("exercises", [])
        ):
            raise HTTPException(409, "Save this exercise in your routine before marking it accepted.")
    if record.feedback != action:
        record.feedback = action
        record.feedback_at = datetime.now(timezone.utc)
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


def train_preferences(db: Session, user_id: int) -> dict:
    """Evaluate on held-out exercise IDs, then deploy only above a constant baseline."""
    status = learning_status(db, user_id)
    if not status["can_train"]:
        raise HTTPException(409, "More varied positive and negative feedback is needed before training.")
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import balanced_accuracy_score, brier_score_loss, log_loss
    from sklearn.model_selection import GroupShuffleSplit

    rows = feedback_examples(db, user_id)
    y = np.array([int(row.feedback in POSITIVE) for row in rows])
    groups = np.array([row.exercise_id for row in rows])
    # Grouping by candidate exercise keeps repeated exercise characteristics out of
    # the opposite fold. Search deterministic splits with both classes represented.
    split = None
    for train, test in GroupShuffleSplit(n_splits=20, test_size=.25, random_state=42).split(rows, y, groups):
        if len(set(y[train])) == 2 and len(set(y[test])) == 2:
            split = train, test
            break
    if split is None:
        raise HTTPException(409, "Feedback needs both outcomes across more exercises for a separate evaluation set.")
    train, test = split
    vectorizer = DictVectorizer(sparse=False)
    x_train = vectorizer.fit_transform([rows[i].features for i in train])
    x_test = vectorizer.transform([rows[i].features for i in test])
    estimator = LogisticRegression(C=.5, class_weight="balanced", max_iter=500, random_state=42)
    estimator.fit(x_train, y[train])
    probability = estimator.predict_proba(x_test)[:, 1]
    balanced_accuracy = float(balanced_accuracy_score(y[test], probability >= .5))
    baseline_probability = np.repeat(float(y[train].mean()), len(test))
    metrics = {
        "evaluation": "held_out_exercise_groups", "examples": len(rows),
        "training_examples": len(train), "test_examples": len(test),
        "balanced_accuracy": round(balanced_accuracy, 4), "baseline_balanced_accuracy": .5,
        "log_loss": round(float(log_loss(y[test], probability, labels=[0, 1])), 4),
        "baseline_log_loss": round(float(log_loss(y[test], baseline_probability, labels=[0, 1])), 4),
        "brier_score": round(float(brier_score_loss(y[test], probability)), 4),
    }
    # Being trainable does not guarantee an improvement. Keep the existing ranker
    # when this model cannot beat the baseline on independent held-out exercises.
    deployed = balanced_accuracy > .5 and metrics["log_loss"] < metrics["baseline_log_loss"]
    if deployed:
        x_all = vectorizer.fit_transform([r.features for r in rows])
        estimator.fit(x_all, y)
        parameters = {"version": FEATURE_VERSION, "intercept": float(estimator.intercept_[0]),
                      "weights": dict(zip(vectorizer.get_feature_names_out().tolist(), estimator.coef_[0].tolist()))}
        model = db.get(ExercisePreferenceModel, user_id) or ExercisePreferenceModel(user_id=user_id, parameters={}, metrics={})
        model.parameters, model.metrics, model.trained_at = parameters, metrics, datetime.now(timezone.utc)
        db.add(model)
        db.commit()
    return {"deployed": deployed, "metrics": metrics, "status": learning_status(db, user_id),
            "message": "Your preferences now help rank eligible alternatives." if deployed else
            "The new model did not outperform the baseline. Your current ranking is unchanged; add more varied feedback."}
