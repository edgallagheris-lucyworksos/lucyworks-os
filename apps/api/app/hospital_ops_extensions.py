from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth import AuthContext
from app.hospital_ops_models import CanonicalEpisodeState, ImportBatch, ImportReconciliationItem, OperationalBlock
from app.hospital_ops_service import (
    _assert_version,
    _command,
    _complete_command,
    _emit_change,
    _evidence,
    block_dict,
    episode_dict,
    json_text,
    normalise_dt,
    parse_json,
    ref,
    utc_now,
)
from app.schedule_state_models import ScheduleStateBlock


def patch_episode_gates(session: Session, episode_ref: str, payload: dict[str, Any], auth: AuthContext) -> tuple[CanonicalEpisodeState, Any]:
    row = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="episode not found")
    expected_version = payload.get("expectedVersion")
    _assert_version(row.version, expected_version, "episode")
    incoming = payload.get("gates") or {}
    if not isinstance(incoming, dict) or not incoming:
        raise HTTPException(status_code=400, detail="at least one gate value is required")
    command, _ = _command(
        session,
        command_type="RecordEpisodeGates",
        target_type="episode",
        target_ref=episode_ref,
        expected_version=expected_version,
        payload=payload,
        auth=auth,
        idempotency_key=payload.get("idempotencyKey"),
    )
    before = episode_dict(row)
    gates = parse_json(row.gates_json, {})
    gates.update(incoming)
    row.gates_json = json_text(gates)
    row.next_action = payload.get("nextAction") or row.next_action
    row.version += 1
    row.last_command_ref = command.command_ref
    row.updated_at = utc_now()
    session.add(row)
    after = episode_dict(row)
    risk = "red" if payload.get("overrideReason") else "green"
    evidence_ref = _evidence(
        session,
        command=command,
        auth=auth,
        event_type="episode_gates_recorded",
        action="episode governance gates recorded",
        before=before,
        after=after,
        premises_ref=row.premises_ref,
        operational_date=utc_now().date(),
        risk_level=risk,
        reason=payload.get("reason") or "governance evidence confirmed",
        override_reason=payload.get("overrideReason"),
        entity_type="canonical_episode",
        entity_id=episode_ref,
        referral_episode_id=episode_ref,
    )
    _complete_command(command, {"episode": after}, evidence_ref)
    _emit_change(
        session,
        premises_ref=row.premises_ref,
        operational_date=utc_now().date(),
        event_type="episode_gates_changed",
        entity_type="episode",
        entity_ref=episode_ref,
        entity_version=row.version,
        command_ref=command.command_ref,
        payload=after,
    )
    return row, command


def resolve_reconciliation_item(session: Session, batch_ref: str, item_ref: str, corrected_record: dict[str, Any], auth: AuthContext) -> tuple[ImportBatch, ImportReconciliationItem]:
    batch = session.exec(select(ImportBatch).where(ImportBatch.batch_ref == batch_ref)).first()
    if not batch:
        raise HTTPException(status_code=404, detail="import batch not found")
    if batch.status == "committed":
        raise HTTPException(status_code=409, detail="committed import cannot be changed")
    item = session.exec(select(ImportReconciliationItem).where(ImportReconciliationItem.batch_ref == batch_ref, ImportReconciliationItem.item_ref == item_ref)).first()
    if not item:
        raise HTTPException(status_code=404, detail="reconciliation item not found")
    required = ["patientName", "procedureName", "areaRef", "startsAt", "endsAt"]
    missing = [key for key in required if not corrected_record.get(key)]
    if missing:
        raise HTTPException(status_code=400, detail=f"corrected record is missing: {', '.join(missing)}")
    try:
        starts_at = normalise_dt(datetime.fromisoformat(str(corrected_record["startsAt"]).replace("Z", "+00:00")))
        ends_at = normalise_dt(datetime.fromisoformat(str(corrected_record["endsAt"]).replace("Z", "+00:00")))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="corrected start/end timestamps are invalid") from exc
    if ends_at <= starts_at:
        raise HTTPException(status_code=400, detail="corrected end must be after start")
    normalised = dict(corrected_record)
    normalised.setdefault("blockRef", ref("reconciled-block"))
    normalised.setdefault("blockType", "procedure")
    normalised.setdefault("gates", {})
    normalised["startsAt"] = starts_at.isoformat()
    normalised["endsAt"] = ends_at.isoformat()
    external = normalised.get("externalRefs") or {}
    external["reconciliationItemRef"] = item_ref
    external["importBatchRef"] = batch_ref
    normalised["externalRefs"] = external

    summary = parse_json(batch.summary_json, {})
    rows = list(summary.get("normalisedRows") or [])
    rows.append(normalised)
    summary["normalisedRows"] = rows
    summary["issues"] = max(0, int(summary.get("issues") or 0) - 1)
    batch.summary_json = json_text(summary)
    batch.accepted_count += 1
    batch.rejected_count = max(0, batch.rejected_count - 1)
    batch.status = "ready" if batch.rejected_count == 0 else "preview"
    session.add(batch)

    item.status = "resolved"
    item.resolved_by_subject = auth.subject
    item.resolution_json = json_text({"correctedRecord": normalised, "actorName": auth.actor_name, "actorRole": auth.role})
    item.resolved_at = utc_now()
    session.add(item)
    return batch, item


