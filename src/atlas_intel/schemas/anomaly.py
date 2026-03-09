"""Anomaly detection response schemas."""

from datetime import date, datetime

from pydantic import BaseModel


class AnomalyPoint(BaseModel):
    anomaly_date: date | None = None
    value: float
    zscore: float
    description: str


class AnomalyCategory(BaseModel):
    category: str
    anomalies: list[AnomalyPoint] = []
    count: int = 0


class PriceAnomalyResponse(BaseModel):
    ticker: str
    lookback_days: int = 90
    threshold: float = 2.0
    volume_spikes: list[AnomalyPoint] = []
    return_spikes: list[AnomalyPoint] = []
    volatility_breakouts: list[AnomalyPoint] = []
    total_anomalies: int = 0
    computed_at: datetime | None = None


class FundamentalAnomalyResponse(BaseModel):
    ticker: str
    threshold: float = 2.0
    anomalies: list[AnomalyPoint] = []
    total_anomalies: int = 0
    computed_at: datetime | None = None


class ActivityAnomalyResponse(BaseModel):
    ticker: str
    lookback_days: int = 90
    threshold: float = 2.0
    insider_anomalies: list[AnomalyPoint] = []
    event_anomalies: list[AnomalyPoint] = []
    grade_anomalies: list[AnomalyPoint] = []
    total_anomalies: int = 0
    computed_at: datetime | None = None


class SectorAnomalyResponse(BaseModel):
    ticker: str
    sector: str | None = None
    threshold: float = 2.0
    peer_count: int = 0
    anomalies: list[AnomalyPoint] = []
    total_anomalies: int = 0
    computed_at: datetime | None = None


class AllAnomaliesResponse(BaseModel):
    ticker: str
    price: PriceAnomalyResponse | None = None
    fundamental: FundamentalAnomalyResponse | None = None
    activity: ActivityAnomalyResponse | None = None
    sector: SectorAnomalyResponse | None = None
    total_anomalies: int = 0
    computed_at: datetime | None = None
