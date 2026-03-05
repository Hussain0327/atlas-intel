"""add alternative data tables (news, insider trades, estimates, grades, price targets, holdings)

Revision ID: 005
Revises: 004
Create Date: 2026-03-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add sync timestamps to companies
    op.add_column("companies", sa.Column("news_synced_at", sa.DateTime(), nullable=True))
    op.add_column("companies", sa.Column("insider_trades_synced_at", sa.DateTime(), nullable=True))
    op.add_column(
        "companies", sa.Column("analyst_estimates_synced_at", sa.DateTime(), nullable=True)
    )
    op.add_column("companies", sa.Column("analyst_grades_synced_at", sa.DateTime(), nullable=True))
    op.add_column("companies", sa.Column("price_targets_synced_at", sa.DateTime(), nullable=True))
    op.add_column(
        "companies", sa.Column("institutional_holdings_synced_at", sa.DateTime(), nullable=True)
    )

    # News articles
    op.create_table(
        "news_articles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "url", name="uq_news_article_company_url"),
    )
    op.create_index(
        "ix_news_articles_company_published", "news_articles", ["company_id", "published_at"]
    )
    op.create_index("ix_news_articles_published", "news_articles", ["published_at"])

    # Insider trades
    op.create_table(
        "insider_trades",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("reporting_name", sa.String(500), nullable=False),
        sa.Column("reporting_cik", sa.String(20), nullable=True),
        sa.Column("transaction_type", sa.String(10), nullable=True),
        sa.Column("securities_transacted", sa.Numeric(16, 4), nullable=True),
        sa.Column("price", sa.Numeric(16, 4), nullable=True),
        sa.Column("securities_owned", sa.Numeric(16, 4), nullable=True),
        sa.Column("owner_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "company_id",
            "filing_date",
            "reporting_cik",
            "transaction_type",
            "securities_transacted",
            name="uq_insider_trade_dedup",
        ),
    )
    op.create_index(
        "ix_insider_trades_company_filing", "insider_trades", ["company_id", "filing_date"]
    )
    op.create_index(
        "ix_insider_trades_company_type", "insider_trades", ["company_id", "transaction_type"]
    )

    # Analyst estimates
    op.create_table(
        "analyst_estimates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("estimate_date", sa.Date(), nullable=False),
        sa.Column("estimated_revenue_avg", sa.Numeric(20, 4), nullable=True),
        sa.Column("estimated_revenue_high", sa.Numeric(20, 4), nullable=True),
        sa.Column("estimated_revenue_low", sa.Numeric(20, 4), nullable=True),
        sa.Column("estimated_eps_avg", sa.Numeric(12, 4), nullable=True),
        sa.Column("estimated_eps_high", sa.Numeric(12, 4), nullable=True),
        sa.Column("estimated_eps_low", sa.Numeric(12, 4), nullable=True),
        sa.Column("estimated_ebitda_avg", sa.Numeric(20, 4), nullable=True),
        sa.Column("estimated_ebitda_high", sa.Numeric(20, 4), nullable=True),
        sa.Column("estimated_ebitda_low", sa.Numeric(20, 4), nullable=True),
        sa.Column("number_analysts_revenue", sa.Integer(), nullable=True),
        sa.Column("number_analysts_eps", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "company_id", "period", "estimate_date", name="uq_analyst_estimate_company_period_date"
        ),
    )
    op.create_index(
        "ix_analyst_estimates_company_date", "analyst_estimates", ["company_id", "estimate_date"]
    )

    # Analyst grades
    op.create_table(
        "analyst_grades",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("grade_date", sa.Date(), nullable=False),
        sa.Column("grading_company", sa.String(200), nullable=False),
        sa.Column("previous_grade", sa.String(50), nullable=True),
        sa.Column("new_grade", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "company_id",
            "grade_date",
            "grading_company",
            "new_grade",
            name="uq_analyst_grade_dedup",
        ),
    )
    op.create_index(
        "ix_analyst_grades_company_date", "analyst_grades", ["company_id", "grade_date"]
    )
    op.create_index("ix_analyst_grades_company_action", "analyst_grades", ["company_id", "action"])

    # Price targets
    op.create_table(
        "price_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_high", sa.Numeric(16, 4), nullable=True),
        sa.Column("target_low", sa.Numeric(16, 4), nullable=True),
        sa.Column("target_consensus", sa.Numeric(16, 4), nullable=True),
        sa.Column("target_median", sa.Numeric(16, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", name="uq_price_target_company"),
    )

    # Institutional holdings
    op.create_table(
        "institutional_holdings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("holder", sa.String(500), nullable=False),
        sa.Column("shares", sa.BigInteger(), nullable=True),
        sa.Column("date_reported", sa.Date(), nullable=False),
        sa.Column("change", sa.BigInteger(), nullable=True),
        sa.Column("change_percentage", sa.Numeric(10, 4), nullable=True),
        sa.Column("market_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("portfolio_percent", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "company_id", "holder", "date_reported", name="uq_institutional_holding_dedup"
        ),
    )
    op.create_index(
        "ix_institutional_holdings_company_date",
        "institutional_holdings",
        ["company_id", "date_reported"],
    )
    op.create_index(
        "ix_institutional_holdings_company_shares",
        "institutional_holdings",
        ["company_id", "shares"],
    )


def downgrade() -> None:
    op.drop_table("institutional_holdings")
    op.drop_table("price_targets")
    op.drop_table("analyst_grades")
    op.drop_table("analyst_estimates")
    op.drop_table("insider_trades")
    op.drop_table("news_articles")
    op.drop_column("companies", "institutional_holdings_synced_at")
    op.drop_column("companies", "price_targets_synced_at")
    op.drop_column("companies", "analyst_grades_synced_at")
    op.drop_column("companies", "analyst_estimates_synced_at")
    op.drop_column("companies", "insider_trades_synced_at")
    op.drop_column("companies", "news_synced_at")
