"""Stock screening request/response schemas."""

from pydantic import BaseModel


class ScreenFilter(BaseModel):
    field: str  # "pe_ratio", "roe", "sector", etc.
    op: str = "eq"  # "gt", "gte", "lt", "lte", "eq", "between", "in"
    value: float | str | None = None
    value_high: float | None = None  # for "between"
    values: list[str] | None = None  # for "in"


class SignalFilter(BaseModel):
    signal_type: str  # "sentiment", "growth", "risk", "smart_money"
    op: str = "gt"
    value: float = 0.0


class ScreenRequest(BaseModel):
    metric_filters: list[ScreenFilter] = []
    company_filters: list[ScreenFilter] = []
    signal_filters: list[SignalFilter] = []
    sort_by: str = "market_cap"
    sort_order: str = "desc"
    offset: int = 0
    limit: int = 50


class ScreenResult(BaseModel):
    ticker: str
    name: str
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ev_to_ebitda: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    dividend_yield: float | None = None
    fcf_yield: float | None = None
    signal_scores: dict[str, float | None] | None = None


class ScreenResponse(BaseModel):
    items: list[ScreenResult]
    total: int
    offset: int
    limit: int
    filters_applied: int


class ScreeningStatsResponse(BaseModel):
    total_companies: int = 0
    companies_with_metrics: int = 0
    sectors: list[str] = []
    industries: list[str] = []
