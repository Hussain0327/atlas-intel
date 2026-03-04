"""Sync daily stock prices from FMP."""

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.market_transforms import parse_historical_prices
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.stock_price import StockPrice

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


async def sync_prices(
    session: AsyncSession,
    client: FMPClient,
    company: Company,
    years: int = 5,
    force: bool = False,
) -> int:
    """Sync daily stock prices for a company.

    Incremental: fetches only dates after the latest stored price.
    Returns the number of price records upserted.
    """
    if (
        not force
        and company.prices_synced_at
        and (company.prices_synced_at > utcnow() - timedelta(hours=24))
    ):
        logger.info("Skipping prices for %s (synced recently)", company.ticker)
        return 0

    ticker = company.ticker or ""

    # Determine start date: incremental from last stored price
    result = await session.execute(
        select(func.max(StockPrice.price_date)).where(StockPrice.company_id == company.id)
    )
    last_date = result.scalar()

    if last_date and not force:
        from_date = last_date + timedelta(days=1)
    else:
        from_date = date.today() - timedelta(days=365 * years)

    to_date = date.today()

    if from_date > to_date:
        logger.info("Prices up to date for %s", ticker)
        await session.execute(
            update(Company).where(Company.id == company.id).values(prices_synced_at=utcnow())
        )
        await session.commit()
        return 0

    logger.info("Fetching prices for %s from %s to %s...", ticker, from_date, to_date)
    raw_data = await client.get_historical_prices(
        ticker, from_date.isoformat(), to_date.isoformat()
    )
    prices = parse_historical_prices(raw_data)

    if not prices:
        await session.execute(
            update(Company).where(Company.id == company.id).values(prices_synced_at=utcnow())
        )
        await session.commit()
        return 0

    # Dedup by price_date within batch
    seen_dates: set[date] = set()
    deduped: list[dict[str, Any]] = []
    for p in prices:
        if p["price_date"] not in seen_dates:
            seen_dates.add(p["price_date"])
            deduped.append(p)
    prices = deduped

    total_upserted = 0
    for i in range(0, len(prices), BATCH_SIZE):
        batch = prices[i : i + BATCH_SIZE]
        for p in batch:
            p["company_id"] = company.id

        stmt = pg_insert(StockPrice).values(batch)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_stock_price_company_date",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "adj_close": stmt.excluded.adj_close,
                "volume": stmt.excluded.volume,
                "vwap": stmt.excluded.vwap,
                "change_percent": stmt.excluded.change_percent,
            },
        )
        result = await session.execute(stmt)
        total_upserted += result.rowcount  # type: ignore[attr-defined]

    await session.execute(
        update(Company).where(Company.id == company.id).values(prices_synced_at=utcnow())
    )
    await session.commit()

    logger.info("Upserted %d prices for %s", total_upserted, ticker)
    return total_upserted
