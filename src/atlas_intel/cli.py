"""CLI for running ingestion pipeline."""

import asyncio
import logging
import sys
from typing import Annotated

import typer

app = typer.Typer(name="atlas", help="Atlas Intel — Company & Market Intelligence CLI")


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
    asyncio.run(_run())
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
    asyncio.run(_run())
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
    asyncio.run(_run())
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
    asyncio.run(_run())
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
    asyncio.run(_run())
    typer.echo("Done.")


if __name__ == "__main__":
    app()
