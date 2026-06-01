from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Session, select

from app.conflict_engine_routes import normalised_conflicts
from app.database import get_session
from app.models import AuditEvent, Episode, WorkItem

router = APIRouter(prefix="/api/shadow-mode", tags=["shadow-mode"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ShadowRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    external_ref: str
    episode_ref: Optional[str] = None
    patient_name: Optional[str] = None
    imported_stage: Optional[str] = None
    imported_room: Optional[str] = None
    imported_owner_role: Optional[str] = None
    imported_status: str = "imported"
    source: str = "csv"
    validation_state: str = "pending"
    mismatch_summary: str = ""
    approved: bool = False
    rejected: bool = False
    reviewed_by: Optional[str] = None
    review_note: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    reviewed_at: Optional[datetime] = None


class ShadowImportRow(BaseModel):
    external_ref: str
    episode_ref: Optional[str] = None
    patient_name: Optional[str] = None
    stage: Optional[str] = None
    room: Optional[str] = None
    owner_role: Optional[str] = None
    status: str = "imported"
    source: str = "csv"


class ShadowImportPayload(BaseModel):
    rows: list[ShadowImportRow]
    actor_name: str = "LucyWorks Shadow Mode"


class ShadowReviewPayload(BaseModel):
    ids: list[int]
    actor_name: str = "LucyWorks Shadow Mode"
    note: Optional[str] = None


def row(obj: Any) -> dict[str, Any]:
    fields = getattr(obj, "model_fields", {})
    return {name: getattr(obj, name) for name in fields}


def write_audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str) -> AuditEvent:
    event = AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def validate_record(session: Session, record: ShadowRecord, conflicts: list[dict[str, Any]]) -> list[str]:
    mismatches: list[str] = []
    episode = None
    if record.episode_ref:
        episode = session.exec(select(Episode).where(Episode.episode_ref == record.episode_ref)).first()
    if not episode:
        mismatches.append("unknown_episode")
    else:
        if record.imported_stage and episode.current_phase and record.imported_stage.lower() != episode.current_phase.lower():
            mismatches.append("stage_mismatch")
        if record.imported_room and episode.current_room_name and record.imported_room.lower() != episode.current_room_name.lower():
            mismatches.append("room_mismatch")

    if record.imported_owner_role:
        linked_work = session.exec(
            select(WorkItem).where(
                WorkItem.linked_episode_ref == record.episode_ref,
                WorkItem.owner_role == record.imported_owner_role,
                WorkItem.status != "done",
            )
        ).first()
        if not linked_work:
            mismatches.append("owner_role_unlinked")

    conflict_refs = []
    for conflict in conflicts:
        refs = conflict.get("episode_refs") or []
        if record.episode_ref and record.episode_ref in refs:
            conflict_refs.append(conflict)
    if conflict_refs and not record.approved:
        mismatches.append("conflict_not_acknowledged")

    return mismatches


@router.post("/import-rows")
def import_rows(payload: ShadowImportPayload, session: Session = Depends(get_session)):
    created: list[ShadowRecord] = []
    for incoming in payload.rows:
        record = ShadowRecord(
            external_ref=incoming.external_ref,
            episode_ref=incoming.episode_ref,
            patient_name=incoming.patient_name,
            imported_stage=incoming.stage,
            imported_room=incoming.room,
            imported_owner_role=incoming.owner_role,
            imported_status=incoming.status,
            source=incoming.source,
        )
        session.add(record)
        session.flush()
        created.append(record)
    session.commit()
    audit = write_audit(session, payload.actor_name, "shadow_rows_imported", "shadow_mode", 0, f"Imported {len(created)} shadow records")
    return {"ok": True, "created_count": len(created), "records": [row(item) for item in created], "audit_event": audit}


@router.get("/records")
def records(session: Session = Depends(get_session)):
    items = session.exec(select(ShadowRecord).order_by(ShadowRecord.created_at)).all()
    return {"count": len(items), "records": [row(item) for item in items]}


@router.post("/validate")
def validate(session: Session = Depends(get_session)):
    records = session.exec(select(ShadowRecord).order_by(ShadowRecord.created_at)).all()
    conflicts = normalised_conflicts(session)
    results = []
    for record in records:
        mismatches = validate_record(session, record, conflicts)
        record.mismatch_summary = ",".join(mismatches)
        record.validation_state = "matched" if not mismatches else "mismatch"
        session.add(record)
        results.append({"record": row(record), "mismatches": mismatches})
    session.commit()
    audit = write_audit(session, "LucyWorks Shadow Mode", "shadow_records_validated", "shadow_mode", 0, f"Validated {len(records)} shadow records")
    return {"ok": True, "count": len(results), "results": results, "audit_event": audit}


@router.post("/approve")
def approve(payload: ShadowReviewPayload, session: Session = Depends(get_session)):
    updated = []
    for record_id in payload.ids:
        record = session.get(ShadowRecord, record_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Shadow record {record_id} not found")
        record.approved = True
        record.rejected = False
        record.validation_state = "approved"
        record.reviewed_by = payload.actor_name
        record.review_note = payload.note
        record.reviewed_at = utc_now()
        session.add(record)
        updated.append(record)
    session.commit()
    audit = write_audit(session, payload.actor_name, "shadow_records_approved", "shadow_mode", 0, f"Approved {len(updated)} shadow records")
    return {"ok": True, "updated_count": len(updated), "records": [row(item) for item in updated], "audit_event": audit}


@router.post("/reject")
def reject(payload: ShadowReviewPayload, session: Session = Depends(get_session)):
    updated = []
    for record_id in payload.ids:
        record = session.get(ShadowRecord, record_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Shadow record {record_id} not found")
        record.approved = False
        record.rejected = True
        record.validation_state = "rejected"
        record.reviewed_by = payload.actor_name
        record.review_note = payload.note
        record.reviewed_at = utc_now()
        session.add(record)
        updated.append(record)
    session.commit()
    audit = write_audit(session, payload.actor_name, "shadow_records_rejected", "shadow_mode", 0, f"Rejected {len(updated)} shadow records")
    return {"ok": True, "updated_count": len(updated), "records": [row(item) for item in updated], "audit_event": audit}


@router.get("/summary")
def summary(session: Session = Depends(get_session)):
    items = session.exec(select(ShadowRecord)).all()
    return {
        "count": len(items),
        "pending": len([item for item in items if item.validation_state == "pending"]),
        "matched": len([item for item in items if item.validation_state == "matched"]),
        "mismatch": len([item for item in items if item.validation_state == "mismatch"]),
        "approved": len([item for item in items if item.approved]),
        "rejected": len([item for item in items if item.rejected]),
        "records": [row(item) for item in items[:120]],
    }
