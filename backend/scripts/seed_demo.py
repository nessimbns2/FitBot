"""
scripts/seed_demo.py
Create (or reset) a demo account with realistic data for the live demonstration:
profile, 4 weeks of logged sets, a saved routine and today's meals.

Run from backend/:   python scripts/seed_demo.py
Then log in on http://localhost:5173 with the credentials below.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from app.core.database import engine, init_db  # noqa: E402
from app.modules.auth.models import RegisterRequest, User  # noqa: E402
from app.modules.auth.service import delete_account, register_user  # noqa: E402
from app.modules.exercises.catalog import Equipment, load_catalog  # noqa: E402
from app.modules.exercises.generator import SplitType, generate_routine  # noqa: E402
from app.modules.exercises.models import SavedRoutine  # noqa: E402
from app.modules.nutrition.models import MealLog  # noqa: E402
from app.modules.progressive_overload.models import WorkoutSet  # noqa: E402
from app.modules.user.models import (  # noqa: E402
    ActivityLevel,
    ExperienceLevel,
    Goal,
    Sex,
    Somatotype,
    UserProfileUpdate,
)
from app.modules.user.service import update_profile  # noqa: E402

# Demo credentials (local test account only — documented in database/README.md)
DEMO_EMAIL = "demo@fitbot.app"
DEMO_PASSWORD = "FitBot-Demo-2026"
DEMO_NAME = "Demo Athlete"

# (exercise_id, starting kg, weekly increment kg, reps per set)
LIFTS = [
    ("barbell-bench-press", 60.0, 2.5, [10, 9, 8]),
    ("barbell-back-squat", 80.0, 5.0, [8, 8, 7]),
    ("barbell-bent-over-row", 55.0, 2.5, [10, 10, 9]),
]


def main() -> None:
    init_db()
    load_catalog()
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == DEMO_EMAIL)).first()
        if existing is not None:
            delete_account(session, existing, DEMO_PASSWORD)
            print("Existing demo account reset.")

        user = register_user(
            session, RegisterRequest(full_name=DEMO_NAME, email=DEMO_EMAIL, password=DEMO_PASSWORD)
        )
        uid = user.id
        update_profile(
            session,
            uid,
            UserProfileUpdate(
                age=23,
                sex=Sex.male,
                height_cm=178,
                weight_kg=76,
                body_fat_pct=16,
                experience_level=ExperienceLevel.intermediate,
                somatotype=Somatotype.mesomorph,
                goal=Goal.hypertrophy,
                activity_level=ActivityLevel.moderate,
            ),
        )

        now = datetime.now(timezone.utc)
        for week in range(4):
            day = now - timedelta(days=7 * (3 - week) + 1)
            for exercise_id, start, inc, reps in LIFTS:
                for set_no, rep in enumerate(reps, start=1):
                    session.add(
                        WorkoutSet(
                            user_id=uid,
                            exercise_id=exercise_id,
                            performed_at=day,
                            session_label=f"Week {week + 1}",
                            set_number=set_no,
                            reps=rep,
                            weight_kg=start + inc * week,
                            rpe=7.5 + 0.5 * (set_no - 1),
                            rir=max(0, 3 - set_no),
                        )
                    )

        routine = generate_routine(
            split=SplitType.PUSH_PULL_LEGS,
            days_per_week=4,
            experience_level=ExperienceLevel.intermediate,
            goal=Goal.hypertrophy,
            available_equipment=list(Equipment),
        )
        session.add(
            SavedRoutine(user_id=uid, split="push_pull_legs", days_per_week=4, routine=routine.model_dump(mode="json"))
        )

        for slot, name, kcal, p, c, f in [
            ("Breakfast", "Oats, banana & whey", 520, 38, 72, 9),
            ("Lunch", "Grilled chicken, rice & salad", 690, 52, 78, 16),
        ]:
            session.add(MealLog(user_id=uid, slot=slot, meal_name=name, calories=kcal, protein_g=p, carbs_g=c, fat_g=f))

        session.commit()

    print(f"Demo account ready: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
