"""APScheduler-based background sync scheduler.

Runs in-process with the web app (via FastAPI lifespan) or standalone via ``atlas worker``.
Each job gets its own database session and is wrapped in try/except so failures
never affect other jobs.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from atlas_intel.config import settings

logger = logging.getLogger(__name__)


async def sync_market_job() -> None:
    """Sync market data for all tracked companies."""
    logger.info("scheduler.sync_market_job started")
    try:
        from sqlalchemy import select

        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_market_data_sync
        from atlas_intel.models.company import Company

        async with async_session() as session:
            result = await session.execute(
                select(Company.ticker)
                .where(Company.facts_synced_at.is_not(None), Company.ticker.is_not(None))
                .order_by(Company.ticker)
            )
            tickers = [row[0] for row in result.all()]

            for ticker in tickers:
                try:
                    await run_market_data_sync(session, [ticker])
                except Exception:
                    logger.exception("sync_market_job failed for %s", ticker)

        logger.info("scheduler.sync_market_job completed (%d tickers)", len(tickers))
    except Exception:
        logger.exception("scheduler.sync_market_job failed")


async def sync_alt_job() -> None:
    """Sync alternative data for all tracked companies."""
    logger.info("scheduler.sync_alt_job started")
    try:
        from sqlalchemy import select

        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_alt_data_sync
        from atlas_intel.models.company import Company

        async with async_session() as session:
            result = await session.execute(
                select(Company.ticker)
                .where(Company.facts_synced_at.is_not(None), Company.ticker.is_not(None))
                .order_by(Company.ticker)
            )
            tickers = [row[0] for row in result.all()]

            for ticker in tickers:
                try:
                    await run_alt_data_sync(session, [ticker])
                except Exception:
                    logger.exception("sync_alt_job failed for %s", ticker)

        logger.info("scheduler.sync_alt_job completed (%d tickers)", len(tickers))
    except Exception:
        logger.exception("scheduler.sync_alt_job failed")


async def sync_sec_job() -> None:
    """Sync SEC EDGAR submissions and facts."""
    logger.info("scheduler.sync_sec_job started")
    try:
        from sqlalchemy import select

        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_full_sync
        from atlas_intel.models.company import Company

        async with async_session() as session:
            result = await session.execute(
                select(Company.ticker)
                .where(Company.facts_synced_at.is_not(None), Company.ticker.is_not(None))
                .order_by(Company.ticker)
            )
            tickers = [row[0] for row in result.all()]

            for ticker in tickers:
                try:
                    await run_full_sync(session, [ticker])
                except Exception:
                    logger.exception("sync_sec_job failed for %s", ticker)

        logger.info("scheduler.sync_sec_job completed (%d tickers)", len(tickers))
    except Exception:
        logger.exception("scheduler.sync_sec_job failed")


async def sync_transcripts_job() -> None:
    """Sync earnings transcripts (weekly)."""
    if settings.disable_nlp:
        logger.info("scheduler.sync_transcripts_job skipped (NLP disabled)")
        return

    logger.info("scheduler.sync_transcripts_job started")
    try:
        from sqlalchemy import select

        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_transcript_sync
        from atlas_intel.models.company import Company

        async with async_session() as session:
            result = await session.execute(
                select(Company.ticker)
                .where(Company.facts_synced_at.is_not(None), Company.ticker.is_not(None))
                .order_by(Company.ticker)
            )
            tickers = [row[0] for row in result.all()]

            for ticker in tickers:
                try:
                    await run_transcript_sync(session, [ticker])
                except Exception:
                    logger.exception("sync_transcripts_job failed for %s", ticker)

        logger.info("scheduler.sync_transcripts_job completed (%d tickers)", len(tickers))
    except Exception:
        logger.exception("scheduler.sync_transcripts_job failed")


async def sync_macro_job() -> None:
    """Sync FRED macro indicators."""
    logger.info("scheduler.sync_macro_job started")
    try:
        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_macro_sync

        series_ids = settings.fred_series.split(",")
        async with async_session() as session:
            await run_macro_sync(session, series_ids)

        logger.info("scheduler.sync_macro_job completed")
    except Exception:
        logger.exception("scheduler.sync_macro_job failed")


async def check_alerts_job() -> None:
    """Evaluate all alert rules."""
    logger.info("scheduler.check_alerts_job started")
    try:
        from atlas_intel.database import async_session
        from atlas_intel.services.alert_service import check_all_alerts

        async with async_session() as session:
            events = await check_all_alerts(session)
            if events:
                logger.info("scheduler.check_alerts_job triggered %d events", len(events))

        logger.info("scheduler.check_alerts_job completed")
    except Exception:
        logger.exception("scheduler.check_alerts_job failed")


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the background scheduler (does not start it)."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        sync_market_job, "interval", hours=6, id="sync_market", name="Market Data Sync"
    )
    scheduler.add_job(sync_alt_job, "interval", hours=24, id="sync_alt", name="Alt Data Sync")
    scheduler.add_job(sync_sec_job, "interval", hours=24, id="sync_sec", name="SEC EDGAR Sync")
    scheduler.add_job(
        sync_transcripts_job, "interval", hours=168, id="sync_transcripts", name="Transcript Sync"
    )
    scheduler.add_job(sync_macro_job, "interval", hours=24, id="sync_macro", name="Macro Sync")
    scheduler.add_job(
        check_alerts_job, "interval", minutes=15, id="check_alerts", name="Alert Check"
    )

    logger.info("Scheduler configured with %d jobs", len(scheduler.get_jobs()))
    return scheduler


def get_scheduler_status(scheduler: AsyncIOScheduler | None) -> dict[str, object]:
    """Return scheduler status for the ops endpoint."""
    if scheduler is None:
        return {"running": False, "jobs": []}

    jobs = []
    for job in scheduler.get_jobs():
        next_run = getattr(job, "next_run_time", None)
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
                "trigger": str(job.trigger),
            }
        )

    return {"running": scheduler.running, "jobs": jobs}
