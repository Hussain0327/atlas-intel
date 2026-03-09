"""Sync analyst estimates from FMP."""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.alt_data_transforms import parse_analyst_estimates
from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.analyst_estimate import AnalystEstimate
from atlas_intel.models.company import Company
from atlas_intel.services.analyst_service import invalidate_analyst_consensus_cache

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000

_ESTIMATE_UPDATE_COLS = [
    "estimated_revenue_avg",
    "estimated_revenue_high",
    "estimated_revenue_low",
    "estimated_eps_avg",
    "estimated_eps_high",
    "estimated_eps_low",
    "estimated_ebitda_avg",
    "estimated_ebitda_high",
    "estimated_ebitda_low",
    "number_analysts_revenue",
    "number_analysts_eps",
]


async def sync_analyst_estimates(
    session: AsyncSession,
    client: FMPClient,
    company: Company,
    force: bool = False,
) -> int:
    """Sync analyst estimates (annual + quarterly) for a company.

    Returns the number of records upserted.
    """
    if (
        not force
        and company.analyst_estimates_synced_at
        and (company.analyst_estimates_synced_at > utcnow() - timedelta(days=7))
    ):
        logger.info("Skipping analyst estimates for %s (synced recently)", company.ticker)
        return 0

    ticker = company.ticker or ""

    logger.info("Fetching analyst estimates for %s...", ticker)
    annual_raw = await client.get_analyst_estimates(ticker, period="annual", limit=10)
    quarterly_raw = await client.get_analyst_estimates(ticker, period="quarter", limit=10)

    annual = parse_analyst_estimates(annual_raw, "annual")
    quarterly = parse_analyst_estimates(quarterly_raw, "quarter")
    all_estimates: list[dict[str, Any]] = annual + quarterly

    if not all_estimates:
        await session.execute(
            update(Company)
            .where(Company.id == company.id)
            .values(analyst_estimates_synced_at=utcnow())
        )
        await session.commit()
        return 0

    # Dedup by (period, estimate_date)
    seen: set[tuple[str, object]] = set()
    deduped: list[dict[str, Any]] = []
    for e in all_estimates:
        key = (e["period"], e["estimate_date"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    all_estimates = deduped

    total_upserted = 0
    for i in range(0, len(all_estimates), BATCH_SIZE):
        batch = all_estimates[i : i + BATCH_SIZE]
        for e in batch:
            e["company_id"] = company.id

        stmt = pg_insert(AnalystEstimate).values(batch)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_analyst_estimate_company_period_date",
            set_={col: getattr(stmt.excluded, col) for col in _ESTIMATE_UPDATE_COLS},
        )
        result = await session.execute(stmt)
        total_upserted += result.rowcount  # type: ignore[attr-defined]

    await session.execute(
        update(Company).where(Company.id == company.id).values(analyst_estimates_synced_at=utcnow())
    )
    await session.commit()
    await invalidate_analyst_consensus_cache(company.id)

    logger.info("Upserted %d analyst estimates for %s", total_upserted, ticker)
    return total_upserted
