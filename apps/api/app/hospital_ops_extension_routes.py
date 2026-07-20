from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth import AuthContext, require_authenticated, require_roles
from app.database import get_session
from app.hospital_ops_extensions import patch_episode_gates, resolve_reconciliation_item, shadow_comparison
from app.hospital_ops_service import command_dict, episode_dict

router = APIRouter(prefix="/api/hospital-ops", tags=["hospital-operating-system-v3-extensions"])

OPERATIONAL_WRITE_ROLES = ("clinician", "clinical_director", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor")
IMPORT_ROLES = ("admin", "clinical_director", "governance_lead", "hospital_director", "ops_manager", "senior_clinician", "supervisor")


class EpisodeGatePatch(BaseModel):
    expectedVersion: int
    gates: dict[str, Any]
    nextAction: str | None = None
    reason: str | None = None
    overrideReason: str | None = None
    idempotencyKey: str | None = None


class ReconciliationResolution(BaseModel):
    correctedRecord: dict[str, Any] = Field(default_factory=dict)


@router.patch("/episodes/{episode_ref}/gates")
def record_episode_gates(
    episode_ref: str,
    payload: EpisodeGatePatch,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*OPERATIONAL_WRITE_ROLES)),
) -> dict[str, Any]:
    row, command = patch_episode_gates(session, episode_ref, payload.model_dump(exclude_none=True), auth)
    session.commit()
    session.refresh(row)
    return {"episode": episode_dict(row), "command": command_dict(command)}


@router.patch("/imports/{batch_ref}/items/{item_ref}/resolve")
def resolve_import_item(
    batch_ref: str,
    item_ref: str,
    payload: ReconciliationResolution,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*IMPORT_ROLES)),
) -> dict[str, Any]:
    batch, item = resolve_reconciliation_item(session, batch_ref, item_ref, payload.correctedRecord, auth)
    session.commit()
    return {
        "batchRef": batch.batch_ref,
        "status": batch.status,
        "acceptedCount": batch.accepted_count,
        "rejectedCount": batch.rejected_count,
        "item": {"itemRef": item.item_ref, "status": item.status, "resolvedBySubject": item.resolved_by_subject},
    }


@router.get("/shadow/compare")
def compare_shadow_state(
    premises_ref: str = "default-premises",
    operational_date: date = Query(default_factory=date.today),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    return shadow_comparison(session, premises_ref, operational_date)
