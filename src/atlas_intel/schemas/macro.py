"""Macro indicator schemas."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class MacroIndicatorResponse(BaseModel):
    id: int
    series_id: str
    observation_date: date
    value: Decimal | None = None

    model_config = {"from_attributes": True}


class MacroSeriesLatest(BaseModel):
    series_id: str
    latest_value: Decimal | None = None
    latest_date: date | None = None
    observation_count: int = 0


class MacroSummaryResponse(BaseModel):
    series: list[MacroSeriesLatest] = []
