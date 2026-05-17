from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.models import AuditEvent, MessageEntry, MessageThread
from app.schemas import MessageEntryCreate

router = APIRouter()


def log(session: Session, actor: str, action: str, entity: str, entity_id: int, summary: str):
    session.add(
        AuditEvent(
            actor_name=actor,
            action=action,
            entity_type=entity,
            entity_id=entity_id,
            summary=summary,
        )
    )
    session.commit()


@router.post("/api/messages/{thread_id}")
def create_message(
    thread_id: int,
    payload: MessageEntryCreate,
    session: Session = Depends(get_session),
):
    thread = session.get(MessageThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Message thread not found")

    entry = MessageEntry(
        thread_id=thread_id,
        sender_name=payload.sender_name,
        direction=payload.direction,
        body=payload.body,
        material_decision_flag=payload.material_decision_flag,
    )

    session.add(entry)
    session.commit()
    session.refresh(entry)

    thread.status = "active"
    session.add(thread)
    session.commit()

    log(
        session,
        payload.actor_name,
        "created",
        "message_entry",
        entry.id or 0,
        f"Message added to thread {thread_id}",
    )

    return entry
