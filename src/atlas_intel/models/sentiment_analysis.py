"""Sentence-level sentiment analysis results."""

from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class SentimentAnalysis(TimestampMixin, Base):
    __tablename__ = "sentiment_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("transcript_sections.id", ondelete="CASCADE")
    )
    sentence_index: Mapped[int] = mapped_column(SmallInteger)
    sentence_text: Mapped[str] = mapped_column(Text)
    positive: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    negative: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    neutral: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    label: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4))

    # Relationships
    section: Mapped["TranscriptSection"] = relationship(back_populates="sentiments")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (Index("ix_sentiment_section", "section_id", "sentence_index"),)

    def __repr__(self) -> str:
        return f"<SentimentAnalysis {self.label} ({self.confidence})>"
