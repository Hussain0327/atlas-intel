"""Market metric schemas."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class MarketMetricResponse(BaseModel):
    id: int
    period: str
    period_date: date
    market_cap: Decimal | None = None
    enterprise_value: Decimal | None = None
    pe_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    price_to_sales: Decimal | None = None
    ev_to_ebitda: Decimal | None = None
    ev_to_sales: Decimal | None = None
    earnings_yield: Decimal | None = None
    fcf_yield: Decimal | None = None
    revenue_per_share: Decimal | None = None
    net_income_per_share: Decimal | None = None
    book_value_per_share: Decimal | None = None
    fcf_per_share: Decimal | None = None
    dividend_per_share: Decimal | None = None
    roe: Decimal | None = None
    roic: Decimal | None = None
    debt_to_equity: Decimal | None = None
    debt_to_assets: Decimal | None = None
    current_ratio: Decimal | None = None
    interest_coverage: Decimal | None = None
    dividend_yield: Decimal | None = None
    payout_ratio: Decimal | None = None
    days_sales_outstanding: Decimal | None = None
    days_payables_outstanding: Decimal | None = None
    inventory_turnover: Decimal | None = None

    model_config = {"from_attributes": True}


class MetricCompareItem(BaseModel):
    ticker: str
    company_name: str
    sector: str | None = None
    value: Decimal | None = None
