"""Sync institutional holdings from FMP."""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.alt_data_transforms import parse_institutional_holdings
from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.institutional_holding import InstitutionalHolding

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


async def sync_institutional_holdings(
    session: AsyncSession,
    client: FMPClient,
    company: Company,
    force: bool = False,
) -> int:
    """Sync institutional holdings for a company.

    Returns the number of records inserted.
    """
    if (
        not force
        and company.institutional_holdings_synced_at
        and (company.institutional_holdings_synced_at > utcnow() - timedelta(days=30))
    ):
        logger.info("Skipping institutional holdings for %s (synced recently)", company.ticker)
        return 0

    ticker = company.ticker or ""

    logger.info("Fetching institutional holdings for %s...", ticker)
    raw_data = await client.get_institutional_holders(ticker, limit=50)
    holdings = parse_institutional_holdings(raw_data)

    if not holdings:
        await session.execute(
            update(Company)
            .where(Company.id == company.id)
            .values(institutional_holdings_synced_at=utcnow())
        )
        await session.commit()
        return 0

    # Dedup by (holder, date_reported)
    seen: set[tuple[str, object]] = set()
    deduped: list[dict[str, Any]] = []
    for h in holdings:
        key = (h["holder"], h["date_reported"])
        if key not in seen:
            seen.add(key)
            deduped.append(h)
    holdings = deduped

    total_inserted = 0
    for i in range(0, len(holdings), BATCH_SIZE):
        batch = holdings[i : i + BATCH_SIZE]
        for h in batch:
            h["company_id"] = company.id

        stmt = pg_insert(InstitutionalHolding).values(batch)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_institutional_holding_dedup")
        result = await session.execute(stmt)
        total_inserted += result.rowcount  # type: ignore[attr-defined]

    await session.execute(
        update(Company)
        .where(Company.id == company.id)
        .values(institutional_holdings_synced_at=utcnow())
    )
    await session.commit()

    logger.info("Inserted %d institutional holdings for %s", total_inserted, ticker)
    return total_inserted
