from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/day-control", tags=["day-control"])

_BLOCKS: dict[str, dict[str, Any]] = {}
_AUDIT: list[dict[str, Any]] = []


class BlockPatch(BaseModel):
    time: str | None = None
    lane: str | None = None
    what: str | None = None
    who: str | None = None
    where: str | None = None
    how: str | None = None
    status: str | None = None
    blocker: str | None = None
    next: str | None = None
    route: str | None = None
    subject: str | None = None
    durationMinutes: int | None = None
    generatedFrom: str | None = None


class BlockCreate(BaseModel):
    id: str | None = None
    time: str
    lane: str
    what: str
    who: str
    where: str
    how: str
    status: str = "amber"
    blocker: str = "none"
    next: str = "continue planned flow"
    route: str = "/hospital-board"
    subject: str | None = None
    durationMinutes: int | None = None
    generatedFrom: str | None = None


class ActionPayload(BaseModel):
    action: str = Field(min_length=1)
    actor: str = "system"
    reason: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(block_id: str, action: str, actor: str, before: dict[str, Any] | None, after: dict[str, Any] | None, reason: str | None = None) -> None:
    _AUDIT.append({"id": str(uuid4()), "time": _now(), "blockId": block_id, "action": action, "actor": actor, "reason": reason, "before": before, "after": after})


def _apply_action(block: dict[str, Any], action: str) -> dict[str, Any]:
    updated = dict(block)
    if action == "resolve":
        updated.update({"status": "green", "blocker": "none", "next": "complete or continue planned flow"})
    elif action == "hold":
        updated.update({"status": "blue", "blocker": "on hold", "next": "review hold reason"})
    elif action == "escalate":
        updated.update({"status": "red", "blocker": updated.get("blocker") if updated.get("blocker") != "none" else "escalated", "next": "senior review required"})
    elif action == "request_review":
        updated.update({"status": "amber", "next": "review requested"})
    elif action == "assign":
        updated.update({"status": "red" if updated.get("status") == "red" else "amber", "next": "owner assigned"})
    elif action == "handover":
        updated.update({"status": "green", "blocker": "none", "next": "handover complete"})
    elif action == "owner_update":
        updated.update({"status": "green", "blocker": "none", "next": "update recorded"})
    else:
        updated.update({"status": "amber", "next": f"{action.replace('_', ' ')} requested"})
    updated["updatedAt"] = _now()
    return updated


@router.get("/blocks")
def list_blocks() -> dict[str, Any]:
    return {"blocks": list(_BLOCKS.values()), "count": len(_BLOCKS)}


@router.post("/blocks")
def create_block(payload: BlockCreate) -> dict[str, Any]:
    data = payload.model_dump()
    block_id = data.get("id") or str(uuid4())
    data["id"] = block_id
    data["createdAt"] = _now()
    data["updatedAt"] = data["createdAt"]
    _BLOCKS[block_id] = data
    _audit(block_id, "create", "system", None, data)
    return {"block": data}


@router.put("/blocks/bulk")
def replace_blocks(payload: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    blocks = payload.get("blocks", [])
    _BLOCKS.clear()
    for block in blocks:
        block_id = str(block.get("id") or uuid4())
        block["id"] = block_id
        block["updatedAt"] = _now()
        _BLOCKS[block_id] = block
    _audit("bulk", "replace_blocks", "system", None, {"count": len(_BLOCKS)})
    return {"blocks": list(_BLOCKS.values()), "count": len(_BLOCKS)}


@router.patch("/blocks/{block_id}")
def update_block(block_id: str, payload: BlockPatch) -> dict[str, Any]:
    if block_id not in _BLOCKS:
        raise HTTPException(status_code=404, detail="block not found")
    before = dict(_BLOCKS[block_id])
    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    _BLOCKS[block_id].update(changes)
    _BLOCKS[block_id]["updatedAt"] = _now()
    _audit(block_id, "update", "system", before, dict(_BLOCKS[block_id]))
    return {"block": _BLOCKS[block_id]}


@router.post("/blocks/{block_id}/actions")
def apply_action(block_id: str, payload: ActionPayload) -> dict[str, Any]:
    if block_id not in _BLOCKS:
        raise HTTPException(status_code=404, detail="block not found")
    before = dict(_BLOCKS[block_id])
    after = _apply_action(before, payload.action)
    _BLOCKS[block_id] = after
    _audit(block_id, payload.action, payload.actor, before, after, payload.reason)
    return {"block": after}


@router.get("/audit")
def list_audit() -> dict[str, Any]:
    return {"audit": _AUDIT[-250:], "count": len(_AUDIT)}
