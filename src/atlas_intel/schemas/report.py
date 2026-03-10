"""Report and query request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CompanyContext(BaseModel):
    ticker: str
    name: str
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    exchange: str | None = None
    ceo: str | None = None
    employees: int | None = None
    description: str | None = None
    profile: dict[str, Any] = {}
    financials: list[dict[str, Any]] = []
    price_analytics: dict[str, Any] = {}
    valuation: dict[str, Any] = {}
    signals: dict[str, Any] = {}
    anomalies: dict[str, Any] = {}
    sentiment_trend: list[dict[str, Any]] = []
    recent_news: list[dict[str, Any]] = []
    insider_sentiment: dict[str, Any] = {}
    macro_summary: dict[str, Any] = {}


class SectorContext(BaseModel):
    sector: str
    companies: list[dict[str, Any]] = []
    screen_results: list[dict[str, Any]] = []
    stats: dict[str, Any] = {}


class ReportRequest(BaseModel):
    report_type: str = Field(default="comprehensive", pattern=r"^(comprehensive|quick)$")


class ComparisonRequest(BaseModel):
    tickers: list[str] = Field(min_length=2, max_length=5)
    model_config = {"json_schema_extra": {"examples": [{"tickers": ["AAPL", "MSFT", "GOOGL"]}]}}


class ReportResponse(BaseModel):
    ticker: str | None = None
    report_type: str
    content: str
    data_context: dict[str, Any] = {}
    generated_at: datetime | None = None


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class QueryResponse(BaseModel):
    query: str
    answer: str
    tools_used: list[str] = []
    generated_at: datetime | None = None
