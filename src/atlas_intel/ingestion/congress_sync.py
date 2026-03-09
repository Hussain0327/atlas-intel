"""Sync congressional trading data."""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.congress_client import CongressClient
from atlas_intel.ingestion.congress_transforms import parse_congress_trades
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.congress_trade import CongressTrade

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


async def sync_congress_trades(
    session: AsyncSession,
    client: CongressClient,
    company: Company,
    force: bool = False,
) -> int:
    """Sync congressional trading disclosures for a company.

    Freshness: 7d (STOCK Act has 30-45 day reporting delay).
    Returns the number of trades inserted.
    """
    if (
        not force
        and company.congress_trades_synced_at
        and (company.congress_trades_synced_at > utcnow() - timedelta(days=7))
    ):
        logger.info("Skipping congress trades for %s (synced recently)", company.ticker)
        return 0

    ticker = company.ticker or ""

    logger.info("Fetching congress trades for %s...", ticker)
    senate_data = await client.get_senate_trading(ticker)
    house_data = await client.get_house_trading(ticker)

    trades = parse_congress_trades(senate_data, house_data)

    if not trades:
        await session.execute(
            update(Company)
            .where(Company.id == company.id)
            .values(congress_trades_synced_at=utcnow())
        )
        await session.commit()
        return 0

    # In-batch dedup by (representative, transaction_date, transaction_type)
    seen: set[tuple[str, object, str | None]] = set()
    deduped: list[dict[str, Any]] = []
    for t in trades:
        key = (t["representative"], t["transaction_date"], t["transaction_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    trades = deduped

    total_inserted = 0
    for i in range(0, len(trades), BATCH_SIZE):
        batch = trades[i : i + BATCH_SIZE]
        for t in batch:
            t["company_id"] = company.id

        stmt = pg_insert(CongressTrade).values(batch)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_congress_trade_dedup")
        result = await session.execute(stmt)
        total_inserted += result.rowcount  # type: ignore[attr-defined]

    await session.execute(
        update(Company).where(Company.id == company.id).values(congress_trades_synced_at=utcnow())
    )
    await session.commit()

    logger.info("Inserted %d congress trades for %s", total_inserted, ticker)
    return total_inserted
