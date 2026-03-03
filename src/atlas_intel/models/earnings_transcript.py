"""Earnings call transcript model."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class EarningsTranscript(TimestampMixin, Base):
    __tablename__ = "earnings_transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    quarter: Mapped[int] = mapped_column(SmallInteger)
    year: Mapped[int]
    transcript_date: Mapped[date]
    raw_text: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(500))

    # Aggregate sentiment scores
    sentiment_positive: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    sentiment_negative: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    sentiment_neutral: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    sentiment_label: Mapped[str | None] = mapped_column(String(20))

    # Sync tracking
    nlp_processed_at: Mapped[datetime | None] = mapped_column()

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="earnings_transcripts")  # type: ignore[name-defined] # noqa: F821
    sections: Mapped[list["TranscriptSection"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="transcript", cascade="all, delete-orphan"
    )
    keywords: Mapped[list["KeywordExtraction"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="transcript", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("company_id", "quarter", "year", name="uq_transcript_company_quarter"),
        Index("ix_transcript_company_date", "company_id", "transcript_date"),
        Index("ix_transcript_company_year_quarter", "company_id", "year", "quarter"),
    )

    def __repr__(self) -> str:
        return f"<EarningsTranscript Q{self.quarter} {self.year}>"
