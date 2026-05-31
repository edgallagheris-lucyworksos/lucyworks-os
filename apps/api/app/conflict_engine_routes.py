from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core_machine_routes import detect_conflicts
from app.database import get_session
from app.models import AuditEvent, ConflictAction, Episode, Handover, ResultReview, RoomState, ScheduleBlock, WorkItem

router = APIRouter(prefix="/api/conflict-engine", tags=["conflict-engine"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def row(obj: Any) -> dict[str, Any]:
    fields = getattr(obj, "model_fields", {})
    return {name: getattr(obj, name) for name in fields}


def write_audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str) -> AuditEvent:
    event = AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def severity_rank(severity: str) -> int:
    return {"red": 3, "high": 3, "amber": 2, "medium": 2, "green": 1, "low": 1}.get(severity, 1)


def normalised_conflicts(session: Session) -> list[dict[str, Any]]:
    conflicts = detect_conflicts(session)
    open_work = session.exec(select(WorkItem).where(WorkItem.status != "done")).all()
    rooms = session.exec(select(RoomState)).all()

    for room in rooms:
        if room.state in {"blocked", "cleaning"}:
            conflicts.append({
                "type": "room_state_pressure",
                "severity": "amber",
                "detail": f"{room.room_name} is {room.state}.",
                "department": room.department,
                "episode_refs": [room.current_episode_ref, room.next_episode_ref],
                "next_action": "Release room, complete cleaning, or reroute the next case.",
            })

    for item in open_work:
        if item.urgency in {"red", "amber"}:
            conflicts.append({
                "type": "open_work_pressure",
                "severity": item.urgency,
                "detail": item.description,
                "department": item.section_name or "Work queue",
                "episode_refs": [item.linked_episode_ref],
                "next_action": f"{item.owner_role} must action: {item.title}",
                "work_item_id": item.id,
            })

    conflicts.sort(key=lambda conflict: severity_rank(str(conflict.get("severity", "green"))), reverse=True)
    return conflicts


def pulse(session: Session) -> dict[str, Any]:
    conflicts = normalised_conflicts(session)
    work = session.exec(select(WorkItem).where(WorkItem.status != "done")).all()
    active_cases = session.exec(select(Episode).where(Episode.status == "active")).all()
    blocks = session.exec(select(ScheduleBlock).where(ScheduleBlock.status != "done")).all()
    rooms = session.exec(select(RoomState)).all()
    unack_handoffs = session.exec(select(Handover).where(Handover.acknowledged == False)).all()
    pending_results = session.exec(select(ResultReview).where(ResultReview.status == "pending_review")).all()

    by_severity = Counter([str(conflict.get("severity", "green")) for conflict in conflicts])
    by_type = Counter([str(conflict.get("type", "unknown")) for conflict in conflicts])
    by_department = Counter([str(conflict.get("department", "Unassigned")) for conflict in conflicts])
    red = by_severity.get("red", 0) + by_severity.get("high", 0)
    amber = by_severity.get("amber", 0) + by_severity.get("medium", 0)
    blocked_rooms = len([room for room in rooms if room.state in {"blocked", "cleaning"}])
    pressure_score = min(100, red * 15 + amber * 7 + blocked_rooms * 8 + len(unack_handoffs) * 8 + len(pending_results) * 6)

    return {
        "generated_at": utc_now().isoformat(),
        "state": "red" if pressure_score >= 70 else "amber" if pressure_score >= 35 else "green",
        "pressure_score": pressure_score,
        "active_case_count": len(active_cases),
        "active_schedule_block_count": len(blocks),
        "open_work_count": len(work),
        "conflict_count": len(conflicts),
        "red_conflicts": red,
        "amber_conflicts": amber,
        "blocked_room_count": blocked_rooms,
        "unacknowledged_handoffs": len(unack_handoffs),
        "pending_result_reviews": len(pending_results),
        "conflicts_by_type": dict(by_type),
        "conflicts_by_department": dict(by_department),
        "conflicts": conflicts[:120],
    }


def create_conflict_work_item(session: Session, conflict: dict[str, Any]) -> tuple[ConflictAction, WorkItem]:
    title = f"Resolve {conflict.get('type', 'conflict')}"
    detail = str(conflict.get("detail", title))
    department = str(conflict.get("department", "Operations"))
    severity = str(conflict.get("severity", "amber"))
    urgency = "red" if severity in {"red", "high"} else "amber"
    episode_refs = [ref for ref in conflict.get("episode_refs", []) if ref]

    existing = session.exec(
        select(ConflictAction).where(
            ConflictAction.status == "open",
            ConflictAction.conflict_type == str(conflict.get("type", "unknown")),
            ConflictAction.detail == detail,
        )
    ).first()
    if existing and existing.linked_work_item_id:
        item = session.get(WorkItem, existing.linked_work_item_id)
        if item:
            return existing, item

    item = WorkItem(
        title=title,
        input_type="conflict_engine",
        source="conflict_engine",
        category="conflict",
        description=str(conflict.get("next_action") or detail),
        urgency=urgency,
        owner_role="ops_manager",
        section_name=department,
        linked_episode_ref=episode_refs[0] if episode_refs else None,
        status="new",
        due_at=utc_now() + timedelta(minutes=15 if urgency == "red" else 45),
    )
    session.add(item)
    session.flush()

    action = ConflictAction(
        conflict_type=str(conflict.get("type", "unknown")),
        severity=urgency,
        detail=detail,
        status="open",
        linked_work_item_id=item.id,
    )
    session.add(action)
    session.flush()
    return action, item


@router.get("/conflicts")
def get_conflicts(session: Session = Depends(get_session)):
    conflicts = normalised_conflicts(session)
    return {"count": len(conflicts), "conflicts": conflicts}


@router.post("/recalculate")
def recalculate_conflicts(session: Session = Depends(get_session)):
    conflicts = normalised_conflicts(session)
    audit = write_audit(session, "LucyVet Conflict Engine", "conflicts_recalculated", "system", 0, f"Recalculated {len(conflicts)} conflicts")
    return {"ok": True, "count": len(conflicts), "conflicts": conflicts, "audit_event": audit}


@router.post("/to-work-items")
def conflicts_to_work_items(session: Session = Depends(get_session)):
    conflicts = normalised_conflicts(session)
    selected = [conflict for conflict in conflicts if severity_rank(str(conflict.get("severity", "green"))) >= 2]
    created = []
    for conflict in selected[:30]:
        action, item = create_conflict_work_item(session, conflict)
        created.append({"conflict_action": row(action), "work_item": row(item)})
    session.commit()
    audit = write_audit(session, "LucyVet Conflict Engine", "conflicts_converted_to_work_items", "system", 0, f"Converted {len(created)} conflicts to work items")
    return {"ok": True, "created_count": len(created), "created": created, "audit_event": audit}


@router.get("/pulse")
def get_pulse(session: Session = Depends(get_session)):
    return pulse(session)
