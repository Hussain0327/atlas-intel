"""Analyst estimate, grade, and price target schemas."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class AnalystEstimateResponse(BaseModel):
    id: int
    period: str
    estimate_date: date
    estimated_revenue_avg: Decimal | None = None
    estimated_revenue_high: Decimal | None = None
    estimated_revenue_low: Decimal | None = None
    estimated_eps_avg: Decimal | None = None
    estimated_eps_high: Decimal | None = None
    estimated_eps_low: Decimal | None = None
    estimated_ebitda_avg: Decimal | None = None
    estimated_ebitda_high: Decimal | None = None
    estimated_ebitda_low: Decimal | None = None
    number_analysts_revenue: int | None = None
    number_analysts_eps: int | None = None

    model_config = {"from_attributes": True}


class AnalystGradeResponse(BaseModel):
    id: int
    grade_date: date
    grading_company: str
    previous_grade: str | None = None
    new_grade: str
    action: str | None = None

    model_config = {"from_attributes": True}


class PriceTargetResponse(BaseModel):
    id: int
    target_high: Decimal | None = None
    target_low: Decimal | None = None
    target_consensus: Decimal | None = None
    target_median: Decimal | None = None

    model_config = {"from_attributes": True}


class AnalystConsensusResponse(BaseModel):
    ticker: str
    target_consensus: Decimal | None = None
    target_high: Decimal | None = None
    target_low: Decimal | None = None
    current_price: Decimal | None = None
    upside_pct: float | None = None
    latest_eps_estimate: Decimal | None = None
    latest_revenue_estimate: Decimal | None = None
    grade_distribution: dict[str, int] = {}
    sentiment: str = "neutral"

    model_config = {"from_attributes": True}
