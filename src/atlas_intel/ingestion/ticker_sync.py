"""Sync CIK-ticker mapping from SEC EDGAR."""

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.transforms import parse_company_tickers
from atlas_intel.models.company import Company

logger = logging.getLogger(__name__)


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

    stmt = pg_insert(Company).values(companies)
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
