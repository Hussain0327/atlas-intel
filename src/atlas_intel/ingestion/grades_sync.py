"""Sync analyst grades and price targets from FMP."""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.alt_data_transforms import (
    parse_analyst_grades,
    parse_price_target_consensus,
)
from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.analyst_grade import AnalystGrade
from atlas_intel.models.company import Company
from atlas_intel.models.price_target import PriceTarget
from atlas_intel.services.analyst_service import invalidate_analyst_consensus_cache

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


async def sync_analyst_grades(
    session: AsyncSession,
    client: FMPClient,
    company: Company,
    force: bool = False,
) -> int:
    """Sync analyst grades for a company.

    Returns the number of records inserted.
    """
    if (
        not force
        and company.analyst_grades_synced_at
        and (company.analyst_grades_synced_at > utcnow() - timedelta(hours=24))
    ):
        logger.info("Skipping analyst grades for %s (synced recently)", company.ticker)
        return 0

    ticker = company.ticker or ""

    logger.info("Fetching analyst grades for %s...", ticker)
    raw_data = await client.get_analyst_grades(ticker, limit=50)
    grades = parse_analyst_grades(raw_data)

    if not grades:
        await session.execute(
            update(Company)
            .where(Company.id == company.id)
            .values(analyst_grades_synced_at=utcnow())
        )
        await session.commit()
        return 0

    # Dedup by (grade_date, grading_company, new_grade)
    seen: set[tuple[object, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for g in grades:
        key = (g["grade_date"], g["grading_company"], g["new_grade"])
        if key not in seen:
            seen.add(key)
            deduped.append(g)
    grades = deduped

    total_inserted = 0
    for i in range(0, len(grades), BATCH_SIZE):
        batch = grades[i : i + BATCH_SIZE]
        for g in batch:
            g["company_id"] = company.id

        stmt = pg_insert(AnalystGrade).values(batch)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_analyst_grade_dedup")
        result = await session.execute(stmt)
        total_inserted += result.rowcount  # type: ignore[attr-defined]

    await session.execute(
        update(Company).where(Company.id == company.id).values(analyst_grades_synced_at=utcnow())
    )
    await session.commit()
    await invalidate_analyst_consensus_cache(company.id)

    logger.info("Inserted %d analyst grades for %s", total_inserted, ticker)
    return total_inserted


async def sync_price_targets(
    session: AsyncSession,
    client: FMPClient,
    company: Company,
    force: bool = False,
) -> bool:
    """Sync price target consensus for a company.

    Returns True if the record was upserted, False otherwise.
    """
    if (
        not force
        and company.price_targets_synced_at
        and (company.price_targets_synced_at > utcnow() - timedelta(hours=24))
    ):
        logger.info("Skipping price targets for %s (synced recently)", company.ticker)
        return False

    ticker = company.ticker or ""

    logger.info("Fetching price target consensus for %s...", ticker)
    raw_data = await client.get_price_target_consensus(ticker)
    parsed = parse_price_target_consensus(raw_data)

    if not parsed:
        await session.execute(
            update(Company).where(Company.id == company.id).values(price_targets_synced_at=utcnow())
        )
        await session.commit()
        return False

    parsed["company_id"] = company.id

    stmt = pg_insert(PriceTarget).values([parsed])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_price_target_company",
        set_={
            "target_high": stmt.excluded.target_high,
            "target_low": stmt.excluded.target_low,
            "target_consensus": stmt.excluded.target_consensus,
            "target_median": stmt.excluded.target_median,
        },
    )
    await session.execute(stmt)

    await session.execute(
        update(Company).where(Company.id == company.id).values(price_targets_synced_at=utcnow())
    )
    await session.commit()
    await invalidate_analyst_consensus_cache(company.id)

    logger.info("Upserted price target for %s", ticker)
    return True
