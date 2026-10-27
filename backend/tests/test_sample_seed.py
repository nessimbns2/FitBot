"""Sample seeding must never reset an account or duplicate personal records."""

from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.modules.auth.models import User
from app.modules.exercises.models import SavedRoutine
from app.modules.nutrition.models import FoodLogEntry
from app.modules.progressive_overload.models import WorkoutSet
from app.modules.user.models import ChatMessage, ChatSession, UserProfile
from scripts.seed_user_samples import seed_samples


def test_samples_are_idempotent_and_preserve_personal_records(session, test_user):
    now = datetime(2026, 10, 26, 15, tzinfo=timezone.utc)
    password_hash = test_user.password_hash
    profile = session.exec(select(UserProfile).where(UserProfile.user_id == test_user.id)).one()
    profile.weight_kg = 83
    personal_meal = FoodLogEntry(user_id=test_user.id, log_date=now.date(), name="My meal", calories=400)
    routine = SavedRoutine(user_id=test_user.id, split="full_body", days_per_week=2, routine={"personal": True})
    session.add_all([profile, personal_meal, routine])
    session.commit()

    first = seed_samples(session, test_user, now=now)
    session.commit()
    assert first == {"workout_sets": 189, "food_entries": 26, "conversations": 2, "routines": 0, "deloads": 1}
    assert all(value == 0 for value in seed_samples(session, test_user, now=now).values())
    session.commit()
    session.expire_all()
    assert session.get(User, test_user.id).password_hash == password_hash
    assert session.get(UserProfile, profile.id).weight_kg == 83
    assert session.get(SavedRoutine, routine.id).routine == {"personal": True}
    assert session.get(FoodLogEntry, personal_meal.id).name == "My meal"
    assert len(session.exec(select(FoodLogEntry).where(FoodLogEntry.user_id == test_user.id)).all()) == 27
    assert len(session.exec(select(WorkoutSet).where(WorkoutSet.user_id == test_user.id)).all()) == 189
    assert len(session.exec(select(ChatMessage)).all()) == 4


def test_samples_are_scoped_to_the_requested_user(session, test_user):
    other = User(email="other@example.com", full_name="Other User", password_hash="untouched")
    session.add(other)
    session.commit()
    result = seed_samples(session, test_user)
    session.commit()
    assert result["routines"] == 1
    for model in (WorkoutSet, FoodLogEntry, ChatSession, SavedRoutine):
        assert session.exec(select(model).where(model.user_id == other.id)).all() == []
    assert session.get(User, other.id).password_hash == "untouched"


def test_later_run_fills_today_without_resetting_training(session, test_user):
    now = datetime(2026, 10, 26, 15, tzinfo=timezone.utc)
    seed_samples(session, test_user, now=now)
    session.commit()
    result = seed_samples(session, test_user, now=now + timedelta(days=1))
    session.commit()
    assert result["workout_sets"] == 0
    assert result["food_entries"] == 4  # two new meals today, two to finish yesterday
    today = session.exec(select(FoodLogEntry).where(
        FoodLogEntry.user_id == test_user.id, FoodLogEntry.log_date == (now + timedelta(days=1)).date(),
    )).all()
    assert len(today) == 2
    assert all(value == 0 for value in seed_samples(session, test_user, now=now + timedelta(days=1)).values())
