from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import AuthContext, SENIOR_ROLES, require_authenticated
from app.database import get_session
from app.evidence_service import create_evidence_event
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock
from app.v7_event_service import publish_event
from app.v7_models import CanonicalShadowComparison

router = APIRouter(prefix="/api/v7/shadow", tags=["canonical-shadow-mode"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def comparison_dict(row: CanonicalShadowComparison) -> dict[str, Any]:
    return {
        "comparisonRef": row.comparison_ref,
        "premisesRef": row.premises_ref,
        "sourceSystem": row.source_system,
        "sourceRecordRef": row.source_record_ref,
        "episodeRef": row.episode_ref,
        "blockRef": row.block_ref,
        "sourceSnapshot": row.source_snapshot,
        "canonicalSnapshot": row.canonical_snapshot,
        "mismatchCodes": row.mismatch_codes,
        "validationState": row.validation_state,
        "status": row.status,
        "version": row.version,
        "reviewedBy": row.reviewed_by_name,
        "reviewedByRole": row.reviewed_by_role,
        "reviewNote": row.review_note,
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


class SourceRow(BaseModel):
    source_record_ref: str
    episode_ref: str | None = None
    block_ref: str | None = None
    patient_name: str | None = None
    phase: str | None = None
    status: str | None = None
    area_ref: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    owner_role: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ImportPayload(BaseModel):
    premises_ref: str = "default-premises"
    source_system: str
    rows: list[SourceRow]


class ReviewPayload(BaseModel):
    expected_version: int
    decision: str
    note: str


def canonical_snapshot(session: Session, row: SourceRow) -> tuple[dict[str, Any], list[str]]:
    snapshot: dict[str, Any] = {}
    mismatches: list[str] = []
    episode = None
    block = None
    if row.episode_ref:
        episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == row.episode_ref)).first()
        if not episode:
            mismatches.append("unknown_episode")
        else:
            snapshot["episode"] = {
                "episodeRef": episode.episode_ref,
                "patientName": episode.patient_name,
                "phase": episode.phase,
                "status": episode.status,
                "ownerRole": episode.owner_role,
                "currentAreaRef": episode.current_area_ref,
                "version": episode.version,
            }
            if row.patient_name and row.patient_name.strip().lower() != episode.patient_name.strip().lower():
                mismatches.append("patient_name_mismatch")
            if row.phase and row.phase.strip().lower() != episode.phase.strip().lower():
                mismatches.append("phase_mismatch")
            if row.status and row.status.strip().lower() != episode.status.strip().lower():
                mismatches.append("status_mismatch")
            if row.owner_role and row.owner_role.strip().lower() != episode.owner_role.strip().lower():
                mismatches.append("owner_role_mismatch")
            if row.area_ref and row.area_ref != episode.current_area_ref:
                mismatches.append("episode_area_mismatch")
    if row.block_ref:
        block = session.exec(select(OperationalBlock).where(OperationalBlock.block_ref == row.block_ref)).first()
        if not block:
            mismatches.append("unknown_block")
        else:
            snapshot["block"] = {
                "blockRef": block.block_ref,
                "episodeRef": block.episode_ref,
                "patientName": block.patient_name,
                "status": block.status,
                "areaRef": block.area_ref,
                "startsAt": block.starts_at.isoformat(),
                "endsAt": block.ends_at.isoformat(),
                "leadStaffRole": block.lead_staff_role,
                "version": block.version,
            }
            if row.episode_ref and row.episode_ref != block.episode_ref:
                mismatches.append("block_episode_mismatch")
            if row.area_ref and row.area_ref != block.area_ref:
                mismatches.append("block_area_mismatch")
            if row.status and row.status.strip().lower() != block.status.strip().lower():
                mismatches.append("block_status_mismatch")
            if row.starts_at and row.starts_at != block.starts_at.isoformat():
                mismatches.append("start_time_mismatch")
            if row.ends_at and row.ends_at != block.ends_at.isoformat():
                mismatches.append("end_time_mismatch")
    if not row.episode_ref and not row.block_ref:
        mismatches.append("missing_canonical_reference")
    return snapshot, sorted(set(mismatches))


@router.post("/comparisons")
def import_comparisons(
    payload: ImportPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    created: list[CanonicalShadowComparison] = []
    for incoming in payload.rows:
        existing = session.exec(
            select(CanonicalShadowComparison)
            .where(CanonicalShadowComparison.source_system == payload.source_system)
            .where(CanonicalShadowComparison.source_record_ref == incoming.source_record_ref)
        ).first()
        source_snapshot = incoming.model_dump()
        canonical, mismatches = canonical_snapshot(session, incoming)
        if existing:
            existing.source_snapshot = source_snapshot
            existing.canonical_snapshot = canonical
            existing.mismatch_codes = mismatches
            existing.validation_state = "matched" if not mismatches else "mismatch"
            existing.status = "open"
            existing.version += 1
            existing.updated_at = utc_now()
            row = existing
        else:
            row = CanonicalShadowComparison(
                comparison_ref=f"shadow-{uuid4().hex}",
                premises_ref=payload.premises_ref,
                source_system=payload.source_system,
                source_record_ref=incoming.source_record_ref,
                episode_ref=incoming.episode_ref,
                block_ref=incoming.block_ref,
                source_snapshot=source_snapshot,
                canonical_snapshot=canonical,
                mismatch_codes=mismatches,
                validation_state="matched" if not mismatches else "mismatch",
            )
        session.add(row)
        session.flush()
        publish_event(
            session,
            event_type="shadow_comparison_updated",
            aggregate_type="canonical_shadow_comparison",
            aggregate_ref=row.comparison_ref,
            premises_ref=row.premises_ref,
            severity="warning" if mismatches else "info",
            payload=comparison_dict(row),
            correlation_id=row.episode_ref or row.block_ref,
            idempotency_key=f"shadow-import:{payload.source_system}:{incoming.source_record_ref}:v{row.version}",
        )
        created.append(row)
    session.commit()
    return {"comparisons": [comparison_dict(row) for row in created], "count": len(created)}


@router.get("/comparisons")
def list_comparisons(
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = session.exec(select(CanonicalShadowComparison).order_by(CanonicalShadowComparison.created_at.desc())).all()
    return {"comparisons": [comparison_dict(row) for row in rows], "count": len(rows)}


@router.patch("/comparisons/{comparison_ref}")
def review_comparison(
    comparison_ref: str,
    payload: ReviewPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    if auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="senior operational or clinical authority is required")
    row = session.exec(select(CanonicalShadowComparison).where(CanonicalShadowComparison.comparison_ref == comparison_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="shadow comparison not found")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "stale shadow comparison", "current": comparison_dict(row)})
    decision = payload.decision.strip().lower()
    if decision not in {"approve_source", "accept_canonical", "reject_source", "needs_investigation"}:
        raise HTTPException(status_code=400, detail="unsupported shadow decision")
    previous = comparison_dict(row)
    row.status = decision
    row.reviewed_by_subject = auth.subject
    row.reviewed_by_name = auth.actor_name
    row.reviewed_by_role = auth.role
    row.review_note = payload.note
    row.version += 1
    row.updated_at = utc_now()
    evidence, _ = create_evidence_event(
        session,
        event_type="canonical_shadow_review",
        action=decision,
        referral_episode_id=row.episode_ref,
        schedule_block_id=row.block_ref,
        previous_state=previous,
        new_state=comparison_dict(row),
        reason=payload.note,
        compliance_domain="hospital_operations",
        risk_level="red" if row.mismatch_codes else "amber",
        source_module="canonical-shadow-v7",
        source_record_ref=row.comparison_ref,
        correlation_id=row.episode_ref or row.block_ref,
        entity_type="canonical_shadow_comparison",
        entity_id=row.comparison_ref,
        idempotency_key=f"shadow-review:{row.comparison_ref}:v{row.version}",
    )
    row.evidence_event_ref = evidence.event_ref
    session.add(row)
    publish_event(
        session,
        event_type="shadow_comparison_reviewed",
        aggregate_type="canonical_shadow_comparison",
        aggregate_ref=row.comparison_ref,
        premises_ref=row.premises_ref,
        severity="warning" if row.mismatch_codes else "info",
        payload=comparison_dict(row),
        correlation_id=row.episode_ref or row.block_ref,
        idempotency_key=f"shadow-review-event:{row.comparison_ref}:v{row.version}",
    )
    session.commit()
    session.refresh(row)
    return {"comparison": comparison_dict(row)}


@router.get("/summary")
def summary(session: Session = Depends(get_session), _: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    rows = session.exec(select(CanonicalShadowComparison)).all()
    open_rows = [row for row in rows if row.status == "open"]
    return {
        "count": len(rows),
        "open": len(open_rows),
        "matched": len([row for row in rows if row.validation_state == "matched"]),
        "mismatch": len([row for row in rows if row.validation_state == "mismatch"]),
        "investigation": len([row for row in rows if row.status == "needs_investigation"]),
        "readyForPilotReview": bool(rows) and not open_rows and not any(row.status == "needs_investigation" for row in rows),
    }
