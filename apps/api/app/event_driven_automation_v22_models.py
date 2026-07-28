from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationRuntimeConfigV22(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("config_ref", name="uq_automationruntimeconfigv22_ref"),
        UniqueConstraint("premises_ref", name="uq_automationruntimeconfigv22_premises"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    config_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    mode: str = Field(default="disabled", index=True)
    enabled_trigger_types: list[str] = Field(
        default_factory=lambda: ["observation", "critical_result", "evidence_gap", "operational_delay"],
        sa_column=Column(JSON, nullable=False),
    )
    service_subject: str = Field(default="lucyworks:automation-v22", index=True)
    service_name: str = "LucyWorks governed automation"
    service_role: str = Field(default="senior_clinician", index=True)
    background_scan_enabled: bool = False
    scan_interval_seconds: int = 60
    version: int = 1
    updated_by_subject: str = Field(default="system", index=True)
    updated_by_name: str = "system"
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class AutomationTriggerV22(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("trigger_ref", name="uq_automationtriggerv22_ref"),
        UniqueConstraint(
            "source_type",
            "source_ref",
            "source_state_hash",
            "mode",
            name="uq_automationtriggerv22_source_state_mode",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    trigger_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    source_type: str = Field(index=True)
    source_ref: str = Field(index=True)
    source_version: Optional[int] = Field(default=None, index=True)
    source_state_hash: str = Field(index=True)
    mode: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    attempts: int = 0
    decision_ref: Optional[str] = Field(default=None, index=True)
    decision_outcome: Optional[str] = Field(default=None, index=True)
    work_item_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    source_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    initiated_by_subject: str = Field(default="system", index=True)
    initiated_by_name: str = "system"
    initiated_by_role: str = Field(default="system", index=True)
    error_code: Optional[str] = Field(default=None, index=True)
    error_detail: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    started_at: Optional[datetime] = Field(default=None, index=True)
    processed_at: Optional[datetime] = Field(default=None, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
