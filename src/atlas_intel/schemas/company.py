"""Company schemas."""

from datetime import datetime

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
    submissions_synced_at: datetime | None = None
    facts_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanySummary(CompanyBase):
    id: int
    exchange: str | None = None
    sic_code: str | None = None

    model_config = {"from_attributes": True}
