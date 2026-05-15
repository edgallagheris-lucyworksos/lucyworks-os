from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.flow_state_models import DischargeBlocker, SeverityGate, StaffAssignmentRisk
from app.inpatient_models import FinancialConsentStatus
from app.models import (
    AuditEvent,
    DischargeReadiness,
    Episode,
    Handover,
    OwnerCommsRequirement,
    PharmacyRequest,
    ResultReview,
    RoomState,
    ScheduleBlock,
)

router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str):
    session.add(AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary))
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


def record_gate(session: Session, *, episode_id: Optional[int], gate_name: str, target_entity_type: str, target_entity_id: Optional[int], severity: str, reasons: list[str], actor_name: str, reviewer_name: Optional[str] = None, override_reason: Optional[str] = None) -> SeverityGate:
    action = {
        "MINOR": "Log and proceed.",
        "MODERATE": "Require reviewer identity + reason if overriding.",
        "CRITICAL": "Block LIVE until resolved.",
    }[severity]
    status = "passed" if severity == "MINOR" else "blocked"
    if severity == "MODERATE" and reviewer_name and override_reason:
        status = "overridden"
    gate = SeverityGate(
        episode_id=episode_id,
        gate_name=gate_name,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        severity=severity,
        system_action=action,
        reasons=" | ".join(reasons) if reasons else "No gate issues",
        status=status,
        reviewer_name=reviewer_name,
        override_reason=override_reason,
    )
    session.add(gate)
    session.commit()
    session.refresh(gate)
    audit(session, actor_name, "evaluated", "severity_gate", gate.id or 0, f"{gate_name}: {severity} / {status}")
    return gate


def reject_with_gate(gate: SeverityGate, reasons: list[str]):
    raise HTTPException(status_code=409, detail={
        "blocked": True,
        "gate_id": gate.id,
        "gate_name": gate.gate_name,
        "severity": gate.severity,
        "system_action": gate.system_action,
        "reasons": reasons,
    })


class ActorPayload(BaseModel):
    actor_name: str = "System"
    reviewer_name: Optional[str] = None
    override_reason: Optional[str] = None


class ClinicalTaskPayload(ActorPayload):
    responsible_clinician: Optional[str] = None


@router.post("/api/live-actions/discharge/{episode_id}/approve")
def approve_discharge(episode_id: int, payload: ActorPayload, session: Session = Depends(get_session)):
    require_episode(session, episode_id)
    reasons: list[str] = []

    open_blockers = session.exec(select(DischargeBlocker).where(DischargeBlocker.episode_id == episode_id, DischargeBlocker.status == "open")).all()
    reasons.extend([f"open discharge blocker: {b.blocker_type} - {b.detail}" for b in open_blockers])

    pending_results = session.exec(select(ResultReview).where(ResultReview.episode_id == episode_id, ResultReview.status == "pending_review")).all()
    reasons.extend([f"pending result review: {r.result_type} owner {r.review_owner}" for r in pending_results])

    finance = session.exec(select(FinancialConsentStatus).where(FinancialConsentStatus.episode_id == episode_id)).first()
    if finance and finance.discharge_blocked:
        reasons.append("finance/insurance marks discharge blocked")

    readiness = session.exec(select(DischargeReadiness).where(DischargeReadiness.episode_id == episode_id)).first()
    if readiness:
        checks = {
            "clinician_signoff": readiness.clinician_signoff,
            "medication_ready": readiness.medication_ready,
            "owner_updated": readiness.owner_updated,
            "admin_ready": readiness.admin_ready,
            "results_reviewed": readiness.results_reviewed,
            "care_instructions_ready": readiness.care_instructions_ready,
        }
        missing = [name for name, ok in checks.items() if not ok]
        if missing:
            reasons.append("discharge readiness incomplete: " + ", ".join(missing))

    if reasons:
        gate = record_gate(session, episode_id=episode_id, gate_name="discharge_approval", target_entity_type="episode", target_entity_id=episode_id, severity="CRITICAL", reasons=reasons, actor_name=payload.actor_name)
        reject_with_gate(gate, reasons)

    if not readiness:
        readiness = DischargeReadiness(episode_id=episode_id)
    readiness.clinician_signoff = True
    readiness.medication_ready = True
    readiness.owner_updated = True
    readiness.admin_ready = True
    readiness.results_reviewed = True
    readiness.care_instructions_ready = True
    readiness.readiness_state = "ready"
    readiness.status = "completed"
    readiness.completed_at = utc_now()
    session.add(readiness)
    session.commit()
    session.refresh(readiness)
    gate = record_gate(session, episode_id=episode_id, gate_name="discharge_approval", target_entity_type="episode", target_entity_id=episode_id, severity="MINOR", reasons=["All discharge gates clear"], actor_name=payload.actor_name)
    audit(session, payload.actor_name, "approved", "discharge", episode_id, "Discharge approved after live gate checks")
    return {"ok": True, "gate": row_dict(gate), "discharge_readiness": row_dict(readiness)}


