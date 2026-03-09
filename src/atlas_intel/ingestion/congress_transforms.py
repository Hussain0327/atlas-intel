"""Pure parsing functions for congressional trading data."""

from datetime import date, datetime
from typing import Any


def parse_congress_trades(
    senate_data: list[dict[str, Any]],
    house_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse FMP senate/house trading responses into CongressTrade-ready dicts.

    Combines both chambers into a single list.
    Skips entries missing representative or transaction_date.
    """
    results = []

    for entry in senate_data:
        parsed = _parse_single_trade(entry, chamber="Senate")
        if parsed:
            results.append(parsed)

    for entry in house_data:
        parsed = _parse_single_trade(entry, chamber="House")
        if parsed:
            results.append(parsed)

    return results


def _parse_single_trade(entry: dict[str, Any], chamber: str) -> dict[str, Any] | None:
    """Parse a single congress trade entry."""
    # FMP uses different field names for senate vs house
    representative = (entry.get("firstName", "") + " " + entry.get("lastName", "")).strip()
    if not representative or representative == " ":
        representative = entry.get("representative") or entry.get("name")
    if not representative:
        return None

    transaction_date = _to_date(entry.get("transactionDate") or entry.get("transactDate"))
    if transaction_date is None:
        return None

    # Normalize transaction type
    raw_type = entry.get("type") or entry.get("transactionType") or ""
    transaction_type = _normalize_transaction_type(raw_type)

    return {
        "representative": str(representative)[:200],
        "party": entry.get("party") or None,
        "chamber": chamber,
        "transaction_date": transaction_date,
        "disclosure_date": _to_date(entry.get("disclosureDate")),
        "transaction_type": transaction_type,
        "amount_range": entry.get("amount") or entry.get("amountRange") or None,
        "asset_description": (str(entry.get("assetDescription", ""))[:500] or None)
        if entry.get("assetDescription")
        else None,
        "source": "fmp",
    }


def _normalize_transaction_type(raw_type: str) -> str | None:
    """Normalize transaction type to 'purchase' or 'sale'."""
    if not raw_type:
        return None
    lower = raw_type.lower()
    if "purchase" in lower or "buy" in lower:
        return "purchase"
    if "sale" in lower or "sell" in lower:
        return "sale"
    if "exchange" in lower:
        return "exchange"
    return raw_type[:20]


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
