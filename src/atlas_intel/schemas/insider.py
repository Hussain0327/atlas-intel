"""Insider trading schemas."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class InsiderTradeResponse(BaseModel):
    id: int
    filing_date: date
    transaction_date: date | None = None
    reporting_name: str
    reporting_cik: str | None = None
    transaction_type: str | None = None
    securities_transacted: Decimal | None = None
    price: Decimal | None = None
    securities_owned: Decimal | None = None
    owner_type: str | None = None

    model_config = {"from_attributes": True}


class InsiderSentimentResponse(BaseModel):
    ticker: str
    days: int
    buy_count: int = 0
    sell_count: int = 0
    total_buy_value: float | None = None
    total_sell_value: float | None = None
    net_ratio: float | None = None
    sentiment: str = "neutral"
    top_buyers: list[dict[str, object]] = []
    top_sellers: list[dict[str, object]] = []

    model_config = {"from_attributes": True}