@router.post("/api/live-actions/schedule-blocks/{block_id}/start")
def start_schedule_block(block_id: int, payload: ActorPayload, session: Session = Depends(get_session)):
    block_row = session.get(ScheduleBlock, block_id)
    if not block_row:
        raise HTTPException(status_code=404, detail="Schedule block not found")
    require_episode(session, block_row.episode_id)
    reasons: list[str] = []

    if block_row.status not in {"planned", "ready"}:
        reasons.append(f"schedule block is not startable from status {block_row.status}")

    if block_row.room_name:
        room = session.exec(select(RoomState).where(RoomState.room_name == block_row.room_name)).first()
        if room and room.state in {"blocked", "cleaning", "out_of_service"}:
            reasons.append(f"room {room.room_name} is {room.state}")

    unack_handovers = session.exec(select(Handover).where(Handover.episode_id == block_row.episode_id, Handover.acknowledged == False)).all()
    if unack_handovers:
        reasons.append(f"{len(unack_handovers)} unacknowledged handover(s)")

    risky_staff = session.exec(select(StaffAssignmentRisk).where(StaffAssignmentRisk.episode_id == block_row.episode_id, StaffAssignmentRisk.rota_risk == "HIGH", StaffAssignmentRisk.status != "approved")).all()
    if risky_staff:
        reasons.append("HIGH staff assignment risk not approved")

    if reasons:
        gate = record_gate(session, episode_id=block_row.episode_id, gate_name=f"{block_row.block_type}_start", target_entity_type="schedule_block", target_entity_id=block_id, severity="CRITICAL", reasons=reasons, actor_name=payload.actor_name)
        reject_with_gate(gate, reasons)

    block_row.status = "in_progress"
    session.add(block_row)
    session.commit()
    session.refresh(block_row)
    gate = record_gate(session, episode_id=block_row.episode_id, gate_name=f"{block_row.block_type}_start", target_entity_type="schedule_block", target_entity_id=block_id, severity="MINOR", reasons=["Schedule block start gates clear"], actor_name=payload.actor_name)
    audit(session, payload.actor_name, "started", "schedule_block", block_id, f"Started {block_row.block_type}")
    return {"ok": True, "gate": row_dict(gate), "schedule_block": row_dict(block_row)}


