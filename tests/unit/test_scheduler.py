"""Tests for background scheduler configuration and job error handling."""

from unittest.mock import AsyncMock, MagicMock, patch

from atlas_intel.scheduler import (
    check_alerts_job,
    create_scheduler,
    get_scheduler_status,
    sync_macro_job,
)


def test_create_scheduler_has_expected_jobs():
    """Scheduler creates the expected number of jobs."""
    scheduler = create_scheduler()
    jobs = scheduler.get_jobs()
    job_ids = {j.id for j in jobs}

    assert "sync_market" in job_ids
    assert "sync_alt" in job_ids
    assert "sync_sec" in job_ids
    assert "sync_transcripts" in job_ids
    assert "sync_macro" in job_ids
    assert "check_alerts" in job_ids
    assert len(jobs) == 6


def test_get_scheduler_status_none():
    """Returns empty status when scheduler is None."""
    status = get_scheduler_status(None)
    assert status["running"] is False
    assert status["jobs"] == []


def test_get_scheduler_status_with_scheduler():
    """Returns job info when scheduler is configured."""
    scheduler = create_scheduler()
    status = get_scheduler_status(scheduler)
    assert status["running"] is False  # not started
    assert len(status["jobs"]) == 6
    for job in status["jobs"]:
        assert "id" in job
        assert "name" in job


def _mock_async_session():
    """Create a mock async session context manager."""
    mock_session = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_cm)
    return mock_factory, mock_session


async def test_check_alerts_job_handles_errors():
    """Alert check job catches exceptions gracefully."""
    mock_factory, _mock_sess = _mock_async_session()

    with (
        patch("atlas_intel.database.async_session", mock_factory),
        patch(
            "atlas_intel.services.alert_service.check_all_alerts",
            new_callable=AsyncMock,
            side_effect=Exception("DB down"),
        ),
    ):
        # Should not raise
        await check_alerts_job()


async def test_sync_macro_job_calls_pipeline():
    """Macro sync job calls the pipeline function."""
    mock_factory, _mock_sess = _mock_async_session()

    with (
        patch("atlas_intel.database.async_session", mock_factory),
        patch(
            "atlas_intel.ingestion.pipeline.run_macro_sync",
            new_callable=AsyncMock,
            return_value={"GDP": 100},
        ) as mock_sync,
    ):
        await sync_macro_job()
        mock_sync.assert_called_once()
