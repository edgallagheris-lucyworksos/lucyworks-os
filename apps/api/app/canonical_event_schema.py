from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class SubjectRef(BaseModel):
    kind: str = Field(min_length=1, max_length=64)
    ref: str = Field(min_length=1, max_length=256)


class CanonicalEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}")
    event_type: str = Field(pattern=r"^[a-z0-9_]+\.[a-z0-9_]+$")
    schema_version: int = Field(default=1, ge=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    organisation_ref: str
    site_ref: str
    premises_ref: str
    subjects: list[SubjectRef] = Field(default_factory=list)
    actor_ref: str | None = None
    source: str
    correlation_id: str
    causation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


def event_name_is_fact(event_type: str) -> bool:
    # Guard against command-like names leaking into the fact stream.
    banned = (".create", ".update", ".delete", ".set", ".do", ".request")
    return not event_type.endswith(banned)
