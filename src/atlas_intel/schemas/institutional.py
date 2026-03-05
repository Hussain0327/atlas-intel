"""Institutional holdings schemas."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class InstitutionalHoldingResponse(BaseModel):
    id: int
    holder: str
    shares: int | None = None
    date_reported: date
    change: int | None = None
    change_percentage: Decimal | None = None
    market_value: Decimal | None = None
    portfolio_percent: Decimal | None = None

    model_config = {"from_attributes": True}
