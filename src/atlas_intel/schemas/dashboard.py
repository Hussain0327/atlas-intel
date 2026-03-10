"""Dashboard response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SectorSummary(BaseModel):
    sector: str
    company_count: int = 0
    avg_pe: float | None = None
    avg_roe: float | None = None
    total_market_cap: float | None = None


class MarketOverview(BaseModel):
    total_companies: int = 0
    companies_with_prices: int = 0
    companies_with_sec_data: int = 0
    sectors: list[SectorSummary] = []
    computed_at: datetime | None = None


class TopMover(BaseModel):
    ticker: str
    name: str
    value: float
    change_pct: float | None = None


class TopMoversResponse(BaseModel):
    gainers: list[TopMover] = []
    losers: list[TopMover] = []
    volume_leaders: list[TopMover] = []
    lookback_days: int = 1
    computed_at: datetime | None = None


class AlertSummaryResponse(BaseModel):
    total_rules: int = 0
    active_rules: int = 0
    total_events_24h: int = 0
    total_events_7d: int = 0
    critical_events_24h: int = 0
    recent_events: list[dict[str, Any]] = []
    computed_at: datetime | None = None


class DashboardResponse(BaseModel):
    market_overview: MarketOverview
    top_movers: TopMoversResponse
    alert_summary: AlertSummaryResponse
    computed_at: datetime | None = None
