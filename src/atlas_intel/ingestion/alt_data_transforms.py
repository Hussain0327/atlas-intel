"""Pure parsing functions for FMP alternative data responses."""

from datetime import datetime
from typing import Any

from atlas_intel.ingestion.market_transforms import _to_date, _to_decimal


def _parse_datetime(val: Any) -> datetime | None:
    """Parse a datetime string to naive datetime, returning None on failure."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=None)
    try:
        # FMP uses "2024-01-25 17:00:00" format
        return datetime.strptime(str(val)[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        # Fallback: try date-only
        try:
            return datetime.strptime(str(val)[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return None


def parse_news_articles(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse FMP news response into NewsArticle-ready dicts.

    Skips entries missing title or url.
    """
    results = []
    for entry in data:
        title = entry.get("title")
        url = entry.get("url")
        if not title or not url:
            continue

        published_at = _parse_datetime(entry.get("publishedDate"))
        if published_at is None:
            continue

        results.append(
            {
                "title": str(title)[:1000],
                "snippet": entry.get("text") or None,
                "url": str(url),
                "source_name": entry.get("site") or None,
                "image_url": entry.get("image") or None,
                "published_at": published_at,
            }
        )
    return results


def parse_insider_trades(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse FMP insider trading response into InsiderTrade-ready dicts.

    Skips entries missing filingDate or reportingName.
    """
    results = []
    for entry in data:
        filing_date = _to_date(entry.get("filingDate"))
        reporting_name = entry.get("reportingName")
        if filing_date is None or not reporting_name:
            continue

        results.append(
            {
                "filing_date": filing_date,
                "transaction_date": _to_date(entry.get("transactionDate")),
                "reporting_name": str(reporting_name),
                "reporting_cik": str(entry["reportingCik"]) if entry.get("reportingCik") else None,
                "transaction_type": entry.get("transactionType") or None,
                "securities_transacted": _to_decimal(entry.get("securitiesTransacted")),
                "price": _to_decimal(entry.get("price")),
                "securities_owned": _to_decimal(entry.get("securitiesOwned")),
                "owner_type": entry.get("typeOfOwner") or None,
            }
        )
    return results


def parse_analyst_estimates(data: list[dict[str, Any]], period_type: str) -> list[dict[str, Any]]:
    """Parse FMP analyst estimates response into AnalystEstimate-ready dicts.

    Skips entries missing date. Injects the `period` field.
    """
    results = []
    for entry in data:
        estimate_date = _to_date(entry.get("date"))
        if estimate_date is None:
            continue

        results.append(
            {
                "period": period_type,
                "estimate_date": estimate_date,
                "estimated_revenue_avg": _to_decimal(entry.get("estimatedRevenueAvg")),
                "estimated_revenue_high": _to_decimal(entry.get("estimatedRevenueHigh")),
                "estimated_revenue_low": _to_decimal(entry.get("estimatedRevenueLow")),
                "estimated_eps_avg": _to_decimal(entry.get("estimatedEpsAvg")),
                "estimated_eps_high": _to_decimal(entry.get("estimatedEpsHigh")),
                "estimated_eps_low": _to_decimal(entry.get("estimatedEpsLow")),
                "estimated_ebitda_avg": _to_decimal(entry.get("estimatedEbitdaAvg")),
                "estimated_ebitda_high": _to_decimal(entry.get("estimatedEbitdaHigh")),
                "estimated_ebitda_low": _to_decimal(entry.get("estimatedEbitdaLow")),
                "number_analysts_revenue": entry.get("numberAnalystsEstimatedRevenue"),
                "number_analysts_eps": entry.get("numberAnalystEstimatedEps"),
            }
        )
    return results


def parse_price_target_consensus(data: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Parse FMP price target consensus response.

    Returns a single dict or None if empty.
    """
    if not data:
        return None

    entry = data[0]
    return {
        "target_high": _to_decimal(entry.get("targetHigh")),
        "target_low": _to_decimal(entry.get("targetLow")),
        "target_consensus": _to_decimal(entry.get("targetConsensus")),
        "target_median": _to_decimal(entry.get("targetMedian")),
    }


def parse_analyst_grades(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse FMP analyst grades response into AnalystGrade-ready dicts.

    Skips entries missing grade_date, grading_company, or new_grade.
    """
    results = []
    for entry in data:
        grade_date = _to_date(entry.get("date"))
        grading_company = entry.get("gradingCompany")
        new_grade = entry.get("newGrade")
        if grade_date is None or not grading_company or not new_grade:
            continue

        results.append(
            {
                "grade_date": grade_date,
                "grading_company": str(grading_company),
                "previous_grade": entry.get("previousGrade") or None,
                "new_grade": str(new_grade),
                "action": entry.get("action") or None,
            }
        )
    return results


def parse_institutional_holdings(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse FMP institutional holdings response into InstitutionalHolding-ready dicts.

    Skips entries missing holder or dateReported.
    """
    results = []
    for entry in data:
        holder = entry.get("holder")
        date_reported = _to_date(entry.get("dateReported"))
        if not holder or date_reported is None:
            continue

        shares = entry.get("shares")
        if shares is not None:
            try:
                shares = int(shares)
            except (ValueError, TypeError):
                shares = None

        change = entry.get("change")
        if change is not None:
            try:
                change = int(change)
            except (ValueError, TypeError):
                change = None

        results.append(
            {
                "holder": str(holder),
                "shares": shares,
                "date_reported": date_reported,
                "change": change,
                "change_percentage": _to_decimal(entry.get("changePercentage")),
                "market_value": _to_decimal(entry.get("marketValue")),
                "portfolio_percent": _to_decimal(entry.get("portfolioPercent")),
            }
        )
    return results
