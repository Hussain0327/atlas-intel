"""Pure parsing functions for FMP market data responses."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def _to_decimal(val: Any) -> Decimal | None:
    """Safely convert a value to Decimal, returning None on failure."""
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


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


def parse_historical_prices(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse FMP historical price response into StockPrice-ready dicts.

    Skips entries without a close price.
    """
    results = []
    for entry in data:
        close = _to_decimal(entry.get("close"))
        if close is None:
            continue

        price_date = _to_date(entry.get("date"))
        if price_date is None:
            continue

        results.append(
            {
                "price_date": price_date,
                "open": _to_decimal(entry.get("open")),
                "high": _to_decimal(entry.get("high")),
                "low": _to_decimal(entry.get("low")),
                "close": close,
                "adj_close": _to_decimal(entry.get("adjClose")),
                "volume": entry.get("volume"),
                "vwap": _to_decimal(entry.get("vwap")),
                "change_percent": _to_decimal(entry.get("changePercent")),
            }
        )
    return results


def parse_company_profile(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Parse FMP company profile response into Company update fields.

    Returns an empty dict if data is empty.
    """
    if not data:
        return {}

    profile = data[0]

    employees = profile.get("fullTimeEmployees")
    if employees is not None:
        try:
            employees = int(employees)
        except (ValueError, TypeError):
            employees = None

    return {
        "sector": profile.get("sector") or None,
        "industry": profile.get("industry") or None,
        "country": profile.get("country") or None,
        "currency": profile.get("currency") or None,
        "ceo": profile.get("ceo") or None,
        "full_time_employees": employees,
        "description": profile.get("description") or None,
        "ipo_date": _to_date(profile.get("ipoDate")),
        "is_etf": profile.get("isEtf") if isinstance(profile.get("isEtf"), bool) else None,
        "is_actively_trading": (
            profile.get("isActivelyTrading")
            if isinstance(profile.get("isActivelyTrading"), bool)
            else None
        ),
        "beta": _to_decimal(profile.get("beta")),
        "exchange": profile.get("exchangeShortName") or profile.get("exchange") or None,
        "website": profile.get("website") or None,
    }


# FMP camelCase -> our snake_case DB columns
# Covers both key-metrics and ratios endpoints, plus TTM variants
_METRIC_FIELD_MAP: dict[str, str] = {
    # --- key-metrics endpoint (annual) ---
    "marketCap": "market_cap",
    "enterpriseValue": "enterprise_value",
    "evToEBITDA": "ev_to_ebitda",
    "evToSales": "ev_to_sales",
    "earningsYield": "earnings_yield",
    "freeCashFlowYield": "fcf_yield",
    "currentRatio": "current_ratio",
    "returnOnEquity": "roe",
    "returnOnInvestedCapital": "roic",
    "daysOfSalesOutstanding": "days_sales_outstanding",
    "daysOfPayablesOutstanding": "days_payables_outstanding",
    # --- ratios endpoint (annual) ---
    "priceToEarningsRatio": "pe_ratio",
    "priceToBookRatio": "pb_ratio",
    "priceToSalesRatio": "price_to_sales",
    "revenuePerShare": "revenue_per_share",
    "netIncomePerShare": "net_income_per_share",
    "bookValuePerShare": "book_value_per_share",
    "freeCashFlowPerShare": "fcf_per_share",
    "dividendPerShare": "dividend_per_share",
    "dividendYield": "dividend_yield",
    "dividendPayoutRatio": "payout_ratio",
    "debtToEquityRatio": "debt_to_equity",
    "debtToAssetsRatio": "debt_to_assets",
    "interestCoverageRatio": "interest_coverage",
    "inventoryTurnover": "inventory_turnover",
    # --- key-metrics TTM endpoint ---
    "marketCapTTM": "market_cap",
    "enterpriseValueTTM": "enterprise_value",
    "evToEBITDATTM": "ev_to_ebitda",
    "evToSalesTTM": "ev_to_sales",
    "earningsYieldTTM": "earnings_yield",
    "freeCashFlowYieldTTM": "fcf_yield",
    "currentRatioTTM": "current_ratio",
    "returnOnEquityTTM": "roe",
    "returnOnInvestedCapitalTTM": "roic",
    "daysOfSalesOutstandingTTM": "days_sales_outstanding",
    "daysOfPayablesOutstandingTTM": "days_payables_outstanding",
    # --- ratios TTM endpoint ---
    "priceToEarningsRatioTTM": "pe_ratio",
    "priceToBookRatioTTM": "pb_ratio",
    "priceToSalesRatioTTM": "price_to_sales",
    "revenuePerShareTTM": "revenue_per_share",
    "netIncomePerShareTTM": "net_income_per_share",
    "bookValuePerShareTTM": "book_value_per_share",
    "freeCashFlowPerShareTTM": "fcf_per_share",
    "dividendPerShareTTM": "dividend_per_share",
    "dividendYieldTTM": "dividend_yield",
    "dividendPayoutRatioTTM": "payout_ratio",
    "debtToEquityRatioTTM": "debt_to_equity",
    "debtToAssetsRatioTTM": "debt_to_assets",
    "interestCoverageRatioTTM": "interest_coverage",
    "inventoryTurnoverTTM": "inventory_turnover",
    # Legacy v3 field names (for test fixtures / backwards compat)
    "peRatio": "pe_ratio",
    "pbRatio": "pb_ratio",
    "enterpriseValueOverEBITDA": "ev_to_ebitda",
    "roe": "roe",
    "roic": "roic",
    "debtToEquity": "debt_to_equity",
    "debtToAssets": "debt_to_assets",
    "interestCoverage": "interest_coverage",
    "payoutRatio": "payout_ratio",
    "peRatioTTM": "pe_ratio",
    "pbRatioTTM": "pb_ratio",
    "roeTTM": "roe",
    "roicTTM": "roic",
    "debtToEquityTTM": "debt_to_equity",
    "debtToAssetsTTM": "debt_to_assets",
    "interestCoverageTTM": "interest_coverage",
    "payoutRatioTTM": "payout_ratio",
}


def parse_key_metrics(
    data: list[dict[str, Any]], period_type: str = "annual"
) -> list[dict[str, Any]]:
    """Parse FMP key metrics response into MarketMetric-ready dicts.

    For TTM data without a date field, defaults period_date to today.
    """
    results = []
    for entry in data:
        period_date = _to_date(entry.get("date"))
        if period_date is None:
            # TTM entries often lack a date
            if period_type == "TTM":
                period_date = date.today()
            else:
                continue

        row: dict[str, Any] = {
            "period": period_type,
            "period_date": period_date,
        }

        for fmp_key, db_col in _METRIC_FIELD_MAP.items():
            if fmp_key in entry:
                val = _to_decimal(entry[fmp_key])
                if val is not None:
                    row[db_col] = val

        results.append(row)
    return results
