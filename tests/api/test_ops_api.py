"""API tests for operational endpoints."""

from datetime import timedelta

import pytest

from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.sync_job import SyncJob
from atlas_intel.models.sync_job_run import SyncJobRun


@pytest.fixture
async def seeded_ops(session):
    company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(company)
    await session.flush()

    job = SyncJob(
        name="daily-market-aapl",
        sync_type="market_data",
        tickers=["AAPL"],
        interval_minutes=1440,
        years=3,
        force=False,
        enabled=True,
        next_run_at=utcnow() + timedelta(hours=1),
        last_status="success",
    )
    session.add(job)
    await session.flush()

    run = SyncJobRun(
        job_id=job.id,
        sync_type=job.sync_type,
        status="success",
        started_at=utcnow() - timedelta(minutes=2),
        finished_at=utcnow() - timedelta(minutes=1),
        requested_tickers=["AAPL"],
        result_summary={"results": {"AAPL": {"profile": True, "prices": 10, "metrics": 6}}},
    )
    session.add(run)
    await session.commit()
    return {"job_id": job.id}


class TestOpsAPI:
    async def test_list_jobs(self, client, seeded_ops):
        resp = await client.get("/api/v1/ops/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "daily-market-aapl"

    async def test_list_job_runs(self, client, seeded_ops):
        resp = await client.get(f"/api/v1/ops/jobs/{seeded_ops['job_id']}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "success"

    async def test_freshness(self, client, seeded_ops):
        resp = await client.get("/api/v1/ops/freshness")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_companies" in data
        assert "domains" in data
        assert any(d["domain"] == "submissions" for d in data["domains"])
