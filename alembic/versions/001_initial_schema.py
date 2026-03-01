"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cik", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("ticker", sa.String(20)),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("sic_code", sa.String(10)),
        sa.Column("sic_description", sa.String(500)),
        sa.Column("fiscal_year_end", sa.String(4)),
        sa.Column("exchange", sa.String(50)),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("state_of_incorporation", sa.String(10)),
        sa.Column("ein", sa.String(20)),
        sa.Column("website", sa.Text()),
        sa.Column("submissions_synced_at", sa.DateTime()),
        sa.Column("facts_synced_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_companies_cik", "companies", ["cik"])
    op.create_index("ix_companies_ticker", "companies", ["ticker"])
    op.create_index(
        "ix_companies_name_trgm",
        "companies",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )

    op.create_table(
        "filings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("accession_number", sa.String(30), nullable=False, unique=True),
        sa.Column("form_type", sa.String(20), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("period_of_report", sa.Date()),
        sa.Column("primary_document", sa.Text()),
        sa.Column("is_xbrl", sa.Boolean()),
        sa.Column("filing_url", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_filings_company_form", "filings", ["company_id", "form_type"])
    op.create_index("ix_filings_company_date", "filings", ["company_id", "filing_date"])
    op.create_index("ix_filings_company_period", "filings", ["company_id", "period_of_report"])

    op.create_table(
        "financial_facts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("taxonomy", sa.String(50), nullable=False),
        sa.Column("concept", sa.String(200), nullable=False),
        sa.Column("value", sa.Numeric(28, 4), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("period_start", sa.Date()),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("is_instant", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fiscal_year", sa.Integer()),
        sa.Column("fiscal_period", sa.String(10)),
        sa.Column("form_type", sa.String(20)),
        sa.Column("accession_number", sa.String(30)),
        sa.Column("filed_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "company_id",
            "taxonomy",
            "concept",
            "unit",
            "period_end",
            "period_start",
            "accession_number",
            name="uq_financial_facts_dedup",
        ),
    )
    op.create_index("ix_facts_company_concept", "financial_facts", ["company_id", "concept"])
    op.create_index("ix_facts_concept_period", "financial_facts", ["concept", "period_end"])
    op.create_index(
        "ix_facts_company_fiscal", "financial_facts", ["company_id", "fiscal_year", "fiscal_period"]
    )


def downgrade() -> None:
    op.drop_table("financial_facts")
    op.drop_table("filings")
    op.drop_table("companies")
