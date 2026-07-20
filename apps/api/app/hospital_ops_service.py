from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import random
from collections import defaultdict, deque
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth import AuthContext
from app.control_plane_models import ServiceAvailability
from app.evidence_service import create_evidence_event
from app.hospital_ops_models import (
    BoardChangeEvent,
    CanonicalEpisodeState,
    HospitalPremises,
    ImportBatch,
    ImportReconciliationItem,
    OperationalArea,
    OperationalBlock,
    OperationalCommand,
    OperationalConflict,
    OperationalDependency,
    ScenarioRun,
)
from app.models import Shift, StaffMember


PHASES = [
    "referral_received",
    "intake_validation",
    "accepted",
    "arrived",
    "consultation",
    "diagnostic_plan",
    "estimate_and_consent",
    "preparation",
    "procedure",
    "recovery",
    "ward_or_icu",
    "discharge_readiness",
    "discharged",
    "referring_vet_report",
    "closed",
]

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "referral_received": {"intake_validation"},
    "intake_validation": {"accepted", "closed"},
    "accepted": {"arrived", "closed"},
    "arrived": {"consultation"},
    "consultation": {"diagnostic_plan", "discharge_readiness"},
    "diagnostic_plan": {"estimate_and_consent"},
    "estimate_and_consent": {"preparation", "diagnostic_plan"},
    "preparation": {"procedure", "estimate_and_consent"},
    "procedure": {"recovery"},
    "recovery": {"ward_or_icu", "discharge_readiness"},
    "ward_or_icu": {"discharge_readiness", "procedure"},
    "discharge_readiness": {"discharged", "ward_or_icu"},
    "discharged": {"referring_vet_report"},
    "referring_vet_report": {"closed"},
    "closed": set(),
}

