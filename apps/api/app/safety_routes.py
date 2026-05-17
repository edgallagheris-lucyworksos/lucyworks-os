from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    AuditEvent,
    Blocker,
    DecisionRecord,
    DischargeReadiness,
    Episode,
    EthicsFlag,
    MessageEntry,
    MessageThread,
    OwnerCommsRequirement,
    PharmacyRequest,
    RoomState,
    StockOrder,
    WorkItem,
)

router = APIRouter()


@router.post("/api/messages/{thread_id}")
def create_message_entry(thread_id: int, payload: dict, session: Session = Depends(get_session)):
    thread = session.get(MessageThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Message thread not found")
    entry = MessageEntry(
        thread_id=thread_id,
        sender_name=payload.get("sender_name", "LucyWorks User"),
        direction=payload.get("direction", "outbound"),
        body=payload.get("body", ""),
        material_decision_flag=bool(payload.get("material_decision_flag", False)),
    )
    session.add(entry)
    thread.status = "updated"
    session.add(thread)
    session.commit()
    session.refresh(entry)
    session.add(AuditEvent(actor_name=payload.get("actor_name", "Mail Ops"), action="message_created", entity_type="message_entry", entity_id=entry.id or 0, summary=f"Message added to thread {thread.subject}"))
    session.commit()
    return entry


@router.post("/api/room-states/{room_state_id}/set")
def set_room_state(room_state_id: int, state: str, session: Session = Depends(get_session)):
    room = session.get(RoomState, room_state_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room state not found")
    allowed = {"available", "occupied", "cleaning", "blocked", "offline"}
    if state not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid room state. Allowed: {sorted(allowed)}")
    room.state = state
    session.add(room)
    session.commit()
    session.refresh(room)
    session.add(AuditEvent(actor_name="Rooms", action="state_updated", entity_type="room_state", entity_id=room.id or 0, summary=f"{room.room_name} set to {state}"))
    session.commit()
    return room


@router.get("/api/flow-readiness/{episode_id}")
def flow_readiness(episode_id: int, session: Session = Depends(get_session)):
    episode = session.get(Episode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    hard_blocks = []
    warnings = []

    discharge = session.exec(select(DischargeReadiness).where(DischargeReadiness.episode_id == episode_id)).all()
    for item in discharge:
        if item.readiness_state != "ready":
            hard_blocks.append({"type": "discharge_not_ready", "section": "Discharge", "detail": item.blocker_summary or "Discharge readiness incomplete", "owner_role": item.owner_role, "urgency": item.urgency})

    pharmacy = session.exec(select(PharmacyRequest).where(PharmacyRequest.episode_id == episode_id)).all()
    for item in pharmacy:
        if item.status != "complete":
            hard_blocks.append({"type": "pharmacy_open", "section": "Pharmacy", "detail": f"{item.medication_name} is {item.status}", "owner_role": item.owner_role, "urgency": item.urgency})

    stock_orders = session.exec(select(StockOrder).where(StockOrder.episode_id == episode_id)).all()
    for item in stock_orders:
        if item.status != "complete":
            hard_blocks.append({"type": "stock_order_open", "section": "Stock", "detail": f"{item.item_name}: {item.reason}", "owner_role": "nurse", "urgency": item.urgency})

    owner_comms = session.exec(select(OwnerCommsRequirement).where(OwnerCommsRequirement.episode_id == episode_id)).all()
    for item in owner_comms:
        if item.status != "complete":
            warnings.append({"type": "owner_comms_due", "section": "Mail Ops", "detail": item.required_message, "owner_role": item.owner_role, "urgency": item.urgency})

    ethics = session.exec(select(EthicsFlag).where(EthicsFlag.episode_id == episode_id)).all()
    for item in ethics:
        if item.status != "resolved":
            hard_blocks.append({"type": "ethics_open", "section": "Lucy Ethics", "detail": item.detail, "owner_role": item.owner_role, "urgency": "red" if item.severity == "high" else "amber"})

    decisions = session.exec(select(DecisionRecord).where(DecisionRecord.episode_id == episode_id)).all()
    for item in decisions:
        if item.status != "resolved":
            warnings.append({"type": "decision_open", "section": item.section_name or "Decision", "detail": item.decision_needed, "owner_role": item.owner_role, "urgency": item.urgency})

    blockers = session.exec(select(Blocker).where(Blocker.episode_id == episode_id)).all()
    for item in blockers:
        if item.status != "resolved":
            hard_blocks.append({"type": "blocker_open", "section": item.section_name, "detail": item.detail, "owner_role": item.owner_role, "urgency": item.urgency})

    ep_ref = episode.episode_ref
    work_items = session.exec(select(WorkItem).where(WorkItem.linked_episode_ref == ep_ref)).all()
    red_work = [item for item in work_items if item.status != "done" and item.urgency == "red"]
    for item in red_work:
        hard_blocks.append({"type": "red_work_open", "section": item.section_name or item.category, "detail": item.title, "owner_role": item.owner_role, "urgency": item.urgency})

    ready_for_flow = len(hard_blocks) == 0
    caution = len(warnings) > 0

    return {
        "episode_id": episode_id,
        "episode_ref": ep_ref,
        "ready_for_flow": ready_for_flow,
        "caution": caution,
        "hard_block_count": len(hard_blocks),
        "warning_count": len(warnings),
        "hard_blocks": hard_blocks,
        "warnings": warnings,
    }
