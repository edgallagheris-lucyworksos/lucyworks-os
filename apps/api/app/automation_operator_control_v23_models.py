from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationOperatorActionV23(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("action_ref", name="uq_automationoperatoractionv23_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    action_ref: str = Field(index=True)
    action_type: str = Field(index=True)
    premises_ref: str = Field(index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    target_type: str = Field(index=True)
    target_ref: str = Field(index=True)
    reason: str
    acknowledgement: Optional[str] = None
    previous_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    result_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    actor_auth_source: str
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
