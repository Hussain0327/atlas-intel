"""Operational services for scheduled jobs and freshness visibility."""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.pipeline import (
    run_alt_data_sync,
    run_full_sync,
    run_market_data_sync,
    run_transcript_sync,
)
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.sync_job import SyncJob
from atlas_intel.models.sync_job_run import SyncJobRun

SYNC_TYPE_FULL = "sec_full"
SYNC_TYPE_TRANSCRIPTS = "transcripts"
SYNC_TYPE_MARKET = "market_data"
SYNC_TYPE_ALT = "alt_data"

VALID_SYNC_TYPES = {
    SYNC_TYPE_FULL,
    SYNC_TYPE_TRANSCRIPTS,
    SYNC_TYPE_MARKET,
    SYNC_TYPE_ALT,
}

FRESHNESS_WINDOWS = {
    "submissions": ("submissions_synced_at", timedelta(hours=24)),
    "facts": ("facts_synced_at", timedelta(days=7)),
    "transcripts": ("transcripts_synced_at", timedelta(hours=24)),
    "prices": ("prices_synced_at", timedelta(hours=24)),
    "profile": ("profile_synced_at", timedelta(days=7)),
    "metrics": ("metrics_synced_at", timedelta(days=7)),
    "news": ("news_synced_at", timedelta(hours=6)),
    "insider_trades": ("insider_trades_synced_at", timedelta(hours=24)),
    "analyst_estimates": ("analyst_estimates_synced_at", timedelta(days=7)),
    "analyst_grades": ("analyst_grades_synced_at", timedelta(hours=24)),
    "price_targets": ("price_targets_synced_at", timedelta(hours=24)),
    "institutional_holdings": ("institutional_holdings_synced_at", timedelta(days=30)),
}


async def list_sync_jobs(session: AsyncSession) -> list[SyncJob]:
    result = await session.execute(select(SyncJob).order_by(SyncJob.name.asc()))
    return list(result.scalars().all())


async def get_sync_job(session: AsyncSession, job_id: int) -> SyncJob | None:
    result = await session.execute(select(SyncJob).where(SyncJob.id == job_id))
    return result.scalar_one_or_none()


async def create_sync_job(
    session: AsyncSession,
    *,
    name: str,
    sync_type: str,
    tickers: list[str],
    interval_minutes: int,
    years: int | None = None,
    force: bool = False,
    enabled: bool = True,
) -> SyncJob:
    if sync_type not in VALID_SYNC_TYPES:
        raise ValueError(f"Invalid sync_type: {sync_type}")

    job = SyncJob(
        name=name,
        sync_type=sync_type,
        tickers=[t.upper() for t in tickers],
        interval_minutes=interval_minutes,
        years=years,
        force=force,
        enabled=enabled,
        next_run_at=utcnow(),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def list_job_runs(
    session: AsyncSession,
    job_id: int,
    limit: int = 20,
) -> list[SyncJobRun]:
    result = await session.execute(
        select(SyncJobRun)
        .where(SyncJobRun.job_id == job_id)
        .order_by(SyncJobRun.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def _job_summary_status(summary: dict[str, Any]) -> str:
    raw_results = summary.get("results")
    if not isinstance(raw_results, dict):
        return "success"

    for value in raw_results.values():
        if isinstance(value, dict) and value.get("error"):
            return "partial"
    return "success"


async def _execute_sync_job(job: SyncJob, session: AsyncSession) -> dict[str, Any]:
    tickers = [t.upper() for t in job.tickers]

    results: dict[str, Any] | list[Any] | Any
    if job.sync_type == SYNC_TYPE_FULL:
        results = await run_full_sync(session, tickers, force=job.force)
    elif job.sync_type == SYNC_TYPE_TRANSCRIPTS:
        results = await run_transcript_sync(session, tickers, years=job.years or 3, force=job.force)
    elif job.sync_type == SYNC_TYPE_MARKET:
        results = await run_market_data_sync(
            session,
            tickers,
            years=job.years or 5,
            force=job.force,
        )
    elif job.sync_type == SYNC_TYPE_ALT:
        results = await run_alt_data_sync(session, tickers, force=job.force)
    else:
        raise ValueError(f"Unsupported sync_type: {job.sync_type}")

    return {"results": results}


async def run_sync_job(session: AsyncSession, job: SyncJob) -> SyncJobRun:
    started_at = utcnow()
    run = SyncJobRun(
        job_id=job.id,
        sync_type=job.sync_type,
        status="running",
        started_at=started_at,
        requested_tickers=job.tickers,
    )
    session.add(run)
    await session.flush()

    try:
        summary = await _execute_sync_job(job, session)
        status = _job_summary_status(summary)
        finished_at = utcnow()

        run.status = status
        run.finished_at = finished_at
        run.result_summary = summary

        job.last_run_at = finished_at
        job.last_status = status
        job.last_error = None
        job.next_run_at = finished_at + timedelta(minutes=job.interval_minutes)
        await session.commit()
    except Exception as exc:
        finished_at = utcnow()
        run.status = "failed"
        run.finished_at = finished_at
        run.error_message = str(exc)
        run.result_summary = None

        job.last_run_at = finished_at
        job.last_status = "failed"
        job.last_error = str(exc)
        job.next_run_at = finished_at + timedelta(minutes=job.interval_minutes)
        await session.commit()
        raise

    await session.refresh(run)
    return run


async def run_due_jobs(session: AsyncSession) -> list[SyncJobRun]:
    now = utcnow()
    result = await session.execute(
        select(SyncJob)
        .where(
            SyncJob.enabled.is_(True),
            SyncJob.next_run_at <= now,
        )
        .order_by(SyncJob.next_run_at.asc(), SyncJob.id.asc())
    )
    jobs = list(result.scalars().all())

    runs = []
    for job in jobs:
        runs.append(await run_sync_job(session, job))
    return runs


async def get_freshness_summary(session: AsyncSession) -> dict[str, Any]:
    now = utcnow()
    total_companies = (await session.execute(select(func.count(Company.id)))).scalar() or 0
    domains = []

    for domain, (field_name, max_age) in FRESHNESS_WINDOWS.items():
        field = getattr(Company, field_name)
        cutoff = now - max_age
        stale_count = (
            await session.execute(
                select(func.count(Company.id)).where(or_(field.is_(None), field < cutoff))
            )
        ).scalar() or 0
        domains.append(
            {
                "domain": domain,
                "stale_count": stale_count,
                "fresh_count": max(total_companies - stale_count, 0),
                "max_age_minutes": int(max_age.total_seconds() // 60),
            }
        )

    return {
        "generated_at": now,
        "total_companies": total_companies,
        "domains": domains,
    }
