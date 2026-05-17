from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DepartmentDefinition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    lucy_module: str
    purpose: str
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DepartmentRole(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    department_code: str = Field(index=True)
    role_name: str
    created_at: datetime = Field(default_factory=utc_now)


class DepartmentEntity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    department_code: str = Field(index=True)
    entity_name: str
    created_at: datetime = Field(default_factory=utc_now)


class DepartmentWorkflowState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    department_code: str = Field(index=True)
    state_name: str
    state_order: int = 0
    created_at: datetime = Field(default_factory=utc_now)


class DepartmentConflictPattern(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    department_code: str = Field(index=True)
    conflict_name: str
    severity_default: str = "amber"
    created_at: datetime = Field(default_factory=utc_now)


class DepartmentDashboardNeed(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    department_code: str = Field(index=True)
    need_name: str
    created_at: datetime = Field(default_factory=utc_now)
