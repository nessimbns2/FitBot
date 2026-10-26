"""Seed incline-press fatigue history for an explicitly selected account.

Run from backend/: python seed_incline.py --user-id <account ID>
Uses DATABASE_URL, including PostgreSQL, instead of the former local SQLite file.
"""
import argparse
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, delete

from app.core.database import engine, init_db
from app.modules.auth.models import User
from app.modules.progressive_overload.models import WorkoutSet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True)
    args = parser.parse_args()
    init_db()
    with Session(engine) as session:
        if session.get(User, args.user_id) is None:
            raise SystemExit("Account not found. Register the user before seeding workout history.")
        session.exec(delete(WorkoutSet).where(
            WorkoutSet.exercise_id == "incline-dumbbell-press",
            WorkoutSet.user_id == args.user_id,
        ))
        now = datetime.now(timezone.utc)
        sessions = [
            (21, [(10, 7.5), (10, 7.5), (10, 8.0)]),
            (14, [(10, 8.5), (9, 8.5), (8, 9.0)]),
            (7, [(9, 9.0), (8, 9.0), (7, 9.5)]),
            (0, [(8, 9.5), (7, 9.5), (6, 9.5)]),
        ]
        for days_ago, sets in sessions:
            for number, (reps, rpe) in enumerate(sets, 1):
                session.add(WorkoutSet(
                    user_id=args.user_id, exercise_id="incline-dumbbell-press",
                    weight_kg=32.0, reps=reps, rpe=rpe, set_number=number,
                    performed_at=now - timedelta(days=days_ago),
                ))
        session.commit()
    print(f"Seeded four incline-press sessions for account {args.user_id}.")


if __name__ == "__main__":
    main()
