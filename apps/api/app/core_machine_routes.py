from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Episode, Handover, ResultReview, RoomState, ScheduleBlock, StaffMember, WorkItem

router = APIRouter(prefix="/api", tags=["core-machine"])


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def row(obj: Any) -> dict[str, Any]:
    fields = getattr(obj, "model_fields", {})
    return {name: getattr(obj, name) for name in fields}


def overlaps(a_start, a_end, b_start, b_end) -> bool:
    return not (a_end <= b_start or b_end <= a_start)


def episode_ref(session: Session, episode_id: int | None) -> str | None:
    if not episode_id:
        return None
    episode = session.get(Episode, episode_id)
    return episode.episode_ref if episode else None


def detect_conflicts(session: Session) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    blocks = session.exec(select(ScheduleBlock).order_by(ScheduleBlock.starts_at)).all()

    for index, first in enumerate(blocks):
        for second in blocks[index + 1:]:
            if not overlaps(first.starts_at, first.ends_at, second.starts_at, second.ends_at):
                continue
            if first.room_name and first.room_name == second.room_name:
                conflicts.append({
                    "type": "resource_conflict",
                    "severity": "red",
                    "detail": f"{first.room_name} double-booked between blocks {first.id} and {second.id}",
                    "department": "Resources",
                    "episode_refs": [episode_ref(session, first.episode_id), episode_ref(session, second.episode_id)],
                    "next_action": "Move one schedule block, release room, or approve emergency override.",
                })
            if first.assigned_staff_member_id and first.assigned_staff_member_id == second.assigned_staff_member_id:
                conflicts.append({
                    "type": "staff_conflict",
                    "severity": "red",
                    "detail": f"Staff {first.assigned_staff_member_id} is assigned to overlapping blocks {first.id} and {second.id}",
                    "department": "Staffing",
                    "episode_refs": [episode_ref(session, first.episode_id), episode_ref(session, second.episode_id)],
                    "next_action": "Reassign clinician or move one block.",
                })

    for handover in session.exec(select(Handover).where(Handover.acknowledged == False)).all():
        conflicts.append({
            "type": "handoff_conflict",
            "severity": "red",
            "detail": handover.note,
            "department": "Handoffs",
            "episode_refs": [episode_ref(session, handover.episode_id)],
            "next_action": f"{handover.to_owner} must acknowledge handoff.",
        })

    for result in session.exec(select(ResultReview).where(ResultReview.status == "pending_review")).all():
        conflicts.append({
            "type": "result_review_conflict",
            "severity": "amber",
            "detail": f"{result.result_type} result waiting for {result.review_owner}",
            "department": "Diagnostics",
            "episode_refs": [episode_ref(session, result.episode_id)],
            "next_action": result.required_action or "Assign reviewer and confirm action.",
        })

    return conflicts


def pulse_snapshot(session: Session) -> dict[str, Any]:
    work = session.exec(select(WorkItem).where(WorkItem.status != "done")).all()
    episodes = session.exec(select(Episode).where(Episode.status == "active")).all()
    rooms = session.exec(select(RoomState)).all()
    conflicts = detect_conflicts(session)

    red = len([item for item in work if item.urgency == "red"]) + len([c for c in conflicts if c["severity"] == "red"])
    amber = len([item for item in work if item.urgency == "amber"]) + len([c for c in conflicts if c["severity"] == "amber"])
    blocked_rooms = len([room for room in rooms if room.state in {"blocked", "cleaning"}])
    pending_results = len(session.exec(select(ResultReview).where(ResultReview.status == "pending_review")).all())
    unacknowledged_handoffs = len(session.exec(select(Handover).where(Handover.acknowledged == False)).all())
    score = min(100, red * 14 + amber * 7 + blocked_rooms * 8 + pending_results * 5 + unacknowledged_handoffs * 8)

    return {
        "state": "red" if score >= 70 else "amber" if score >= 35 else "green",
        "pressure_score": score,
        "active_cases": len(episodes),
        "open_work": len(work),
        "red_pressure": red,
        "amber_pressure": amber,
        "blocked_rooms": blocked_rooms,
        "pending_results": pending_results,
        "unacknowledged_handoffs": unacknowledged_handoffs,
        "conflict_count": len(conflicts),
        "work_by_section": dict(Counter([item.section_name or "Unassigned" for item in work])),
    }


def product_view(session: Session, mode: str, role: str | None = None) -> dict[str, Any]:
    work = session.exec(select(WorkItem).where(WorkItem.status != "done").order_by(WorkItem.urgency, WorkItem.due_at)).all()
    if mode == "my-shift" and role:
        work = [item for item in work if item.owner_role == role or item.owner_role == "unowned"]
    if mode == "interrupts":
        work = [item for item in work if item.urgency in {"red", "amber"} or item.category in {"handoff", "timing", "critical_care"}]
    if mode == "resources":
        work = [item for item in work if item.section_name in {"Theatres", "Imaging", "ICU", "Wards", "Recovery", "Pharmacy"}]

    lanes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    items = []
    for item in work[:80]:
        payload = {
            "id": item.id,
            "title": item.title,
            "patient": item.linked_patient_name,
            "episode_ref": item.linked_episode_ref,
            "section": item.section_name,
            "room": item.room_name,
            "urgency": item.urgency,
            "owner_role": item.owner_role,
            "status": item.status,
            "description": item.description,
            "due_at": item.due_at.isoformat() if item.due_at else None,
            "next_action": item.description,
        }
        items.append(payload)
        lanes[payload["section"] or "Unassigned"].append(payload)

    return {
        "mode": mode,
        "generated_at": now_iso(),
        "pulse": pulse_snapshot(session),
        "conflicts": detect_conflicts(session),
        "work_items": items,
        "lanes": dict(lanes),
        "resources": [row(room) for room in session.exec(select(RoomState).order_by(RoomState.department, RoomState.room_name)).all()],
        "staff": [row(member) for member in session.exec(select(StaffMember).where(StaffMember.active == True).order_by(StaffMember.role, StaffMember.name)).all()],
        "schedule": [row(block) for block in session.exec(select(ScheduleBlock).order_by(ScheduleBlock.starts_at)).all()[:120]],
    }


@router.get("/core-machine/conflicts")
def core_conflicts(session: Session = Depends(get_session)):
    conflicts = detect_conflicts(session)
    return {"count": len(conflicts), "conflicts": conflicts}


@router.get("/core-machine/pulse")
def core_pulse(session: Session = Depends(get_session)):
    return pulse_snapshot(session)


@router.get("/product/now")
def product_now(session: Session = Depends(get_session)):
    return product_view(session, "now")


@router.get("/product/flow")
def product_flow(session: Session = Depends(get_session)):
    return product_view(session, "flow")


@router.get("/product/resources")
def product_resources(session: Session = Depends(get_session)):
    return product_view(session, "resources")


@router.get("/product/my-shift")
def product_my_shift(role: str = "nurse", session: Session = Depends(get_session)):
    return product_view(session, "my-shift", role=role)


@router.get("/product/interrupts")
def product_interrupts(session: Session = Depends(get_session)):
    return product_view(session, "interrupts")
