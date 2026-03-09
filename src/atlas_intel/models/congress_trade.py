"""Congress trade model (congressional stock trading disclosures)."""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class CongressTrade(TimestampMixin, Base):
    __tablename__ = "congress_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    representative: Mapped[str] = mapped_column(String(200))
    party: Mapped[str | None] = mapped_column(String(10))
    chamber: Mapped[str | None] = mapped_column(String(10))
    transaction_date: Mapped[date] = mapped_column(Date)
    disclosure_date: Mapped[date | None] = mapped_column(Date)
    transaction_type: Mapped[str | None] = mapped_column(String(20))
    amount_range: Mapped[str | None] = mapped_column(String(50))
    asset_description: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(50), default="fmp")

    company: Mapped["Company"] = relationship(back_populates="congress_trades")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "representative",
            "transaction_date",
            "transaction_type",
            name="uq_congress_trade_dedup",
        ),
        Index("ix_congress_trades_company_date", "company_id", "transaction_date"),
        Index("ix_congress_trades_representative", "representative"),
    )

    def __repr__(self) -> str:
        return f"<CongressTrade {self.representative} {self.transaction_date}>"
