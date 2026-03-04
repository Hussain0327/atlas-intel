"""Company schemas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class CompanyBase(BaseModel):
    cik: int
    ticker: str | None = None
    name: str


class CompanyDetail(CompanyBase):
    id: int
    sic_code: str | None = None
    sic_description: str | None = None
    fiscal_year_end: str | None = None
    exchange: str | None = None
    entity_type: str | None = None
    state_of_incorporation: str | None = None
    ein: str | None = None
    website: str | None = None
    # Profile fields
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    currency: str | None = None
    ceo: str | None = None
    full_time_employees: int | None = None
    description: str | None = None
    ipo_date: date | None = None
    is_etf: bool | None = None
    is_actively_trading: bool | None = None
    beta: Decimal | None = None
    # Sync timestamps
    submissions_synced_at: datetime | None = None
    facts_synced_at: datetime | None = None
    transcripts_synced_at: datetime | None = None
    prices_synced_at: datetime | None = None
    profile_synced_at: datetime | None = None
    metrics_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanySummary(CompanyBase):
    id: int
    exchange: str | None = None
    sic_code: str | None = None
    sector: str | None = None
    industry: str | None = None

    model_config = {"from_attributes": True}
