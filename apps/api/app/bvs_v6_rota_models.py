from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkforceShiftV6(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("premises_ref", "shift_ref", name="uq_workforce_shift_v6_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    premises_ref: str = Field(index=True)
    shift_ref: str = Field(index=True)
    staff_ref: str = Field(index=True)
    department_ref: str = Field(index=True)
    area_ref: Optional[str] = Field(default=None, index=True)
    starts_at: datetime = Field(index=True)
    ends_at: datetime = Field(index=True)
    shift_type: str = "standard"
    status: str = "planned"
    on_call: bool = False
    source_status: str = "draft"
    version: int = 1
    updated_by_actor_id: str
    updated_by_actor_name: str
    updated_at: datetime = Field(default_factory=utc_now)


class WorkforceAvailabilityExceptionV6(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("premises_ref", "exception_ref", name="uq_workforce_availability_exception_v6_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    premises_ref: str = Field(index=True)
    exception_ref: str = Field(index=True)
    staff_ref: str = Field(index=True)
    starts_at: datetime = Field(index=True)
    ends_at: datetime = Field(index=True)
    exception_type: str = "leave"
    status: str = "approved"
    detail: Optional[str] = None
    source_status: str = "draft"
    version: int = 1
    updated_by_actor_id: str
    updated_by_actor_name: str
    updated_at: datetime = Field(default_factory=utc_now)
