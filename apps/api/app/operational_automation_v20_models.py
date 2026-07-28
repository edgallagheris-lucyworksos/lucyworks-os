from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationDecisionV20(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("decision_ref", name="uq_automationdecisionv20_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    decision_ref: str = Field(index=True)
    action_fingerprint: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    trigger_type: str = Field(index=True)
    trigger_ref: str = Field(index=True)
    trigger_facts: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    proposals: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    commit_requested: bool = False
    committed: bool = Field(default=False, index=True)
    replayed: bool = False
    outcome: str = Field(default="proposed", index=True)
    created_work_item_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    actor_auth_source: str
    reason: str
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
