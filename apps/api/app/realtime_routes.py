import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.conflict_engine_routes import pulse, normalised_conflicts
from app.database import get_session
from app.models import AuditEvent, ScheduleBlock, WorkItem

router = APIRouter(prefix="/api/realtime", tags=["realtime"])

EVENT_BUFFER: list[dict[str, Any]] = []
MAX_EVENTS = 200


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PublishEventPayload(BaseModel):
    event_type: str = "manual_update"
    title: str
    detail: str = ""
    severity: str = "info"
    source: str = "manual"
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    actor_name: str = "LucyWorks Realtime"


def push_event(event: dict[str, Any]) -> dict[str, Any]:
    event = {"id": len(EVENT_BUFFER) + 1, "created_at": utc_now(), **event}
    EVENT_BUFFER.append(event)
    if len(EVENT_BUFFER) > MAX_EVENTS:
        del EVENT_BUFFER[:-MAX_EVENTS]
    return event


def write_audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str) -> AuditEvent:
    event = AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def generated_events(session: Session) -> list[dict[str, Any]]:
    pulse_state = pulse(session)
    conflicts = normalised_conflicts(session)
    open_work = session.exec(select(WorkItem).where(WorkItem.status != "done")).all()
    active_blocks = session.exec(select(ScheduleBlock).where(ScheduleBlock.status != "done").order_by(ScheduleBlock.starts_at)).all()
    events = [
        {
            "id": "pulse-current",
            "created_at": utc_now(),
            "event_type": "pulse_update",
            "title": f"Pulse {pulse_state.get('state', 'unknown')}",
            "detail": f"Pressure score {pulse_state.get('pressure_score', 0)} with {pulse_state.get('conflict_count', 0)} conflicts.",
            "severity": pulse_state.get("state", "info"),
            "source": "pulse",
            "payload": pulse_state,
        },
        {
            "id": "work-current",
            "created_at": utc_now(),
            "event_type": "work_queue_update",
            "title": f"{len(open_work)} open work items",
            "detail": "Live role queues have open work.",
            "severity": "amber" if open_work else "green",
            "source": "role_queues",
            "payload": {"open_work_count": len(open_work)},
        },
        {
            "id": "scheduler-current",
            "created_at": utc_now(),
            "event_type": "scheduler_update",
            "title": f"{len(active_blocks)} active schedule blocks",
            "detail": "Scheduler has active blocks not marked done.",
            "severity": "info",
            "source": "scheduler",
            "payload": {"active_schedule_block_count": len(active_blocks)},
        },
    ]
    if conflicts:
        events.append(
            {
                "id": "conflict-current",
                "created_at": utc_now(),
                "event_type": "conflict_update",
                "title": f"{len(conflicts)} live conflicts",
                "detail": "Conflict engine reports current pressure.",
                "severity": str(conflicts[0].get("severity", "amber")),
                "source": "conflict_engine",
                "payload": {"conflicts": conflicts[:25]},
            }
        )
    return events


@router.get("/events")
def events(session: Session = Depends(get_session)):
    generated = generated_events(session)
    return {"count": len(generated) + len(EVENT_BUFFER), "generated": generated, "published": EVENT_BUFFER[-80:]}


@router.post("/publish")
def publish(payload: PublishEventPayload, session: Session = Depends(get_session)):
    event = push_event(
        {
            "event_type": payload.event_type,
            "title": payload.title,
            "detail": payload.detail,
            "severity": payload.severity,
            "source": payload.source,
            "entity_type": payload.entity_type,
            "entity_id": payload.entity_id,
        }
    )
    audit = write_audit(
        session,
        payload.actor_name,
        "realtime_event_published",
        payload.entity_type or "realtime",
        payload.entity_id or 0,
        f"Published {payload.event_type}: {payload.title}",
    )
    return {"ok": True, "event": event, "audit_event": audit}


@router.get("/status")
def status(session: Session = Depends(get_session)):
    snapshot = generated_events(session)
    return {
        "generated_at": utc_now(),
        "stream": "available",
        "published_buffer_count": len(EVENT_BUFFER),
        "snapshot_event_count": len(snapshot),
        "event_types": ["pulse_update", "conflict_update", "work_queue_update", "scheduler_update", "shadow_mode_update", "access_audit_update", "manual_update"],
    }


async def event_generator(session: Session):
    for event in generated_events(session):
        yield f"event: {event['event_type']}\n"
        yield f"data: {json.dumps(event, default=str)}\n\n"
    while True:
        keepalive = {"event_type": "keepalive", "created_at": utc_now(), "title": "LucyWorks realtime stream alive"}
        yield "event: keepalive\n"
        yield f"data: {json.dumps(keepalive)}\n\n"
        await asyncio.sleep(15)


@router.get("/stream")
def stream(session: Session = Depends(get_session)):
    return StreamingResponse(event_generator(session), media_type="text/event-stream")
