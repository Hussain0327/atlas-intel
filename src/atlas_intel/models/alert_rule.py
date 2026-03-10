"""Alert rule model."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class AlertRule(TimestampMixin, Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200))
    rule_type: Mapped[str] = mapped_column(String(50))
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    cooldown_minutes: Mapped[int] = mapped_column(Integer, server_default="60")
    last_triggered_at: Mapped[datetime | None] = mapped_column()
    trigger_count: Mapped[int] = mapped_column(Integer, server_default="0")

    company: Mapped["Company | None"] = relationship(back_populates="alert_rules")  # type: ignore[name-defined] # noqa: F821
    events: Mapped[list["AlertEvent"]] = relationship(back_populates="rule")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        Index("ix_alert_rules_company_enabled", "company_id", "enabled"),
        Index("ix_alert_rules_rule_type", "rule_type"),
    )

    def __repr__(self) -> str:
        return f"<AlertRule {self.id}: {self.name} ({self.rule_type})>"