PHASE_OWNER = {
    "referral_received": "reception",
    "intake_validation": "admin",
    "accepted": "coordinator",
    "arrived": "reception",
    "consultation": "clinician",
    "diagnostic_plan": "clinician",
    "estimate_and_consent": "clinician",
    "preparation": "nurse",
    "procedure": "clinician",
    "recovery": "nurse",
    "ward_or_icu": "nurse",
    "discharge_readiness": "clinician",
    "discharged": "admin",
    "referring_vet_report": "clinician",
    "closed": "admin",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


def parse_json(value: str | None, fallback: Any = None) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def normalise_dt(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return normalise_dt(a_start) < normalise_dt(b_end) and normalise_dt(b_start) < normalise_dt(a_end)


def premises_dict(row: HospitalPremises) -> dict[str, Any]:
    return {
        "id": row.id,
        "premisesRef": row.premises_ref,
        "name": row.name,
        "timezone": row.timezone_name,
        "status": row.status,
    }


def area_dict(row: OperationalArea) -> dict[str, Any]:
    return {
        "id": row.id,
        "areaRef": row.area_ref,
        "premisesRef": row.premises_ref,
        "name": row.name,
        "areaType": row.area_type,
        "department": row.department,
        "capacity": row.capacity,
        "turnoverMinutes": row.turnover_minutes,
        "requiredSkills": parse_json(row.required_skills_json, []),
        "compatibleProcedures": parse_json(row.compatible_procedures_json, []),
        "equipmentRefs": parse_json(row.equipment_refs_json, []),
        "active": row.active,
    }


def episode_dict(row: CanonicalEpisodeState) -> dict[str, Any]:
    return {
        "id": row.id,
        "episodeRef": row.episode_ref,
        "patientRef": row.patient_ref,
        "patientName": row.patient_name,
        "premisesRef": row.premises_ref,
        "serviceLine": row.service_line,
        "urgency": row.urgency,
        "phase": row.phase,
        "status": row.status,
        "ownerRole": row.owner_role,
        "ownerSubject": row.owner_subject,
        "currentAreaRef": row.current_area_ref,
        "nextAction": row.next_action,
        "gates": parse_json(row.gates_json, {}),
        "flags": parse_json(row.flags_json, []),
        "version": row.version,
        "lastCommandRef": row.last_command_ref,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def block_dict(row: OperationalBlock) -> dict[str, Any]:
    return {
        "id": row.id,
        "blockRef": row.block_ref,
        "premisesRef": row.premises_ref,
        "operationalDate": row.operational_date.isoformat(),
        "episodeRef": row.episode_ref,
        "patientRef": row.patient_ref,
        "patientName": row.patient_name,
        "procedureRef": row.procedure_ref,
        "procedureName": row.procedure_name,
        "blockType": row.block_type,
        "areaRef": row.area_ref,
        "areaName": row.area_name,
        "startsAt": row.starts_at.isoformat(),
        "endsAt": row.ends_at.isoformat(),
        "status": row.status,
        "riskLevel": row.risk_level,
        "priority": row.priority,
        "leadStaffRef": row.lead_staff_ref,
        "leadStaffName": row.lead_staff_name,
        "leadStaffRole": row.lead_staff_role,
        "assistantRefs": parse_json(row.assistant_refs_json, []),
        "equipmentRefs": parse_json(row.equipment_refs_json, []),
        "requiredSkills": parse_json(row.required_skills_json, []),
        "dependencyRefs": parse_json(row.dependency_refs_json, []),
        "blockers": parse_json(row.blockers_json, []),
        "gates": parse_json(row.gates_json, {}),
        "pharmacyRefs": parse_json(row.pharmacy_refs_json, []),
        "externalRefs": parse_json(row.external_refs_json, {}),
        "notes": row.notes,
        "version": row.version,
        "lastCommandRef": row.last_command_ref,
        "updatedBy": {
            "subject": row.updated_by_subject,
            "name": row.updated_by_name,
            "role": row.updated_by_role,
            "authSource": row.updated_by_auth_source,
        },
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def conflict_dict(row: OperationalConflict) -> dict[str, Any]:
    return {
        "id": row.id,
        "conflictRef": row.conflict_ref,
        "premisesRef": row.premises_ref,
        "operationalDate": row.operational_date.isoformat(),
        "conflictType": row.conflict_type,
        "severity": row.severity,
        "status": row.status,
        "primaryBlockRef": row.primary_block_ref,
        "relatedRefs": parse_json(row.related_refs_json, []),
        "explanation": row.explanation,
        "options": parse_json(row.options_json, []),
        "fingerprint": row.fingerprint,
        "detectedAt": row.detected_at.isoformat() if row.detected_at else None,
    }


def command_dict(row: OperationalCommand) -> dict[str, Any]:
    return {
        "commandRef": row.command_ref,
        "commandType": row.command_type,
        "targetType": row.target_type,
        "targetRef": row.target_ref,
        "expectedVersion": row.expected_version,
        "request": parse_json(row.request_json, {}),
        "result": parse_json(row.result_json, {}),
        "status": row.status,
        "actor": {
            "subject": row.actor_subject,
            "name": row.actor_name,
            "role": row.actor_role,
            "authSource": row.auth_source,
        },
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
    }


def ensure_default_premises_and_areas(session: Session, premises_ref: str = "default-premises") -> tuple[HospitalPremises, list[OperationalArea]]:
    premises = session.exec(select(HospitalPremises).where(HospitalPremises.premises_ref == premises_ref)).first()
    if not premises:
        premises = HospitalPremises(premises_ref=premises_ref, name="LucyWorks Referral Hospital")
        session.add(premises)
        session.flush()

    existing = session.exec(select(OperationalArea).where(OperationalArea.premises_ref == premises_ref)).all()
    if existing:
        return premises, existing

    definitions: list[tuple[str, str, str, str, int, int, list[str]]] = []
    for number in range(1, 12):
        definitions.append((f"theatre-{number}", f"Theatre {number}", "theatre", "Surgery", 1, 20, ["surgical", "anaesthesia"]));
    definitions.extend([
        ("mri", "MRI", "imaging", "Diagnostic imaging", 1, 20, ["mri", "anaesthesia"]),
        ("ct", "CT", "imaging", "Diagnostic imaging", 1, 15, ["ct", "anaesthesia"]),
        ("xray", "X-ray", "imaging", "Diagnostic imaging", 1, 10, ["radiography"]),
        ("ultrasound", "Ultrasound", "imaging", "Diagnostic imaging", 2, 5, ["ultrasound"]),
        ("prep", "Prep", "prep", "Surgery", 4, 5, ["nursing"]),
        ("recovery", "Recovery", "recovery", "Nursing", 8, 0, ["recovery"]),
        ("icu", "ICU", "ward", "Critical care", 8, 0, ["critical_care"]),
        ("ward-dog", "Dog ward", "ward", "Wards", 20, 0, ["inpatient"]),
        ("ward-cat", "Cat ward", "ward", "Wards", 14, 0, ["inpatient"]),
        ("pharmacy", "Pharmacy", "support", "Pharmacy", 3, 0, ["pharmacy"]),
        ("laboratory", "Laboratory", "support", "Laboratory", 3, 0, ["laboratory"]),
        ("reception", "Reception", "admin", "Client services", 6, 0, ["admin"]),
    ])
    for number in range(1, 5):
        definitions.append((f"consult-{number}", f"Consult {number}", "consult", "Consultations", 1, 5, ["consultation"]))

    rows: list[OperationalArea] = []
    for area_ref, name, area_type, department, capacity, turnover, skills in definitions:
        row = OperationalArea(
            area_ref=area_ref,
            premises_ref=premises_ref,
            name=name,
            area_type=area_type,
            department=department,
            capacity=capacity,
            turnover_minutes=turnover,
            required_skills_json=json_text(skills),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return premises, rows


def _command(session: Session, *, command_type: str, target_type: str, target_ref: str, expected_version: int | None, payload: dict[str, Any], auth: AuthContext, idempotency_key: str | None = None) -> tuple[OperationalCommand, bool]:
    if idempotency_key:
        existing = session.exec(select(OperationalCommand).where(OperationalCommand.idempotency_key == idempotency_key)).first()
        if existing:
            return existing, False
    command = OperationalCommand(
        command_ref=ref("cmd"),
        command_type=command_type,
        target_type=target_type,
        target_ref=target_ref,
        expected_version=expected_version,
        request_json=json_text(payload) or "{}",
        idempotency_key=idempotency_key,
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        auth_source=auth.auth_source,
    )
    session.add(command)
    session.flush()
    return command, True


def _complete_command(command: OperationalCommand, result: dict[str, Any], evidence_ref: str | None = None) -> None:
    command.status = "completed"
    command.result_json = json_text(result)
    command.evidence_event_ref = evidence_ref
    command.completed_at = utc_now()


def _emit_change(session: Session, *, premises_ref: str, operational_date: date, event_type: str, entity_type: str, entity_ref: str, entity_version: int | None, command_ref: str | None, payload: dict[str, Any]) -> BoardChangeEvent:
    event = BoardChangeEvent(
        event_ref=ref("change"),
        premises_ref=premises_ref,
        operational_date=operational_date,
        event_type=event_type,
        entity_type=entity_type,
        entity_ref=entity_ref,
        entity_version=entity_version,
        command_ref=command_ref,
        payload_json=json_text(payload) or "{}",
    )
    session.add(event)
    return event


def _evidence(session: Session, *, command: OperationalCommand, auth: AuthContext, event_type: str, action: str, before: Any, after: Any, premises_ref: str, operational_date: date, risk_level: str = "amber", reason: str | None = None, override_reason: str | None = None, entity_type: str, entity_id: str, patient_case_id: str | None = None, referral_episode_id: str | None = None) -> str:
    event, _ = create_evidence_event(
        session,
        event_type=event_type,
        action=action,
        patient_case_id=patient_case_id,
        referral_episode_id=referral_episode_id,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=before,
        new_state=after,
        reason=reason,
        justification=f"Operational command {command.command_ref}",
        evidence_links=[
            {"type": "operational_command", "id": command.command_ref},
            {"type": "premises", "id": premises_ref},
            {"type": "operational_date", "id": operational_date.isoformat()},
        ],
        override_reason=override_reason,
        supervisor_required=bool(override_reason) or risk_level == "red",
        supervisor_approval_status="pending" if override_reason or risk_level == "red" else "not_required",
        compliance_domain="hospital_operations",
        risk_level=risk_level,
        source_module="hospital-ops-v3",
        source_record_ref=entity_id,
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=referral_episode_id or patient_case_id or entity_id,
        idempotency_key=f"evidence:{command.command_ref}",
    )
    return event.event_ref


def _assert_version(actual: int, expected: int | None, entity: str) -> None:
    if expected is None:
        raise HTTPException(status_code=428, detail=f"expectedVersion is required for {entity} updates")
    if actual != expected:
        raise HTTPException(status_code=409, detail={
            "code": "stale_version",
            "message": f"{entity} changed since it was opened",
            "expectedVersion": expected,
            "currentVersion": actual,
        })


def create_episode(session: Session, payload: dict[str, Any], auth: AuthContext) -> tuple[CanonicalEpisodeState, OperationalCommand, bool]:
    episode_ref = str(payload.get("episodeRef") or ref("episode"))
    command, created = _command(
        session,
        command_type="CreateEpisode",
        target_type="episode",
        target_ref=episode_ref,
        expected_version=None,
        payload=payload,
        auth=auth,
        idempotency_key=payload.get("idempotencyKey"),
    )
    if not created:
        existing = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == command.target_ref)).first()
        if not existing:
            raise HTTPException(status_code=409, detail="idempotent command exists but episode is missing")
        return existing, command, False
    if session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first():
        raise HTTPException(status_code=409, detail="episodeRef already exists")
    premises_ref = str(payload.get("premisesRef") or "default-premises")
    ensure_default_premises_and_areas(session, premises_ref)
    row = CanonicalEpisodeState(
        episode_ref=episode_ref,
        patient_ref=payload.get("patientRef"),
        patient_name=str(payload.get("patientName") or "Unnamed patient"),
        premises_ref=premises_ref,
        service_line=str(payload.get("serviceLine") or "referral"),
        urgency=str(payload.get("urgency") or "routine"),
        phase="referral_received",
        owner_role="reception",
        owner_subject=auth.subject,
        next_action="validate referral information",
        gates_json=json_text(payload.get("gates") or {}),
        flags_json=json_text(payload.get("flags") or []),
        last_command_ref=command.command_ref,
    )
    session.add(row)
    session.flush()
    after = episode_dict(row)
    evidence_ref = _evidence(
        session,
        command=command,
        auth=auth,
        event_type="episode_created",
        action="referral episode created",
        before=None,
        after=after,
        premises_ref=premises_ref,
        operational_date=utc_now().date(),
        reason="referral intake",
        entity_type="canonical_episode",
        entity_id=episode_ref,
        referral_episode_id=episode_ref,
    )
    _complete_command(command, {"episode": after}, evidence_ref)
    _emit_change(session, premises_ref=premises_ref, operational_date=utc_now().date(), event_type="episode_created", entity_type="episode", entity_ref=episode_ref, entity_version=row.version, command_ref=command.command_ref, payload=after)
    return row, command, True


def transition_episode(session: Session, episode_ref: str, payload: dict[str, Any], auth: AuthContext) -> tuple[CanonicalEpisodeState, OperationalCommand]:
    row = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="episode not found")
    expected_version = payload.get("expectedVersion")
    _assert_version(row.version, expected_version, "episode")
    target_phase = str(payload.get("phase") or "")
    if target_phase not in PHASES:
        raise HTTPException(status_code=400, detail="unknown episode phase")
    override_reason = payload.get("overrideReason")
    if target_phase not in ALLOWED_TRANSITIONS.get(row.phase, set()) and not override_reason:
        raise HTTPException(status_code=409, detail=f"transition {row.phase} -> {target_phase} is not allowed")

    gates = parse_json(row.gates_json, {})
    unmet: list[str] = []
    if target_phase == "preparation":
        if gates.get("consent") not in {"approved", "authorised", "emergency_authority"}:
            unmet.append("consent is not authorised")
        if gates.get("estimate") not in {"approved", "accepted", "emergency_authority"}:
            unmet.append("estimate authority is not recorded")
    if target_phase == "procedure" and gates.get("preparation") not in {"complete", "ready"}:
        unmet.append("preparation is not complete")
    if target_phase == "discharged":
        for key in ("discharge", "medication", "owner_update"):
            if gates.get(key) not in {"complete", "ready", "sent", True}:
                unmet.append(f"{key.replace('_', ' ')} is incomplete")
    if unmet and not override_reason:
        raise HTTPException(status_code=409, detail={"code": "transition_blocked", "unmet": unmet})

    command, _ = _command(
        session,
        command_type="TransitionEpisode",
        target_type="episode",
        target_ref=episode_ref,
        expected_version=expected_version,
        payload=payload,
        auth=auth,
        idempotency_key=payload.get("idempotencyKey"),
    )
    before = episode_dict(row)
    row.phase = target_phase
    row.owner_role = str(payload.get("ownerRole") or PHASE_OWNER[target_phase])
    row.owner_subject = payload.get("ownerSubject") or auth.subject
    row.current_area_ref = payload.get("currentAreaRef") or row.current_area_ref
    row.next_action = payload.get("nextAction") or f"complete {target_phase.replace('_', ' ')}"
    if payload.get("gates"):
        gates.update(payload["gates"])
        row.gates_json = json_text(gates)
    if target_phase == "closed":
        row.status = "closed"
    row.version += 1
    row.last_command_ref = command.command_ref
    row.updated_at = utc_now()
    session.add(row)
    after = episode_dict(row)
    risk = "red" if override_reason or unmet else "green"
    evidence_ref = _evidence(
        session,
        command=command,
        auth=auth,
        event_type="episode_transition",
        action=f"episode moved from {before['phase']} to {target_phase}",
        before=before,
        after=after,
        premises_ref=row.premises_ref,
        operational_date=utc_now().date(),
        risk_level=risk,
        reason=payload.get("reason") or "workflow phase completed",
        override_reason=override_reason,
        entity_type="canonical_episode",
        entity_id=episode_ref,
        referral_episode_id=episode_ref,
    )
    _complete_command(command, {"episode": after, "unmetOverridden": unmet}, evidence_ref)
    _emit_change(session, premises_ref=row.premises_ref, operational_date=utc_now().date(), event_type="episode_transition", entity_type="episode", entity_ref=episode_ref, entity_version=row.version, command_ref=command.command_ref, payload=after)
    return row, command


def create_block(session: Session, payload: dict[str, Any], auth: AuthContext) -> tuple[OperationalBlock, OperationalCommand, bool]:
    block_ref = str(payload.get("blockRef") or ref("block"))
    command, created = _command(
        session,
        command_type="CreateOperationalBlock",
        target_type="operational_block",
        target_ref=block_ref,
        expected_version=None,
        payload=payload,
        auth=auth,
        idempotency_key=payload.get("idempotencyKey"),
    )
    if not created:
        existing = session.exec(select(OperationalBlock).where(OperationalBlock.block_ref == command.target_ref)).first()
        if not existing:
            raise HTTPException(status_code=409, detail="idempotent command exists but block is missing")
        return existing, command, False
    if session.exec(select(OperationalBlock).where(OperationalBlock.block_ref == block_ref)).first():
        raise HTTPException(status_code=409, detail="blockRef already exists")
    starts_at = normalise_dt(datetime.fromisoformat(str(payload["startsAt"]).replace("Z", "+00:00"))) if isinstance(payload.get("startsAt"), str) else normalise_dt(payload["startsAt"])
    ends_at = normalise_dt(datetime.fromisoformat(str(payload["endsAt"]).replace("Z", "+00:00"))) if isinstance(payload.get("endsAt"), str) else normalise_dt(payload["endsAt"])
    if ends_at <= starts_at:
        raise HTTPException(status_code=400, detail="endsAt must be after startsAt")
    premises_ref = str(payload.get("premisesRef") or "default-premises")
    _, areas = ensure_default_premises_and_areas(session, premises_ref)
    area_ref = str(payload.get("areaRef") or "")
    area = next((item for item in areas if item.area_ref == area_ref), None)
    if not area:
        raise HTTPException(status_code=404, detail="operational area not found")
    episode_ref = payload.get("episodeRef")
    episode = None
    if episode_ref:
        episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first()
    row = OperationalBlock(
        block_ref=block_ref,
        premises_ref=premises_ref,
        operational_date=starts_at.date(),
        episode_ref=episode_ref,
        patient_ref=payload.get("patientRef") or (episode.patient_ref if episode else None),
        patient_name=payload.get("patientName") or (episode.patient_name if episode else None),
        procedure_ref=payload.get("procedureRef"),
        procedure_name=str(payload.get("procedureName") or "Operational work"),
        block_type=str(payload.get("blockType") or "procedure"),
        area_ref=area.area_ref,
        area_name=area.name,
        starts_at=starts_at,
        ends_at=ends_at,
        status=str(payload.get("status") or "planned"),
        risk_level=str(payload.get("riskLevel") or "amber"),
        priority=int(payload.get("priority") or 50),
        lead_staff_ref=payload.get("leadStaffRef"),
        lead_staff_name=payload.get("leadStaffName"),
        lead_staff_role=payload.get("leadStaffRole"),
        assistant_refs_json=json_text(payload.get("assistantRefs") or []),
        equipment_refs_json=json_text(payload.get("equipmentRefs") or []),
        required_skills_json=json_text(payload.get("requiredSkills") or []),
        dependency_refs_json=json_text(payload.get("dependencyRefs") or []),
        blockers_json=json_text(payload.get("blockers") or []),
        gates_json=json_text(payload.get("gates") or {}),
        pharmacy_refs_json=json_text(payload.get("pharmacyRefs") or []),
        external_refs_json=json_text(payload.get("externalRefs") or {}),
        notes=payload.get("notes"),
        last_command_ref=command.command_ref,
        updated_by_subject=auth.subject,
        updated_by_name=auth.actor_name,
        updated_by_role=auth.role,
        updated_by_auth_source=auth.auth_source,
    )
    session.add(row)
    session.flush()
    for predecessor_ref in payload.get("dependencyRefs") or []:
        dependency = OperationalDependency(
            dependency_ref=ref("dep"),
            premises_ref=premises_ref,
            predecessor_block_ref=str(predecessor_ref),
            successor_block_ref=block_ref,
            dependency_type="finish_to_start",
            lag_minutes=0,
        )
        session.add(dependency)
    after = block_dict(row)
    evidence_ref = _evidence(
        session,
        command=command,
        auth=auth,
        event_type="operational_block_created",
        action="operational block created",
        before=None,
        after=after,
        premises_ref=premises_ref,
        operational_date=row.operational_date,
        risk_level=row.risk_level,
        reason=payload.get("reason") or "hospital plan created",
        entity_type="operational_block",
        entity_id=block_ref,
        patient_case_id=row.patient_ref,
        referral_episode_id=row.episode_ref,
    )
    _complete_command(command, {"block": after}, evidence_ref)
    _emit_change(session, premises_ref=premises_ref, operational_date=row.operational_date, event_type="block_created", entity_type="operational_block", entity_ref=block_ref, entity_version=row.version, command_ref=command.command_ref, payload=after)
    return row, command, True


PATCH_FIELDS = {
    "procedureName": "procedure_name",
    "blockType": "block_type",
    "areaRef": "area_ref",
    "startsAt": "starts_at",
    "endsAt": "ends_at",
    "status": "status",
    "riskLevel": "risk_level",
    "priority": "priority",
    "leadStaffRef": "lead_staff_ref",
    "leadStaffName": "lead_staff_name",
    "leadStaffRole": "lead_staff_role",
    "assistantRefs": "assistant_refs_json",
    "equipmentRefs": "equipment_refs_json",
    "requiredSkills": "required_skills_json",
    "blockers": "blockers_json",
    "gates": "gates_json",
    "pharmacyRefs": "pharmacy_refs_json",
    "notes": "notes",
}
JSON_PATCH_FIELDS = {"assistantRefs", "equipmentRefs", "requiredSkills", "blockers", "gates", "pharmacyRefs"}


def patch_block(session: Session, block_ref: str, payload: dict[str, Any], auth: AuthContext) -> tuple[OperationalBlock, OperationalCommand]:
    row = session.exec(select(OperationalBlock).where(OperationalBlock.block_ref == block_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="operational block not found")
    expected_version = payload.get("expectedVersion")
    _assert_version(row.version, expected_version, "operational block")
    command, _ = _command(
        session,
        command_type=str(payload.get("commandType") or "PatchOperationalBlock"),
        target_type="operational_block",
        target_ref=block_ref,
        expected_version=expected_version,
        payload=payload,
        auth=auth,
        idempotency_key=payload.get("idempotencyKey"),
    )
    before = block_dict(row)
    for key, attribute in PATCH_FIELDS.items():
        if key not in payload:
            continue
        value = payload[key]
        if key in {"startsAt", "endsAt"}:
            value = normalise_dt(datetime.fromisoformat(str(value).replace("Z", "+00:00"))) if isinstance(value, str) else normalise_dt(value)
        if key in JSON_PATCH_FIELDS:
            value = json_text(value)
        setattr(row, attribute, value)
    if row.ends_at <= row.starts_at:
        raise HTTPException(status_code=400, detail="endsAt must be after startsAt")
    if "areaRef" in payload:
        area = session.exec(select(OperationalArea).where(OperationalArea.area_ref == row.area_ref, OperationalArea.premises_ref == row.premises_ref)).first()
        if not area:
            raise HTTPException(status_code=404, detail="operational area not found")
        row.area_name = area.name
    row.operational_date = normalise_dt(row.starts_at).date()
    row.version += 1
    row.last_command_ref = command.command_ref
    row.updated_at = utc_now()
    row.updated_by_subject = auth.subject
    row.updated_by_name = auth.actor_name
    row.updated_by_role = auth.role
    row.updated_by_auth_source = auth.auth_source
    session.add(row)
    after = block_dict(row)
    risk = "red" if payload.get("overrideReason") else row.risk_level
    evidence_ref = _evidence(
        session,
        command=command,
        auth=auth,
        event_type="operational_block_changed",
        action=str(payload.get("action") or "operational block changed"),
        before=before,
        after=after,
        premises_ref=row.premises_ref,
        operational_date=row.operational_date,
        risk_level=risk,
        reason=payload.get("reason") or "hospital plan updated",
        override_reason=payload.get("overrideReason"),
        entity_type="operational_block",
        entity_id=block_ref,
        patient_case_id=row.patient_ref,
        referral_episode_id=row.episode_ref,
    )
    _complete_command(command, {"block": after}, evidence_ref)
    _emit_change(session, premises_ref=row.premises_ref, operational_date=row.operational_date, event_type="block_changed", entity_type="operational_block", entity_ref=block_ref, entity_version=row.version, command_ref=command.command_ref, payload=after)
    return row, command


def _staff_tokens(block: OperationalBlock) -> set[str]:
    tokens = set()
    if block.lead_staff_ref:
        tokens.add(str(block.lead_staff_ref))
    for item in parse_json(block.assistant_refs_json, []):
        if isinstance(item, dict):
            candidate = item.get("staffRef") or item.get("id")
        else:
            candidate = item
        if candidate:
            tokens.add(str(candidate))
    return tokens


def _equipment_tokens(block: OperationalBlock) -> set[str]:
    values = parse_json(block.equipment_refs_json, [])
    return {str(item.get("equipmentRef") or item.get("id")) if isinstance(item, dict) else str(item) for item in values if item}


def _conflict_fingerprint(conflict_type: str, refs: Iterable[str], explanation: str) -> str:
    material = f"{conflict_type}|{'|'.join(sorted(set(refs)))}|{explanation}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _option(option_type: str, label: str, description: str, score: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"type": option_type, "label": label, "description": description, "score": score, "payload": payload or {}}


def _add_conflict(target: list[dict[str, Any]], *, conflict_type: str, severity: str, block: OperationalBlock | None, related: list[str], explanation: str, options: list[dict[str, Any]]) -> None:
    refs = ([block.block_ref] if block else []) + related
    target.append({
        "conflictType": conflict_type,
        "severity": severity,
        "primaryBlockRef": block.block_ref if block else None,
        "relatedRefs": related,
        "explanation": explanation,
        "options": sorted(options, key=lambda item: item["score"], reverse=True),
        "fingerprint": _conflict_fingerprint(conflict_type, refs, explanation),
    })


def detect_constraints(session: Session, premises_ref: str, operational_date: date, persist: bool = True) -> list[dict[str, Any]]:
    blocks = session.exec(
        select(OperationalBlock)
        .where(OperationalBlock.premises_ref == premises_ref, OperationalBlock.operational_date == operational_date)
        .order_by(OperationalBlock.starts_at, OperationalBlock.area_ref)
    ).all()
    blocks = [row for row in blocks if row.status not in {"cancelled", "done"}]
    areas = {row.area_ref: row for row in session.exec(select(OperationalArea).where(OperationalArea.premises_ref == premises_ref)).all()}
    dependencies = session.exec(select(OperationalDependency).where(OperationalDependency.premises_ref == premises_ref)).all()
    by_ref = {row.block_ref: row for row in blocks}
    conflicts: list[dict[str, Any]] = []

    # Capacity, person and equipment overlap.
    for index, first in enumerate(blocks):
        for second in blocks[index + 1:]:
            if not overlaps(first.starts_at, first.ends_at, second.starts_at, second.ends_at):
                continue
            if first.area_ref == second.area_ref:
                area = areas.get(first.area_ref)
                simultaneous = [item for item in blocks if item.area_ref == first.area_ref and overlaps(first.starts_at, first.ends_at, item.starts_at, item.ends_at)]
                capacity = area.capacity if area else 1
                if len(simultaneous) > capacity:
                    related = sorted({item.block_ref for item in simultaneous if item.block_ref != first.block_ref})
                    _add_conflict(conflicts, conflict_type="area_capacity", severity="red", block=first, related=related, explanation=f"{first.area_name} has {len(simultaneous)} simultaneous blocks but capacity is {capacity}.", options=[
                        _option("move_block", "Move a lower-priority block", "Use another compatible area or later time.", 95),
                        _option("swap_blocks", "Swap cases", "Swap with a compatible later case after checking patient priority.", 80),
                        _option("override", "Emergency override", "Proceed only with named senior approval and a recorded safety justification.", 20),
                    ])
            common_staff = _staff_tokens(first) & _staff_tokens(second)
            if common_staff:
                _add_conflict(conflicts, conflict_type="staff_overlap", severity="red", block=first, related=[second.block_ref], explanation=f"Staff {', '.join(sorted(common_staff))} are assigned to overlapping blocks {first.block_ref} and {second.block_ref}.", options=[
                    _option("reassign_staff", "Assign alternative qualified staff", "Select a staff member on shift with the required competencies.", 100),
                    _option("move_block", "Move one block", "Move the lower-priority block outside the overlap.", 85),
                ])
            common_equipment = _equipment_tokens(first) & _equipment_tokens(second)
            if common_equipment:
                _add_conflict(conflicts, conflict_type="equipment_overlap", severity="red", block=first, related=[second.block_ref], explanation=f"Equipment {', '.join(sorted(common_equipment))} is allocated to overlapping work.", options=[
                    _option("reassign_equipment", "Use alternative equipment", "Select a compatible available equipment item.", 95),
                    _option("move_block", "Move one block", "Move one block until the equipment is released and cleaned.", 85),
                ])

    # Turnover windows.
    by_area: dict[str, list[OperationalBlock]] = defaultdict(list)
    for block in blocks:
        by_area[block.area_ref].append(block)
    for area_ref, rows in by_area.items():
        area = areas.get(area_ref)
        turnover = area.turnover_minutes if area else 0
        ordered = sorted(rows, key=lambda row: row.starts_at)
        for previous, current in zip(ordered, ordered[1:]):
            gap = int((normalise_dt(current.starts_at) - normalise_dt(previous.ends_at)).total_seconds() / 60)
            if gap < turnover:
                _add_conflict(conflicts, conflict_type="turnover_window", severity="red", block=current, related=[previous.block_ref], explanation=f"{current.area_name} has {gap} minutes turnover between cases; {turnover} minutes is required.", options=[
                    _option("move_block", "Move the later case", f"Delay {current.block_ref} by at least {turnover - gap} minutes.", 100, {"minutes": turnover - gap}),
                    _option("alternate_area", "Use another compatible area", "Move the case if another prepared area is available.", 80),
                ])

    # Staff shift and skill checks.
    staff_rows = session.exec(select(StaffMember).where(StaffMember.active == True)).all()
    staff_by_ref = {str(row.id): row for row in staff_rows if row.id is not None}
    shifts = session.exec(select(Shift)).all()
    shifts_by_staff: dict[str, list[Shift]] = defaultdict(list)
    for shift in shifts:
        shifts_by_staff[str(shift.staff_member_id)].append(shift)
    for block in blocks:
        required = {str(value).lower() for value in parse_json(block.required_skills_json, [])}
        area = areas.get(block.area_ref)
        required.update(str(value).lower() for value in parse_json(area.required_skills_json, []) if area)
        for staff_ref in _staff_tokens(block):
            staff = staff_by_ref.get(staff_ref)
            if not staff:
                _add_conflict(conflicts, conflict_type="unknown_staff", severity="amber", block=block, related=[staff_ref], explanation=f"Assigned staff reference {staff_ref} is not present in the staff register.", options=[_option("reconcile_staff", "Reconcile staff identity", "Link the external or imported staff reference to a verified staff record.", 100)])
                continue
            covering = [shift for shift in shifts_by_staff.get(staff_ref, []) if normalise_dt(shift.starts_at) <= normalise_dt(block.starts_at) and normalise_dt(shift.ends_at) >= normalise_dt(block.ends_at) and shift.status not in {"cancelled", "sick", "leave"}]
            if not covering:
                _add_conflict(conflicts, conflict_type="outside_shift", severity="red", block=block, related=[staff_ref], explanation=f"{staff.name} is not covered by an active shift for the full block.", options=[
                    _option("reassign_staff", "Assign on-shift staff", "Choose a qualified person whose shift covers the full block.", 100),
                    _option("approved_overtime", "Approve overtime", "Use only after fatigue and rest checks with named approval.", 45),
                ])
            skills = {part.strip().lower() for part in str(staff.skills or "").replace(";", ",").split(",") if part.strip()}
            missing = sorted(required - skills)
            if missing:
                _add_conflict(conflicts, conflict_type="skill_gap", severity="red", block=block, related=[staff_ref], explanation=f"{staff.name} lacks required competencies: {', '.join(missing)}.", options=[
                    _option("reassign_staff", "Assign competent staff", "Choose staff with every required competency.", 100),
                    _option("supervision", "Add qualified supervision", "Add a named qualified supervisor where policy permits.", 60),
                ])
        for shift in shifts:
            duration_hours = (normalise_dt(shift.ends_at) - normalise_dt(shift.starts_at)).total_seconds() / 3600
            if duration_hours > 12 and str(shift.staff_member_id) in _staff_tokens(block):
                _add_conflict(conflicts, conflict_type="fatigue_risk", severity="amber", block=block, related=[str(shift.staff_member_id)], explanation=f"Assigned shift is {duration_hours:.1f} hours; fatigue review is required.", options=[
                    _option("reassign_staff", "Use rested staff", "Reassign the block to a rested qualified person.", 90),
                    _option("fatigue_review", "Record fatigue review", "Document rest, breaks, workload and mitigation before proceeding.", 55),
                ])

    # Gates and dependencies.
    for block in blocks:
        gates = parse_json(block.gates_json, {})
        if block.block_type in {"procedure", "anaesthesia", "surgery", "imaging"}:
            unmet_red = []
            unmet_amber = []
            if gates.get("consent") not in {"approved", "authorised", "emergency_authority"}:
                unmet_red.append("consent")
            if gates.get("estimate") not in {"approved", "accepted", "emergency_authority"}:
                unmet_amber.append("estimate")
            if gates.get("insurance") in {"required", "pending", "declined"}:
                unmet_amber.append("insurance")
            if parse_json(block.pharmacy_refs_json, []) and gates.get("pharmacy") not in {"ready", "complete", True}:
                unmet_red.append("pharmacy")
            if unmet_red or unmet_amber:
                severity = "red" if unmet_red else "amber"
                items = unmet_red + unmet_amber
                _add_conflict(conflicts, conflict_type="governance_gate", severity=severity, block=block, related=[], explanation=f"{block.procedure_name} cannot proceed cleanly because {', '.join(items)} are incomplete.", options=[
                    _option("complete_gate", "Complete required gate", "Record the missing authorisation or readiness evidence.", 100),
                    _option("override", "Emergency authority", "Use only for genuine welfare urgency with named senior approval.", 15),
                ])
    for dependency in dependencies:
        predecessor = by_ref.get(dependency.predecessor_block_ref)
        successor = by_ref.get(dependency.successor_block_ref)
        if not predecessor or not successor:
            continue
        required_start = normalise_dt(predecessor.ends_at) + timedelta(minutes=dependency.lag_minutes)
        if normalise_dt(successor.starts_at) < required_start:
            _add_conflict(conflicts, conflict_type="dependency_violation", severity="red" if dependency.hard_constraint else "amber", block=successor, related=[predecessor.block_ref], explanation=f"{successor.procedure_name} starts before dependency {predecessor.procedure_name} can finish plus {dependency.lag_minutes} minutes lag.", options=[
                _option("propagate_delay", "Propagate predecessor timing", "Move the successor and all dependent work to the earliest safe time.", 100),
                _option("remove_dependency", "Review dependency", "Remove only if a qualified owner confirms it is not clinically or operationally required.", 30),
            ])

    # Declared service availability.
    services = session.exec(select(ServiceAvailability).where(ServiceAvailability.premises_ref == premises_ref)).all()
    unavailable_departments = {row.department.lower(): row for row in services if row.operational_status != "available" or not all([row.staffing_ready, row.equipment_ready, row.consumables_ready])}
    for block in blocks:
        area = areas.get(block.area_ref)
        if not area:
            continue
        service = unavailable_departments.get(area.department.lower())
        if service:
            _add_conflict(conflicts, conflict_type="service_unavailable", severity="red", block=block, related=[service.service_ref], explanation=f"{area.department} is {service.operational_status}: {service.limiting_reason or 'readiness condition failed'}.", options=[
                _option("alternate_service", "Move to available service", "Use another compatible area or partner service.", 100),
                _option("defer", "Defer with communication", "Reschedule and record owner/referring-vet communication.", 75),
            ])

    # Deduplicate identical detections.
    unique: dict[str, dict[str, Any]] = {item["fingerprint"]: item for item in conflicts}
    conflicts = list(unique.values())

    if persist:
        open_rows = session.exec(select(OperationalConflict).where(OperationalConflict.premises_ref == premises_ref, OperationalConflict.operational_date == operational_date, OperationalConflict.status == "open")).all()
        for row in open_rows:
            session.delete(row)
        session.flush()
        for item in conflicts:
            session.add(OperationalConflict(
                conflict_ref=ref("conflict"),
                premises_ref=premises_ref,
                operational_date=operational_date,
                conflict_type=item["conflictType"],
                severity=item["severity"],
                primary_block_ref=item["primaryBlockRef"],
                related_refs_json=json_text(item["relatedRefs"]),
                explanation=item["explanation"],
                options_json=json_text(item["options"]),
                fingerprint=item["fingerprint"],
            ))
        session.flush()
    return conflicts


def board_snapshot(session: Session, premises_ref: str, operational_date: date) -> dict[str, Any]:
    premises, areas = ensure_default_premises_and_areas(session, premises_ref)
    blocks = session.exec(select(OperationalBlock).where(OperationalBlock.premises_ref == premises_ref, OperationalBlock.operational_date == operational_date).order_by(OperationalBlock.starts_at, OperationalBlock.area_ref)).all()
    episodes = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.premises_ref == premises_ref, CanonicalEpisodeState.status == "active").order_by(CanonicalEpisodeState.updated_at.desc())).all()
    conflicts = detect_constraints(session, premises_ref, operational_date, persist=True)
    last_change = session.exec(select(BoardChangeEvent).where(BoardChangeEvent.premises_ref == premises_ref, BoardChangeEvent.operational_date == operational_date).order_by(BoardChangeEvent.id.desc())).first()
    return {
        "generatedAt": utc_now().isoformat(),
        "premises": premises_dict(premises),
        "operationalDate": operational_date.isoformat(),
        "areas": [area_dict(row) for row in sorted(areas, key=lambda item: (item.department, item.name))],
        "blocks": [block_dict(row) for row in blocks],
        "episodes": [episode_dict(row) for row in episodes],
        "conflicts": conflicts,
        "summary": {
            "blocks": len(blocks),
            "episodes": len(episodes),
            "redConflicts": len([item for item in conflicts if item["severity"] == "red"]),
            "amberConflicts": len([item for item in conflicts if item["severity"] == "amber"]),
            "unassignedBlocks": len([row for row in blocks if not row.lead_staff_ref]),
            "blockedBlocks": len([row for row in blocks if parse_json(row.blockers_json, [])]),
            "lastChangeId": last_change.id if last_change else 0,
        },
    }


def propagation_preview(session: Session, block_ref: str, minutes: int) -> dict[str, Any]:
    source = session.exec(select(OperationalBlock).where(OperationalBlock.block_ref == block_ref)).first()
    if not source:
        raise HTTPException(status_code=404, detail="operational block not found")
    if minutes == 0:
        return {"sourceBlockRef": block_ref, "minutes": 0, "affected": [], "alternatives": []}
    blocks = session.exec(select(OperationalBlock).where(OperationalBlock.premises_ref == source.premises_ref, OperationalBlock.operational_date == source.operational_date)).all()
    by_ref = {row.block_ref: row for row in blocks}
    dependencies = session.exec(select(OperationalDependency).where(OperationalDependency.premises_ref == source.premises_ref)).all()
    successors: dict[str, list[str]] = defaultdict(list)
    for dep in dependencies:
        successors[dep.predecessor_block_ref].append(dep.successor_block_ref)
    queue: deque[str] = deque([block_ref])
    affected_refs: set[str] = set()
    while queue:
        current = queue.popleft()
        if current in affected_refs:
            continue
        affected_refs.add(current)
        queue.extend(successors.get(current, []))
    # Same episode later stages and same-area later cases are operationally affected.
    for row in blocks:
        if row.block_ref == block_ref:
            continue
        if source.episode_ref and row.episode_ref == source.episode_ref and normalise_dt(row.starts_at) >= normalise_dt(source.starts_at):
            affected_refs.add(row.block_ref)
        if row.area_ref == source.area_ref and normalise_dt(row.starts_at) >= normalise_dt(source.ends_at):
            affected_refs.add(row.block_ref)
    delta = timedelta(minutes=minutes)
    affected = []
    for candidate_ref in sorted(affected_refs, key=lambda item: normalise_dt(by_ref[item].starts_at) if item in by_ref else utc_now()):
        row = by_ref.get(candidate_ref)
        if not row:
            continue
        affected.append({
            "blockRef": row.block_ref,
            "patientName": row.patient_name,
            "procedureName": row.procedure_name,
            "areaName": row.area_name,
            "currentStartsAt": row.starts_at.isoformat(),
            "proposedStartsAt": (normalise_dt(row.starts_at) + delta).isoformat(),
            "currentEndsAt": row.ends_at.isoformat(),
            "proposedEndsAt": (normalise_dt(row.ends_at) + delta).isoformat(),
            "expectedVersion": row.version,
        })
    alternatives = [
        _option("apply_propagation", "Apply propagated delay", f"Move {len(affected)} connected blocks by {minutes} minutes and re-run constraints.", 95, {"minutes": minutes}),
        _option("swap_cases", "Swap with a compatible later case", "Keep the area productive while protecting clinical priority and preparation state.", 75),
        _option("alternate_area", "Move to another compatible area", "Use another prepared area if staffing, equipment and infection-control constraints permit.", 70),
        _option("defer", "Defer with owner and referring-vet communication", "Record the reason, new plan and communication evidence.", 50),
    ]
    return {"sourceBlockRef": block_ref, "minutes": minutes, "affected": affected, "alternatives": alternatives}


def apply_propagated_delay(session: Session, block_ref: str, payload: dict[str, Any], auth: AuthContext) -> tuple[list[OperationalBlock], OperationalCommand]:
    minutes = int(payload.get("minutes") or 0)
    preview = propagation_preview(session, block_ref, minutes)
    expected_versions = payload.get("expectedVersions") or {item["blockRef"]: item["expectedVersion"] for item in preview["affected"]}
    command, _ = _command(session, command_type="PropagateDelay", target_type="operational_block", target_ref=block_ref, expected_version=expected_versions.get(block_ref), payload=payload, auth=auth, idempotency_key=payload.get("idempotencyKey"))
    delta = timedelta(minutes=minutes)
    changed: list[OperationalBlock] = []
    before_rows: list[dict[str, Any]] = []
    for item in preview["affected"]:
        row = session.exec(select(OperationalBlock).where(OperationalBlock.block_ref == item["blockRef"])).first()
        if not row:
            continue
        _assert_version(row.version, expected_versions.get(row.block_ref), f"operational block {row.block_ref}")
        before_rows.append(block_dict(row))
        row.starts_at = normalise_dt(row.starts_at) + delta
        row.ends_at = normalise_dt(row.ends_at) + delta
        row.operational_date = row.starts_at.date()
        row.version += 1
        row.last_command_ref = command.command_ref
        row.updated_at = utc_now()
        row.updated_by_subject = auth.subject
        row.updated_by_name = auth.actor_name
        row.updated_by_role = auth.role
        row.updated_by_auth_source = auth.auth_source
        session.add(row)
        changed.append(row)
    after_rows = [block_dict(row) for row in changed]
    source = next((row for row in changed if row.block_ref == block_ref), changed[0] if changed else None)
    if not source:
        raise HTTPException(status_code=409, detail="no blocks were changed")
    evidence_ref = _evidence(session, command=command, auth=auth, event_type="delay_propagated", action=f"propagated {minutes} minute delay across {len(changed)} blocks", before=before_rows, after=after_rows, premises_ref=source.premises_ref, operational_date=source.operational_date, risk_level="red" if payload.get("overrideReason") else "amber", reason=payload.get("reason") or "upstream delay", override_reason=payload.get("overrideReason"), entity_type="operational_block_chain", entity_id=block_ref, referral_episode_id=source.episode_ref)
    _complete_command(command, {"blocks": after_rows, "preview": preview}, evidence_ref)
    for row in changed:
        _emit_change(session, premises_ref=row.premises_ref, operational_date=row.operational_date, event_type="block_delayed", entity_type="operational_block", entity_ref=row.block_ref, entity_version=row.version, command_ref=command.command_ref, payload=block_dict(row))
    detect_constraints(session, source.premises_ref, source.operational_date, persist=True)
    return changed, command


def run_scenario(session: Session, payload: dict[str, Any], auth: AuthContext) -> ScenarioRun:
    premises_ref = str(payload.get("premisesRef") or "simulation-premises")
    operational_date = date.fromisoformat(str(payload.get("operationalDate") or utc_now().date().isoformat()))
    seed = int(payload.get("seed") or 42)
    commit = bool(payload.get("commit", False))
    case_count = max(10, min(int(payload.get("caseCount") or 40), 100))
    rng = random.Random(seed)
    ensure_default_premises_and_areas(session, premises_ref)
    run = ScenarioRun(run_ref=ref("scenario"), scenario_name=str(payload.get("scenarioName") or "referral-hospital-day"), premises_ref=premises_ref, operational_date=operational_date, seed=seed, committed=commit, configuration_json=json_text(payload) or "{}", created_by_subject=auth.subject)
    session.add(run)
    session.flush()

    areas = session.exec(select(OperationalArea).where(OperationalArea.premises_ref == premises_ref)).all()
    procedure_areas = [row for row in areas if row.area_type in {"theatre", "imaging", "consult"}]
    simulated: list[dict[str, Any]] = []
    base = datetime.combine(operational_date, time(8, 0), tzinfo=timezone.utc)
    for index in range(case_count):
        episode_ref = f"sim-{run.run_ref}-{index + 1:03d}"
        area = rng.choice(procedure_areas)
        duration = rng.choice([30, 45, 60, 75, 90, 120])
        slot = rng.randint(0, 36)
        starts = base + timedelta(minutes=15 * slot)
        if index in {5, 17}:  # deliberate pressure cases
            starts = base + timedelta(minutes=15 * 8)
            area = next((item for item in procedure_areas if item.area_ref == "mri"), area)
        block = {
            "blockRef": f"sim-block-{run.run_ref}-{index + 1:03d}",
            "episodeRef": episode_ref,
            "patientName": f"Simulation patient {index + 1}",
            "procedureName": rng.choice(["MRI", "CT", "Spinal surgery", "Orthopaedic surgery", "Ultrasound", "Specialist consult"]),
            "blockType": "procedure",
            "areaRef": area.area_ref,
            "areaName": area.name,
            "startsAt": starts,
            "endsAt": starts + timedelta(minutes=duration),
            "leadStaffRef": str(rng.randint(1, 16)),
            "requiredSkills": parse_json(area.required_skills_json, []),
            "gates": {"consent": "approved" if index % 9 else "pending", "estimate": "approved" if index % 7 else "pending", "pharmacy": "ready" if index % 11 else "pending"},
            "priority": 90 if index % 13 == 0 else 50,
        }
        simulated.append(block)
        if commit:
            episode = CanonicalEpisodeState(episode_ref=episode_ref, patient_name=block["patientName"], premises_ref=premises_ref, phase="estimate_and_consent", owner_role="clinician", gates_json=json_text(block["gates"]), next_action="prepare scheduled work")
            session.add(episode)
            row = OperationalBlock(
                block_ref=block["blockRef"], premises_ref=premises_ref, operational_date=operational_date, episode_ref=episode_ref, patient_name=block["patientName"], procedure_name=block["procedureName"], block_type="procedure", area_ref=area.area_ref, area_name=area.name, starts_at=starts, ends_at=starts + timedelta(minutes=duration), priority=block["priority"], lead_staff_ref=block["leadStaffRef"], required_skills_json=json_text(block["requiredSkills"]), gates_json=json_text(block["gates"]), updated_by_subject=auth.subject, updated_by_name=auth.actor_name, updated_by_role=auth.role, updated_by_auth_source=auth.auth_source,
            )
            session.add(row)
    session.flush()
    if commit:
        conflicts = detect_constraints(session, premises_ref, operational_date, persist=True)
    else:
        # Dry-run basic collision metrics without persisting blocks.
        conflicts = []
        for index, first in enumerate(simulated):
            for second in simulated[index + 1:]:
                if first["areaRef"] == second["areaRef"] and overlaps(first["startsAt"], first["endsAt"], second["startsAt"], second["endsAt"]):
                    conflicts.append({"severity": "red", "type": "area_capacity"})
                if first["leadStaffRef"] == second["leadStaffRef"] and overlaps(first["startsAt"], first["endsAt"], second["startsAt"], second["endsAt"]):
                    conflicts.append({"severity": "red", "type": "staff_overlap"})
    metrics = {
        "caseCount": case_count,
        "blockCount": len(simulated),
        "redConflicts": len([item for item in conflicts if item.get("severity") == "red"]),
        "amberConflicts": len([item for item in conflicts if item.get("severity") == "amber"]),
        "unapprovedConsent": len([item for item in simulated if item["gates"].get("consent") != "approved"]),
        "unapprovedEstimate": len([item for item in simulated if item["gates"].get("estimate") != "approved"]),
        "committed": commit,
        "target": {"theatres": 11, "dailyEpisodes": case_count},
    }
    run.status = "completed"
    run.metrics_json = json_text(metrics)
    run.completed_at = utc_now()
    session.add(run)
    return run


def _parse_import_content(source_type: str, content: str) -> list[dict[str, Any]]:
    if source_type.lower() == "json":
        value = json.loads(content)
        if isinstance(value, dict):
            value = value.get("rows") or value.get("blocks") or [value]
        if not isinstance(value, list):
            raise HTTPException(status_code=400, detail="JSON import must contain an array or rows/blocks array")
        return [dict(item) for item in value]
    reader = csv.DictReader(io.StringIO(content))
    return [dict(row) for row in reader]


def preview_import(session: Session, payload: dict[str, Any], auth: AuthContext) -> ImportBatch:
    source_type = str(payload.get("sourceType") or "csv").lower()
    content = str(payload.get("content") or "")
    if not content:
        raise HTTPException(status_code=400, detail="import content is empty")
    rows = _parse_import_content(source_type, content)
    mapping = payload.get("mapping") or {}
    premises_ref = str(payload.get("premisesRef") or "default-premises")
    source_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    batch_ref = ref("import")
    normalised: list[dict[str, Any]] = []
    rejected = 0
    ensure_default_premises_and_areas(session, premises_ref)
    areas = {row.area_ref: row for row in session.exec(select(OperationalArea).where(OperationalArea.premises_ref == premises_ref)).all()}

    def value(row: dict[str, Any], target: str, *fallback: str) -> Any:
        source = mapping.get(target) or target
        if source in row and row[source] not in {None, ""}:
            return row[source]
        for key in fallback:
            if key in row and row[key] not in {None, ""}:
                return row[key]
        return None

    for row_number, source in enumerate(rows, start=2 if source_type == "csv" else 1):
        issues: list[str] = []
        area_ref = str(value(source, "areaRef", "area", "room") or "")
        patient_name = str(value(source, "patientName", "patient", "name") or "")
        procedure_name = str(value(source, "procedureName", "procedure", "work") or "")
        starts_raw = value(source, "startsAt", "start", "starts_at")
        ends_raw = value(source, "endsAt", "end", "ends_at")
        try:
            starts = normalise_dt(datetime.fromisoformat(str(starts_raw).replace("Z", "+00:00")))
            ends = normalise_dt(datetime.fromisoformat(str(ends_raw).replace("Z", "+00:00")))
            if ends <= starts:
                issues.append("end must be after start")
        except Exception:
            starts = ends = utc_now()
            issues.append("invalid start or end timestamp")
        if not patient_name:
            issues.append("patient is missing")
        if not procedure_name:
            issues.append("procedure is missing")
        if area_ref not in areas:
            issues.append(f"area {area_ref or '[blank]'} is not recognised")
        normal = {
            "blockRef": str(value(source, "blockRef", "id", "external_id") or ref("imported-block")),
            "episodeRef": value(source, "episodeRef", "episode", "case_id"),
            "patientName": patient_name,
            "procedureName": procedure_name,
            "blockType": str(value(source, "blockType", "type") or "procedure"),
            "areaRef": area_ref,
            "startsAt": starts.isoformat(),
            "endsAt": ends.isoformat(),
            "leadStaffRef": value(source, "leadStaffRef", "staff_id", "clinician_id"),
            "externalRefs": {"source": payload.get("sourceName"), "sourceRecord": value(source, "externalId", "id", "external_id")},
            "gates": {},
        }
        if issues:
            rejected += 1
            session.add(ImportReconciliationItem(item_ref=ref("reconcile"), batch_ref=batch_ref, row_number=row_number, issue_type="validation", detail="; ".join(issues), source_record_json=json_text(source) or "{}", suggested_match_json=json_text(normal)))
        else:
            normalised.append(normal)
    batch = ImportBatch(batch_ref=batch_ref, source_type=source_type, source_name=str(payload.get("sourceName") or "manual import"), premises_ref=premises_ref, status="preview", row_count=len(rows), accepted_count=len(normalised), rejected_count=rejected, source_hash=source_hash, mapping_json=json_text(mapping), summary_json=json_text({"normalisedRows": normalised, "issues": rejected}), created_by_subject=auth.subject)
    session.add(batch)
    return batch


def commit_import(session: Session, batch_ref: str, auth: AuthContext) -> tuple[ImportBatch, list[OperationalBlock]]:
    batch = session.exec(select(ImportBatch).where(ImportBatch.batch_ref == batch_ref)).first()
    if not batch:
        raise HTTPException(status_code=404, detail="import batch not found")
    if batch.status == "committed":
        existing = session.exec(select(OperationalBlock).where(OperationalBlock.external_refs_json.contains(batch_ref))).all()
        return batch, existing
    summary = parse_json(batch.summary_json, {})
    normalised = summary.get("normalisedRows") or []
    created: list[OperationalBlock] = []
    for index, item in enumerate(normalised):
        item = dict(item)
        external = item.get("externalRefs") or {}
        external["importBatchRef"] = batch_ref
        item["externalRefs"] = external
        item["premisesRef"] = batch.premises_ref
        item["idempotencyKey"] = f"import:{batch_ref}:{index}"
        row, _, was_created = create_block(session, item, auth)
        if was_created:
            created.append(row)
    batch.status = "committed"
    batch.committed_at = utc_now()
    session.add(batch)
    return batch, created


def operational_readiness(session: Session) -> dict[str, Any]:
    checks = {
        "databaseConfigured": bool(os.getenv("DATABASE_URL")),
        "migrationsRequired": os.getenv("AUTO_CREATE_SCHEMA", "false").lower() not in {"1", "true", "yes"},
        "authenticationRequired": os.getenv("AUTH_ENFORCEMENT", "audit").lower() == "required",
        "oidcConfigured": os.getenv("AUTH_MODE", "local").lower() == "oidc" and bool(os.getenv("OIDC_ISSUER")) and bool(os.getenv("OIDC_JWKS_URL")),
        "backupConfigured": bool(os.getenv("BACKUP_POLICY_REF")) or bool(os.getenv("DATABASE_BACKUP_ENABLED")),
        "errorReportingConfigured": bool(os.getenv("ERROR_REPORTING_DSN")),
        "retentionConfigured": bool(os.getenv("DATA_RETENTION_POLICY_REF")),
        "incidentPlanConfigured": bool(os.getenv("INCIDENT_RESPONSE_PLAN_REF")),
    }
    premises_count = len(session.exec(select(HospitalPremises)).all())
    block_count = len(session.exec(select(OperationalBlock)).all())
    failed = [key for key, value in checks.items() if not value]
    return {
        "readyForProduction": not failed,
        "checks": checks,
        "failedChecks": failed,
        "database": {"premises": premises_count, "operationalBlocks": block_count},
        "generatedAt": utc_now().isoformat(),
    }
