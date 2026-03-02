"""XBRL financial data model (EAV/tall table)."""

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class FinancialFact(TimestampMixin, Base):
    __tablename__ = "financial_facts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    taxonomy: Mapped[str] = mapped_column(String(50))
    concept: Mapped[str] = mapped_column(String(200))
    value: Mapped[Decimal] = mapped_column(Numeric(28, 4))
    unit: Mapped[str] = mapped_column(String(50))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    is_instant: Mapped[bool] = mapped_column(Boolean, default=False)
    fiscal_year: Mapped[int | None]
    fiscal_period: Mapped[str | None] = mapped_column(String(10))
    form_type: Mapped[str | None] = mapped_column(String(20))
    accession_number: Mapped[str | None] = mapped_column(String(30))
    filed_date: Mapped[date | None] = mapped_column(Date)

    company: Mapped["Company"] = relationship(back_populates="financial_facts")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "taxonomy",
            "concept",
            "unit",
            "period_end",
            "period_start",
            "accession_number",
            name="uq_financial_facts_dedup",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_facts_company_concept", "company_id", "concept"),
        Index("ix_facts_concept_period", "concept", "period_end"),
        Index("ix_facts_company_fiscal", "company_id", "fiscal_year", "fiscal_period"),
    )

    def __repr__(self) -> str:
        return f"<FinancialFact {self.concept}={self.value} ({self.period_end})>"
