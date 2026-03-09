"""Macro economic indicator model (FRED data)."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from atlas_intel.models.base import Base, TimestampMixin


class MacroIndicator(TimestampMixin, Base):
    __tablename__ = "macro_indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(20))
    observation_date: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))

    __table_args__ = (
        UniqueConstraint("series_id", "observation_date", name="uq_macro_indicator_series_date"),
        Index("ix_macro_indicators_series_date", "series_id", "observation_date"),
    )

    def __repr__(self) -> str:
        return f"<MacroIndicator {self.series_id} {self.observation_date}>"
