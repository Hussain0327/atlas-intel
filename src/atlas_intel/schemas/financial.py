"""Financial fact schemas."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class FinancialFactResponse(BaseModel):
    id: int
    company_id: int
    taxonomy: str
    concept: str
    value: Decimal
    unit: str
    period_start: date | None = None
    period_end: date
    is_instant: bool
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    form_type: str | None = None
    accession_number: str | None = None
    filed_date: date | None = None

    model_config = {"from_attributes": True}


class FinancialSummaryItem(BaseModel):
    concept: str
    values: list["FiscalYearValue"]


class FiscalYearValue(BaseModel):
    fiscal_year: int
    fiscal_period: str
    value: Decimal
    unit: str
    period_end: date


class CompareItem(BaseModel):
    ticker: str
    company_name: str
    values: list[FiscalYearValue]
