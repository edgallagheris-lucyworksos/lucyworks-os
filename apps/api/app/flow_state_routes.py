from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.flow_state_models import (
    ComplianceGate,
    DischargeBlocker,
    MessagingTemplate,
    OccupancyRecord,
    SeverityGate,
    SpeechTarget,
    StaffAssignmentRisk,
)
from app.models import Admission, AuditEvent, Episode, Handover, ResultReview, StaffMember

router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def log(session: Session, actor: str, action: str, entity: str, entity_id: int, summary: str):
    session.add(AuditEvent(actor_name=actor, action=action, entity_type=entity, entity_id=entity_id, summary=summary))
    session.commit()


def row_dict(obj):
    mapper = getattr(obj, "__mapper__", None)
    if mapper is None:
        return obj
    return {col.key: getattr(obj, col.key) for col in mapper.columns}


def require_episode(session: Session, episode_id: int) -> Episode:
    episode = session.get(Episode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


class HandoverCreate(BaseModel):
    episode_id: int
    from_owner: str
    to_owner: str
    note: str
    actor_name: str = "System"


class ResultReviewCreate(BaseModel):
    episode_id: int
    result_type: str
    review_owner: str
    required_action: Optional[str] = None
    actor_name: str = "System"


class AdmissionCreate(BaseModel):
    episode_id: int
    admitted_to: str
    actor_name: str = "System"


class DischargeBlockerCreate(BaseModel):
    episode_id: int
    blocker_type: str
    detail: str
    owner_role: str = "clinician"
    severity: str = "amber"
    actor_name: str = "System"


class OccupancyCreate(BaseModel):
    episode_id: Optional[int] = None
    space_id: str
    space_type: str
    expected_release: Optional[datetime] = None
    actor_name: str = "System"


class SeverityGateRequest(BaseModel):
    episode_id: Optional[int] = None
    gate_name: str
    target_entity_type: str
    target_entity_id: Optional[int] = None
    triage_red_flags: bool = False
    safeguarding_escalation: bool = False
    rota_risk: str = "LOW"
    reviewer_name: Optional[str] = None
    override_reason: Optional[str] = None
    actor_name: str = "System"


class StaffAssignmentRiskRequest(BaseModel):
    episode_id: Optional[int] = None
    staff_member_id: Optional[int] = None
    role_required: str
    required_skills: list[str] = []
    current_load: int = 0
    max_cases_per_day: int = 1
    reviewer_name: Optional[str] = None
    override_reason: Optional[str] = None
    actor_name: str = "System"


@router.post("/api/flow/handovers")
def create_handover(payload: HandoverCreate, session: Session = Depends(get_session)):
    require_episode(session, payload.episode_id)
    row = Handover(episode_id=payload.episode_id, from_owner=payload.from_owner, to_owner=payload.to_owner, note=payload.note)
    session.add(row)
    session.commit()
    session.refresh(row)
    log(session, payload.actor_name, "created", "handover", row.id or 0, f"Handover created from {payload.from_owner} to {payload.to_owner}")
    return row_dict(row)


@router.post("/api/flow/handovers/{handover_id}/ack")
def acknowledge_handover(handover_id: int, actor_name: str = "System", session: Session = Depends(get_session)):
    row = session.get(Handover, handover_id)
    if not row:
        raise HTTPException(status_code=404, detail="Handover not found")
    row.acknowledged = True
    session.add(row)
    session.commit()
    session.refresh(row)
    log(session, actor_name, "acknowledged", "handover", row.id or 0, "Handover acknowledged by receiving owner")
    return row_dict(row)


@router.get("/api/flow/handovers")
def list_handovers(session: Session = Depends(get_session)):
    return session.exec(select(Handover).order_by(Handover.created_at.desc())).all()


@router.post("/api/flow/results")
def create_result_review(payload: ResultReviewCreate, session: Session = Depends(get_session)):
    require_episode(session, payload.episode_id)
    row = ResultReview(episode_id=payload.episode_id, result_type=payload.result_type, review_owner=payload.review_owner, required_action=payload.required_action)
    session.add(row)
    session.commit()
    session.refresh(row)
    log(session, payload.actor_name, "created", "result_review", row.id or 0, f"Result review created for {payload.result_type}")
    return row_dict(row)


@router.post("/api/flow/results/{result_id}/review")
def mark_result_reviewed(result_id: int, actor_name: str = "System", session: Session = Depends(get_session)):
    row = session.get(ResultReview, result_id)
    if not row:
        raise HTTPException(status_code=404, detail="Result review not found")
    row.status = "reviewed"
    row.reviewed_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    log(session, actor_name, "reviewed", "result_review", row.id or 0, "Result marked reviewed")
    return row_dict(row)


@router.get("/api/flow/results")
def list_result_reviews(session: Session = Depends(get_session)):
    return session.exec(select(ResultReview).order_by(ResultReview.id.desc())).all()


@router.post("/api/flow/admissions")
def create_admission(payload: AdmissionCreate, session: Session = Depends(get_session)):
    require_episode(session, payload.episode_id)
    row = Admission(episode_id=payload.episode_id, admitted_to=payload.admitted_to)
    session.add(row)
    session.commit()
    session.refresh(row)
    log(session, payload.actor_name, "created", "admission", row.id or 0, f"Admission created to {payload.admitted_to}")
    return row_dict(row)


@router.get("/api/flow/admissions")
def list_admissions(session: Session = Depends(get_session)):
    return session.exec(select(Admission).order_by(Admission.admitted_at.desc())).all()


@router.post("/api/flow/discharge-blockers")
def create_discharge_blocker(payload: DischargeBlockerCreate, session: Session = Depends(get_session)):
    require_episode(session, payload.episode_id)
    row = DischargeBlocker(episode_id=payload.episode_id, blocker_type=payload.blocker_type, detail=payload.detail, owner_role=payload.owner_role, severity=payload.severity)
    session.add(row)
    session.commit()
    session.refresh(row)
    log(session, payload.actor_name, "created", "discharge_blocker", row.id or 0, f"Discharge blocker created: {payload.blocker_type}")
    return row_dict(row)


@router.post("/api/flow/discharge-blockers/{blocker_id}/resolve")
def resolve_discharge_blocker(blocker_id: int, note: str = "Resolved", actor_name: str = "System", session: Session = Depends(get_session)):
    row = session.get(DischargeBlocker, blocker_id)
    if not row:
        raise HTTPException(status_code=404, detail="Discharge blocker not found")
    row.status = "resolved"
    row.resolved_at = utc_now()
    row.resolution_note = note
    session.add(row)
    session.commit()
    session.refresh(row)
    log(session, actor_name, "resolved", "discharge_blocker", row.id or 0, note)
    return row_dict(row)


@router.get("/api/flow/discharge-blockers")
def list_discharge_blockers(session: Session = Depends(get_session)):
    return session.exec(select(DischargeBlocker).order_by(DischargeBlocker.created_at.desc())).all()


@router.post("/api/flow/occupancy")
def create_occupancy(payload: OccupancyCreate, session: Session = Depends(get_session)):
    if payload.episode_id:
        require_episode(session, payload.episode_id)
    row = OccupancyRecord(space_id=payload.space_id, space_type=payload.space_type, episode_id=payload.episode_id, expected_release=payload.expected_release)
    session.add(row)
    session.commit()
    session.refresh(row)
    log(session, payload.actor_name, "created", "occupancy", row.id or 0, f"Occupancy created for {payload.space_id}")
    return row_dict(row)


@router.post("/api/flow/occupancy/{occupancy_id}/release")
def release_occupancy(occupancy_id: int, actor_name: str = "System", session: Session = Depends(get_session)):
    row = session.get(OccupancyRecord, occupancy_id)
    if not row:
        raise HTTPException(status_code=404, detail="Occupancy record not found")
    row.status = "cleaning"
    row.released_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    log(session, actor_name, "released", "occupancy", row.id or 0, "Occupancy released into cleaning state")
    return row_dict(row)


@router.get("/api/flow/occupancy")
def list_occupancy(session: Session = Depends(get_session)):
    return session.exec(select(OccupancyRecord).order_by(OccupancyRecord.created_at.desc())).all()


def evaluate_gate(payload: SeverityGateRequest):
    reasons = []
    severity = "MINOR"
    if payload.triage_red_flags:
        severity = "CRITICAL"
        reasons.append("Critical triage red flag present.")
    if payload.safeguarding_escalation:
        severity = "CRITICAL"
        reasons.append("Safeguarding escalation required.")
    elif payload.rota_risk.upper() == "HIGH" and severity != "CRITICAL":
        severity = "MODERATE"
        reasons.append("Rota risk is HIGH.")
    actions = {
        "MINOR": "Log and proceed.",
        "MODERATE": "Require reviewer identity + reason if overriding.",
        "CRITICAL": "Block LIVE until safeguarding acknowledged.",
    }
    return severity, actions[severity], reasons or ["No severity triggers"]


@router.post("/api/flow/severity-gates/evaluate")
def evaluate_severity_gate(payload: SeverityGateRequest, session: Session = Depends(get_session)):
    if payload.episode_id:
        require_episode(session, payload.episode_id)
    severity, action, reasons = evaluate_gate(payload)
    status = "passed" if severity == "MINOR" else "blocked"
    if severity == "MODERATE" and payload.reviewer_name and payload.override_reason:
        status = "overridden"
    row = SeverityGate(
        episode_id=payload.episode_id,
        gate_name=payload.gate_name,
        target_entity_type=payload.target_entity_type,
        target_entity_id=payload.target_entity_id,
        severity=severity,
        system_action=action,
        reasons=" | ".join(reasons),
        status=status,
        reviewer_name=payload.reviewer_name,
        override_reason=payload.override_reason,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    log(session, payload.actor_name, "evaluated", "severity_gate", row.id or 0, f"{payload.gate_name}: {severity} / {status}")
    return row_dict(row)


@router.get("/api/flow/severity-gates")
def list_severity_gates(session: Session = Depends(get_session)):
    return session.exec(select(SeverityGate).order_by(SeverityGate.created_at.desc())).all()


def split_skills(value: str) -> set[str]:
    return {x.strip() for x in str(value).split(",") if x.strip()}


@router.post("/api/flow/staff-assignment-risk")
def create_staff_assignment_risk(payload: StaffAssignmentRiskRequest, session: Session = Depends(get_session)):
    if payload.episode_id:
        require_episode(session, payload.episode_id)
    staff = session.get(StaffMember, payload.staff_member_id) if payload.staff_member_id else None
    staff_skills = split_skills(staff.skills) if staff else set()
    required = set(payload.required_skills)
    matched = sorted(required.intersection(staff_skills))
    max_cases = payload.max_cases_per_day or 1
    load_ratio = payload.current_load / max_cases
    rota_risk = "LOW" if load_ratio < 0.7 and matched else "MED"
    if not staff or not matched:
        rota_risk = "HIGH"
    if load_ratio >= 1:
        rota_risk = "HIGH"
    row = StaffAssignmentRisk(
        episode_id=payload.episode_id,
        staff_member_id=payload.staff_member_id,
        role_required=payload.role_required,
        required_skills=", ".join(payload.required_skills),
        matched_skills=", ".join(matched),
        skill_match_count=len(matched),
        load_ratio=load_ratio,
        rota_risk=rota_risk,
        status="approved" if rota_risk == "LOW" else "review_required",
        reviewer_name=payload.reviewer_name,
        override_reason=payload.override_reason,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    log(session, payload.actor_name, "evaluated", "staff_assignment_risk", row.id or 0, f"Staff assignment risk {rota_risk}")
    return row_dict(row)


@router.get("/api/flow/staff-assignment-risk")
def list_staff_assignment_risk(session: Session = Depends(get_session)):
    return session.exec(select(StaffAssignmentRisk).order_by(StaffAssignmentRisk.created_at.desc())).all()


@router.get("/api/flow/catalogues")
def flow_catalogues(session: Session = Depends(get_session)):
    return {
        "discharge_blockers": ["meds_not_ready", "review_pending", "owner_not_contacted", "notes_incomplete"],
        "room_states": ["ready", "occupied", "cleaning", "blocked", "reserved", "out_of_service"],
        "intake_statuses": ["received", "triaged", "booked", "arrived", "handed_over"],
        "alerts": ["overdue_result", "blocked_discharge", "room_unavailable", "staffing_gap", "unacknowledged_handover", "icu_pressure", "imaging_backlog", "cleaning_overrun"],
        "message_templates": session.exec(select(MessagingTemplate).where(MessagingTemplate.active == True)).all(),
        "speech_targets": session.exec(select(SpeechTarget).where(SpeechTarget.active == True)).all(),
        "compliance_controls": ["clinical_disclaimer_visible", "role_based_access", "consent_before_comms", "audit_all_access"],
    }


@router.get("/api/flow-state")
def flow_state(session: Session = Depends(get_session)):
    open_handovers = session.exec(select(Handover).where(Handover.acknowledged == False)).all()
    pending_results = session.exec(select(ResultReview).where(ResultReview.status == "pending_review")).all()
    open_discharge_blockers = session.exec(select(DischargeBlocker).where(DischargeBlocker.status == "open")).all()
    active_occupancy = session.exec(select(OccupancyRecord).where(OccupancyRecord.status != "released")).all()
    blocked_gates = session.exec(select(SeverityGate).where(SeverityGate.status == "blocked")).all()
    risky_staff = session.exec(select(StaffAssignmentRisk).where(StaffAssignmentRisk.rota_risk != "LOW")).all()
    return {
        "summary": {
            "unacknowledged_handovers": len(open_handovers),
            "pending_results": len(pending_results),
            "open_discharge_blockers": len(open_discharge_blockers),
            "active_occupancy": len(active_occupancy),
            "blocked_live_gates": len(blocked_gates),
            "staff_assignments_requiring_review": len(risky_staff),
        },
        "unacknowledged_handovers": open_handovers,
        "pending_results": pending_results,
        "open_discharge_blockers": open_discharge_blockers,
        "active_occupancy": active_occupancy,
        "blocked_live_gates": blocked_gates,
        "staff_assignments_requiring_review": risky_staff,
    }
