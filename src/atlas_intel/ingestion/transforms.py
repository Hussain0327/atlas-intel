"""Data parsing and normalization for SEC EDGAR responses."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def parse_date(value: str | None) -> date | None:
    """Parse a date string (YYYY-MM-DD) into a date object."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_decimal(value: Any) -> Decimal | None:
    """Parse a numeric value into Decimal."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_accession_number(raw: str) -> str:
    """Normalize accession number format (remove dashes or add them)."""
    return raw.replace("-", "").strip() if raw else raw


def normalize_ticker(ticker: str | None) -> str | None:
    """Normalize ticker symbol to uppercase."""
    if not ticker:
        return None
    return ticker.upper().strip()


def parse_company_tickers(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse SEC company_tickers.json into list of company dicts.

    Input format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    """
    results = []
    for entry in data.values():
        cik = entry.get("cik_str")
        ticker = entry.get("ticker")
        name = entry.get("title")
        if cik and name:
            results.append(
                {
                    "cik": int(cik),
                    "ticker": normalize_ticker(ticker),
                    "name": name,
                }
            )
    return results


def parse_submissions(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse SEC submissions JSON into company metadata and filing records.

    Returns (company_info, filings_list).
    """
    company_info: dict[str, Any] = {
        "name": data.get("name"),
        "sic_code": data.get("sic"),
        "sic_description": data.get("sicDescription"),
        "fiscal_year_end": data.get("fiscalYearEnd"),
        "exchange": data.get("exchanges", [None])[0] if data.get("exchanges") else None,
        "entity_type": data.get("entityType"),
        "state_of_incorporation": data.get("stateOfIncorporation"),
        "ein": data.get("ein"),
        "website": (
            (data.get("website") or [None])[0]
            if isinstance(data.get("website"), list)
            else data.get("website")
        ),
    }

    filings: list[dict[str, Any]] = []
    recent = data.get("filings", {}).get("recent", {})
    if not recent:
        return company_info, filings

    accession_numbers = recent.get("accessionNumber", [])
    form_types = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    periods = recent.get("reportDate", [])
    primary_docs = recent.get("primaryDocument", [])
    is_xbrls = recent.get("isXBRL", [])

    for i in range(len(accession_numbers)):
        accession = parse_accession_number(accession_numbers[i])
        form_type = form_types[i] if i < len(form_types) else None
        filing_date = parse_date(filing_dates[i] if i < len(filing_dates) else None)

        if not accession or not form_type or not filing_date:
            continue

        period = parse_date(periods[i] if i < len(periods) else None)
        primary_doc = primary_docs[i] if i < len(primary_docs) else None
        is_xbrl = bool(is_xbrls[i]) if i < len(is_xbrls) else None

        cik = str(data.get("cik", "")).zfill(10)
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{primary_doc}"
            if primary_doc
            else None
        )

        filings.append(
            {
                "accession_number": accession,
                "form_type": form_type,
                "filing_date": filing_date,
                "period_of_report": period,
                "primary_document": primary_doc,
                "is_xbrl": is_xbrl,
                "filing_url": filing_url,
            }
        )

    return company_info, filings


def parse_company_facts(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse SEC company facts XBRL JSON into flat fact records.

    Input structure: facts.[taxonomy].[concept].units.[unit] -> [{val, end, start?, ...}]
    """
    facts_list = []
    facts = data.get("facts", {})

    for taxonomy, concepts in facts.items():
        for concept, concept_data in concepts.items():
            units = concept_data.get("units", {})
            for unit, entries in units.items():
                for entry in entries:
                    val = parse_decimal(entry.get("val"))
                    if val is None:
                        continue

                    end_date = parse_date(entry.get("end"))
                    if not end_date:
                        continue

                    start_date = parse_date(entry.get("start"))
                    is_instant = start_date is None
                    filed_date = parse_date(entry.get("filed"))
                    accession = parse_accession_number(entry.get("accn", ""))
                    fiscal_year = entry.get("fy")
                    fiscal_period = entry.get("fp")
                    form_type = entry.get("form")

                    facts_list.append(
                        {
                            "taxonomy": taxonomy,
                            "concept": concept,
                            "value": val,
                            "unit": unit,
                            "period_start": start_date,
                            "period_end": end_date,
                            "is_instant": is_instant,
                            "fiscal_year": int(fiscal_year) if fiscal_year else None,
                            "fiscal_period": fiscal_period,
                            "form_type": form_type,
                            "accession_number": accession if accession else None,
                            "filed_date": filed_date,
                        }
                    )

    return facts_list
