"""Scheduled sync job configuration."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class SyncJob(TimestampMixin, Base):
    __tablename__ = "sync_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    sync_type: Mapped[str] = mapped_column(String(50))
    tickers: Mapped[list[str]] = mapped_column(JSON, default=list)
    interval_minutes: Mapped[int] = mapped_column(Integer)
    years: Mapped[int | None] = mapped_column(Integer)
    force: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime]
    last_run_at: Mapped[datetime | None] = mapped_column()
    last_status: Mapped[str | None] = mapped_column(String(20))
    last_error: Mapped[str | None] = mapped_column(Text)

    runs: Mapped[list["SyncJobRun"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="job",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_sync_jobs_enabled_next_run", "enabled", "next_run_at"),
        Index("ix_sync_jobs_type", "sync_type"),
    )

    def __repr__(self) -> str:
        return f"<SyncJob {self.name} type={self.sync_type}>"
