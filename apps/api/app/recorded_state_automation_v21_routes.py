from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, require_roles
from app.clinical_execution_models import ClinicalObservation
from app.control_plane_models import CriticalResultAcknowledgement
from app.database import get_session
from app.hospital_ops_models import CanonicalEpisodeState
from app.operational_automation_v20_routes import (
    AUTOMATION_ROLES,
    AutomationEvaluate,
    evaluate_automation,
    require_episode,
)


generic_guard_router = APIRouter(
    prefix="/api/v20/automation",
    tags=["recorded-state-automation-guard-v21"],
)
recorded_router = APIRouter(
    prefix="/api/v21/automation",
    tags=["recorded-state-automation-v21"],
)

DATABASE_BACKED_TRIGGER_TYPES = {"observation", "critical_result", "evidence_gap"}


class RecordedAutomationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commitActions: bool = False
    reason: str = PydanticField(min_length=8, max_length=2000)
    expectedVersion: int | None = PydanticField(default=None, ge=1)
    expectedStateHash: str | None = PydanticField(default=None, min_length=64, max_length=64)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalise_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def canonical_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def state_hash(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def require_version(payload: RecordedAutomationRequest, current_version: int, label: str) -> None:
    if not payload.commitActions:
        return
    if payload.expectedVersion is None:
        raise HTTPException(status_code=409, detail=f"expectedVersion is required to commit {label} automation")
    if payload.expectedVersion != current_version:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "source_version_conflict",
                "source": label,
                "expectedVersion": payload.expectedVersion,
                "currentVersion": current_version,
            },
        )


def require_hash(payload: RecordedAutomationRequest, current_hash: str, label: str) -> None:
    if not payload.commitActions:
        return
    if payload.expectedStateHash is None:
        raise HTTPException(status_code=409, detail=f"expectedStateHash is required to commit {label} automation")
    if payload.expectedStateHash != current_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "source_state_conflict",
                "source": label,
                "expectedStateHash": payload.expectedStateHash,
                "currentStateHash": current_hash,
            },
        )


def run_recorded(
    *,
    episode_ref: str,
    trigger_type: str,
    trigger_ref: str,
    facts: dict[str, Any],
    payload: RecordedAutomationRequest,
    source: dict[str, Any],
    session: Session,
    auth: AuthContext,
) -> dict[str, Any]:
    result = evaluate_automation(
        AutomationEvaluate(
            episodeRef=episode_ref,
            triggerType=trigger_type,
            triggerRef=trigger_ref,
            facts=canonical_copy(facts),
            commitActions=payload.commitActions,
            reason=payload.reason,
        ),
        session=session,
        auth=auth,
    )
    result["sourceAuthority"] = {
        **source,
        "factsAcceptedFromBrowser": False,
        "derivedFromCanonicalDatabase": True,
    }
    return result


def observation_snapshot(row: ClinicalObservation) -> dict[str, Any]:
    return {
        "recordType": "clinical_observation",
        "observationRef": row.observation_ref,
        "episodeRef": row.episode_ref,
        "areaRef": row.area_ref,
        "observationType": row.observation_type,
        "values": canonical_copy(row.values),
        "concernLevel": row.concern_level,
        "escalationRequired": row.escalation_required,
        "escalationStatus": row.escalation_status,
        "escalatedToRole": row.escalated_to_role,
        "escalationNote": row.escalation_note,
        "resolvedAt": row.resolved_at.isoformat() if row.resolved_at else None,
        "recordedAt": row.recorded_at.isoformat() if row.recorded_at else None,
        "version": row.version,
    }


def critical_result_snapshot(row: CriticalResultAcknowledgement) -> dict[str, Any]:
    due_at = normalise_utc(row.due_at)
    return {
        "recordType": "critical_result_acknowledgement",
        "resultRef": row.result_ref,
        "episodeRef": row.referral_episode_id,
        "patientCaseId": row.patient_case_id,
        "resultType": row.result_type,
        "severity": row.severity,
        "summary": row.summary,
        "status": row.status,
        "assignedTo": row.assigned_to,
        "assignedRole": row.assigned_role,
        "dueAt": due_at.isoformat() if due_at else None,
        "acknowledgedBy": row.acknowledged_by,
        "acknowledgedAt": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
        "actionTaken": row.action_taken,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def parse_gates(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=409, detail="canonical episode gates are not valid JSON")
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=409, detail="canonical episode gates are not an object")
    return parsed


def gate_is_complete(value: Any, accepted: set[Any]) -> bool:
    if isinstance(value, str):
        value = value.strip().lower()
    return value in accepted


def derive_evidence_gaps(episode: CanonicalEpisodeState, gates: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    late_phases = {
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
    }
    discharge_phases = {"discharge_readiness", "discharged", "referring_vet_report", "closed"}

    if episode.phase in late_phases or "consent" in gates:
        if not gate_is_complete(gates.get("consent"), {"approved", "authorised", "emergency_authority"}):
            gaps.append("consent")
    if episode.phase in late_phases or "estimate" in gates:
        if not gate_is_complete(gates.get("estimate"), {"approved", "accepted", "emergency_authority"}):
            gaps.append("estimate_authority")
    if "handover" in gates and not gate_is_complete(gates.get("handover"), {"complete", "accepted", "acknowledged", True}):
        gaps.append("handover")
    result_value = gates.get("result_review", gates.get("results"))
    if ("result_review" in gates or "results" in gates) and not gate_is_complete(
        result_value,
        {"complete", "reviewed", "acknowledged", True},
    ):
        gaps.append("result_review")
    if episode.phase in discharge_phases or "discharge" in gates:
        if not gate_is_complete(gates.get("discharge"), {"complete", "ready", True}):
            gaps.append("discharge")
    owner_value = gates.get("owner_update", gates.get("owner_communication"))
    if episode.phase in discharge_phases or "owner_update" in gates or "owner_communication" in gates:
        if not gate_is_complete(owner_value, {"complete", "sent", "recorded", True}):
            gaps.append("owner_communication")
    return list(dict.fromkeys(gaps))


@generic_guard_router.post("/evaluate")
def guarded_generic_evaluation(
    payload: AutomationEvaluate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*AUTOMATION_ROLES)),
):
    trigger_type = payload.triggerType.strip().lower()
    if payload.commitActions and trigger_type in DATABASE_BACKED_TRIGGER_TYPES:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "recorded_source_required",
                "message": "Committed automation for this trigger must use a v21 recorded-state route.",
                "triggerType": trigger_type,
            },
        )
    return evaluate_automation(payload, session=session, auth=auth)


