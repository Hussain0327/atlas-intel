"""Alert rule and event schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AlertRuleCreate(BaseModel):
    company_id: int | None = None
    name: str = Field(max_length=200)
    rule_type: str = Field(
        pattern=r"^(price_threshold|volume_spike|signal_drop|anomaly_detected|freshness_stale|metric_threshold)$"
    )
    conditions: dict[str, Any]
    enabled: bool = True
    cooldown_minutes: int = Field(default=60, ge=1, le=1440)


class AlertRuleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    conditions: dict[str, Any] | None = None
    enabled: bool | None = None
    cooldown_minutes: int | None = Field(default=None, ge=1, le=1440)


class AlertRuleResponse(BaseModel):
    id: int
    company_id: int | None = None
    name: str
    rule_type: str
    conditions: dict[str, Any]
    enabled: bool
    cooldown_minutes: int
    last_triggered_at: datetime | None = None
    trigger_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertEventResponse(BaseModel):
    id: int
    rule_id: int
    company_id: int | None = None
    triggered_at: datetime
    rule_type: str
    severity: str
    title: str
    detail: str | None = None
    data: dict[str, Any] | None = None
    acknowledged: bool = False
    acknowledged_at: datetime | None = None

    model_config = {"from_attributes": True}


class AlertEventListResponse(BaseModel):
    items: list[AlertEventResponse]
    total: int
    unacknowledged: int
