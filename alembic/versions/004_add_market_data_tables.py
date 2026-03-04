"""add market data tables and company profile columns

Revision ID: 004
Revises: 003
Create Date: 2026-03-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add profile columns to companies
    op.add_column("companies", sa.Column("sector", sa.String(100), nullable=True))
    op.add_column("companies", sa.Column("industry", sa.String(200), nullable=True))
    op.add_column("companies", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("companies", sa.Column("currency", sa.String(10), nullable=True))
    op.add_column("companies", sa.Column("ceo", sa.String(200), nullable=True))
    op.add_column("companies", sa.Column("full_time_employees", sa.Integer(), nullable=True))
    op.add_column("companies", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("ipo_date", sa.Date(), nullable=True))
    op.add_column("companies", sa.Column("is_etf", sa.Boolean(), nullable=True))
    op.add_column("companies", sa.Column("is_actively_trading", sa.Boolean(), nullable=True))
    op.add_column("companies", sa.Column("beta", sa.Numeric(8, 4), nullable=True))

    # Add sync timestamps
    op.add_column("companies", sa.Column("prices_synced_at", sa.DateTime(), nullable=True))
    op.add_column("companies", sa.Column("profile_synced_at", sa.DateTime(), nullable=True))
    op.add_column("companies", sa.Column("metrics_synced_at", sa.DateTime(), nullable=True))

    # Add indexes on sector/industry
    op.create_index("ix_companies_sector", "companies", ["sector"])
    op.create_index("ix_companies_industry", "companies", ["industry"])

    # Stock prices table
    op.create_table(
        "stock_prices",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(16, 4), nullable=True),
        sa.Column("high", sa.Numeric(16, 4), nullable=True),
        sa.Column("low", sa.Numeric(16, 4), nullable=True),
        sa.Column("close", sa.Numeric(16, 4), nullable=True),
        sa.Column("adj_close", sa.Numeric(16, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("vwap", sa.Numeric(16, 4), nullable=True),
        sa.Column("change_percent", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "price_date", name="uq_stock_price_company_date"),
    )
    op.create_index("ix_stock_prices_company_date", "stock_prices", ["company_id", "price_date"])
    op.create_index("ix_stock_prices_date", "stock_prices", ["price_date"])

    # Market metrics table
    op.create_table(
        "market_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        # Valuation
        sa.Column("market_cap", sa.Numeric(20, 4), nullable=True),
        sa.Column("enterprise_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("pe_ratio", sa.Numeric(12, 4), nullable=True),
        sa.Column("pb_ratio", sa.Numeric(12, 4), nullable=True),
        sa.Column("price_to_sales", sa.Numeric(12, 4), nullable=True),
        sa.Column("ev_to_ebitda", sa.Numeric(12, 4), nullable=True),
        sa.Column("ev_to_sales", sa.Numeric(12, 4), nullable=True),
        # Yield
        sa.Column("earnings_yield", sa.Numeric(10, 4), nullable=True),
        sa.Column("fcf_yield", sa.Numeric(10, 4), nullable=True),
        # Per-share
        sa.Column("revenue_per_share", sa.Numeric(16, 4), nullable=True),
        sa.Column("net_income_per_share", sa.Numeric(16, 4), nullable=True),
        sa.Column("book_value_per_share", sa.Numeric(16, 4), nullable=True),
        sa.Column("fcf_per_share", sa.Numeric(16, 4), nullable=True),
        sa.Column("dividend_per_share", sa.Numeric(16, 4), nullable=True),
        # Profitability
        sa.Column("roe", sa.Numeric(10, 4), nullable=True),
        sa.Column("roic", sa.Numeric(10, 4), nullable=True),
        # Leverage
        sa.Column("debt_to_equity", sa.Numeric(12, 4), nullable=True),
        sa.Column("debt_to_assets", sa.Numeric(10, 4), nullable=True),
        sa.Column("current_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("interest_coverage", sa.Numeric(12, 4), nullable=True),
        # Dividends
        sa.Column("dividend_yield", sa.Numeric(10, 4), nullable=True),
        sa.Column("payout_ratio", sa.Numeric(10, 4), nullable=True),
        # Efficiency
        sa.Column("days_sales_outstanding", sa.Numeric(10, 4), nullable=True),
        sa.Column("days_payables_outstanding", sa.Numeric(10, 4), nullable=True),
        sa.Column("inventory_turnover", sa.Numeric(10, 4), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "company_id", "period", "period_date", name="uq_market_metric_company_period"
        ),
    )
    op.create_index("ix_market_metrics_company_period", "market_metrics", ["company_id", "period"])
    op.create_index(
        "ix_market_metrics_company_date", "market_metrics", ["company_id", "period_date"]
    )


def downgrade() -> None:
    op.drop_table("market_metrics")
    op.drop_table("stock_prices")
    op.drop_index("ix_companies_industry", table_name="companies")
    op.drop_index("ix_companies_sector", table_name="companies")
    op.drop_column("companies", "metrics_synced_at")
    op.drop_column("companies", "profile_synced_at")
    op.drop_column("companies", "prices_synced_at")
    op.drop_column("companies", "beta")
    op.drop_column("companies", "is_actively_trading")
    op.drop_column("companies", "is_etf")
    op.drop_column("companies", "ipo_date")
    op.drop_column("companies", "description")
    op.drop_column("companies", "full_time_employees")
    op.drop_column("companies", "ceo")
    op.drop_column("companies", "currency")
    op.drop_column("companies", "country")
    op.drop_column("companies", "industry")
    op.drop_column("companies", "sector")
