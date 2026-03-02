"""nulls not distinct on financial_facts dedup constraint

Revision ID: 002
Revises: 001
Create Date: 2026-03-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_financial_facts_dedup", "financial_facts", type_="unique")
    op.execute(
        """
        ALTER TABLE financial_facts
        ADD CONSTRAINT uq_financial_facts_dedup
        UNIQUE NULLS NOT DISTINCT (
            company_id, taxonomy, concept, unit,
            period_end, period_start, accession_number
        )
        """
    )


def downgrade() -> None:
    op.drop_constraint("uq_financial_facts_dedup", "financial_facts", type_="unique")
    op.create_unique_constraint(
        "uq_financial_facts_dedup",
        "financial_facts",
        [
            "company_id",
            "taxonomy",
            "concept",
            "unit",
            "period_end",
            "period_start",
            "accession_number",
        ],
    )
