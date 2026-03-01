"""Seed script to ingest a starter set of companies."""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)

SEED_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]


async def main() -> None:
    from atlas_intel.database import async_session
    from atlas_intel.ingestion.pipeline import run_full_sync

    async with async_session() as session:
        results = await run_full_sync(session, SEED_TICKERS)
        for ticker, counts in results.items():
            print(f"  {ticker}: {counts}")

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
