"""Material event model (SEC 8-K filings)."""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class MaterialEvent(TimestampMixin, Base):
    __tablename__ = "material_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    event_date: Mapped[date] = mapped_column(Date)
    event_type: Mapped[str] = mapped_column(String(50))
    item_number: Mapped[str | None] = mapped_column(String(10))
    description: Mapped[str | None] = mapped_column(Text)
    filing_url: Mapped[str | None] = mapped_column(Text)
    accession_number: Mapped[str | None] = mapped_column(String(30))
    source: Mapped[str | None] = mapped_column(String(50), default="sec_8k")

    company: Mapped["Company"] = relationship(back_populates="material_events")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "company_id", "accession_number", "item_number", name="uq_material_event_dedup"
        ),
        Index("ix_material_events_company_date", "company_id", "event_date"),
        Index("ix_material_events_event_type", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<MaterialEvent {self.event_type} {self.event_date}>"