@router.post("/api/live-actions/pharmacy-requests/{request_id}/complete")
def complete_pharmacy_request(request_id: int, payload: ClinicalTaskPayload, session: Session = Depends(get_session)):
    request = session.get(PharmacyRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Pharmacy request not found")
    reasons: list[str] = []
    severity = "CRITICAL"

    if request.status not in {"requested", "ready", "prepared"}:
        reasons.append(f"pharmacy request status is {request.status}")

    if request.episode_id:
        finance = session.exec(select(FinancialConsentStatus).where(FinancialConsentStatus.episode_id == request.episode_id)).first()
        if finance and finance.pharmacy_blocked:
            reasons.append("finance/insurance marks pharmacy blocked")

    if request.controlled_or_legal_status != "standard" and not payload.responsible_clinician:
        severity = "MODERATE"
        reasons.append("restricted pharmacy item requires responsible clinician signoff")

    if reasons:
        gate = record_gate(session, episode_id=request.episode_id, gate_name="pharmacy_request_completion", target_entity_type="pharmacy_request", target_entity_id=request_id, severity=severity, reasons=reasons, actor_name=payload.actor_name, reviewer_name=payload.reviewer_name or payload.responsible_clinician, override_reason=payload.override_reason)
        if gate.status != "overridden":
            reject_with_gate(gate, reasons)

    request.status = "completed"
    request.completed_at = utc_now()
    session.add(request)
    session.commit()
    session.refresh(request)
    gate = record_gate(session, episode_id=request.episode_id, gate_name="pharmacy_request_completion", target_entity_type="pharmacy_request", target_entity_id=request_id, severity="MINOR", reasons=["Pharmacy request completion gates clear"], actor_name=payload.actor_name)
    audit(session, payload.actor_name, "completed", "pharmacy_request", request_id, f"Completed pharmacy request {request.medication_name}")
    return {"ok": True, "gate": row_dict(gate), "pharmacy_request": row_dict(request)}


@router.post("/api/live-actions/staff-assignment-risk/{risk_id}/approve")
def approve_staff_assignment_risk(risk_id: int, payload: ActorPayload, session: Session = Depends(get_session)):
    risk = session.get(StaffAssignmentRisk, risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="Staff assignment risk not found")
    reasons = []
    if risk.rota_risk in {"MED", "HIGH"} and not (payload.reviewer_name and payload.override_reason):
        reasons.append(f"{risk.rota_risk} staff assignment requires reviewer and override reason")
    if reasons:
        gate = record_gate(session, episode_id=risk.episode_id, gate_name="staff_assignment_approval", target_entity_type="staff_assignment_risk", target_entity_id=risk_id, severity="MODERATE" if risk.rota_risk == "MED" else "CRITICAL", reasons=reasons, actor_name=payload.actor_name)
        reject_with_gate(gate, reasons)
    risk.status = "approved"
    risk.reviewer_name = payload.reviewer_name
    risk.override_reason = payload.override_reason
    risk.resolved_at = utc_now()
    session.add(risk)
    session.commit()
    session.refresh(risk)
    gate = record_gate(session, episode_id=risk.episode_id, gate_name="staff_assignment_approval", target_entity_type="staff_assignment_risk", target_entity_id=risk_id, severity="MINOR", reasons=["Staff assignment approval gate clear"], actor_name=payload.actor_name, reviewer_name=payload.reviewer_name, override_reason=payload.override_reason)
    audit(session, payload.actor_name, "approved", "staff_assignment_risk", risk_id, f"Approved {risk.rota_risk} staff assignment")
    return {"ok": True, "gate": row_dict(gate), "staff_assignment_risk": row_dict(risk)}


@router.post("/api/live-actions/owner-comms/{requirement_id}/close")
def close_owner_comms_requirement(requirement_id: int, payload: ActorPayload, session: Session = Depends(get_session)):
    req = session.get(OwnerCommsRequirement, requirement_id)
    if not req:
        raise HTTPException(status_code=404, detail="Owner comms requirement not found")
    reasons = []
    finance = session.exec(select(FinancialConsentStatus).where(FinancialConsentStatus.episode_id == req.episode_id)).first() if req.episode_id else None
    if finance and finance.owner_financial_constraint and not (payload.reviewer_name and payload.override_reason):
        reasons.append("owner financial constraint requires reviewer before closing communication")
    if reasons:
        gate = record_gate(session, episode_id=req.episode_id, gate_name="owner_comms_close", target_entity_type="owner_comms_requirement", target_entity_id=requirement_id, severity="MODERATE", reasons=reasons, actor_name=payload.actor_name)
        reject_with_gate(gate, reasons)
    req.status = "completed"
    req.completed_at = utc_now()
    session.add(req)
    session.commit()
    session.refresh(req)
    gate = record_gate(session, episode_id=req.episode_id, gate_name="owner_comms_close", target_entity_type="owner_comms_requirement", target_entity_id=requirement_id, severity="MINOR", reasons=["Owner communication closure gate clear"], actor_name=payload.actor_name, reviewer_name=payload.reviewer_name, override_reason=payload.override_reason)
    audit(session, payload.actor_name, "closed", "owner_comms_requirement", requirement_id, "Owner communication requirement closed")
    return {"ok": True, "gate": row_dict(gate), "owner_comms_requirement": row_dict(req)}
