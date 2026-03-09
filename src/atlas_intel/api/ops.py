"""Operational endpoints for sync jobs and freshness visibility."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.schemas.ops import (
    FreshnessSummaryResponse,
    SyncJobResponse,
    SyncJobRunResponse,
)
from atlas_intel.services.ops_service import (
    get_freshness_summary,
    get_sync_job,
    list_job_runs,
    list_sync_jobs,
)

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/jobs", response_model=list[SyncJobResponse])
async def jobs(
    session: AsyncSession = Depends(get_session),
) -> list[SyncJobResponse]:
    """List configured sync jobs."""
    jobs = await list_sync_jobs(session)
    return [SyncJobResponse.model_validate(job) for job in jobs]


@router.get("/jobs/{job_id}/runs", response_model=list[SyncJobRunResponse])
async def job_runs(
    job_id: int,
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[SyncJobRunResponse]:
    """List recent runs for a sync job."""
    job = await get_sync_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Sync job not found: {job_id}")

    runs = await list_job_runs(session, job_id, limit=limit)
    return [SyncJobRunResponse.model_validate(run) for run in runs]


@router.get("/freshness", response_model=FreshnessSummaryResponse)
async def freshness(
    session: AsyncSession = Depends(get_session),
) -> FreshnessSummaryResponse:
    """Get sync freshness summary across all company domains."""
    summary = await get_freshness_summary(session)
    return FreshnessSummaryResponse(**summary)
