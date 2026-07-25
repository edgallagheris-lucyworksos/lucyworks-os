from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated
from app.database import engine, get_session
from app.v7_event_service import event_dict, publish_event
from app.v7_models import DurableEvent

router = APIRouter(prefix="/api/v7/events", tags=["durable-realtime"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PublishPayload(BaseModel):
    event_type: str
    aggregate_type: str
    aggregate_ref: str
    payload: dict[str, Any] = Field(default_factory=dict)
    premises_ref: str = "default-premises"
    severity: str = "info"
    correlation_id: str | None = None
    causation_ref: str | None = None
    idempotency_key: str | None = None


@router.get("")
def list_events(
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = session.exec(
        select(DurableEvent)
        .where(DurableEvent.sequence > after_sequence)
        .order_by(DurableEvent.sequence)
        .limit(limit)
    ).all()
    return {
        "events": [event_dict(row) for row in rows],
        "nextSequence": rows[-1].sequence if rows else after_sequence,
        "hasMore": len(rows) == limit,
    }


@router.post("")
def publish(
    payload: PublishPayload,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = publish_event(
        session,
        event_type=payload.event_type,
        aggregate_type=payload.aggregate_type,
        aggregate_ref=payload.aggregate_ref,
        payload=payload.payload,
        premises_ref=payload.premises_ref,
        severity=payload.severity,
        correlation_id=payload.correlation_id,
        causation_ref=payload.causation_ref,
        idempotency_key=payload.idempotency_key,
    )
    session.commit()
    session.refresh(row)
    return {"event": event_dict(row)}


async def stream_events(request: Request, after_sequence: int):
    cursor = max(0, after_sequence)
    last_keepalive = utc_now()
    while True:
        if await request.is_disconnected():
            return
        with Session(engine) as session:
            rows = session.exec(
                select(DurableEvent)
                .where(DurableEvent.sequence > cursor)
                .order_by(DurableEvent.sequence)
                .limit(250)
            ).all()
        if rows:
            for row in rows:
                cursor = row.sequence
                yield f"id: {row.sequence}\n"
                yield f"event: {row.event_type}\n"
                yield f"data: {json.dumps(event_dict(row), default=str)}\n\n"
            last_keepalive = utc_now()
            continue
        if (utc_now() - last_keepalive).total_seconds() >= 15:
            yield f"event: keepalive\ndata: {json.dumps({'sequence': cursor, 'createdAt': utc_now().isoformat()})}\n\n"
            last_keepalive = utc_now()
        await asyncio.sleep(1)


@router.get("/stream")
def stream(
    request: Request,
    after_sequence: int = Query(default=0, ge=0),
    _: AuthContext = Depends(require_authenticated),
) -> StreamingResponse:
    return StreamingResponse(
        stream_events(request, after_sequence),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
