"""Alert event model."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class AlertEvent(TimestampMixin, Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id", ondelete="CASCADE"))
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )
    triggered_at: Mapped[datetime] = mapped_column()
    rule_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(500))
    detail: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    acknowledged: Mapped[bool] = mapped_column(Boolean, server_default="false")
    acknowledged_at: Mapped[datetime | None] = mapped_column()

    rule: Mapped["AlertRule"] = relationship(back_populates="events")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        Index("ix_alert_events_company_triggered", "company_id", "triggered_at"),
        Index("ix_alert_events_rule_triggered", "rule_id", "triggered_at"),
        Index("ix_alert_events_ack_triggered", "acknowledged", "triggered_at"),
    )

    def __repr__(self) -> str:
        return f"<AlertEvent {self.id}: {self.title} ({self.severity})>"
