"""Pure parsing functions for FRED API responses."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def parse_fred_observations(data: dict[str, Any], series_id: str) -> list[dict[str, Any]]:
    """Parse FRED series observations into MacroIndicator-ready dicts.

    FRED uses "." for missing/unavailable values. These are stored as NULL.
    """
    observations = data.get("observations", [])
    results = []
    for obs in observations:
        obs_date = _to_date(obs.get("date"))
        if obs_date is None:
            continue

        value = _to_decimal(obs.get("value"))
        # FRED uses "." for missing values — value will be None

        results.append(
            {
                "series_id": series_id,
                "observation_date": obs_date,
                "value": value,
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


def _to_decimal(val: Any) -> Decimal | None:
    """Safely convert a value to Decimal, returning None on failure.

    FRED uses "." for missing data points.
    """
    if val is None or str(val).strip() == ".":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None
