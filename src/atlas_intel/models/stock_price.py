"""Daily stock price OHLCV model."""

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class StockPrice(TimestampMixin, Base):
    __tablename__ = "stock_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    price_date: Mapped[date] = mapped_column(Date)
    open: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    high: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    low: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    close: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    change_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    company: Mapped["Company"] = relationship(back_populates="stock_prices")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        UniqueConstraint("company_id", "price_date", name="uq_stock_price_company_date"),
        Index("ix_stock_prices_company_date", "company_id", "price_date"),
        Index("ix_stock_prices_date", "price_date"),
    )

    def __repr__(self) -> str:
        return f"<StockPrice {self.price_date} close={self.close}>"
