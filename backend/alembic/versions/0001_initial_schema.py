"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-26
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

category_enum = postgresql.ENUM(
    "water", "electricity", "sanitation", "roads", "streetlights", "other",
    name="category_enum",
)
priority_enum = postgresql.ENUM("high", "normal", "low", name="priority_enum")
status_enum = postgresql.ENUM("open", "in_progress", "resolved", "rejected", name="status_enum")


def upgrade():
    bind = op.get_bind()
    category_enum.create(bind, checkfirst=True)
    priority_enum.create(bind, checkfirst=True)
    status_enum.create(bind, checkfirst=True)

    op.create_table(
        "complaints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("text", sa.String(2000), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("reporter_contact", sa.String(200), nullable=True),
        sa.Column("category", category_enum, nullable=False),
        sa.Column("priority", priority_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="open"),
        sa.Column("ai_summary", sa.String(140), nullable=True),
        sa.Column("triaged_by", sa.String(50), nullable=False),
        sa.Column("triage_latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("char_length(text) >= 10 AND char_length(text) <= 2000", name="ck_text_length"),
        sa.CheckConstraint("char_length(location) >= 3 AND char_length(location) <= 200", name="ck_location_length"),
    )

    # Serves: dashboard default view (WHERE status=... ORDER BY priority)
    op.create_index("ix_complaints_status_priority", "complaints", ["status", "priority"])
    # Serves: recency feed / date-range queries (ORDER BY created_at DESC)
    op.create_index("ix_complaints_created_at", "complaints", ["created_at"])


def downgrade():
    op.drop_index("ix_complaints_created_at", table_name="complaints")
    op.drop_index("ix_complaints_status_priority", table_name="complaints")
    op.drop_table("complaints")
    status_enum.drop(op.get_bind(), checkfirst=True)
    priority_enum.drop(op.get_bind(), checkfirst=True)
    category_enum.drop(op.get_bind(), checkfirst=True)
