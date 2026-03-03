"""Keyword extraction results from earnings transcripts."""

from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class KeywordExtraction(TimestampMixin, Base):
    __tablename__ = "keyword_extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    transcript_id: Mapped[int] = mapped_column(
        ForeignKey("earnings_transcripts.id", ondelete="CASCADE")
    )
    keyword: Mapped[str] = mapped_column(String(200))
    relevance_score: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    frequency: Mapped[int] = mapped_column(SmallInteger, default=1)

    # Relationships
    transcript: Mapped["EarningsTranscript"] = relationship(back_populates="keywords")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        Index("ix_keyword_transcript", "transcript_id"),
        Index("ix_keyword_keyword", "keyword"),
    )

    def __repr__(self) -> str:
        return f"<KeywordExtraction '{self.keyword}' ({self.relevance_score})>"