@recorded_router.post("/observations/{observation_ref}/evaluate")
def evaluate_recorded_observation(
    observation_ref: str,
    payload: RecordedAutomationRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*AUTOMATION_ROLES)),
):
    row = session.exec(
        select(ClinicalObservation).where(ClinicalObservation.observation_ref == observation_ref)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="recorded clinical observation not found")
    episode = require_episode(session, row.episode_ref)
    require_version(payload, row.version, "clinical observation")
    snapshot = observation_snapshot(row)
    current_hash = state_hash(snapshot)
    if payload.expectedStateHash is not None:
        require_hash(payload, current_hash, "clinical observation")
    detail = f"{row.observation_type}: {json.dumps(row.values, sort_keys=True, default=str)}"
    if row.escalation_note:
        detail = f"{detail}; recorded escalation note: {row.escalation_note}"
    return run_recorded(
        episode_ref=episode.episode_ref,
        trigger_type="observation",
        trigger_ref=row.observation_ref,
        facts={
            "concernLevel": row.concern_level,
            "detail": detail,
            "sourceRecordType": "clinical_observation",
            "sourceRecordRef": row.observation_ref,
            "sourceVersion": row.version,
            "sourceStateHash": current_hash,
            "escalationRequired": row.escalation_required,
            "escalationStatus": row.escalation_status,
        },
        payload=payload,
        source={
            "recordType": "clinical_observation",
            "recordRef": row.observation_ref,
            "sourceVersion": row.version,
            "sourceStateHash": current_hash,
        },
        session=session,
        auth=auth,
    )


@recorded_router.post("/critical-results/{result_ref}/evaluate")
def evaluate_recorded_critical_result(
    result_ref: str,
    payload: RecordedAutomationRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*AUTOMATION_ROLES)),
):
    row = session.exec(
        select(CriticalResultAcknowledgement).where(CriticalResultAcknowledgement.result_ref == result_ref)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="recorded critical result not found")
    episode = require_episode(session, row.referral_episode_id)
    if row.patient_case_id and row.patient_case_id != episode.patient_ref:
        raise HTTPException(status_code=409, detail="critical result patient does not match canonical episode")
    snapshot = critical_result_snapshot(row)
    current_hash = state_hash(snapshot)
    require_hash(payload, current_hash, "critical result")
    due_at = normalise_utc(row.due_at)
    acknowledged = row.status == "acknowledged" or row.acknowledged_at is not None
    overdue = bool(not acknowledged and due_at and due_at < utc_now())
    return run_recorded(
        episode_ref=episode.episode_ref,
        trigger_type="critical_result",
        trigger_ref=row.result_ref,
        facts={
            "critical": row.severity.strip().lower() in {"red", "critical"},
            "acknowledged": acknowledged,
            "overdue": overdue,
            "summary": f"{row.result_type}: {row.summary}",
            "sourceRecordType": "critical_result_acknowledgement",
            "sourceRecordRef": row.result_ref,
            "sourceStateHash": current_hash,
            "deadlineState": "overdue" if overdue else "acknowledged" if acknowledged else "within_window",
        },
        payload=payload,
        source={
            "recordType": "critical_result_acknowledgement",
            "recordRef": row.result_ref,
            "sourceStateHash": current_hash,
        },
        session=session,
        auth=auth,
    )


@recorded_router.post("/episodes/{episode_ref}/evidence-gaps/evaluate")
def evaluate_recorded_evidence_gaps(
    episode_ref: str,
    payload: RecordedAutomationRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*AUTOMATION_ROLES)),
):
    episode = require_episode(session, episode_ref)
    require_version(payload, episode.version, "canonical episode gates")
    gates = parse_gates(episode.gates_json)
    snapshot = {
        "recordType": "canonical_episode_gates",
        "episodeRef": episode.episode_ref,
        "phase": episode.phase,
        "status": episode.status,
        "version": episode.version,
        "gates": canonical_copy(gates),
    }
    current_hash = state_hash(snapshot)
    if payload.expectedStateHash is not None:
        require_hash(payload, current_hash, "canonical episode gates")
    gaps = derive_evidence_gaps(episode, gates)
    return run_recorded(
        episode_ref=episode.episode_ref,
        trigger_type="evidence_gap",
        trigger_ref=f"episode-gates:{episode.episode_ref}:v{episode.version}",
        facts={
            "gaps": gaps,
            "detail": f"Canonical episode gates at phase {episode.phase}",
            "sourceRecordType": "canonical_episode_gates",
            "sourceRecordRef": episode.episode_ref,
            "sourceVersion": episode.version,
            "sourceStateHash": current_hash,
            "storedGates": canonical_copy(gates),
        },
        payload=payload,
        source={
            "recordType": "canonical_episode_gates",
            "recordRef": episode.episode_ref,
            "sourceVersion": episode.version,
            "sourceStateHash": current_hash,
        },
        session=session,
        auth=auth,
    )
