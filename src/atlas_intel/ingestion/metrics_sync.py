"""Sync key financial metrics from FMP."""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.market_transforms import parse_key_metrics
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.market_metric import MarketMetric
from atlas_intel.services.company_service import invalidate_company_detail_cache
from atlas_intel.services.metric_service import invalidate_metrics_cache

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000

# All metric columns that should be updated on conflict
_METRIC_UPDATE_COLS = [
    "market_cap",
    "enterprise_value",
    "pe_ratio",
    "pb_ratio",
    "price_to_sales",
    "ev_to_ebitda",
    "ev_to_sales",
    "earnings_yield",
    "fcf_yield",
    "revenue_per_share",
    "net_income_per_share",
    "book_value_per_share",
    "fcf_per_share",
    "dividend_per_share",
    "roe",
    "roic",
    "debt_to_equity",
    "debt_to_assets",
    "current_ratio",
    "interest_coverage",
    "dividend_yield",
    "payout_ratio",
    "days_sales_outstanding",
    "days_payables_outstanding",
    "inventory_turnover",
]


def _merge_entries(
    km_data: list[dict[str, Any]], ratios_data: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge key-metrics and ratios entries by date.

    Both endpoints return lists with a 'date' field. We merge entries
    with matching dates into a single dict. For TTM (no date), we merge
    all entries into one.
    """
    if not km_data and not ratios_data:
        return []

    # Index ratios by date for O(1) lookup
    ratios_by_date: dict[str | None, dict[str, Any]] = {}
    for r in ratios_data:
        key = r.get("date")
        ratios_by_date[key] = r

    merged: list[dict[str, Any]] = []
    seen_dates: set[str | None] = set()

    for km in km_data:
        entry = dict(km)  # copy
        date_key = km.get("date")
        if date_key in ratios_by_date:
            # Merge ratios into the key-metrics entry (ratios don't overwrite existing)
            for k, v in ratios_by_date[date_key].items():
                if k not in entry:
                    entry[k] = v
        merged.append(entry)
        seen_dates.add(date_key)

    # Add any ratio entries with dates not in key-metrics
    for date_key, r in ratios_by_date.items():
        if date_key not in seen_dates:
            merged.append(r)

    return merged


async def sync_metrics(
    session: AsyncSession,
    client: FMPClient,
    company: Company,
    force: bool = False,
) -> int:
    """Sync key financial metrics (TTM + annual) for a company.

    Returns the number of metric records upserted.
    """
    if (
        not force
        and company.metrics_synced_at
        and (company.metrics_synced_at > utcnow() - timedelta(days=7))
    ):
        logger.info("Skipping metrics for %s (synced recently)", company.ticker)
        return 0

    ticker = company.ticker or ""

    # Fetch from both key-metrics and ratios endpoints, then merge by date
    logger.info("Fetching TTM metrics for %s...", ticker)
    ttm_km = await client.get_key_metrics_ttm(ticker)
    ttm_ratios = await client.get_ratios_ttm(ticker)
    # Merge TTM: combine dicts from both endpoints
    ttm_merged = _merge_entries(ttm_km, ttm_ratios)
    ttm_parsed = parse_key_metrics(ttm_merged, period_type="TTM")

    logger.info("Fetching annual metrics for %s...", ticker)
    annual_km = await client.get_key_metrics(ticker, period="annual", limit=5)
    annual_ratios = await client.get_ratios(ticker, period="annual", limit=5)
    annual_merged = _merge_entries(annual_km, annual_ratios)
    annual_parsed = parse_key_metrics(annual_merged, period_type="annual")

    all_metrics: list[dict[str, Any]] = ttm_parsed + annual_parsed

    if not all_metrics:
        await session.execute(
            update(Company).where(Company.id == company.id).values(metrics_synced_at=utcnow())
        )
        await session.commit()
        return 0

    # Dedup by (period, period_date) within batch
    seen: set[tuple[str, object]] = set()
    deduped: list[dict[str, Any]] = []
    for m in all_metrics:
        key = (m["period"], m["period_date"])
        if key not in seen:
            seen.add(key)
            deduped.append(m)
    all_metrics = deduped

    total_upserted = 0
    for i in range(0, len(all_metrics), BATCH_SIZE):
        batch = all_metrics[i : i + BATCH_SIZE]
        for m in batch:
            m["company_id"] = company.id

        stmt = pg_insert(MarketMetric).values(batch)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_market_metric_company_period",
            set_={col: getattr(stmt.excluded, col) for col in _METRIC_UPDATE_COLS},
        )
        result = await session.execute(stmt)
        total_upserted += result.rowcount  # type: ignore[attr-defined]

    await session.execute(
        update(Company).where(Company.id == company.id).values(metrics_synced_at=utcnow())
    )
    await session.commit()
    await invalidate_company_detail_cache(company)
    await invalidate_metrics_cache(company.id)

    logger.info("Upserted %d metrics for %s", total_upserted, ticker)
    return total_upserted
