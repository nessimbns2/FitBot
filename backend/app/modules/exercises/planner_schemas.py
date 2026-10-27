from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.exercises.catalog import Equipment, Exercise


class AlternativesRequest(BaseModel):
    exercise_id: str = Field(min_length=1, max_length=100)
    available_equipment: list[Equipment] = Field(default_factory=lambda: list(Equipment), max_length=4)
    exclude_ids: list[str] = Field(default_factory=list, max_length=100)


class Alternative(BaseModel):
    recommendation_id: str
    exercise: Exercise
    similarity: float
    preference_score: float | None = None
    reason: str


class AlternativesResponse(BaseModel):
    source_exercise_id: str
    alternatives: list[Alternative]
    method: str
    message: str


class FeedbackRequest(BaseModel):
    action: Literal["accepted", "replaced", "liked", "disliked"]


class PreferenceMetrics(BaseModel):
    evaluation: str
    examples: int
    training_examples: int
    test_examples: int
    balanced_accuracy: float
    baseline_balanced_accuracy: float
    log_loss: float
    baseline_log_loss: float
    brier_score: float


class PreferenceStatus(BaseModel):
    examples: int
    positive: int
    negative: int
    neutral_replacements: int = 0
    unique_exercises: int
    minimum_examples: int
    minimum_per_class: int
    minimum_exercises: int
    can_train: bool
    active: bool
    method: Literal["content_similarity", "personalized_logistic_regression"]
    trained_at: datetime | None = None
    metrics: PreferenceMetrics | None = None


class FeedbackResponse(BaseModel):
    recommendation_id: str
    feedback: str
    status: PreferenceStatus


class TrainingResponse(BaseModel):
    deployed: bool
    metrics: PreferenceMetrics
    status: PreferenceStatus
    message: str


class PlannedExercise(BaseModel):
    exercise_id: str = Field(min_length=1, max_length=100)
    sets: int = Field(ge=1, le=12)
    rep_range: str = Field(default="8-12", pattern=r"^\d{1,2}(?:-\d{1,2})?$", max_length=5)


class PlannedDay(BaseModel):
    exercises: list[PlannedExercise] = Field(min_length=1, max_length=20)


class ExplanationRoutine(BaseModel):
    days: list[PlannedDay] = Field(min_length=1, max_length=7)


class ExplanationRequest(BaseModel):
    routine: ExplanationRoutine


class EvidenceSource(BaseModel):
    id: int
    source: str
    page: int
    excerpt: str


class ExplanationSection(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=1800)
    citations: list[int] = Field(min_length=1, max_length=6)


class GeneratedExplanation(BaseModel):
    sections: list[ExplanationSection] = Field(min_length=1, max_length=4)


class ExplanationResponse(BaseModel):
    plan_summary: str
    weekly_sets: dict[str, int]
    sections: list[ExplanationSection] = Field(default_factory=list)
    sources: list[EvidenceSource] = Field(default_factory=list)
    mode: Literal["rag", "retrieved_guides", "unavailable"]
    message: str
