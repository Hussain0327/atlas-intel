"""Transcript section model for structured earnings call segments."""

from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class TranscriptSection(TimestampMixin, Base):
    __tablename__ = "transcript_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    transcript_id: Mapped[int] = mapped_column(
        ForeignKey("earnings_transcripts.id", ondelete="CASCADE")
    )
    section_type: Mapped[str] = mapped_column(String(50))  # prepared_remarks / q_and_a / operator
    section_order: Mapped[int] = mapped_column(SmallInteger)
    speaker_name: Mapped[str | None] = mapped_column(String(200))
    speaker_title: Mapped[str | None] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)

    # Section-level sentiment
    sentiment_positive: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    sentiment_negative: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    sentiment_neutral: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    sentiment_label: Mapped[str | None] = mapped_column(String(20))

    # Relationships
    transcript: Mapped["EarningsTranscript"] = relationship(back_populates="sections")  # type: ignore[name-defined] # noqa: F821
    sentiments: Mapped[list["SentimentAnalysis"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="section", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_section_transcript", "transcript_id", "section_order"),)

    def __repr__(self) -> str:
        return f"<TranscriptSection {self.section_type} #{self.section_order}>"
