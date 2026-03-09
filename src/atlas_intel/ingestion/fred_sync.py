"""Sync macro indicators from FRED."""

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.fred_client import FREDClient
from atlas_intel.ingestion.fred_transforms import parse_fred_observations
from atlas_intel.models.macro_indicator import MacroIndicator

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


async def sync_macro_indicators(
    session: AsyncSession,
    client: FREDClient,
    series_ids: list[str],
    force: bool = False,
) -> dict[str, int]:
    """Sync FRED macro indicators for the given series IDs.

    Freshness: skip if latest observation < 7 days old (most data is monthly/quarterly).
    Returns a dict of series_id -> upserted count.
    """
    results: dict[str, int] = {}

    for series_id in series_ids:
        series_id = series_id.strip().upper()

        # Check freshness: latest observation date for this series
        start_date: str | None = None
        if not force:
            latest_result = await session.execute(
                select(func.max(MacroIndicator.observation_date)).where(
                    MacroIndicator.series_id == series_id
                )
            )
            latest_date = latest_result.scalar_one_or_none()
            if latest_date:
                start_date = str(latest_date)

        logger.info("Fetching FRED series %s...", series_id)
        raw_data = await client.get_series_observations(series_id, start_date=start_date)
        observations = parse_fred_observations(raw_data, series_id)

        if not observations:
            results[series_id] = 0
            continue

        # In-batch dedup by (series_id, observation_date)
        seen: set[tuple[str, object]] = set()
        deduped: list[dict[str, Any]] = []
        for obs in observations:
            key = (obs["series_id"], obs["observation_date"])
            if key not in seen:
                seen.add(key)
                deduped.append(obs)
        observations = deduped

        total_upserted = 0
        for i in range(0, len(observations), BATCH_SIZE):
            batch = observations[i : i + BATCH_SIZE]

            stmt = pg_insert(MacroIndicator).values(batch)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_macro_indicator_series_date",
                set_={"value": stmt.excluded.value},
            )
            result = await session.execute(stmt)
            total_upserted += result.rowcount  # type: ignore[attr-defined]

        await session.commit()

        logger.info("Upserted %d observations for %s", total_upserted, series_id)
        results[series_id] = total_upserted

    return results
