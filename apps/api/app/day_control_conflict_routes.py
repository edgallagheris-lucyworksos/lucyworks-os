from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.schedule_state_models import ScheduleStateBlock

router = APIRouter(prefix="/api/day-control", tags=["day-control"])


def _row(row: ScheduleStateBlock) -> dict[str, Any]:
    return {
        "id": row.id,
        "time": row.time,
        "lane": row.lane,
        "what": row.what,
        "who": row.who,
        "where": row.where,
        "status": row.status,
        "blocker": row.blocker,
        "next": row.next,
        "subject": row.subject,
    }


@router.get("/conflicts")
def list_day_control_conflicts(session: Session = Depends(get_session)) -> dict[str, Any]:
    blocks = session.exec(select(ScheduleStateBlock).order_by(ScheduleStateBlock.time, ScheduleStateBlock.lane)).all()
    warnings: list[dict[str, Any]] = []

    by_time_place: dict[tuple[str, str], list[ScheduleStateBlock]] = defaultdict(list)
    by_time_owner: dict[tuple[str, str], list[ScheduleStateBlock]] = defaultdict(list)

    for block in blocks:
        if block.where and block.where not in {"Reception", "Admin queue", "Client contact"}:
            by_time_place[(block.time, block.where)].append(block)
        if block.who:
            by_time_owner[(block.time, block.who)].append(block)
        if block.blocker != "none":
            warnings.append({
                "type": "blocker",
                "severity": "red" if block.status == "red" else "amber",
                "title": f"{block.time} {block.what}",
                "detail": f"{block.blocker} -> {block.next}",
                "blocks": [_row(block)],
            })
        if block.lane in {"insurance", "reception"} and block.blocker != "none":
            warnings.append({
                "type": "admin_blocker",
                "severity": "amber",
                "title": f"Admin unresolved: {block.subject or block.what}",
                "detail": f"{block.blocker} -> {block.next}",
                "blocks": [_row(block)],
            })
        if block.lane == "client" and block.blocker != "none":
            warnings.append({
                "type": "contact_update_blocked",
                "severity": "amber",
                "title": f"Contact update blocked: {block.subject or block.what}",
                "detail": f"{block.blocker} -> {block.next}",
                "blocks": [_row(block)],
            })

    for (time, place), matching in by_time_place.items():
        if len(matching) > 1:
            warnings.append({
                "type": "resource_clash",
                "severity": "red",
                "title": f"Resource clash at {time}: {place}",
                "detail": " / ".join(block.what for block in matching),
                "blocks": [_row(block) for block in matching],
            })

    for (time, owner), matching in by_time_owner.items():
        if len(matching) > 1:
            warnings.append({
                "type": "owner_clash",
                "severity": "amber",
                "title": f"Owner clash at {time}: {owner}",
                "detail": " / ".join(block.what for block in matching),
                "blocks": [_row(block) for block in matching],
            })

    return {"conflicts": warnings, "count": len(warnings)}
