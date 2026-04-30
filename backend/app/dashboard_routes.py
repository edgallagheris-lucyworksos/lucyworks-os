from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.main_fixed import alerts_for, compute_conflicts
from app.models import (
    Blocker,
    DecisionRecord,
    DischargeReadiness,
    Episode,
    EthicsFlag,
    LucyCareTask,
    MessageThread,
    OwnerCommsRequirement,
    Patient,
    PharmacyRequest,
    ResultReview,
    RoomState,
    ScheduleBlock,
    StaffMember,
    StockOrder,
    TriageAssessment,
    WorkItem,
)
from app.operating_catalogue import HOSPITAL_OPERATING_CATALOGUE

router = APIRouter()


def _find_template(name: str | None):
    if not name:
        return None
    for template in HOSPITAL_OPERATING_CATALOGUE.get("procedure_templates", []):
        if template.get("name", "").lower() == name.lower():
            return template
    return None


def _lookup(collection: str, key: str, value: str | None):
    if not value:
        return None
    for row in HOSPITAL_OPERATING_CATALOGUE.get(collection, []):
        if row.get(key) == value:
            return row
    return None


def _to_iso(dt):
    return dt.isoformat() if dt else None


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def _episode_bundle(session: Session, episode: Episode | None):
    if not episode:
        return None
    patient = session.get(Patient, episode.patient_id)
    return {
        "episode_id": episode.id,
        "episode_ref": episode.episode_ref,
        "phase": episode.current_phase,
        "section": episode.current_section_name,
        "room": episode.current_room_name,
        "patient": {
            "name": patient.patient_name if patient else None,
            "species": patient.species if patient else None,
            "owner_name": patient.owner_name if patient else None,
        },
    }


def _episode_pressures(session: Session, episode: Episode | None):
    if not episode:
        return {
            "hard_blocks": [],
            "warnings": [],
            "counts": {},
            "next_action": None,
        }
    ep_id = episode.id
    ep_ref = episode.episode_ref
    hard_blocks = []
    warnings = []

    discharge = session.exec(select(DischargeReadiness).where(DischargeReadiness.episode_id == ep_id)).all()
    for item in discharge:
        if item.readiness_state != "ready" or item.status != "complete":
            hard_blocks.append({"type": "discharge", "section": "Discharge", "detail": item.blocker_summary or "Discharge readiness incomplete", "owner_role": item.owner_role, "urgency": item.urgency})

    pharmacy = session.exec(select(PharmacyRequest).where(PharmacyRequest.episode_id == ep_id)).all()
    for item in pharmacy:
        if item.status != "complete":
            hard_blocks.append({"type": "pharmacy", "section": "Pharmacy", "detail": f"{item.medication_name} is {item.status}", "owner_role": item.owner_role, "urgency": item.urgency})

    stock = session.exec(select(StockOrder).where(StockOrder.episode_id == ep_id)).all()
    for item in stock:
        if item.status != "complete":
            hard_blocks.append({"type": "stock", "section": "Stock", "detail": f"{item.item_name}: {item.reason}", "owner_role": "nurse", "urgency": item.urgency})

    ethics = session.exec(select(EthicsFlag).where(EthicsFlag.episode_id == ep_id)).all()
    for item in ethics:
        if item.status != "resolved":
            hard_blocks.append({"type": "ethics", "section": "Lucy Ethics", "detail": item.detail, "owner_role": item.owner_role, "urgency": "red" if item.severity == "high" else "amber"})

    blockers = session.exec(select(Blocker).where(Blocker.episode_id == ep_id)).all()
    for item in blockers:
        if item.status != "resolved":
            hard_blocks.append({"type": "blocker", "section": item.section_name, "detail": item.detail, "owner_role": item.owner_role, "urgency": item.urgency})

    triage = session.exec(select(TriageAssessment).where(TriageAssessment.episode_id == ep_id)).all()
    for item in triage:
        if item.status != "resolved" and item.urgency in {"red", "amber"}:
            warnings.append({"type": "triage", "section": "LucyFlow", "detail": item.reasoning, "owner_role": item.assigned_owner_role, "urgency": item.urgency})

    decisions = session.exec(select(DecisionRecord).where(DecisionRecord.episode_id == ep_id)).all()
    for item in decisions:
        if item.status != "resolved":
            warnings.append({"type": "decision", "section": item.section_name or "Decision", "detail": item.decision_needed, "owner_role": item.owner_role, "urgency": item.urgency})

    owner_comms = session.exec(select(OwnerCommsRequirement).where(OwnerCommsRequirement.episode_id == ep_id)).all()
    for item in owner_comms:
        if item.status != "complete":
            warnings.append({"type": "owner_comms", "section": "Mail Ops", "detail": item.required_message, "owner_role": item.owner_role, "urgency": item.urgency})

    results = session.exec(select(ResultReview).where(ResultReview.episode_id == ep_id)).all()
    for item in results:
        if item.status == "pending_review":
            warnings.append({"type": "result_review", "section": "Results", "detail": item.required_action or f"{item.result_type} pending review", "owner_role": item.review_owner, "urgency": "amber"})

    care = session.exec(select(LucyCareTask).where(LucyCareTask.episode_id == ep_id)).all()
    for item in care:
        if item.status != "done" and item.escalation_required:
            warnings.append({"type": "care", "section": "Lucy Care", "detail": item.detail, "owner_role": item.owner_role, "urgency": "amber"})

    work = session.exec(select(WorkItem).where(WorkItem.linked_episode_ref == ep_ref)).all()
    for item in work:
        if item.status != "done" and item.urgency == "red":
            hard_blocks.append({"type": "red_work", "section": item.section_name or item.category, "detail": item.title, "owner_role": item.owner_role, "urgency": item.urgency})
        elif item.status != "done":
            warnings.append({"type": "work", "section": item.section_name or item.category, "detail": item.title, "owner_role": item.owner_role, "urgency": item.urgency})

    combined = hard_blocks + warnings
    next_action = combined[0] if combined else None
    return {
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "counts": {
            "discharge": len([x for x in discharge if x.readiness_state != "ready" or x.status != "complete"]),
            "pharmacy": len([x for x in pharmacy if x.status != "complete"]),
            "stock": len([x for x in stock if x.status != "complete"]),
            "ethics": len([x for x in ethics if x.status != "resolved"]),
            "triage": len([x for x in triage if x.status != "resolved"]),
            "decisions": len([x for x in decisions if x.status != "resolved"]),
            "owner_comms": len([x for x in owner_comms if x.status != "complete"]),
            "results": len([x for x in results if x.status == "pending_review"]),
            "care": len([x for x in care if x.status != "done"]),
            "work": len([x for x in work if x.status != "done"]),
        },
        "next_action": next_action,
    }


