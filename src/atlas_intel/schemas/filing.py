"""Filing schemas."""

from datetime import date, datetime

from pydantic import BaseModel


class FilingResponse(BaseModel):
    id: int
    company_id: int
    accession_number: str
    form_type: str
    filing_date: date
    period_of_report: date | None = None
    primary_document: str | None = None
    is_xbrl: bool | None = None
    filing_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
