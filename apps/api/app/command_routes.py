from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.access_control_routes import allowed
from app.database import get_session
from app.models import AuditEvent, DischargeReadiness, Episode, Handover, ResultReview, WorkItem
from app.realtime_routes import push_event

router = APIRouter(prefix="/api/command", tags=["command"])

COMMAND_HISTORY: list[dict[str, Any]] = []
MAX_HISTORY = 300


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def row(obj: Any) -> dict[str, Any]:
    fields = getattr(obj, "model_fields", {})
    return {name: getattr(obj, name) for name in fields}


class CommandPayload(BaseModel):
    command: str
    actor_name: str = "LucyWorks Command"
    role: str = "ops_manager"
    episode_id: Optional[int] = None
    episode_ref: Optional[str] = None
    department: Optional[str] = None
    room_name: Optional[str] = None
    section_name: Optional[str] = None
    owner_role: Optional[str] = None
    target_owner: Optional[str] = None
    note: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    urgency: str = "amber"
    result_review_id: Optional[int] = None
    handover_id: Optional[int] = None
    metadata: dict[str, Any] = {}


def write_audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str) -> AuditEvent:
    event = AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def find_episode(session: Session, payload: CommandPayload) -> Episode:
    episode = None
    if payload.episode_id:
        episode = session.get(Episode, payload.episode_id)
    if not episode and payload.episode_ref:
        episode = session.exec(select(Episode).where(Episode.episode_ref == payload.episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


def permission_for_command(command: str) -> str:
    if command in {"move_episode", "create_work_item"}:
        return "manage_flow"
    if command in {"review_result"}:
        return "review_results"
    if command in {"create_handoff", "acknowledge_handoff"}:
        return "manage_care_tasks"
    if command in {"mark_meds_ready", "mark_owner_updated", "approve_discharge", "close_case"}:
        return "manage_flow"
    return "manage_flow"


def remember(command: dict[str, Any]) -> dict[str, Any]:
    record = {"id": len(COMMAND_HISTORY) + 1, "created_at": utc_now().isoformat(), **command}
    COMMAND_HISTORY.append(record)
    if len(COMMAND_HISTORY) > MAX_HISTORY:
        del COMMAND_HISTORY[:-MAX_HISTORY]
    return record


def ensure_discharge(session: Session, episode_id: int) -> DischargeReadiness:
    readiness = session.exec(select(DischargeReadiness).where(DischargeReadiness.episode_id == episode_id)).first()
    if not readiness:
        readiness = DischargeReadiness(episode_id=episode_id, blocker_summary="Created by command layer", status="open")
        session.add(readiness)
        session.flush()
    return readiness


@router.post("/execute")
def execute(payload: CommandPayload, session: Session = Depends(get_session)):
    permission = permission_for_command(payload.command)
    ok, reason = allowed(payload.role, permission, payload.department or payload.section_name)
    if not ok:
        raise HTTPException(status_code=403, detail=reason)

    episode: Optional[Episode] = None
    changed: dict[str, Any] = {}
    entity_type = "command"
    entity_id = 0

    if payload.command == "move_episode":
        episode = find_episode(session, payload)
        if payload.section_name:
            episode.current_section_name = payload.section_name
        if payload.room_name:
            episode.current_room_name = payload.room_name
        if payload.metadata.get("phase"):
            episode.current_phase = str(payload.metadata["phase"])
        session.add(episode)
        changed = {"episode": row(episode)}
        entity_type = "episode"
        entity_id = episode.id or 0

    elif payload.command == "create_handoff":
        episode = find_episode(session, payload)
        handoff = Handover(
            episode_id=episode.id,
            from_owner=payload.owner_role or payload.role,
            to_owner=payload.target_owner or payload.owner_role or "nurse",
            note=payload.note or "Command-created handoff",
        )
        session.add(handoff)
        session.flush()
        changed = {"handover": row(handoff)}
        entity_type = "handover"
        entity_id = handoff.id or 0

    elif payload.command == "acknowledge_handoff":
        handoff = session.get(Handover, payload.handover_id) if payload.handover_id else None
        if not handoff:
            raise HTTPException(status_code=404, detail="Handover not found")
        handoff.acknowledged = True
        session.add(handoff)
        changed = {"handover": row(handoff)}
        entity_type = "handover"
        entity_id = handoff.id or 0

    elif payload.command == "review_result":
        result = session.get(ResultReview, payload.result_review_id) if payload.result_review_id else None
        if not result:
            raise HTTPException(status_code=404, detail="Result review not found")
        result.status = "reviewed"
        result.required_action = payload.note or result.required_action
        result.reviewed_at = utc_now()
        session.add(result)
        changed = {"result_review": row(result)}
        entity_type = "result_review"
        entity_id = result.id or 0

    elif payload.command in {"mark_meds_ready", "mark_owner_updated", "approve_discharge"}:
        episode = find_episode(session, payload)
        readiness = ensure_discharge(session, episode.id)
        if payload.command == "mark_meds_ready":
            readiness.medication_ready = True
        if payload.command == "mark_owner_updated":
            readiness.owner_updated = True
        if payload.command == "approve_discharge":
            readiness.clinician_signoff = True
            readiness.admin_ready = True
            readiness.care_instructions_ready = True
            readiness.results_reviewed = True
            readiness.readiness_state = "ready" if readiness.medication_ready and readiness.owner_updated else "part_ready"
        session.add(readiness)
        changed = {"discharge_readiness": row(readiness)}
        entity_type = "discharge_readiness"
        entity_id = readiness.id or 0

    elif payload.command == "close_case":
        episode = find_episode(session, payload)
        episode.status = "closed"
        episode.current_phase = "closed"
        session.add(episode)
        changed = {"episode": row(episode)}
        entity_type = "episode"
        entity_id = episode.id or 0

    elif payload.command == "create_work_item":
        item = WorkItem(
            title=payload.title or "Command-created work item",
            input_type="command",
            source="command_layer",
            category="operational",
            description=payload.description or payload.note or "Created by command layer",
            urgency=payload.urgency,
            owner_role=payload.owner_role or payload.role,
            section_name=payload.section_name,
            room_name=payload.room_name,
            linked_episode_ref=payload.episode_ref,
        )
        session.add(item)
        session.flush()
        changed = {"work_item": row(item)}
        entity_type = "work_item"
        entity_id = item.id or 0

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported command {payload.command}")

    session.commit()
    audit = write_audit(session, payload.actor_name, f"command_{payload.command}", entity_type, entity_id, payload.note or f"Executed {payload.command}")
    event = push_event(
        {
            "event_type": "command_executed",
            "title": payload.command,
            "detail": payload.note or f"{payload.actor_name} executed {payload.command}",
            "severity": payload.urgency,
            "source": "command_layer",
            "entity_type": entity_type,
            "entity_id": entity_id,
        }
    )
    history = remember(
        {
            "command": payload.command,
            "actor_name": payload.actor_name,
            "role": payload.role,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "changed": changed,
            "audit_event_id": audit.id,
            "realtime_event_id": event["id"],
        }
    )
    return {"ok": True, "command": payload.command, "changed": changed, "audit_event": audit, "realtime_event": event, "history": history}


@router.get("/status")
def status():
    return {
        "available": True,
        "supported_commands": [
            "move_episode",
            "create_handoff",
            "acknowledge_handoff",
            "review_result",
            "mark_meds_ready",
            "mark_owner_updated",
            "approve_discharge",
            "close_case",
            "create_work_item",
        ],
        "history_count": len(COMMAND_HISTORY),
    }


@router.get("/history")
def history():
    return {"count": len(COMMAND_HISTORY), "commands": COMMAND_HISTORY[-120:]}
