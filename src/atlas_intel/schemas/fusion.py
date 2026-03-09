"""Fusion signal schemas."""

from datetime import datetime

from pydantic import BaseModel


class SignalComponent(BaseModel):
    name: str
    score: float | None = None
    weight: float = 0.0
    has_data: bool = False


class SignalResponse(BaseModel):
    signal_type: str
    score: float | None = None
    label: str = "unavailable"
    confidence: float = 0.0
    components: list[SignalComponent] = []
    computed_at: datetime | None = None


class AllSignalsResponse(BaseModel):
    ticker: str
    sentiment: SignalResponse | None = None
    growth: SignalResponse | None = None
    risk: SignalResponse | None = None
    smart_money: SignalResponse | None = None
