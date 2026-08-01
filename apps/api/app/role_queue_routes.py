from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.conflict_engine_routes import normalised_conflicts, pulse
from app.database import get_session
from app.hospital_command_models import EpisodeHandoverV9
from app.hospital_ops_models import CanonicalEpisodeState
from app.models import Handover, ResultReview, RoomState, ScheduleBlock, StaffMember, WorkItem

router = APIRouter(prefix="/api/role-queues", tags=["role-queues"])

ROLE_ALIASES: dict[str, set[str]] = {
    "manager": {"manager", "ops_manager", "hospital_director", "clinical_director", "senior_clinician", "supervisor", "clinical_director_or_ops_manager", "capacity_hold_queue"},
    "clinician": {"clinician", "vet", "specialist", "surgeon", "service_clinician", "clinical_owner_or_senior", "admin_or_service_clinician"},
    "nurse": {"nurse", "rvn", "ward_nurse", "theatre_nurse", "nurse_lead", "ward_or_icu_lead", "theatre_lead", "imaging_lead", "pharmacy_owner"},
    "pca": {"pca", "kennel_assistant", "assistant", "receiving_role"},
    "admin": {"admin", "reception", "receptionist", "client_care", "insurance_admin", "admin_or_service_clinician"},
    "pharmacy": {"pharmacy", "pharmacy_owner"},
    "imaging": {"imaging", "imaging_lead"},
    "theatre": {"theatre", "theatre_lead", "theatre_nurse"},
    "icu": {"icu", "icu_nurse", "ward_or_icu_lead"},
    "ward": {"ward", "ward_nurse", "ward_or_icu_lead"},
    "insurance": {"insurance", "insurance_admin"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def row(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    fields = getattr(obj, "model_fields", {})
    return {name: getattr(obj, name) for name in fields}


def role_set(role: str) -> set[str]:
    key = role.lower().replace("-", "_")
    return ROLE_ALIASES.get(key, {key})


def _canonical_for_role(session: Session, role: str, roles: set[str]) -> list[CanonicalEpisodeState]:
    episodes = session.exec(
        select(CanonicalEpisodeState)
        .where(CanonicalEpisodeState.status == "active")
        .order_by(CanonicalEpisodeState.urgency.desc(), CanonicalEpisodeState.updated_at)
    ).all()
    if role == "manager":
        return episodes
    return [
        episode for episode in episodes
        if episode.owner_role in roles
        or episode.service_line in roles
        or episode.current_area_ref in roles
    ]


def _governed_handovers_for_role(session: Session, role: str, roles: set[str]) -> list[EpisodeHandoverV9]:
    handovers = session.exec(
        select(EpisodeHandoverV9)
        .where(EpisodeHandoverV9.status == "offered")
        .order_by(EpisodeHandoverV9.created_at)
    ).all()
    if role == "manager":
        return handovers
    return [handover for handover in handovers if handover.to_role in roles]


def queue_for_role(session: Session, role: str) -> dict[str, Any]:
    roles = role_set(role)
    all_work = session.exec(select(WorkItem).where(WorkItem.status != "done").order_by(WorkItem.urgency, WorkItem.due_at)).all()
    work = [item for item in all_work if item.owner_role in roles or item.category in roles or item.owner_role in {"unowned", "ops_manager"} and "ops_manager" in roles]

    canonical_episodes = _canonical_for_role(session, role, roles)
    governed_handovers = _governed_handovers_for_role(session, role, roles)

    conflicts = normalised_conflicts(session)
    relevant_conflicts = []
    for conflict in conflicts:
        next_action = str(conflict.get("next_action", "")).lower()
        department = str(conflict.get("department", "")).lower()
        if role in next_action or any(alias in next_action for alias in roles) or any(alias in department for alias in roles):
            relevant_conflicts.append(conflict)
        elif role == "manager" and str(conflict.get("severity")) in {"red", "high", "amber"}:
            relevant_conflicts.append(conflict)

    handovers = session.exec(select(Handover).where(Handover.acknowledged == False).order_by(Handover.created_at)).all()  # noqa: E712
    results = session.exec(select(ResultReview).where(ResultReview.status == "pending_review")).all()
    rooms = session.exec(select(RoomState).order_by(RoomState.department, RoomState.room_name)).all()
    schedule = session.exec(select(ScheduleBlock).where(ScheduleBlock.status != "done").order_by(ScheduleBlock.starts_at)).all()
    staff = session.exec(select(StaffMember).where(StaffMember.active == True).order_by(StaffMember.role, StaffMember.name)).all()  # noqa: E712

    role_staff = [member for member in staff if member.role in roles]
    lanes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    work_payload = []
    for item in work[:100]:
        payload = row(item)
        work_payload.append(payload)
        lanes[item.section_name or item.category or "Unassigned"].append(payload)

    canonical_payload = [row(episode) for episode in canonical_episodes[:100]]
    for episode in canonical_payload:
        lanes[f"Canonical · {episode.get('service_line') or 'Referral'}"].append({
            "canonical": True,
            "title": episode.get("next_action") or f"{episode.get('patient_name')} — {episode.get('phase')}",
            "description": f"{episode.get('patient_name')} · {episode.get('phase')} · {episode.get('current_area_ref') or 'unplaced'}",
            "urgency": episode.get("urgency"),
            "owner_role": episode.get("owner_role"),
            "linked_episode_ref": episode.get("episode_ref"),
            "linked_patient_name": episode.get("patient_name"),
            "status": episode.get("status"),
            "updated_at": episode.get("updated_at"),
        })

    urgency_counts = Counter([item.urgency for item in work])
    canonical_urgency = Counter([item.urgency for item in canonical_episodes])
    return {
        "role": role,
        "role_aliases": sorted(roles),
        "generated_at": utc_now(),
        "pulse": pulse(session),
        "summary": {
            "work_count": len(work),
            "canonical_episode_count": len(canonical_episodes),
            "red_work": urgency_counts.get("red", 0) + canonical_urgency.get("red", 0) + canonical_urgency.get("emergency", 0),
            "amber_work": urgency_counts.get("amber", 0) + canonical_urgency.get("urgent", 0),
            "conflict_count": len(relevant_conflicts),
            "handoff_count": len(handovers) + len(governed_handovers),
            "governed_handoff_count": len(governed_handovers),
            "pending_result_count": len(results),
            "role_staff_count": len(role_staff),
        },
        "work_items": work_payload,
        "canonical_episodes": canonical_payload,
        "lanes": dict(lanes),
        "conflicts": relevant_conflicts[:80],
        "unacknowledged_handovers": [row(handover) for handover in handovers[:80]],
        "governed_handovers": [row(handover) for handover in governed_handovers[:80]],
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
    canonical = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.status == "active")).all()
    critical_canonical = [item for item in canonical if item.urgency in {"red", "emergency", "urgent"}]
    governed_handovers = session.exec(select(EpisodeHandoverV9).where(EpisodeHandoverV9.status == "offered")).all()
    return {
        "generated_at": utc_now(),
        "pulse": pulse(session),
        "critical_work": [row(item) for item in critical_work[:100]],
        "critical_conflicts": critical_conflicts[:100],
        "critical_canonical_episodes": [row(item) for item in critical_canonical[:100]],
        "unacknowledged_governed_handovers": [row(item) for item in governed_handovers[:100]],
        "count": len(critical_work) + len(critical_conflicts) + len(critical_canonical) + len(governed_handovers),
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
            "pharmacy": queue_for_role(session, "pharmacy")["summary"],
            "imaging": queue_for_role(session, "imaging")["summary"],
            "theatre": queue_for_role(session, "theatre")["summary"],
            "icu": queue_for_role(session, "icu")["summary"],
            "ward": queue_for_role(session, "ward")["summary"],
            "insurance": queue_for_role(session, "insurance")["summary"],
        },
        "interrupts": interrupts_payload(session)["count"],
    }
