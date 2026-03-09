"""add congress trades table

Revision ID: 010
Revises: 009
Create Date: 2026-03-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add sync timestamp to companies
    op.add_column("companies", sa.Column("congress_trades_synced_at", sa.DateTime(), nullable=True))

    op.create_table(
        "congress_trades",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("representative", sa.String(200), nullable=False),
        sa.Column("party", sa.String(10), nullable=True),
        sa.Column("chamber", sa.String(10), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("disclosure_date", sa.Date(), nullable=True),
        sa.Column("transaction_type", sa.String(20), nullable=True),
        sa.Column("amount_range", sa.String(50), nullable=True),
        sa.Column("asset_description", sa.String(500), nullable=True),
        sa.Column("source", sa.String(50), nullable=True, server_default="fmp"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "company_id",
            "representative",
            "transaction_date",
            "transaction_type",
            name="uq_congress_trade_dedup",
        ),
    )
    op.create_index(
        "ix_congress_trades_company_date", "congress_trades", ["company_id", "transaction_date"]
    )
    op.create_index("ix_congress_trades_representative", "congress_trades", ["representative"])


def downgrade() -> None:
    op.drop_table("congress_trades")
    op.drop_column("companies", "congress_trades_synced_at")
