"""Price target consensus model."""

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class PriceTarget(TimestampMixin, Base):
    __tablename__ = "price_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    target_high: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    target_low: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    target_consensus: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    target_median: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))

    company: Mapped["Company"] = relationship(back_populates="price_target")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (UniqueConstraint("company_id", name="uq_price_target_company"),)

    def __repr__(self) -> str:
        return f"<PriceTarget consensus={self.target_consensus}>"
