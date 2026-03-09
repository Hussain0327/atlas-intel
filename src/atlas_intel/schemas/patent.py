"""Patent schemas."""

from datetime import date

from pydantic import BaseModel


class PatentResponse(BaseModel):
    id: int
    patent_number: str
    title: str | None = None
    grant_date: date | None = None
    application_date: date | None = None
    patent_type: str | None = None
    cpc_class: str | None = None
    citation_count: int | None = None
    abstract: str | None = None

    model_config = {"from_attributes": True}


class CpcClassCount(BaseModel):
    cpc_class: str
    count: int


class InnovationSummaryResponse(BaseModel):
    ticker: str
    total_patents: int = 0
    patents_12m: int = 0
    patents_prior_12m: int = 0
    velocity_change_pct: float | None = None
    top_cpc_classes: list[CpcClassCount] = []
