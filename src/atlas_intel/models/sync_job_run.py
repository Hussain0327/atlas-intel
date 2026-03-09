"""Execution records for scheduled sync jobs."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base


class SyncJobRun(Base):
    __tablename__ = "sync_job_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("sync_jobs.id", ondelete="CASCADE"))
    sync_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    requested_tickers: Mapped[list[str]] = mapped_column(JSON, default=list)
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)

    job: Mapped["SyncJob"] = relationship(back_populates="runs")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        Index("ix_sync_job_runs_job_started", "job_id", "started_at"),
        Index("ix_sync_job_runs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<SyncJobRun job={self.job_id} status={self.status}>"
