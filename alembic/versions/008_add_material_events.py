"""add material events table

Revision ID: 008
Revises: 007
Create Date: 2026-03-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add sync timestamp to companies
    op.add_column("companies", sa.Column("material_events_synced_at", sa.DateTime(), nullable=True))

    op.create_table(
        "material_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("item_number", sa.String(10), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("filing_url", sa.Text(), nullable=True),
        sa.Column("accession_number", sa.String(30), nullable=True),
        sa.Column("source", sa.String(50), nullable=True, server_default="sec_8k"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "company_id", "accession_number", "item_number", name="uq_material_event_dedup"
        ),
    )
    op.create_index(
        "ix_material_events_company_date", "material_events", ["company_id", "event_date"]
    )
    op.create_index("ix_material_events_event_type", "material_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("material_events")
    op.drop_column("companies", "material_events_synced_at")
