"""Pure parsing functions for USPTO PatentsView responses."""

from datetime import date, datetime
from typing import Any


def parse_patents(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse PatentsView search results into Patent-ready dicts.

    Skips entries missing patent_number.
    """
    patents = data.get("patents", [])
    results = []
    for entry in patents:
        patent_number = entry.get("patent_number")
        if not patent_number:
            continue

        # Extract first CPC class if available
        cpcs = entry.get("cpcs", [])
        cpc_class = cpcs[0].get("cpc_group_id") if cpcs else None

        # Citation count
        citation_count = entry.get("patent_num_us_patent_citations")
        if citation_count is not None:
            try:
                citation_count = int(citation_count)
            except (ValueError, TypeError):
                citation_count = None

        # Application filing date
        application = entry.get("application", {}) or {}
        application_date = _to_date(application.get("filing_date"))

        results.append(
            {
                "patent_number": str(patent_number),
                "title": str(entry.get("patent_title", ""))[:1000] or None,
                "grant_date": _to_date(entry.get("patent_date")),
                "application_date": application_date,
                "patent_type": entry.get("patent_type") or None,
                "cpc_class": str(cpc_class)[:20] if cpc_class else None,
                "citation_count": citation_count,
                "abstract": entry.get("patent_abstract") or None,
            }
        )
    return results


def _to_date(val: Any) -> date | None:
    """Parse a date string (YYYY-MM-DD) to date, returning None on failure."""
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
