"""add patents table

Revision ID: 009
Revises: 008
Create Date: 2026-03-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add sync timestamp to companies
    op.add_column("companies", sa.Column("patents_synced_at", sa.DateTime(), nullable=True))

    op.create_table(
        "patents",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("patent_number", sa.String(20), nullable=False),
        sa.Column("title", sa.String(1000), nullable=True),
        sa.Column("grant_date", sa.Date(), nullable=True),
        sa.Column("application_date", sa.Date(), nullable=True),
        sa.Column("patent_type", sa.String(50), nullable=True),
        sa.Column("cpc_class", sa.String(20), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "patent_number", name="uq_patent_company_number"),
    )
    op.create_index("ix_patents_company_grant_date", "patents", ["company_id", "grant_date"])
    op.create_index("ix_patents_company_cpc_class", "patents", ["company_id", "cpc_class"])


def downgrade() -> None:
    op.drop_table("patents")
    op.drop_column("companies", "patents_synced_at")
