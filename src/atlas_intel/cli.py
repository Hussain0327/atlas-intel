"""CLI for running ingestion pipeline."""

import asyncio
import logging
import sys
from typing import Annotated

import typer

app = typer.Typer(name="atlas", help="Atlas Intel — Company & Market Intelligence CLI")
jobs_app = typer.Typer(help="Manage scheduled sync jobs")
app.add_typer(jobs_app, name="jobs")
alerts_app = typer.Typer(help="Manage alert rules and events")
app.add_typer(alerts_app, name="alerts")


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


@app.command()
def report(
    ticker: Annotated[str, typer.Argument(help="Company ticker")],
    report_type: Annotated[str, typer.Option(help="comprehensive or quick")] = "comprehensive",
    output: Annotated[str | None, typer.Option(help="Output file path")] = None,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Generate an LLM-powered company report."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.company_service import get_company_by_identifier
        from atlas_intel.services.report_service import generate_company_report

        async with async_session() as session:
            company = await get_company_by_identifier(session, ticker)
            if not company:
                typer.echo(f"Company not found: {ticker}", err=True)
                raise typer.Exit(1)

            typer.echo(f"Generating {report_type} report for {ticker}...")
            result = await generate_company_report(
                session,
                company.id,
                company.ticker or ticker,
                company.name,
                report_type,
            )
            if output:
                with open(output, "w") as f:
                    f.write(result.content)
                typer.echo(f"Report written to {output}")
            else:
                typer.echo(result.content)

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@app.command()
def query(
    question: Annotated[str, typer.Argument(help="Natural language question")],
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Ask a natural language question about companies and markets."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.query_service import process_natural_language_query

        async with async_session() as session:
            result = await process_natural_language_query(session, question)
            typer.echo(result.answer)
            if result.tools_used:
                typer.echo(f"\nTools used: {', '.join(result.tools_used)}", err=True)

    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@alerts_app.command("list")
def alerts_list(
    company_id: Annotated[int | None, typer.Option(help="Filter by company ID")] = None,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """List alert rules."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.alert_service import list_alert_rules

        async with async_session() as session:
            rules = await list_alert_rules(session, company_id=company_id)
            for rule in rules:
                typer.echo(
                    f"  {rule.id}: {rule.name} [{rule.rule_type}] "
                    f"enabled={rule.enabled} triggers={rule.trigger_count}"
                )
            if not rules:
                typer.echo("  No alert rules configured")

    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@alerts_app.command("create")
def alerts_create(
    name: Annotated[str, typer.Option(help="Rule name")],
    rule_type: Annotated[str, typer.Option(help="Rule type (price_threshold, volume_spike, etc.)")],
    conditions: Annotated[str, typer.Option(help="JSON conditions string")],
    company_id: Annotated[int | None, typer.Option(help="Company ID (null for global)")] = None,
    cooldown: Annotated[int, typer.Option(help="Cooldown in minutes")] = 60,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Create an alert rule."""
    import json

    setup_logging(log_level)

    try:
        conds = json.loads(conditions)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON conditions: {exc}", err=True)
        raise typer.Exit(1) from None

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.schemas.alert import AlertRuleCreate
        from atlas_intel.services.alert_service import create_alert_rule

        async with async_session() as session:
            data = AlertRuleCreate(
                company_id=company_id,
                name=name,
                rule_type=rule_type,
                conditions=conds,
                cooldown_minutes=cooldown,
            )
            rule = await create_alert_rule(session, data)
            typer.echo(f"Created alert rule {rule.id}: {rule.name}")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@alerts_app.command("events")
def alerts_events(
    limit: Annotated[int, typer.Option(help="Max events to show")] = 20,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """List recent alert events."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.alert_service import list_alert_events

        async with async_session() as session:
            events, total, unack = await list_alert_events(session, limit=limit)
            typer.echo(f"Total events: {total} ({unack} unacknowledged)")
            for event in events:
                ack = "ACK" if event.acknowledged else "NEW"
                typer.echo(
                    f"  [{ack}] {event.triggered_at.isoformat()} [{event.severity}] {event.title}"
                )

    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@alerts_app.command("check")
def alerts_check(
    company_id: Annotated[int | None, typer.Option(help="Check rules for specific company")] = None,
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Manually evaluate all alert rules."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.alert_service import check_alerts_for_company, check_all_alerts

        async with async_session() as session:
            if company_id is not None:
                events = await check_alerts_for_company(session, company_id)
            else:
                events = await check_all_alerts(session)

            if events:
                typer.echo(f"Triggered {len(events)} alert(s):")
                for event in events:
                    typer.echo(f"  [{event.severity}] {event.title}")
            else:
                typer.echo("No alerts triggered")

    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@app.command()
def dashboard(
    log_level: Annotated[str, typer.Option(help="Log level")] = "INFO",
) -> None:
    """Print market dashboard summary."""
    setup_logging(log_level)

    async def _run() -> None:
        from atlas_intel.database import async_session
        from atlas_intel.services.dashboard_service import get_full_dashboard_cached

        async with async_session() as session:
            dash = await get_full_dashboard_cached(session)

            typer.echo("=== Market Overview ===")
            typer.echo(
                f"  Companies: {dash.market_overview.total_companies} "
                f"(with prices: {dash.market_overview.companies_with_prices})"
            )
            for sector in dash.market_overview.sectors[:10]:
                typer.echo(
                    f"  {sector.sector}: {sector.company_count} companies"
                    + (f", avg PE={sector.avg_pe:.1f}" if sector.avg_pe else "")
                )

            typer.echo("\n=== Top Movers ===")
            if dash.top_movers.gainers:
                typer.echo("  Gainers:")
                for m in dash.top_movers.gainers[:5]:
                    typer.echo(f"    {m.ticker}: +{m.change_pct:.1f}% (${m.value:.2f})")
            if dash.top_movers.losers:
                typer.echo("  Losers:")
                for m in dash.top_movers.losers[:5]:
                    typer.echo(f"    {m.ticker}: {m.change_pct:.1f}% (${m.value:.2f})")

            typer.echo("\n=== Alerts ===")
            a = dash.alert_summary
            typer.echo(f"  Rules: {a.active_rules}/{a.total_rules} active")
            typer.echo(
                f"  Events: {a.total_events_24h} (24h), "
                f"{a.total_events_7d} (7d), "
                f"{a.critical_events_24h} critical"
            )

    try:
        asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    app()
