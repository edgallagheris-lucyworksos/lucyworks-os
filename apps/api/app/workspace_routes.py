from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.database import get_session
from app.flow_state_models import DischargeBlocker, OccupancyRecord, SeverityGate, StaffAssignmentRisk
from app.inpatient_models import NightHandover, ObservationTask
from app.models import (
    AuditEvent,
    Handover,
    LucyCareTask,
    MessageThread,
    OwnerCommsRequirement,
    ResultReview,
    ScheduleBlock,
    Shift,
    StaffMember,
    WorkItem,
)

router = APIRouter()

ROLE_SCOPES = {
    "ops_manager": {"ops_manager", "clinical_director", "clinician", "nurse", "ward_nurse", "icu_nurse", "admin", "insurance_admin", "reception", "theatre_nurse", "anaesthetist", "surgeon", "radiographer", "stock_controller"},
    "clinical_director": {"clinical_director", "clinician", "surgeon", "anaesthetist", "ops_manager"},
    "clinician": {"clinician", "clinical_director", "surgeon", "anaesthetist", "medicine_specialist", "orthopaedic_surgeon", "neurologist", "dental_vet"},
    "nurse": {"nurse", "ward_nurse", "icu_nurse", "theatre_nurse", "anaesthesia_nurse", "recovery_nurse", "ecc_nurse"},
    "admin": {"admin", "reception", "insurance_admin", "owner_comms", "coordinator"},
    "stock_controller": {"stock_controller", "nurse"},
    "imaging_staff": {"imaging_staff", "radiographer", "radiologist", "clinician"},
    "theatre_staff": {"theatre_staff", "theatre_nurse", "scrub_nurse", "anaesthetist", "surgeon", "nurse"},
    "ward_staff": {"ward_staff", "ward_nurse", "icu_nurse", "nurse"},
}


def role_scope(role: str) -> set[str]:
    return ROLE_SCOPES.get(role, {role})


def is_command(role: str) -> bool:
    return role in {"ops_manager", "clinical_director"}


def staff_name_for(session: Session, staff_member_id: int | None):
    if not staff_member_id:
        return None
    staff = session.get(StaffMember, staff_member_id)
    return staff.name if staff else None


@router.get("/api/workspace")
def get_workspace(
    role: str = Query("ops_manager"),
    staff_member_id: int | None = None,
    session: Session = Depends(get_session),
):
    scope = role_scope(role)
    staff_name = staff_name_for(session, staff_member_id)

    work_items = session.exec(select(WorkItem).where(WorkItem.status != "done").order_by(WorkItem.created_at.desc())).all()
    care_tasks = session.exec(select(LucyCareTask).where(LucyCareTask.status != "completed").order_by(LucyCareTask.created_at.desc())).all()
    handovers = session.exec(select(Handover).where(Handover.acknowledged == False).order_by(Handover.created_at.desc())).all()
    night_handovers = session.exec(select(NightHandover).where(NightHandover.acknowledged == False).order_by(NightHandover.created_at.desc())).all()
    results = session.exec(select(ResultReview).where(ResultReview.status == "pending_review")).all()
    discharge_blockers = session.exec(select(DischargeBlocker).where(DischargeBlocker.status == "open").order_by(DischargeBlocker.created_at.desc())).all()
    observations = session.exec(select(ObservationTask).where(ObservationTask.status != "done").order_by(ObservationTask.due_at)).all()
    messages = session.exec(select(MessageThread).where(MessageThread.status != "closed").order_by(MessageThread.created_at.desc())).all()
    owner_comms = session.exec(select(OwnerCommsRequirement).where(OwnerCommsRequirement.status != "completed").order_by(OwnerCommsRequirement.created_at.desc())).all()
    gates = session.exec(select(SeverityGate).where(SeverityGate.status == "blocked").order_by(SeverityGate.created_at.desc())).all()
    staff_risks = session.exec(select(StaffAssignmentRisk).where(StaffAssignmentRisk.status != "approved").order_by(StaffAssignmentRisk.created_at.desc())).all()
    occupancy = session.exec(select(OccupancyRecord).where(OccupancyRecord.status != "released").order_by(OccupancyRecord.created_at.desc())).all()
    schedule_blocks = session.exec(select(ScheduleBlock).where(ScheduleBlock.status != "completed").order_by(ScheduleBlock.starts_at)).all()

    if not is_command(role):
        work_items = [x for x in work_items if x.owner_role in scope or (staff_member_id and x.owner_user_id == staff_member_id)]
        care_tasks = [x for x in care_tasks if x.owner_role in scope or (staff_member_id and x.owner_user_id == staff_member_id)]
        handovers = [x for x in handovers if x.to_owner in scope or x.to_owner == role or (staff_name and x.to_owner == staff_name)]
        night_handovers = [x for x in night_handovers if x.to_role in scope or x.to_role == role]
        results = [x for x in results if x.review_owner in scope or x.review_owner == role or (staff_name and x.review_owner == staff_name)]
        discharge_blockers = [x for x in discharge_blockers if x.owner_role in scope]
        observations = [x for x in observations if x.owner_role in scope]
        messages = [x for x in messages if x.owner_role in scope or (staff_member_id and x.owner_user_id == staff_member_id)]
        owner_comms = [x for x in owner_comms if x.owner_role in scope]
        gates = [x for x in gates if role in {"clinical_director", "ops_manager"} or x.severity != "CRITICAL"]
        staff_risks = [x for x in staff_risks if role in {"clinical_director", "ops_manager"} or x.role_required in scope]
        schedule_blocks = [x for x in schedule_blocks if x.owner_role in scope or (staff_member_id and x.assigned_staff_member_id == staff_member_id)]

    shifts = []
    if staff_member_id:
        shifts = session.exec(select(Shift).where(Shift.staff_member_id == staff_member_id).order_by(Shift.starts_at)).all()
    elif is_command(role):
        shifts = session.exec(select(Shift).order_by(Shift.starts_at)).all()

    summary = {
        "work_items": len(work_items),
        "care_tasks": len(care_tasks),
        "handovers": len(handovers) + len(night_handovers),
        "results": len(results),
        "discharge_blockers": len(discharge_blockers),
        "observations": len(observations),
        "messages": len(messages),
        "owner_comms": len(owner_comms),
        "blocked_gates": len(gates),
        "staff_risks": len(staff_risks),
        "occupancy": len(occupancy),
        "schedule_blocks": len(schedule_blocks),
        "shifts": len(shifts),
    }

    session.add(AuditEvent(actor_name=f"workspace:{role}", action="read", entity_type="workspace", entity_id=staff_member_id or 0, summary=f"Workspace opened for role {role}"))
    session.commit()

    return {
        "role": role,
        "staff_member_id": staff_member_id,
        "staff_name": staff_name,
        "scope": sorted(scope),
        "summary": summary,
        "queues": {
            "work_items": work_items,
            "care_tasks": care_tasks,
            "handovers": handovers,
            "night_handovers": night_handovers,
            "results": results,
            "discharge_blockers": discharge_blockers,
            "observations": observations,
            "messages": messages,
            "owner_comms": owner_comms,
            "blocked_gates": gates,
            "staff_risks": staff_risks,
            "occupancy": occupancy,
            "schedule_blocks": schedule_blocks,
            "shifts": shifts,
        },
    }
