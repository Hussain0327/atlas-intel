"""CLI for running ingestion pipeline."""

import asyncio
import logging
import sys
from typing import Annotated

import typer

app = typer.Typer(name="atlas", help="Atlas Intel — Company & Market Intelligence CLI")
jobs_app = typer.Typer(help="Manage scheduled sync jobs")
app.add_typer(jobs_app, name="jobs")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


@app.command()
def sync(
    ticker: Annotated[list[str] | None, typer.Option(help="Ticker(s) to sync")] = None,
    force: Annotated[bool, typer.Option(help="Force refresh even if recently synced")] = False,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Sync SEC EDGAR data for specified companies."""
    setup_logging(log_level)

    if not ticker:
        typer.echo("No tickers specified. Use --ticker AAPL --ticker MSFT")
        raise typer.Exit(1)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_full_sync

        async with async_session() as session:
            results = await run_full_sync(session, ticker, force=force)
            for t, counts in results.items():
                if "error" in counts:
                    typer.echo(f"  {t}: NOT FOUND")
                else:
                    typer.echo(f"  {t}: {counts['filings']} filings, {counts['facts']} facts")

    typer.echo(f"Syncing {len(ticker)} company(ies)...")
    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("Done.")


@app.command()
def sync_tickers(
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Sync only the CIK-ticker mapping from SEC."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_ticker_sync

        async with async_session() as session:
            count = await run_ticker_sync(session)
            typer.echo(f"Synced {count} companies")

    typer.echo("Syncing ticker mapping...")
    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("Done.")


@app.command()
def sync_transcripts(
    ticker: Annotated[list[str] | None, typer.Option(help="Ticker(s) to sync")] = None,
    years: Annotated[int, typer.Option(help="Number of years to look back")] = 3,
    force: Annotated[bool, typer.Option(help="Force refresh even if recently synced")] = False,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Sync earnings call transcripts and run NLP analysis."""
    setup_logging(log_level)

    if not ticker:
        typer.echo("No tickers specified. Use --ticker AAPL --ticker MSFT")
        raise typer.Exit(1)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_transcript_sync

        async with async_session() as session:
            results = await run_transcript_sync(session, ticker, years=years, force=force)
            for t, count in results.items():
                typer.echo(f"  {t}: {count} transcripts processed")

    typer.echo(f"Syncing transcripts for {len(ticker)} company(ies) (last {years} years)...")
    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("Done.")


@app.command()
def sync_market(
    ticker: Annotated[list[str] | None, typer.Option(help="Ticker(s) to sync")] = None,
    years: Annotated[int, typer.Option(help="Number of years of price history")] = 5,
    force: Annotated[bool, typer.Option(help="Force refresh even if recently synced")] = False,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Sync market data (profile, prices, metrics) from FMP."""
    setup_logging(log_level)

    if not ticker:
        typer.echo("No tickers specified. Use --ticker AAPL --ticker MSFT")
        raise typer.Exit(1)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_market_data_sync

        async with async_session() as session:
            results = await run_market_data_sync(session, ticker, years=years, force=force)
            for t, counts in results.items():
                if counts.get("error"):
                    typer.echo(f"  {t}: NOT FOUND")
                else:
                    typer.echo(
                        f"  {t}: profile={'updated' if counts['profile'] else 'skipped'}, "
                        f"{counts['prices']} prices, {counts['metrics']} metrics"
                    )

    typer.echo(f"Syncing market data for {len(ticker)} company(ies) (last {years} years)...")
    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("Done.")


@app.command()
def sync_alt(
    ticker: Annotated[list[str] | None, typer.Option(help="Ticker(s) to sync")] = None,
    force: Annotated[bool, typer.Option(help="Force refresh even if recently synced")] = False,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Sync alternative data (news, insider, estimates, grades, targets, holdings)."""
    setup_logging(log_level)

    if not ticker:
        typer.echo("No tickers specified. Use --ticker AAPL --ticker MSFT")
        raise typer.Exit(1)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_alt_data_sync

        async with async_session() as session:
            results = await run_alt_data_sync(session, ticker, force=force)
            for t, counts in results.items():
                if counts.get("error"):
                    typer.echo(f"  {t}: NOT FOUND")
                else:
                    typer.echo(
                        f"  {t}: {counts['news']} news, {counts['insider_trades']} insider, "
                        f"{counts['estimates']} estimates, {counts['grades']} grades, "
                        f"target={'updated' if counts['price_target'] else 'skipped'}, "
                        f"{counts['holdings']} holdings"
                    )

    typer.echo(f"Syncing alt data for {len(ticker)} company(ies)...")
    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("Done.")


@app.command()
def sync_macro(
    series: Annotated[str | None, typer.Option(help="Comma-separated series IDs")] = None,
    force: Annotated[bool, typer.Option(help="Force refresh even if recently synced")] = False,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Sync FRED macro indicators (GDP, UNRATE, DFF, etc.)."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.config import settings
        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_macro_sync

        series_ids = (series or settings.fred_series).split(",")
        async with async_session() as session:
            results = await run_macro_sync(session, series_ids, force=force)
            for s_id, count in results.items():
                typer.echo(f"  {s_id}: {count} observations")

    typer.echo("Syncing FRED macro indicators...")
    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("Done.")


@app.command()
def sync_expanded(
    ticker: Annotated[list[str] | None, typer.Option(help="Ticker(s) to sync")] = None,
    force: Annotated[bool, typer.Option(help="Force refresh even if recently synced")] = False,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Sync expanded data (8-K events, patents, congress trades)."""
    setup_logging(log_level)

    if not ticker:
        typer.echo("No tickers specified. Use --ticker AAPL --ticker MSFT")
        raise typer.Exit(1)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.ingestion.pipeline import run_expanded_sync

        async with async_session() as session:
            results = await run_expanded_sync(session, ticker, force=force)
            for t, counts in results.items():
                if counts.get("error"):
                    typer.echo(f"  {t}: NOT FOUND")
                else:
                    typer.echo(
                        f"  {t}: {counts['events']} events, "
                        f"{counts['patents']} patents, "
                        f"{counts['congress_trades']} congress trades"
                    )

    typer.echo(f"Syncing expanded data for {len(ticker)} company(ies)...")
    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("Done.")


@jobs_app.command("list")
def list_jobs(
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """List configured sync jobs."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.ops_service import list_sync_jobs

        async with async_session() as session:
            jobs = await list_sync_jobs(session)
            for job in jobs:
                typer.echo(
                    f"  {job.id}: {job.name} [{job.sync_type}] "
                    f"enabled={job.enabled} next={job.next_run_at.isoformat()} "
                    f"tickers={','.join(job.tickers)}"
                )
            if not jobs:
                typer.echo("  No jobs configured")

    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@jobs_app.command("create")
def create_job(
    name: Annotated[str, typer.Option(help="Unique job name")],
    sync_type: Annotated[
        str,
        typer.Option(help="One of: sec_full, transcripts, market_data, alt_data"),
    ],
    ticker: Annotated[list[str] | None, typer.Option(help="Ticker(s) to target")] = None,
    interval_minutes: Annotated[int, typer.Option(help="Run cadence in minutes")] = 1440,
    years: Annotated[
        int | None,
        typer.Option(help="Optional lookback years for transcripts/market"),
    ] = None,
    force: Annotated[bool, typer.Option(help="Force refresh when the job runs")] = False,
    disabled: Annotated[bool, typer.Option(help="Create job in disabled state")] = False,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Create a scheduled sync job."""
    setup_logging(log_level)

    if not ticker:
        typer.echo("No tickers specified. Use --ticker AAPL --ticker MSFT")
        raise typer.Exit(1)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.ops_service import create_sync_job

        async with async_session() as session:
            job = await create_sync_job(
                session,
                name=name,
                sync_type=sync_type,
                tickers=ticker,
                interval_minutes=interval_minutes,
                years=years,
                force=force,
                enabled=not disabled,
            )
            typer.echo(f"Created job {job.id}: {job.name}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@jobs_app.command("run-due")
def run_due(
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Run all enabled jobs that are due."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.ops_service import run_due_jobs

        async with async_session() as session:
            runs = await run_due_jobs(session)
            for run in runs:
                typer.echo(
                    f"  run={run.id} job={run.job_id} type={run.sync_type} status={run.status}"
                )
            if not runs:
                typer.echo("  No due jobs")

    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@jobs_app.command("run")
def run_job(
    job_id: Annotated[int, typer.Option(help="Job ID to run now")],
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Run a specific job immediately."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.ops_service import get_sync_job, run_sync_job

        async with async_session() as session:
            job = await get_sync_job(session, job_id)
            if not job:
                typer.echo(f"Job not found: {job_id}", err=True)
                raise typer.Exit(1)

            run = await run_sync_job(session, job)
            typer.echo(f"Completed run {run.id} with status={run.status}")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@jobs_app.command("runs")
def job_runs(
    job_id: Annotated[int, typer.Option(help="Job ID")],
    limit: Annotated[int, typer.Option(help="Number of runs to show")] = 20,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """List recent runs for a job."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.ops_service import get_sync_job, list_job_runs

        async with async_session() as session:
            job = await get_sync_job(session, job_id)
            if not job:
                typer.echo(f"Job not found: {job_id}", err=True)
                raise typer.Exit(1)

            runs = await list_job_runs(session, job_id, limit=limit)
            for run in runs:
                typer.echo(
                    f"  {run.id}: {run.status} started={run.started_at.isoformat()} "
                    f"finished={run.finished_at.isoformat() if run.finished_at else '-'}"
                )

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@app.command()
def freshness(
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Show sync freshness summary across company domains."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.ops_service import get_freshness_summary

        async with async_session() as session:
            summary = await get_freshness_summary(session)
            typer.echo(f"Total companies: {summary['total_companies']}")
            for domain in summary["domains"]:
                typer.echo(
                    f"  {domain['domain']}: fresh={domain['fresh_count']} "
                    f"stale={domain['stale_count']} max_age_m={domain['max_age_minutes']}"
                )

    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    app()
