"""Add labelled sample data to an existing account without resetting it.

Run from backend/: python scripts/seed_user_samples.py --email ahmed@gmail.com
Existing credentials, profile, routine and user-entered records are preserved.
The first run anchors six weeks of training to today. Later runs preserve that
history and fill missing sample meals for the last seven days without duplicates.
No AI provider is called; sample conversations are explicitly labelled.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from app.core.database import engine, init_db  # noqa: E402
from app.modules.auth.models import User  # noqa: E402
from app.modules.exercises.catalog import Equipment, load_catalog  # noqa: E402
from app.modules.exercises.generator import SplitType, generate_routine  # noqa: E402
from app.modules.exercises.models import SavedRoutine  # noqa: E402
from app.modules.nutrition.models import FoodLogEntry, MealSlotName  # noqa: E402
from app.modules.progressive_overload.models import DeloadRecord, WorkoutSet  # noqa: E402
from app.modules.user.models import ChatMessage, ChatSession, UserProfile  # noqa: E402

MARKER = "[FitBot sample v1]"
MEALS = [
    ("breakfast", "Oats, banana and Greek yogurt", 35, 70, 12),
    ("lunch", "Grilled chicken, rice and salad", 50, 85, 18),
    ("snack", "Cottage cheese and almonds", 25, 15, 16),
    ("dinner", "Baked fish, potatoes and vegetables", 45, 65, 18),
]


def seed_samples(session: Session, user: User, *, now: datetime | None = None) -> dict[str, int]:
    """Stage only missing samples; caller commits the complete transaction."""
    now = now or datetime.now(timezone.utc)
    catalog = load_catalog()
    counts = {"workout_sets": 0, "food_entries": 0, "conversations": 0, "routines": 0, "deloads": 0}
    existing_sets = set(session.exec(select(WorkoutSet.notes).where(WorkoutSet.user_id == user.id)).all())
    existing_food = {
        (entry.log_date, entry.meal_slot, entry.name)
        for entry in session.exec(select(FoodLogEntry).where(FoodLogEntry.user_id == user.id)).all()
        if (entry.notes or "").startswith(MARKER)
    }

    # Bench and row improve; squat stalls with increasing effort.
    # Distinct dates allow the real progression and diagnosis algorithms to run.
    lifts = [("barbell-bench-press", 50.0), ("barbell-back-squat", 80.0), ("barbell-bent-over-row", 45.0)]
    for workout in range(13):
        day = now.date() - timedelta(days=42 - workout * 3 if workout < 12 else 0)
        performed_at = datetime.combine(day, time(8), tzinfo=timezone.utc)
        if performed_at > now:
            performed_at = now
        for exercise_id, initial_weight in lifts:
            if exercise_id not in catalog:
                raise ValueError(f"Unknown sample exercise: {exercise_id}")
            stalled = exercise_id == "barbell-back-squat"
            for set_no in range(1, 4):
                key = f"{MARKER} workout-{workout}/{exercise_id}/{set_no}"
                if key in existing_sets:
                    continue
                rpe = min(9.5, 7 + workout * .2 + (set_no - 1) * .25) if stalled else 7 + (set_no - 1) * .5
                session.add(WorkoutSet(
                    user_id=user.id, exercise_id=exercise_id, performed_at=performed_at,
                    session_label=f"Demo full body {workout + 1:02d}", set_number=set_no,
                    weight_kg=initial_weight if stalled else initial_weight + (workout // 2) * 2.5,
                    reps=max(6, 10 - workout // 4 - (set_no - 1)) if stalled else 10 - (set_no - 1),
                    rpe=rpe, rir=round(10 - rpe), notes=key,
                ))
                counts["workout_sets"] += 1

    # Cover the other muscle groups and lifts in the existing PPL routine.
    accessories = [("barbell-good-morning", 30), ("cable-lateral-raise", 5),
                   ("barbell-bicep-curl", 20), ("cable-kneeling-crunch", 25)]
    for week in range(6):
        performed_at = min(now, datetime.combine(now.date() - timedelta(days=7 * (5 - week)), time(9), tzinfo=timezone.utc))
        for exercise_id, weight in accessories:
            if exercise_id not in catalog:
                raise ValueError(f"Unknown sample exercise: {exercise_id}")
            for set_no in range(1, 4):
                key = f"{MARKER} accessory-{week}/{exercise_id}/{set_no}"
                if key in existing_sets:
                    continue
                session.add(WorkoutSet(
                    user_id=user.id, exercise_id=exercise_id, performed_at=performed_at,
                    session_label=f"Demo accessories {week + 1:02d}", set_number=set_no,
                    weight_kg=weight, reps=10 + week // 2, rpe=7.5, rir=2, notes=key,
                ))
                counts["workout_sets"] += 1

    for offset in range(7):
        for index, (slot, name, protein, carbs, fat) in enumerate(MEALS):
            # Leave room today to try adding a meal and AI suggestions.
            if offset == 0 and index >= 2:
                continue
            log_date = now.date() - timedelta(days=offset)
            key = f"{MARKER} meal-{log_date}/{slot}"
            if (log_date, MealSlotName(slot), name) in existing_food:
                continue
            session.add(FoodLogEntry(
                user_id=user.id, log_date=log_date,
                meal_slot=MealSlotName(slot), name=name,
                calories=4 * protein + 4 * carbs + 9 * fat,
                protein_g=protein, carbs_g=carbs, fat_g=fat, notes=key,
            ))
            counts["food_entries"] += 1

    if not session.exec(select(SavedRoutine).where(SavedRoutine.user_id == user.id)).first():
        profile = session.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
        if profile is None:
            raise ValueError("Complete the user's profile before seeding a routine.")
        routine = generate_routine(
            split=SplitType.FULL_BODY, days_per_week=3,
            experience_level=profile.experience_level, goal=profile.goal,
            available_equipment=list(Equipment),
        )
        session.add(SavedRoutine(user_id=user.id, split="full_body", days_per_week=3, routine=routine.model_dump(mode="json")))
        counts["routines"] += 1

    conversations = [
        ("Demo: getting started", "How can I test FitBot with these sample records?",
         "This is a sample conversation, not a live AI response. Open Nutrition to review your food log, Workouts to view your saved routine, and Tracker to inspect your training history. You can edit or delete the sample meals and add your own sets."),
        ("Demo: training progress", "Which sample exercises should I explore in Tracker?",
         "This is a sample conversation. Barbell Bench Press has an improving history; Barbell Back Squat has a stalled history with increasing effort for testing the plateau diagnosis. Select either lift in Tracker to see the actual calculations. Send a new question here to test the live coach."),
    ]
    for index, (title, question, answer) in enumerate(conversations):
        conversation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fitbot-samples-v1/{user.id}/chat/{index}"))
        if session.get(ChatSession, conversation_id) is not None:
            continue
        created = now - timedelta(days=index + 1)
        session.add(ChatSession(id=conversation_id, user_id=user.id, title=title, created_at=created, updated_at=created))
        session.flush()
        session.add(ChatMessage(session_id=conversation_id, role="user", content=question, created_at=created))
        session.add(ChatMessage(session_id=conversation_id, role="assistant", content=answer, sources="[]", created_at=created + timedelta(seconds=1)))
        counts["conversations"] += 1

    # A completed historical recovery block leaves current lifts free for testing
    # apply/cancel-deload. Feedback is intentionally unrated so it can be tested.
    prior = session.exec(select(DeloadRecord).where(
        DeloadRecord.user_id == user.id, DeloadRecord.constants_version == "sample-v1",
    )).first()
    if prior is None:
        session.add(DeloadRecord(
            user_id=user.id, exercise_id="barbell-bent-over-row", strategy="weight_reduction",
            root_cause="fatigue_pattern", confidence="medium", target_weight_kg=35,
            target_sets=2, target_reps_range="8-10", target_rpe_ceiling=7,
            resume_weight_kg=45, duration_sessions=2, constants_version="sample-v1",
            applied_at=now - timedelta(days=60), expires_at=now - timedelta(days=32),
            completed_at=now - timedelta(days=50),
        ))
        counts["deloads"] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="An existing local account; its password is never changed")
    args = parser.parse_args()
    init_db()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == args.email.strip().lower())).first()
        if user is None:
            raise SystemExit("Account not found. Register it first; this script never creates or resets accounts.")
        if not user.is_active:
            raise SystemExit("Account is inactive; no data was changed.")
        counts = seed_samples(session, user)
        session.commit()
        print(f"Samples added for {user.email}: {counts}")
        print("Existing password, profile, routine and personal records preserved.")


if __name__ == "__main__":
    main()
