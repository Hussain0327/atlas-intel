"""Sync CIK-ticker mapping from SEC EDGAR."""

import logging
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.transforms import parse_company_tickers
from atlas_intel.models.company import Company

logger = logging.getLogger(__name__)

# asyncpg has a 32767 parameter limit. Each company row has 3 columns,
# so we batch at 5000 rows to stay safely under that limit.
BATCH_SIZE = 5000


async def sync_tickers(session: AsyncSession, client: SECClient) -> int:
    """Fetch and upsert all company tickers from SEC.

    Returns the number of companies upserted.
    """
    logger.info("Fetching company tickers from SEC...")
    data = await client.get_company_tickers()
    companies = parse_company_tickers(data)
    logger.info("Parsed %d companies from ticker data", len(companies))

    if not companies:
        return 0

    # SEC's company_tickers.json can contain duplicate CIK entries (e.g.,
    # companies with multiple share classes like JPM, JPM-PC, VYLD all under
    # CIK 19617). PostgreSQL ON CONFLICT DO UPDATE cannot affect the same row
    # twice in a single INSERT, so dedup first. We keep the first occurrence
    # per CIK since SEC orders by market cap — the primary ticker comes first.
    deduped: dict[int, dict[str, Any]] = {}
    for c in companies:
        deduped.setdefault(c["cik"], c)
    companies = list(deduped.values())

    for i in range(0, len(companies), BATCH_SIZE):
        batch = companies[i : i + BATCH_SIZE]
        stmt = pg_insert(Company).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=["cik"],
            set_={
                "ticker": stmt.excluded.ticker,
                "name": stmt.excluded.name,
            },
        )
        await session.execute(stmt)
    await session.commit()

    logger.info("Upserted %d companies", len(companies))
    return len(companies)
