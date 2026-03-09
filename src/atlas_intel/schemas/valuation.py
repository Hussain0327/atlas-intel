"""Valuation response schemas."""

from datetime import datetime

from pydantic import BaseModel


class DCFScenario(BaseModel):
    label: str  # "bear", "base", "bull"
    growth_rate: float
    discount_rate: float
    intrinsic_value_per_share: float
    upside_pct: float | None = None
    projected_fcfs: list[float]
    terminal_value: float


class DCFResponse(BaseModel):
    ticker: str
    current_price: float | None = None
    shares_outstanding: float | None = None
    latest_fcf: float | None = None
    historical_fcf_growth: float | None = None
    risk_free_rate: float | None = None
    beta: float | None = None
    wacc: float | None = None
    scenarios: list[DCFScenario] = []
    data_quality: str = "insufficient"  # "insufficient" | "limited" | "good"
    missing_inputs: list[str] = []
    computed_at: datetime | None = None


class MultipleBenchmark(BaseModel):
    metric_name: str
    company_value: float | None = None
    sector_median: float | None = None
    sector_mean: float | None = None
    peer_count: int = 0
    premium_pct: float | None = None
    assessment: str = "unavailable"  # "discount" | "fair" | "premium"


class RelativeValuationResponse(BaseModel):
    ticker: str
    sector: str | None = None
    peer_count: int = 0
    multiples: list[MultipleBenchmark] = []
    composite_premium_pct: float | None = None
    assessment: str = "unavailable"  # "undervalued" | "fairly_valued" | "overvalued"
    computed_at: datetime | None = None


class AnalystValuationResponse(BaseModel):
    ticker: str
    current_price: float | None = None
    target_consensus: float | None = None
    target_high: float | None = None
    target_low: float | None = None
    upside_pct: float | None = None
    downside_risk_pct: float | None = None
    upside_potential_pct: float | None = None
    analyst_count: int | None = None
    computed_at: datetime | None = None


class FullValuationResponse(BaseModel):
    ticker: str
    dcf: DCFResponse | None = None
    relative: RelativeValuationResponse | None = None
    analyst: AnalystValuationResponse | None = None
    composite_assessment: str = "unavailable"
    computed_at: datetime | None = None
