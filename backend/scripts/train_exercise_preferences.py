"""Inspect or train an existing user's workout preference model.

From backend/: python scripts/train_exercise_preferences.py --email user@example.com
Add --train to evaluate a candidate model and save it only if it beats baseline.
This command never creates users, feedback labels, synthetic data or API calls.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.database import engine, import_all_models
from app.modules.auth.models import User
from app.modules.exercises.recommendations import learning_status, train_preferences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--train", action="store_true")
    args = parser.parse_args()
    import_all_models()
    with Session(engine) as db:
        user = db.exec(select(User).where(User.email == args.email.strip().lower())).first()
        if user is None or not user.is_active:
            raise SystemExit("Active account not found.")
        try:
            result = train_preferences(db, user.id) if args.train else learning_status(db, user.id)
        except HTTPException as error:
            raise SystemExit(error.detail) from error
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
