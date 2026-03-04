"""Market metrics and financial ratios model."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class MarketMetric(TimestampMixin, Base):
    __tablename__ = "market_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    period: Mapped[str] = mapped_column(String(10))  # "TTM", "annual"
    period_date: Mapped[date] = mapped_column(Date)

    # Valuation
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    enterprise_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    pb_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    price_to_sales: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    ev_to_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    ev_to_sales: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    # Yield
    earnings_yield: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fcf_yield: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    # Per-share
    revenue_per_share: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    net_income_per_share: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    book_value_per_share: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    fcf_per_share: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    dividend_per_share: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))

    # Profitability
    roe: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    roic: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    # Leverage
    debt_to_equity: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    debt_to_assets: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    current_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    interest_coverage: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    # Dividends
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    payout_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    # Efficiency
    days_sales_outstanding: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    days_payables_outstanding: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    inventory_turnover: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    company: Mapped["Company"] = relationship(back_populates="market_metrics")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "company_id", "period", "period_date", name="uq_market_metric_company_period"
        ),
        Index("ix_market_metrics_company_period", "company_id", "period"),
        Index("ix_market_metrics_company_date", "company_id", "period_date"),
    )

    def __repr__(self) -> str:
        return f"<MarketMetric {self.period} {self.period_date} pe={self.pe_ratio}>"
