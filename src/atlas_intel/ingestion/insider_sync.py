"""Sync insider trading data from FMP."""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.alt_data_transforms import parse_insider_trades
from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.insider_trade import InsiderTrade

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


async def sync_insider_trades(
    session: AsyncSession,
    client: FMPClient,
    company: Company,
    force: bool = False,
) -> int:
    """Sync insider trading transactions for a company.

    Returns the number of records inserted.
    """
    if (
        not force
        and company.insider_trades_synced_at
        and (company.insider_trades_synced_at > utcnow() - timedelta(hours=24))
    ):
        logger.info("Skipping insider trades for %s (synced recently)", company.ticker)
        return 0

    ticker = company.ticker or ""

    logger.info("Fetching insider trades for %s...", ticker)
    raw_data = await client.get_insider_trading(ticker, limit=100)
    trades = parse_insider_trades(raw_data)

    if not trades:
        await session.execute(
            update(Company)
            .where(Company.id == company.id)
            .values(insider_trades_synced_at=utcnow())
        )
        await session.commit()
        return 0

    # Dedup by (filing_date, reporting_cik, transaction_type, securities_transacted)
    seen: set[tuple[object, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for t in trades:
        key = (
            t["filing_date"],
            t["reporting_cik"],
            t["transaction_type"],
            t["securities_transacted"],
        )
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    trades = deduped

    total_inserted = 0
    for i in range(0, len(trades), BATCH_SIZE):
        batch = trades[i : i + BATCH_SIZE]
        for t in batch:
            t["company_id"] = company.id

        stmt = pg_insert(InsiderTrade).values(batch)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_insider_trade_dedup")
        result = await session.execute(stmt)
        total_inserted += result.rowcount  # type: ignore[attr-defined]

    await session.execute(
        update(Company).where(Company.id == company.id).values(insider_trades_synced_at=utcnow())
    )
    await session.commit()

    logger.info("Inserted %d insider trades for %s", total_inserted, ticker)
    return total_inserted
