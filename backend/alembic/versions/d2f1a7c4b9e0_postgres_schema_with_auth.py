"""PostgreSQL schema with authentication and per-user data

Creates every FitBot table:
  users            — accounts (email unique, bcrypt password hash)
  user_profile     — 1:1 biometric profile of a user
  chat_session     — coach conversations of a user
  chat_message     — messages of a conversation (with retrieved sources as JSON text)
  workout_sets     — logged sets used by the progressive-overload engine
  meal_logs        — nutrition diary (was browser localStorage)
  saved_routines   — routine the user follows (was browser localStorage)

All personal data hangs off users.id with ON DELETE CASCADE.

Revision ID: d2f1a7c4b9e0
Revises: c8414bb283f9
Create Date: 2026-10-25 16:30:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d2f1a7c4b9e0"
down_revision: Union[str, Sequence[str], None] = "c8414bb283f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


sex_enum = sa.Enum("male", "female", name="sex")
experience_enum = sa.Enum("beginner", "intermediate", "advanced", name="experiencelevel")
somatotype_enum = sa.Enum("ectomorph", "mesomorph", "endomorph", "unknown", name="somatotype")
goal_enum = sa.Enum("hypertrophy", "fat_loss", "strength", "athletic_performance", name="goal")
activity_enum = sa.Enum("sedentary", "light", "moderate", "very_active", "extreme", name="activitylevel")
unit_enum = sa.Enum("metric", "imperial", name="unitsystem")

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", TS, nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("sex", sex_enum, nullable=False, server_default="male"),
        sa.Column("height_cm", sa.Float(), nullable=False, server_default="175"),
        sa.Column("weight_kg", sa.Float(), nullable=False, server_default="75"),
        sa.Column("body_fat_pct", sa.Float(), nullable=True),
        sa.Column("experience_level", experience_enum, nullable=False, server_default="beginner"),
        sa.Column("somatotype", somatotype_enum, nullable=False, server_default="unknown"),
        sa.Column("goal", goal_enum, nullable=False, server_default="hypertrophy"),
        sa.Column("activity_level", activity_enum, nullable=False, server_default="moderate"),
        sa.Column("unit_system", unit_enum, nullable=False, server_default="metric"),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("age BETWEEN 14 AND 100", name="ck_profile_age"),
        sa.CheckConstraint("height_cm BETWEEN 120 AND 230", name="ck_profile_height"),
        sa.CheckConstraint("weight_kg BETWEEN 30 AND 300", name="ck_profile_weight"),
        sa.CheckConstraint("body_fat_pct IS NULL OR body_fat_pct BETWEEN 3 AND 60", name="ck_profile_body_fat"),
    )
    op.create_index("ix_user_profile_user_id", "user_profile", ["user_id"], unique=True)

    op.create_table(
        "chat_session",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default="New conversation"),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_session_user_id", "chat_session", ["user_id"])

    op.create_table(
        "chat_message",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.Text(), nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_message_role"),
    )
    op.create_index("ix_chat_message_session_id", "chat_message", ["session_id"])

    op.create_table(
        "workout_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", sa.String(100), nullable=False),
        sa.Column("performed_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("session_label", sa.String(100), nullable=True),
        sa.Column("set_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("rpe", sa.Float(), nullable=True),
        sa.Column("rir", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("reps BETWEEN 1 AND 100", name="ck_workout_sets_reps"),
        sa.CheckConstraint("weight_kg BETWEEN 0 AND 500", name="ck_workout_sets_weight"),
    )
    op.create_index("ix_workout_sets_user_id", "workout_sets", ["user_id"])
    op.create_index("ix_workout_sets_exercise_id", "workout_sets", ["exercise_id"])
    op.create_index("ix_workout_sets_performed_at", "workout_sets", ["performed_at"])

    op.create_table(
        "meal_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("logged_on", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("slot", sa.String(40), nullable=False, server_default="Snack"),
        sa.Column("meal_name", sa.String(200), nullable=False),
        sa.Column("calories", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("protein_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("carbs_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fat_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("food_items", sa.JSON(), nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("calories >= 0", name="ck_meal_logs_calories"),
    )
    op.create_index("ix_meal_logs_user_id", "meal_logs", ["user_id"])
    op.create_index("ix_meal_logs_logged_on", "meal_logs", ["logged_on"])

    op.create_table(
        "saved_routines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("split", sa.String(40), nullable=False, server_default="push_pull_legs"),
        sa.Column("days_per_week", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("routine", sa.JSON(), nullable=False),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("days_per_week BETWEEN 1 AND 7", name="ck_saved_routines_days"),
    )
    op.create_index("ix_saved_routines_user_id", "saved_routines", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_table("saved_routines")
    op.drop_table("meal_logs")
    op.drop_table("workout_sets")
    op.drop_table("chat_message")
    op.drop_table("chat_session")
    op.drop_table("user_profile")
    op.drop_table("users")
    bind = op.get_bind()
    for enum in (unit_enum, activity_enum, goal_enum, somatotype_enum, experience_enum, sex_enum):
        enum.drop(bind, checkfirst=True)
