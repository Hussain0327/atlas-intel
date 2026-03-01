"""SEC filing metadata model."""

from datetime import date

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class Filing(TimestampMixin, Base):
    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    accession_number: Mapped[str] = mapped_column(String(30), unique=True)
    form_type: Mapped[str] = mapped_column(String(20))
    filing_date: Mapped[date]
    period_of_report: Mapped[date | None]
    primary_document: Mapped[str | None] = mapped_column(Text)
    is_xbrl: Mapped[bool | None]
    filing_url: Mapped[str | None] = mapped_column(Text)

    company: Mapped["Company"] = relationship(back_populates="filings")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        Index("ix_filings_company_form", "company_id", "form_type"),
        Index("ix_filings_company_date", "company_id", "filing_date"),
        Index("ix_filings_company_period", "company_id", "period_of_report"),
    )

    def __repr__(self) -> str:
        return f"<Filing {self.accession_number} ({self.form_type})>"
