from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.conflict_engine_routes import normalised_conflicts, pulse
from app.database import get_session
from app.models import Handover, ResultReview, RoomState, ScheduleBlock, StaffMember, WorkItem

router = APIRouter(prefix="/api/role-queues", tags=["role-queues"])

ROLE_ALIASES: dict[str, set[str]] = {
    "manager": {"manager", "ops_manager", "clinical_director"},
    "clinician": {"clinician", "vet", "specialist", "surgeon"},
    "nurse": {"nurse", "rvn", "ward_nurse", "theatre_nurse"},
    "pca": {"pca", "kennel_assistant", "assistant"},
    "admin": {"admin", "reception", "receptionist", "client_care"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def row(obj: Any) -> dict[str, Any]:
    fields = getattr(obj, "model_fields", {})
    return {name: getattr(obj, name) for name in fields}


def role_set(role: str) -> set[str]:
    key = role.lower().replace("-", "_")
    return ROLE_ALIASES.get(key, {key})


def queue_for_role(session: Session, role: str) -> dict[str, Any]:
    roles = role_set(role)
    all_work = session.exec(select(WorkItem).where(WorkItem.status != "done").order_by(WorkItem.urgency, WorkItem.due_at)).all()
    work = [item for item in all_work if item.owner_role in roles or item.owner_role in {"unowned", "ops_manager"} and "ops_manager" in roles]

    conflicts = normalised_conflicts(session)
    relevant_conflicts = []
    for conflict in conflicts:
        next_action = str(conflict.get("next_action", "")).lower()
        department = str(conflict.get("department", "")).lower()
        if role in next_action or any(alias in next_action for alias in roles) or any(alias in department for alias in roles):
            relevant_conflicts.append(conflict)
        elif role == "manager" and str(conflict.get("severity")) in {"red", "high", "amber"}:
            relevant_conflicts.append(conflict)

    handovers = session.exec(select(Handover).where(Handover.acknowledged == False).order_by(Handover.created_at)).all()
    results = session.exec(select(ResultReview).where(ResultReview.status == "pending_review")).all()
    rooms = session.exec(select(RoomState).order_by(RoomState.department, RoomState.room_name)).all()
    schedule = session.exec(select(ScheduleBlock).where(ScheduleBlock.status != "done").order_by(ScheduleBlock.starts_at)).all()
    staff = session.exec(select(StaffMember).where(StaffMember.active == True).order_by(StaffMember.role, StaffMember.name)).all()

    role_staff = [member for member in staff if member.role in roles]
    lanes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    work_payload = []
    for item in work[:100]:
        payload = row(item)
        work_payload.append(payload)
        lanes[item.section_name or "Unassigned"].append(payload)

    urgency_counts = Counter([item.urgency for item in work])
    return {
        "role": role,
        "role_aliases": sorted(roles),
        "generated_at": utc_now(),
        "pulse": pulse(session),
        "summary": {
            "work_count": len(work),
            "red_work": urgency_counts.get("red", 0),
            "amber_work": urgency_counts.get("amber", 0),
            "conflict_count": len(relevant_conflicts),
            "handoff_count": len(handovers),
            "pending_result_count": len(results),
            "role_staff_count": len(role_staff),
        },
        "work_items": work_payload,
        "lanes": dict(lanes),
        "conflicts": relevant_conflicts[:80],
        "unacknowledged_handovers": [row(handover) for handover in handovers[:80]],
        "pending_results": [row(result) for result in results[:80]],
        "rooms": [row(room) for room in rooms],
        "schedule": [row(block) for block in schedule[:120]],
        "staff": [row(member) for member in role_staff],
    }


def interrupts_payload(session: Session) -> dict[str, Any]:
    conflicts = normalised_conflicts(session)
    work = session.exec(select(WorkItem).where(WorkItem.status != "done").order_by(WorkItem.urgency, WorkItem.due_at)).all()
    critical_work = [item for item in work if item.urgency in {"red", "amber"}]
    critical_conflicts = [conflict for conflict in conflicts if str(conflict.get("severity")) in {"red", "high", "amber", "medium"}]
    return {
        "generated_at": utc_now(),
        "pulse": pulse(session),
        "critical_work": [row(item) for item in critical_work[:100]],
        "critical_conflicts": critical_conflicts[:100],
        "count": len(critical_work) + len(critical_conflicts),
    }


@router.get("/manager")
def manager_queue(session: Session = Depends(get_session)):
    return queue_for_role(session, "manager")


@router.get("/clinician")
def clinician_queue(session: Session = Depends(get_session)):
    return queue_for_role(session, "clinician")


@router.get("/nurse")
def nurse_queue(session: Session = Depends(get_session)):
    return queue_for_role(session, "nurse")


@router.get("/pca")
def pca_queue(session: Session = Depends(get_session)):
    return queue_for_role(session, "pca")


@router.get("/admin")
def admin_queue(session: Session = Depends(get_session)):
    return queue_for_role(session, "admin")


@router.get("/my-shift")
def my_shift(role: str = "nurse", session: Session = Depends(get_session)):
    return queue_for_role(session, role)


@router.get("/interrupts")
def interrupts(session: Session = Depends(get_session)):
    return interrupts_payload(session)


@router.get("/overview")
def overview(session: Session = Depends(get_session)):
    return {
        "generated_at": utc_now(),
        "pulse": pulse(session),
        "roles": {
            "manager": queue_for_role(session, "manager")["summary"],
            "clinician": queue_for_role(session, "clinician")["summary"],
            "nurse": queue_for_role(session, "nurse")["summary"],
            "pca": queue_for_role(session, "pca")["summary"],
            "admin": queue_for_role(session, "admin")["summary"],
        },
        "interrupts": interrupts_payload(session)["count"],
    }
