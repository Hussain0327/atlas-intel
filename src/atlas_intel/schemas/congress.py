"""Congress trading schemas."""

from datetime import date

from pydantic import BaseModel


class CongressTradeResponse(BaseModel):
    id: int
    representative: str
    party: str | None = None
    chamber: str | None = None
    transaction_date: date
    disclosure_date: date | None = None
    transaction_type: str | None = None
    amount_range: str | None = None
    asset_description: str | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class TraderSummary(BaseModel):
    representative: str
    trade_count: int


class CongressSummaryResponse(BaseModel):
    ticker: str
    total_trades: int = 0
    purchases: int = 0
    sales: int = 0
    democrat_trades: int = 0
    republican_trades: int = 0
    top_traders: list[TraderSummary] = []
