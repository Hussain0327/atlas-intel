"""Insider trading model."""

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class InsiderTrade(TimestampMixin, Base):
    __tablename__ = "insider_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    filing_date: Mapped[date] = mapped_column(Date)
    transaction_date: Mapped[date | None] = mapped_column(Date)
    reporting_name: Mapped[str] = mapped_column(String(500))
    reporting_cik: Mapped[str | None] = mapped_column(String(20))
    transaction_type: Mapped[str | None] = mapped_column(String(10))
    securities_transacted: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    price: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    securities_owned: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    owner_type: Mapped[str | None] = mapped_column(String(50))

    company: Mapped["Company"] = relationship(back_populates="insider_trades")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "filing_date",
            "reporting_cik",
            "transaction_type",
            "securities_transacted",
            name="uq_insider_trade_dedup",
        ),
        Index("ix_insider_trades_company_filing", "company_id", "filing_date"),
        Index("ix_insider_trades_company_type", "company_id", "transaction_type"),
    )

    def __repr__(self) -> str:
        return f"<InsiderTrade {self.filing_date} {self.reporting_name} {self.transaction_type}>"
