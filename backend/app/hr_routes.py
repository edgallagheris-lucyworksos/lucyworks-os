from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.hr_models import (
    AbsenceRecord,
    CompetencyRecord,
    FatigueRiskRecord,
    HRApprovalGate,
    LeaveRequest,
    OnCallAssignment,
    OvertimeRequest,
    StaffProfile,
)
from app.models import AuditEvent, Shift, StaffMember

router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str):
    session.add(AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary))
    session.commit()


class ProfilePayload(BaseModel):
    staff_member_id: int
    employment_type: str = "employed"
    contract_hours_per_week: float = 40.0
    primary_department: str = "Hospital"
    seniority: str = "standard"
    line_manager: str = ""
    actor_name: str = "System"


class CompetencyPayload(BaseModel):
    staff_member_id: int
    competency: str
    department: str = "Hospital"
    expires_at: datetime | None = None
    evidence_note: str = ""
    actor_name: str = "System"


class CompetencyApprovalPayload(BaseModel):
    reviewer_name: str
    decision_note: str = ""
    actor_name: str = "System"


class LeavePayload(BaseModel):
    staff_member_id: int
    leave_type: str = "annual_leave"
    starts_at: datetime
    ends_at: datetime
    reason: str = ""
    actor_name: str = "System"


class LeaveDecisionPayload(BaseModel):
    reviewer_name: str
    approve: bool = True
    decision_note: str = ""
    actor_name: str = "System"


class OvertimePayload(BaseModel):
    staff_member_id: int
    shift_id: int | None = None
    hours: float
    reason: str
    actor_name: str = "System"


class OvertimeDecisionPayload(BaseModel):
    reviewer_name: str
    approve: bool = True
    decision_note: str = ""
    actor_name: str = "System"


class OnCallPayload(BaseModel):
    staff_member_id: int
    department: str = "Hospital"
    starts_at: datetime
    ends_at: datetime
    escalation_role: str = "on_call"
    actor_name: str = "System"


class AbsencePayload(BaseModel):
    staff_member_id: int
    absence_type: str = "sickness"
    starts_at: datetime
    notes: str = ""
    actor_name: str = "System"


