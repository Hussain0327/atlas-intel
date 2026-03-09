"""Operational schemas for jobs and freshness visibility."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SyncJobResponse(BaseModel):
    id: int
    name: str
    sync_type: str
    tickers: list[str]
    interval_minutes: int
    years: int | None = None
    force: bool
    enabled: bool
    next_run_at: datetime
    last_run_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None

    model_config = {"from_attributes": True}


class SyncJobRunResponse(BaseModel):
    id: int
    job_id: int
    sync_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    requested_tickers: list[str]
    result_summary: dict[str, Any] | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class FreshnessDomainResponse(BaseModel):
    domain: str
    stale_count: int
    fresh_count: int
    max_age_minutes: int


class FreshnessSummaryResponse(BaseModel):
    generated_at: datetime
    total_companies: int
    domains: list[FreshnessDomainResponse] = Field(default_factory=list)
