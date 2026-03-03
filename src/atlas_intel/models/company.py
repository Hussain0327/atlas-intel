"""Company entity model."""

from datetime import datetime

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    cik: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    ticker: Mapped[str | None] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(500))
    sic_code: Mapped[str | None] = mapped_column(String(10))
    sic_description: Mapped[str | None] = mapped_column(String(500))
    fiscal_year_end: Mapped[str | None] = mapped_column(String(4))  # MMDD
    exchange: Mapped[str | None] = mapped_column(String(50))
    entity_type: Mapped[str | None] = mapped_column(String(50))
    state_of_incorporation: Mapped[str | None] = mapped_column(String(10))
    ein: Mapped[str | None] = mapped_column(String(20))
    website: Mapped[str | None] = mapped_column(Text)

    submissions_synced_at: Mapped[datetime | None] = mapped_column()
    facts_synced_at: Mapped[datetime | None] = mapped_column()
    transcripts_synced_at: Mapped[datetime | None] = mapped_column()

    filings: Mapped[list["Filing"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    financial_facts: Mapped[list["FinancialFact"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    earnings_transcripts: Mapped[list["EarningsTranscript"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="company"
    )

    __table_args__ = (
        Index(
            "ix_companies_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<Company {self.ticker} ({self.cik})>"
