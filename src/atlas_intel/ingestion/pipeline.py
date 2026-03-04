"""Orchestrator for the SEC EDGAR ingestion pipeline."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.facts_sync import sync_facts
from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.metrics_sync import sync_metrics
from atlas_intel.ingestion.price_sync import sync_prices
from atlas_intel.ingestion.profile_sync import sync_profile
from atlas_intel.ingestion.submission_sync import sync_submissions
from atlas_intel.ingestion.ticker_sync import sync_tickers
from atlas_intel.ingestion.transcript_sync import sync_transcripts
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


async def run_transcript_sync(
    session: AsyncSession,
    tickers: list[str],
    years: int = 3,
    force: bool = False,
) -> dict[str, int]:
    """Run transcript ingestion + NLP pipeline for the given tickers.

    Returns a summary dict with transcript counts per ticker.
    """
    results: dict[str, int] = {}

    async with FMPClient() as client:
        for ticker in tickers:
            ticker = ticker.upper()
            result = await session.execute(select(Company).where(Company.ticker == ticker))
            company = result.scalar_one_or_none()

            if not company:
                logger.warning("Company not found for ticker %s", ticker)
                results[ticker] = 0
                continue

            count = await sync_transcripts(session, client, company, years=years, force=force)
            results[ticker] = count
            logger.info("Completed transcript sync for %s: %d transcripts", ticker, count)

    return results


async def run_market_data_sync(
    session: AsyncSession,
    tickers: list[str],
    years: int = 5,
    force: bool = False,
) -> dict[str, dict[str, int | bool]]:
    """Run market data sync (profile, prices, metrics) for the given tickers.

    Returns a summary dict per ticker with counts.
    """
    results: dict[str, dict[str, int | bool]] = {}

    async with FMPClient() as client:
        for ticker in tickers:
            ticker = ticker.upper()
            result = await session.execute(select(Company).where(Company.ticker == ticker))
            company = result.scalar_one_or_none()

            if not company:
                logger.warning("Company not found for ticker %s", ticker)
                results[ticker] = {"error": True, "profile": False, "prices": 0, "metrics": 0}
                continue

            profile_updated = await sync_profile(session, client, company, force=force)
            prices_count = await sync_prices(session, client, company, years=years, force=force)
            metrics_count = await sync_metrics(session, client, company, force=force)

            results[ticker] = {
                "profile": profile_updated,
                "prices": prices_count,
                "metrics": metrics_count,
            }
            logger.info(
                "Completed market data sync for %s: profile=%s, %d prices, %d metrics",
                ticker,
                profile_updated,
                prices_count,
                metrics_count,
            )

    return results


async def run_ticker_sync(session: AsyncSession) -> int:
    """Run only the ticker sync step."""
    async with SECClient() as client:
        return await sync_tickers(session, client)