def assert_import_ready(session: Session, batch_ref: str) -> ImportBatch:
    batch = session.exec(select(ImportBatch).where(ImportBatch.batch_ref == batch_ref)).first()
    if not batch:
        raise HTTPException(status_code=404, detail="import batch not found")
    unresolved = session.exec(select(ImportReconciliationItem).where(ImportReconciliationItem.batch_ref == batch_ref, ImportReconciliationItem.status != "resolved")).all()
    if unresolved or batch.rejected_count:
        raise HTTPException(status_code=409, detail={
            "code": "reconciliation_required",
            "message": "all rejected rows must be resolved before import commit",
            "unresolvedCount": len(unresolved),
        })
    return batch


def shadow_comparison(session: Session, premises_ref: str, operational_date: date) -> dict[str, Any]:
    legacy = session.exec(select(ScheduleStateBlock).order_by(ScheduleStateBlock.time, ScheduleStateBlock.lane)).all()
    canonical = session.exec(select(OperationalBlock).where(OperationalBlock.premises_ref == premises_ref, OperationalBlock.operational_date == operational_date).order_by(OperationalBlock.starts_at, OperationalBlock.area_ref)).all()

    def legacy_key(row: ScheduleStateBlock) -> str:
        return "|".join([
            str(row.episode_ref or row.subject or "").strip().lower(),
            str(row.what or "").strip().lower(),
            str(row.where or "").strip().lower(),
            str(row.time or "").strip(),
        ])

    def canonical_key(row: OperationalBlock) -> str:
        local = row.starts_at.astimezone(timezone.utc) if row.starts_at.tzinfo else row.starts_at.replace(tzinfo=timezone.utc)
        return "|".join([
            str(row.episode_ref or row.patient_name or "").strip().lower(),
            str(row.procedure_name or "").strip().lower(),
            str(row.area_name or "").strip().lower(),
            local.strftime("%H:%M"),
        ])

    legacy_map = {legacy_key(row): row for row in legacy}
    canonical_map = {canonical_key(row): row for row in canonical}
    matched = sorted(set(legacy_map) & set(canonical_map))
    legacy_only = [legacy_map[key] for key in sorted(set(legacy_map) - set(canonical_map))]
    canonical_only = [canonical_map[key] for key in sorted(set(canonical_map) - set(legacy_map))]
    denominator = max(1, len(set(legacy_map) | set(canonical_map)))
    agreement = round(len(matched) / denominator * 100, 1)
    return {
        "premisesRef": premises_ref,
        "operationalDate": operational_date.isoformat(),
        "agreementPercent": agreement,
        "matchedCount": len(matched),
        "legacyCount": len(legacy),
        "canonicalCount": len(canonical),
        "legacyOnly": [{"id": row.id, "episodeRef": row.episode_ref, "patient": row.subject, "work": row.what, "location": row.where, "time": row.time} for row in legacy_only[:100]],
        "canonicalOnly": [block_dict(row) for row in canonical_only[:100]],
        "recommendation": "continue shadow mode" if agreement < 95 else "eligible for controlled operational pilot",
        "generatedAt": utc_now().isoformat(),
    }