def _block_context(session: Session, block: ScheduleBlock):
    episode = session.get(Episode, block.episode_id)
    staff = session.get(StaffMember, block.assigned_staff_member_id) if block.assigned_staff_member_id else None
    room = session.exec(select(RoomState).where(RoomState.room_name == block.room_name)).first() if block.room_name else None
    procedure = None
    operating = None
    if block.case_procedure_id:
        # ProcedureType lives through CaseProcedure; import locally to avoid cluttering model list above if refactor changes.
        from app.models import CaseProcedure, ProcedureType
        cp = session.get(CaseProcedure, block.case_procedure_id)
        pt = session.get(ProcedureType, cp.procedure_type_id) if cp else None
        template = _find_template(pt.name if pt else None)
        procedure = {"name": pt.name if pt else None, "department": pt.department if pt else None, "case_procedure_id": cp.id if cp else None}
        if template:
            operating = {
                "template": template,
                "family": _lookup("procedure_families", "family", template.get("family")),
                "anaesthesia": _lookup("anaesthesia_levels", "level", template.get("anaesthesia_level")),
                "recovery": _lookup("recovery_standards", "class", template.get("recovery_class")),
                "cleaning": _lookup("cleaning_turnover_standards", "area", template.get("cleaning_standard")),
            }
    pressure = _episode_pressures(session, episode)
    return {
        "block_id": block.id,
        "block_type": block.block_type,
        "starts_at": _to_iso(block.starts_at),
        "ends_at": _to_iso(block.ends_at),
        "status": block.status,
        "room": {"name": block.room_name, "state": room.state if room else None, "department": room.department if room else None},
        "owner_role": block.owner_role,
        "assigned_staff": {"id": staff.id, "name": staff.name, "role": staff.role, "skills": staff.skills} if staff else None,
        "episode": _episode_bundle(session, episode),
        "procedure": procedure,
        "operating": operating,
        "pressure": pressure,
        "next_action": pressure.get("next_action"),
    }


@router.get("/api/dashboard/intelligence")
def dashboard_intelligence(session: Session = Depends(get_session)):
    now = datetime.now()
    day_start = now.replace(hour=7, minute=0, second=0, microsecond=0)
    slots = []
    blocks = session.exec(select(ScheduleBlock).order_by(ScheduleBlock.starts_at)).all()
    rooms = session.exec(select(RoomState).order_by(RoomState.department, RoomState.room_name)).all()
    conflicts = compute_conflicts(session)
    alerts = alerts_for(session)

    for index in range(56):
        slot_start = day_start + timedelta(minutes=15 * index)
        slot_end = slot_start + timedelta(minutes=15)
        slot_blocks = [block for block in blocks if _overlaps(slot_start, slot_end, block.starts_at, block.ends_at)]
        contexts = [_block_context(session, block) for block in slot_blocks]
        hard = sum(len(ctx["pressure"]["hard_blocks"]) for ctx in contexts)
        warnings = sum(len(ctx["pressure"]["warnings"]) for ctx in contexts)
        slots.append({
            "slot_index": index,
            "starts_at": _to_iso(slot_start),
            "ends_at": _to_iso(slot_end),
            "active_count": len(contexts),
            "hard_block_count": hard,
            "warning_count": warnings,
            "risk": "red" if hard else "amber" if warnings else "green",
            "blocks": contexts,
        })

    open_work = session.exec(select(WorkItem)).all()
    return {
        "generated_at": _to_iso(now),
        "dashboard_basis": "15-minute operational command grid",
        "summary": {
            "rooms": len(rooms),
            "schedule_blocks": len(blocks),
            "active_slots": len([slot for slot in slots if slot["active_count"]]),
            "red_slots": len([slot for slot in slots if slot["risk"] == "red"]),
            "amber_slots": len([slot for slot in slots if slot["risk"] == "amber"]),
            "alerts": len(alerts),
            "high_alerts": len([a for a in alerts if a.get("severity") == "high"]),
            "conflicts": len(conflicts),
            "open_work": len([item for item in open_work if item.status != "done"]),
        },
        "rooms": [room.model_dump() for room in rooms],
        "slots": slots,
        "conflicts": conflicts,
        "alerts": alerts,
    }