@router.post("/api/hr/profiles")
def create_or_update_profile(payload: ProfilePayload, session: Session = Depends(get_session)):
    staff = session.get(StaffMember, payload.staff_member_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    profile = session.exec(select(StaffProfile).where(StaffProfile.staff_member_id == payload.staff_member_id)).first()
    if not profile:
        profile = StaffProfile(staff_member_id=payload.staff_member_id)
    profile.employment_type = payload.employment_type
    profile.contract_hours_per_week = payload.contract_hours_per_week
    profile.primary_department = payload.primary_department
    profile.seniority = payload.seniority
    profile.line_manager = payload.line_manager
    profile.updated_at = utc_now()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    audit(session, payload.actor_name, "updated", "staff_profile", profile.id or 0, "Updated staff profile")
    return profile


@router.post("/api/hr/competencies")
def create_competency(payload: CompetencyPayload, session: Session = Depends(get_session)):
    competency = CompetencyRecord(**payload.model_dump(exclude={"actor_name"}))
    session.add(competency)
    session.commit()
    session.refresh(competency)
    audit(session, payload.actor_name, "created", "competency", competency.id or 0, f"Competency {payload.competency}")
    return competency


@router.post("/api/hr/competencies/{competency_id}/approve")
def approve_competency(competency_id: int, payload: CompetencyApprovalPayload, session: Session = Depends(get_session)):
    competency = session.get(CompetencyRecord, competency_id)
    if not competency:
        raise HTTPException(status_code=404, detail="Competency not found")
    competency.status = "approved"
    competency.signed_off_by = payload.reviewer_name
    competency.signed_off_at = utc_now()
    session.add(competency)
    session.commit()
    session.refresh(competency)
    audit(session, payload.actor_name, "approved", "competency", competency_id, payload.decision_note or "Competency approved")
    return competency


@router.post("/api/hr/leave")
def create_leave_request(payload: LeavePayload, session: Session = Depends(get_session)):
    leave = LeaveRequest(**payload.model_dump(exclude={"actor_name"}))
    session.add(leave)
    session.commit()
    session.refresh(leave)
    audit(session, payload.actor_name, "created", "leave_request", leave.id or 0, f"{payload.leave_type} request")
    return leave


@router.post("/api/hr/leave/{leave_id}/decision")
def decide_leave(leave_id: int, payload: LeaveDecisionPayload, session: Session = Depends(get_session)):
    leave = session.get(LeaveRequest, leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    leave.status = "approved" if payload.approve else "declined"
    leave.reviewer_name = payload.reviewer_name
    leave.decision_note = payload.decision_note
    leave.decided_at = utc_now()
    session.add(leave)
    session.commit()
    session.refresh(leave)
    audit(session, payload.actor_name, leave.status, "leave_request", leave_id, payload.decision_note or leave.status)
    return leave


@router.post("/api/hr/overtime")
def create_overtime_request(payload: OvertimePayload, session: Session = Depends(get_session)):
    overtime = OvertimeRequest(**payload.model_dump(exclude={"actor_name"}))
    session.add(overtime)
    session.commit()
    session.refresh(overtime)
    audit(session, payload.actor_name, "created", "overtime_request", overtime.id or 0, payload.reason)
    return overtime


@router.post("/api/hr/overtime/{request_id}/decision")
def decide_overtime(request_id: int, payload: OvertimeDecisionPayload, session: Session = Depends(get_session)):
    overtime = session.get(OvertimeRequest, request_id)
    if not overtime:
        raise HTTPException(status_code=404, detail="Overtime request not found")
    overtime.status = "approved" if payload.approve else "declined"
    overtime.reviewer_name = payload.reviewer_name
    overtime.decision_note = payload.decision_note
    overtime.decided_at = utc_now()
    session.add(overtime)
    session.commit()
    session.refresh(overtime)
    audit(session, payload.actor_name, overtime.status, "overtime_request", request_id, payload.decision_note or overtime.status)
    return overtime


@router.post("/api/hr/on-call")
def create_on_call(payload: OnCallPayload, session: Session = Depends(get_session)):
    assignment = OnCallAssignment(**payload.model_dump(exclude={"actor_name"}))
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    audit(session, payload.actor_name, "created", "on_call_assignment", assignment.id or 0, f"On-call for {payload.department}")
    return assignment


@router.post("/api/hr/absence")
def create_absence(payload: AbsencePayload, session: Session = Depends(get_session)):
    absence = AbsenceRecord(**payload.model_dump(exclude={"actor_name"}))
    session.add(absence)
    session.commit()
    session.refresh(absence)
    audit(session, payload.actor_name, "created", "absence", absence.id or 0, payload.absence_type)
    return absence


@router.post("/api/hr/fatigue/evaluate/{staff_member_id}")
def evaluate_fatigue(staff_member_id: int, actor_name: str = "System", session: Session = Depends(get_session)):
    now = utc_now()
    since = now - timedelta(hours=72)
    shifts = session.exec(select(Shift).where(Shift.staff_member_id == staff_member_id, Shift.starts_at >= since)).all()
    on_call = session.exec(select(OnCallAssignment).where(OnCallAssignment.staff_member_id == staff_member_id, OnCallAssignment.starts_at >= since)).all()
    overtime = session.exec(select(OvertimeRequest).where(OvertimeRequest.staff_member_id == staff_member_id, OvertimeRequest.status == "approved")).all()

    total_shift_hours = 0.0
    for shift in shifts:
        if shift.ends_at and shift.starts_at:
            total_shift_hours += (shift.ends_at - shift.starts_at).total_seconds() / 3600

    total_overtime = sum(x.hours for x in overtime)
    reasons = []
    level = "LOW"

    if total_shift_hours > 55:
        level = "MED"
        reasons.append(f"{round(total_shift_hours,1)} hours worked in 72h")

    if len(on_call) >= 3:
        level = "HIGH"
        reasons.append(f"{len(on_call)} on-call assignments in 72h")

    if total_overtime > 12:
        level = "HIGH"
        reasons.append(f"{round(total_overtime,1)} overtime hours approved")

    risk = FatigueRiskRecord(staff_member_id=staff_member_id, risk_level=level, reasons=" | ".join(reasons) if reasons else "within threshold")
    session.add(risk)

    if level in {"MED", "HIGH"}:
        gate = HRApprovalGate(
            gate_name="fatigue_risk",
            staff_member_id=staff_member_id,
            entity_type="fatigue",
            severity="red" if level == "HIGH" else "amber",
            reasons=risk.reasons,
        )
        session.add(gate)

    session.commit()
    session.refresh(risk)
    audit(session, actor_name, "evaluated", "fatigue_risk", risk.id or 0, risk.reasons)
    return {
        "risk": risk,
        "summary": {
            "shift_hours_72h": round(total_shift_hours, 1),
            "on_call_count_72h": len(on_call),
            "approved_overtime_hours": round(total_overtime, 1),
        },
    }


@router.get("/api/hr")
def get_hr_overview(session: Session = Depends(get_session)):
    return {
        "profiles": session.exec(select(StaffProfile)).all(),
        "competencies": session.exec(select(CompetencyRecord).order_by(CompetencyRecord.created_at.desc())).all(),
        "leave_requests": session.exec(select(LeaveRequest).order_by(LeaveRequest.created_at.desc())).all(),
        "absence_records": session.exec(select(AbsenceRecord).order_by(AbsenceRecord.created_at.desc())).all(),
        "overtime_requests": session.exec(select(OvertimeRequest).order_by(OvertimeRequest.requested_at.desc())).all(),
        "on_call": session.exec(select(OnCallAssignment).order_by(OnCallAssignment.starts_at.desc())).all(),
        "fatigue_risks": session.exec(select(FatigueRiskRecord).order_by(FatigueRiskRecord.created_at.desc())).all(),
        "approval_gates": session.exec(select(HRApprovalGate).order_by(HRApprovalGate.created_at.desc())).all(),
    }
