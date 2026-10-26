"""Integrate main's food diary and plateau diagnosis with user accounts.

Revision ID: e3c2b8d5f0a1
Revises: d2f1a7c4b9e0
"""
import json

from alembic import op
import sqlalchemy as sa


revision = "e3c2b8d5f0a1"
down_revision = "d2f1a7c4b9e0"
branch_labels = None
depends_on = None

meal_slot_enum = sa.Enum("breakfast", "lunch", "dinner", "post_workout", "snack", name="mealslotname")
log_source_enum = sa.Enum("manual", "photo_scan", "ai_text", "ai_suggestion", name="logsource")
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    diary = op.create_table(
        "food_log_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("meal_slot", meal_slot_enum, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("calories", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
        sa.Column("source", log_source_enum, nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_index("ix_food_log_entries_user_id", "food_log_entries", ["user_id"])
    op.create_index("ix_food_log_entries_log_date", "food_log_entries", ["log_date"])

    op.create_table(
        "deload_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", sa.String(), nullable=False),
        sa.Column("strategy", sa.String(), nullable=False),
        sa.Column("root_cause", sa.String(), nullable=False),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column("target_weight_kg", sa.Float(), nullable=False),
        sa.Column("target_sets", sa.Integer(), nullable=False),
        sa.Column("target_reps_range", sa.String(), nullable=False),
        sa.Column("target_rpe_ceiling", sa.Float(), nullable=False),
        sa.Column("resume_weight_kg", sa.Float(), nullable=False),
        sa.Column("duration_sessions", sa.Integer(), nullable=False),
        sa.Column("constants_version", sa.String(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("plate_increment_kg", sa.Float(), nullable=False),
        sa.Column("weight_match_tolerance_kg", sa.Float(), nullable=False),
        sa.Column("profile_is_default", sa.Boolean(), nullable=False),
        sa.Column("applied_at", TS, nullable=False),
        sa.Column("expires_at", TS, nullable=True),
        sa.Column("cancelled_at", TS, nullable=True),
        sa.Column("cancel_reason", sa.String(), nullable=True),
        sa.Column("completed_at", TS, nullable=True),
        sa.Column("feedback", sa.String(), nullable=True),
    )
    for column in ("user_id", "exercise_id", "applied_at"):
        op.create_index(f"ix_deload_records_{column}", "deload_records", [column])

    # The former UI saved meals here. Copy them into the expanded upstream diary
    # so that an upgrade does not make existing meals disappear from the screen.
    bind = op.get_bind()
    legacy = sa.Table("meal_logs", sa.MetaData(), autoload_with=bind)
    for meal in bind.execute(sa.select(legacy)).mappings():
        slot = meal["slot"].lower().replace("-", "_").replace(" ", "_")
        if slot not in ("breakfast", "lunch", "dinner", "post_workout", "snack"):
            slot = "snack"
        items = meal["food_items"]
        if isinstance(items, str):
            items = json.loads(items)
        notes = ", ".join(str(item.get("name", "")) for item in items or [])[:500] or None
        bind.execute(diary.insert().values(
            user_id=meal["user_id"], log_date=meal["logged_on"], meal_slot=slot,
            name=meal["meal_name"], calories=meal["calories"],
            protein_g=meal["protein_g"], carbs_g=meal["carbs_g"], fat_g=meal["fat_g"],
            source="photo_scan", notes=notes,
            created_at=meal["created_at"], updated_at=meal["created_at"],
        ))


def downgrade() -> None:
    op.drop_table("deload_records")
    op.drop_table("food_log_entries")
    for enum in (log_source_enum, meal_slot_enum):
        enum.drop(op.get_bind(), checkfirst=True)
