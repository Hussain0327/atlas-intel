"""Analyst grade (upgrade/downgrade) model."""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class AnalystGrade(TimestampMixin, Base):
    __tablename__ = "analyst_grades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    grade_date: Mapped[date] = mapped_column(Date)
    grading_company: Mapped[str] = mapped_column(String(200))
    previous_grade: Mapped[str | None] = mapped_column(String(50))
    new_grade: Mapped[str] = mapped_column(String(50))
    action: Mapped[str | None] = mapped_column(String(50))

    company: Mapped["Company"] = relationship(back_populates="analyst_grades")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "grade_date",
            "grading_company",
            "new_grade",
            name="uq_analyst_grade_dedup",
        ),
        Index("ix_analyst_grades_company_date", "company_id", "grade_date"),
        Index("ix_analyst_grades_company_action", "company_id", "action"),
    )

    def __repr__(self) -> str:
        return f"<AnalystGrade {self.grade_date} {self.grading_company} {self.action}>"
