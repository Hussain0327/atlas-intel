"""Pure parsing functions for SEC 8-K material events."""

from datetime import date, datetime
from typing import Any

# SEC 8-K Item number → event type classification
ITEM_TYPE_MAP: dict[str, str] = {
    "1.01": "acquisition",
    "1.02": "bankruptcy",
    "2.01": "asset_acquisition",
    "2.02": "operating_results",
    "2.05": "cost_restructuring",
    "2.06": "impairment",
    "3.01": "delisting",
    "5.02": "officer_change",
    "5.03": "bylaw_amendment",
    "8.01": "other_event",
}


def classify_event_type(item_number: str | None) -> str:
    """Classify 8-K event type from item number."""
    if not item_number:
        return "other_event"
    # Normalize: strip whitespace, take first item if multiple
    item = item_number.strip().split(",")[0].strip()
    return ITEM_TYPE_MAP.get(item, "other_event")


def parse_8k_events(filings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse 8-K filing dicts from submissions data into MaterialEvent-ready dicts.

    Expects a list of dicts with keys: filingDate, accessionNumber, items, description.
    """
    results = []
    for filing in filings:
        filed_at = _to_date(filing.get("filingDate"))
        if filed_at is None:
            continue

        accession = filing.get("accessionNumber", "")
        description = filing.get("description", "")
        items = filing.get("items", "")

        filing_url = ""
        if accession:
            acc_no_dashes = accession.replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/{acc_no_dashes}/{accession}-index.htm"
            )

        # Split items string into individual item numbers (e.g. "5.02,9.01")
        item_list = [i.strip() for i in str(items).split(",") if i.strip()] if items else [""]

        for item_number in item_list:
            event_type = classify_event_type(item_number or None)
            results.append(
                {
                    "event_date": filed_at,
                    "event_type": event_type,
                    "item_number": item_number or None,
                    "description": description[:2000] if description else None,
                    "filing_url": filing_url or None,
                    "accession_number": accession or None,
                    "source": "sec_8k",
                }
            )
    return results


def _to_date(val: Any) -> date | None:
    """Parse a date string to date, returning None on failure."""
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
