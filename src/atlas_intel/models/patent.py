"""Patent model (USPTO PatentsView data)."""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class Patent(TimestampMixin, Base):
    __tablename__ = "patents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    patent_number: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(1000))
    grant_date: Mapped[date | None] = mapped_column(Date)
    application_date: Mapped[date | None] = mapped_column(Date)
    patent_type: Mapped[str | None] = mapped_column(String(50))
    cpc_class: Mapped[str | None] = mapped_column(String(20))
    citation_count: Mapped[int | None] = mapped_column(Integer)
    abstract: Mapped[str | None] = mapped_column(Text)

    company: Mapped["Company"] = relationship(back_populates="patents")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        UniqueConstraint("company_id", "patent_number", name="uq_patent_company_number"),
        Index("ix_patents_company_grant_date", "company_id", "grant_date"),
        Index("ix_patents_company_cpc_class", "company_id", "cpc_class"),
    )

    def __repr__(self) -> str:
        return f"<Patent {self.patent_number} {self.title[:50] if self.title else ''}>"
