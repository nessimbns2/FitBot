"""Account-scoped exercise recommendations, feedback and preference models.

Revision ID: f4a8d3b2c601
Revises: e3c2b8d5f0a1
"""
from alembic import op
import sqlalchemy as sa

revision = "f4a8d3b2c601"
down_revision = "e3c2b8d5f0a1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "exercise_recommendations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_exercise_id", sa.String(100), nullable=False),
        sa.Column("exercise_id", sa.String(100), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("feedback", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feedback_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("feedback IS NULL OR feedback IN ('accepted','replaced','liked','disliked')", name="ck_exercise_feedback"),
    )
    op.create_index("ix_exercise_recommendations_user_id", "exercise_recommendations", ["user_id"])
    op.create_table(
        "exercise_preference_models",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("exercise_preference_models")
    op.drop_table("exercise_recommendations")
