from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/operational-actions", tags=["operational-actions"])


class ActionRequest(BaseModel):
    action: str
    target_id: str
    target_label: str
    target_type: str
    owner_role: str | None = None
    blocker: str | None = None
    next_action: str | None = None


EVENTS: list[dict] = []


@router.post("/execute")
def execute_action(request: ActionRequest):
    event = {
        "id": f"opact-{len(EVENTS) + 1:05d}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "action": request.action,
        "target_id": request.target_id,
        "target_label": request.target_label,
        "target_type": request.target_type,
        "owner_role": request.owner_role,
        "blocker": request.blocker,
        "next_action": request.next_action,
    }
    EVENTS.append(event)
    return {"ok": True, "event": event}


@router.get("/events")
def list_events():
    return {"events": EVENTS[-100:]}
