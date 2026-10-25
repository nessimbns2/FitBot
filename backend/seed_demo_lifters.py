"""
backend/seed_demo_lifters.py
Seeds 3 demo lifters in the database to test and demo the plateau diagnostician:
1. Lifter 1 (Fatigue Demo): Alex (ID 101) - flat weight, rising RPE, rep dropoff -> fatigue_pattern
2. Lifter 2 (Under-Stimulus Demo): Jordan (ID 102) - flat weight, falling RPE -> insufficient_stimulus
3. Lifter 3 (Progressing Demo): Sam (ID 103) - rising weight & 1RM, steady RPE -> progressing
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select, delete

from app.core.database import engine, init_db
from app.modules.progressive_overload.models import WorkoutSet, DeloadRecord
from app.modules.progressive_overload.service import get_diagnosis
from app.modules.user.models import UserProfile, ExperienceLevel, Goal, UnitSystem


def seed_demo_lifters():
    init_db()
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        # Clean up any existing demo lifter data
        demo_ids = [101, 102, 103]
        for uid in demo_ids:
            session.exec(delete(WorkoutSet).where(WorkoutSet.user_id == uid))
            session.exec(delete(DeloadRecord).where(DeloadRecord.user_id == uid))
            existing_user = session.get(UserProfile, uid)
            if existing_user:
                session.delete(existing_user)
        session.commit()

        # 1. Fatigue Lifter (Alex)
        user_fatigue = UserProfile(
            id=101,
            email="alex_fatigue@demo.fitbot",
            name="Alex Fatigue",
            experience_level=ExperienceLevel.intermediate,
            goal=Goal.hypertrophy,
            unit_system=UnitSystem.metric,
            weight_kg=80.0,
            height_cm=178.0,
        )
        session.add(user_fatigue)

        # 4 sessions over 21 days: flat 80kg, rising RPE 7.0 -> 9.4, rep dropoff (8,8,8 -> 8,7,5)
        offsets = [-21, -14, -7, 0]
        rpes = [7.0, 7.8, 8.6, 9.4]
        reps_sets = [
            [8, 8, 8],
            [8, 8, 7],
            [8, 7, 6],
            [8, 7, 5],
        ]
        for off, rpe, sets in zip(offsets, rpes, reps_sets):
            dt = now + timedelta(days=off)
            for set_num, reps in enumerate(sets, start=1):
                session.add(
                    WorkoutSet(
                        user_id=101,
                        exercise_id="barbell-bench-press",
                        performed_at=dt,
                        set_number=set_num,
                        reps=reps,
                        weight_kg=80.0,
                        rpe=rpe,
                    )
                )

        # 2. Under-Stimulus Lifter (Jordan)
        user_stim = UserProfile(
            id=102,
            email="jordan_stim@demo.fitbot",
            name="Jordan Under-Stimulus",
            experience_level=ExperienceLevel.intermediate,
            goal=Goal.hypertrophy,
            unit_system=UnitSystem.metric,
            weight_kg=75.0,
            height_cm=175.0,
        )
        session.add(user_stim)

        # 4 sessions over 21 days: flat 100kg, falling RPE 8.5 -> 7.0, hitting 8 reps easily
        stim_rpes = [8.5, 8.0, 7.5, 7.0]
        for off, rpe in zip(offsets, stim_rpes):
            dt = now + timedelta(days=off)
            for set_num in range(1, 4):
                session.add(
                    WorkoutSet(
                        user_id=102,
                        exercise_id="barbell-back-squat",
                        performed_at=dt,
                        set_number=set_num,
                        reps=8,
                        weight_kg=100.0,
                        rpe=rpe,
                    )
                )

        # 3. Progressing Lifter (Sam)
        user_prog = UserProfile(
            id=103,
            email="sam_prog@demo.fitbot",
            name="Sam Progressing",
            experience_level=ExperienceLevel.intermediate,
            goal=Goal.strength,
            unit_system=UnitSystem.metric,
            weight_kg=82.0,
            height_cm=180.0,
        )
        session.add(user_prog)

        # 4 sessions over 21 days: progressive load 120 -> 125 -> 130 -> 135 kg, steady RPE 8.0
        weights = [120.0, 125.0, 130.0, 135.0]
        for off, w in zip(offsets, weights):
            dt = now + timedelta(days=off)
            for set_num in range(1, 4):
                session.add(
                    WorkoutSet(
                        user_id=103,
                        exercise_id="barbell-deadlift",
                        performed_at=dt,
                        set_number=set_num,
                        reps=5,
                        weight_kg=w,
                        rpe=8.0,
                    )
                )

        session.commit()
        print("Successfully seeded 3 demo lifters (IDs: 101, 102, 103).")

        # Verify diagnoses
        print("\n--- Verifying Diagnoses ---")
        d1 = get_diagnosis(session, "barbell-bench-press", user_id=101)["diagnosis"]
        print(f"Alex (Fatigue): root_cause={d1.root_cause.value}, strategy={d1.deload_target.strategy.value}")

        d2 = get_diagnosis(session, "barbell-back-squat", user_id=102)["diagnosis"]
        print(f"Jordan (Under-Stimulus): root_cause={d2.root_cause.value}, strategy={d2.deload_target.strategy.value}")

        d3 = get_diagnosis(session, "barbell-deadlift", user_id=103)["diagnosis"]
        print(f"Sam (Progressing): root_cause={d3.root_cause.value}, strategy={d3.deload_target.strategy.value}")


if __name__ == "__main__":
    seed_demo_lifters()
