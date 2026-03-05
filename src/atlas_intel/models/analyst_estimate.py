"""Analyst consensus estimate model."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class AnalystEstimate(TimestampMixin, Base):
    __tablename__ = "analyst_estimates"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    period: Mapped[str] = mapped_column(String(10))  # "annual" or "quarter"
    estimate_date: Mapped[date] = mapped_column(Date)

    # Revenue estimates
    estimated_revenue_avg: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    estimated_revenue_high: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    estimated_revenue_low: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))

    # EPS estimates
    estimated_eps_avg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    estimated_eps_high: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    estimated_eps_low: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    # EBITDA estimates
    estimated_ebitda_avg: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    estimated_ebitda_high: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    estimated_ebitda_low: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))

    # Analyst counts
    number_analysts_revenue: Mapped[int | None] = mapped_column(Integer)
    number_analysts_eps: Mapped[int | None] = mapped_column(Integer)

    company: Mapped["Company"] = relationship(back_populates="analyst_estimates")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "company_id", "period", "estimate_date", name="uq_analyst_estimate_company_period_date"
        ),
        Index("ix_analyst_estimates_company_date", "company_id", "estimate_date"),
    )

    def __repr__(self) -> str:
        return f"<AnalystEstimate {self.period} {self.estimate_date}>"
