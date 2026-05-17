from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StaffProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_member_id: int = Field(foreign_key="staffmember.id", index=True)
    employment_type: str = "employed"
    contract_hours_per_week: float = 40.0
    primary_department: str = "Hospital"
    seniority: str = "standard"
    line_manager: str = ""
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CompetencyRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_member_id: int = Field(foreign_key="staffmember.id", index=True)
    competency: str
    department: str = "Hospital"
    status: str = "pending"
    signed_off_by: str = ""
    signed_off_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    evidence_note: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class LeaveRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_member_id: int = Field(foreign_key="staffmember.id", index=True)
    leave_type: str = "annual_leave"
    starts_at: datetime
    ends_at: datetime
    status: str = "requested"
    reason: str = ""
    reviewer_name: Optional[str] = None
    decision_note: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    decided_at: Optional[datetime] = None


class AbsenceRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_member_id: int = Field(foreign_key="staffmember.id", index=True)
    absence_type: str = "sickness"
    starts_at: datetime
    ends_at: Optional[datetime] = None
    status: str = "open"
    return_to_work_required: bool = True
    return_to_work_completed: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    closed_at: Optional[datetime] = None


class OvertimeRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_member_id: int = Field(foreign_key="staffmember.id", index=True)
    shift_id: Optional[int] = Field(default=None, foreign_key="shift.id")
    hours: float
    reason: str
    status: str = "requested"
    requested_at: datetime = Field(default_factory=utc_now)
    reviewer_name: Optional[str] = None
    decision_note: Optional[str] = None
    decided_at: Optional[datetime] = None


class OnCallAssignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_member_id: int = Field(foreign_key="staffmember.id", index=True)
    department: str = "Hospital"
    starts_at: datetime
    ends_at: datetime
    status: str = "scheduled"
    escalation_role: str = "on_call"
    created_at: datetime = Field(default_factory=utc_now)


class FatigueRiskRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_member_id: int = Field(foreign_key="staffmember.id", index=True)
    risk_level: str = "LOW"
    reasons: str = ""
    measured_window_hours: int = 72
    open: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None


class HRApprovalGate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    gate_name: str
    staff_member_id: Optional[int] = Field(default=None, foreign_key="staffmember.id")
    entity_type: str
    entity_id: Optional[int] = None
    status: str = "open"
    severity: str = "amber"
    reasons: str = ""
    reviewer_name: Optional[str] = None
    decision_note: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    decided_at: Optional[datetime] = None
