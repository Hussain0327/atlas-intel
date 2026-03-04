"""Stock price schemas."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class StockPriceResponse(BaseModel):
    id: int
    price_date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    adj_close: Decimal | None = None
    volume: int | None = None
    vwap: Decimal | None = None
    change_percent: Decimal | None = None

    model_config = {"from_attributes": True}


class DailyReturnResponse(BaseModel):
    price_date: date
    close: Decimal
    daily_return: float | None = None


class PriceAnalyticsResponse(BaseModel):
    ticker: str
    latest_close: Decimal | None = None
    latest_date: date | None = None
    daily_return_pct: float | None = None
    weekly_return_pct: float | None = None
    monthly_return_pct: float | None = None
    ytd_return_pct: float | None = None
    volatility_30d: float | None = None
    volatility_90d: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    high_52w: Decimal | None = None
    low_52w: Decimal | None = None
    avg_volume_30d: float | None = None
