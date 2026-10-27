from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, delete

from app.core.database import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.exercises.models import ExercisePreferenceModel, ExerciseRecommendation
from app.modules.exercises.planner_explanation import explain_routine
from app.modules.exercises.planner_schemas import (
    AlternativesRequest, AlternativesResponse, ExplanationRequest, ExplanationResponse, FeedbackRequest,
    FeedbackResponse, PreferenceStatus, TrainingResponse,
)
from app.modules.exercises.recommendations import learning_status, recommend_alternatives, record_feedback, train_preferences
from app.modules.user.service import get_or_create_profile

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/alternatives", response_model=AlternativesResponse)
def alternatives(body: AlternativesRequest, user: CurrentUser, db: SessionDep):
    profile = get_or_create_profile(db, user.id)
    return recommend_alternatives(db, user.id, profile, body.exercise_id, body.available_equipment, body.exclude_ids)


@router.put("/recommendations/{recommendation_id}/feedback", response_model=FeedbackResponse)
def feedback(recommendation_id: str, body: FeedbackRequest, user: CurrentUser, db: SessionDep):
    record = record_feedback(db, user.id, recommendation_id, body.action)
    return {"recommendation_id": record.id, "feedback": record.feedback, "status": learning_status(db, user.id)}


@router.get("/preferences/status", response_model=PreferenceStatus)
def preference_status(user: CurrentUser, db: SessionDep):
    return learning_status(db, user.id)


@router.post("/preferences/train", response_model=TrainingResponse)
def train(user: CurrentUser, db: SessionDep):
    return train_preferences(db, user.id)


@router.delete("/preferences", status_code=204)
def reset_preferences(user: CurrentUser, db: SessionDep) -> Response:
    """Erase this account's feedback and model; keep its saved workout routine."""
    db.exec(delete(ExercisePreferenceModel).where(ExercisePreferenceModel.user_id == user.id))
    db.exec(delete(ExerciseRecommendation).where(ExerciseRecommendation.user_id == user.id))
    db.commit()
    return Response(status_code=204)


@router.post("/routine/explanation", response_model=ExplanationResponse)
def explanation(body: ExplanationRequest, user: CurrentUser, db: SessionDep):
    return explain_routine(body, get_or_create_profile(db, user.id))
