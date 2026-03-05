"""Institutional ownership holding model."""

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class InstitutionalHolding(TimestampMixin, Base):
    __tablename__ = "institutional_holdings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    holder: Mapped[str] = mapped_column(String(500))
    shares: Mapped[int | None] = mapped_column(BigInteger)
    date_reported: Mapped[date] = mapped_column(Date)
    change: Mapped[int | None] = mapped_column(BigInteger)
    change_percentage: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    portfolio_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    company: Mapped["Company"] = relationship(back_populates="institutional_holdings")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "company_id", "holder", "date_reported", name="uq_institutional_holding_dedup"
        ),
        Index("ix_institutional_holdings_company_date", "company_id", "date_reported"),
        Index(
            "ix_institutional_holdings_company_shares",
            "company_id",
            "shares",
        ),
    )

    def __repr__(self) -> str:
        return f"<InstitutionalHolding {self.holder} {self.shares} shares>"
