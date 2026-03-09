"""Material event schemas."""

from datetime import date

from pydantic import BaseModel


class MaterialEventResponse(BaseModel):
    id: int
    event_date: date
    event_type: str
    item_number: str | None = None
    description: str | None = None
    filing_url: str | None = None
    accession_number: str | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class EventTypeSummary(BaseModel):
    event_type: str
    count: int


class EventSummaryResponse(BaseModel):
    ticker: str
    total_events: int = 0
    events_90d: int = 0
    events_365d: int = 0
    by_type: list[EventTypeSummary] = []
