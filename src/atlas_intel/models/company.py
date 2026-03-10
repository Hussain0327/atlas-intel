"""Company entity model."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    cik: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    ticker: Mapped[str | None] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(500))
    sic_code: Mapped[str | None] = mapped_column(String(10))
    sic_description: Mapped[str | None] = mapped_column(String(500))
    fiscal_year_end: Mapped[str | None] = mapped_column(String(4))  # MMDD
    exchange: Mapped[str | None] = mapped_column(String(50))
    entity_type: Mapped[str | None] = mapped_column(String(50))
    state_of_incorporation: Mapped[str | None] = mapped_column(String(10))
    ein: Mapped[str | None] = mapped_column(String(20))
    website: Mapped[str | None] = mapped_column(Text)

    # Profile fields (from FMP company profile)
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(100))
    currency: Mapped[str | None] = mapped_column(String(10))
    ceo: Mapped[str | None] = mapped_column(String(200))
    full_time_employees: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    ipo_date: Mapped[date | None] = mapped_column(Date)
    is_etf: Mapped[bool | None] = mapped_column(Boolean)
    is_actively_trading: Mapped[bool | None] = mapped_column(Boolean)
    beta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Sync timestamps
    submissions_synced_at: Mapped[datetime | None] = mapped_column()
    facts_synced_at: Mapped[datetime | None] = mapped_column()
    transcripts_synced_at: Mapped[datetime | None] = mapped_column()
    prices_synced_at: Mapped[datetime | None] = mapped_column()
    profile_synced_at: Mapped[datetime | None] = mapped_column()
    metrics_synced_at: Mapped[datetime | None] = mapped_column()
    news_synced_at: Mapped[datetime | None] = mapped_column()
    insider_trades_synced_at: Mapped[datetime | None] = mapped_column()
    analyst_estimates_synced_at: Mapped[datetime | None] = mapped_column()
    analyst_grades_synced_at: Mapped[datetime | None] = mapped_column()
    price_targets_synced_at: Mapped[datetime | None] = mapped_column()
    institutional_holdings_synced_at: Mapped[datetime | None] = mapped_column()
    material_events_synced_at: Mapped[datetime | None] = mapped_column()
    patents_synced_at: Mapped[datetime | None] = mapped_column()
    congress_trades_synced_at: Mapped[datetime | None] = mapped_column()

    filings: Mapped[list["Filing"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    financial_facts: Mapped[list["FinancialFact"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    earnings_transcripts: Mapped[list["EarningsTranscript"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="company"
    )
    stock_prices: Mapped[list["StockPrice"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    market_metrics: Mapped[list["MarketMetric"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    news_articles: Mapped[list["NewsArticle"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    insider_trades: Mapped[list["InsiderTrade"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    analyst_estimates: Mapped[list["AnalystEstimate"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    analyst_grades: Mapped[list["AnalystGrade"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    price_target: Mapped["PriceTarget | None"] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="company", uselist=False
    )
    institutional_holdings: Mapped[list["InstitutionalHolding"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="company"
    )
    material_events: Mapped[list["MaterialEvent"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    patents: Mapped[list["Patent"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    congress_trades: Mapped[list["CongressTrade"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821
    alert_rules: Mapped[list["AlertRule"]] = relationship(back_populates="company")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        Index(
            "ix_companies_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index("ix_companies_sector", "sector"),
        Index("ix_companies_industry", "industry"),
    )

    def __repr__(self) -> str:
        return f"<Company {self.ticker} ({self.cik})>"
