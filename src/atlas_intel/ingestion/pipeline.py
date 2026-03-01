"""Orchestrator for the SEC EDGAR ingestion pipeline."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.facts_sync import sync_facts
from atlas_intel.ingestion.submission_sync import sync_submissions
from atlas_intel.ingestion.ticker_sync import sync_tickers
from atlas_intel.models.company import Company

logger = logging.getLogger(__name__)


async def run_full_sync(
    session: AsyncSession,
    tickers: list[str],
    force: bool = False,
) -> dict[str, dict[str, int]]:
    """Run the full ingestion pipeline for the given tickers.

    Returns a summary dict per ticker with counts.
    """
    results: dict[str, dict[str, int]] = {}

    async with SECClient() as client:
        # Step 1: Ensure ticker mapping is up to date
        await sync_tickers(session, client)

        # Step 2+3: For each ticker, sync submissions and facts
        for ticker in tickers:
            ticker = ticker.upper()
            result = await session.execute(select(Company).where(Company.ticker == ticker))
            company = result.scalar_one_or_none()

            if not company:
                logger.warning("Company not found for ticker %s", ticker)
                results[ticker] = {"error": 1, "filings": 0, "facts": 0}
                continue

            filings_count = await sync_submissions(session, client, company, force=force)
            facts_count = await sync_facts(session, client, company, force=force)

            results[ticker] = {
                "filings": filings_count,
                "facts": facts_count,
            }
            logger.info(
                "Completed sync for %s: %d filings, %d facts",
                ticker,
                filings_count,
                facts_count,
            )

    return results


async def run_ticker_sync(session: AsyncSession) -> int:
    """Run only the ticker sync step."""
    async with SECClient() as client:
        return await sync_tickers(session, client)
