from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth import AuthContext, CLINICAL_ROLES
from app.clinical_execution_models import ClinicalObservation
from app.control_plane_models import CriticalResultAcknowledgement
from app.database import engine
from app.event_driven_automation_v22_models import AutomationRuntimeConfigV22, AutomationTriggerV22
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock
from app.operational_automation_v20_routes import AUTOMATION_ROLES, evaluate_trigger
from app.recorded_state_automation_v21_routes import (
    RecordedAutomationRequest,
    canonical_copy,
    critical_result_snapshot,
    derive_evidence_gaps,
    evaluate_recorded_critical_result,
    evaluate_recorded_evidence_gaps,
    evaluate_recorded_observation,
    observation_snapshot,
    parse_gates,
    require_episode,
    require_hash,
    require_version,
    run_recorded,
    state_hash,
)

SUPPORTED_MODES = {"disabled", "preview_only", "governed_commit"}
SUPPORTED_SOURCE_TYPES = {"observation", "critical_result", "evidence_gap", "operational_delay"}
TERMINAL_TRIGGER_STATES = {"completed", "previewed", "no_action", "skipped"}
FINISHED_BLOCK_STATES = {"completed", "cancelled", "closed", "finished"}
ACTIVE_BLOCK_STATES = {"in_progress", "started", "active", "procedure", "running"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def normalise_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def block_snapshot(row: OperationalBlock) -> dict[str, Any]:
    return {
        "recordType": "operational_block",
        "blockRef": row.block_ref,
        "premisesRef": row.premises_ref,
        "episodeRef": row.episode_ref,
        "patientRef": row.patient_ref,
        "procedureRef": row.procedure_ref,
        "procedureName": row.procedure_name,
        "blockType": row.block_type,
        "areaRef": row.area_ref,
        "startsAt": normalise_utc(row.starts_at).isoformat(),
        "endsAt": normalise_utc(row.ends_at).isoformat(),
        "status": row.status,
        "riskLevel": row.risk_level,
        "priority": row.priority,
        "blockers": canonical_copy(parse_json_object(row.blockers_json)),
        "gates": canonical_copy(parse_json_object(row.gates_json)),
        "externalRefs": canonical_copy(parse_json_object(row.external_refs_json)),
        "version": row.version,
        "lastCommandRef": row.last_command_ref,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def episode_gate_snapshot(row: CanonicalEpisodeState) -> dict[str, Any]:
    return {
        "recordType": "canonical_episode_gates",
        "episodeRef": row.episode_ref,
        "phase": row.phase,
        "status": row.status,
        "version": row.version,
        "gates": canonical_copy(parse_gates(row.gates_json)),
    }


def derive_delay(row: OperationalBlock, *, now: datetime | None = None) -> dict[str, Any]:
    current = normalise_utc(now or utc_now())
    status = (row.status or "planned").strip().lower()
    starts_at = normalise_utc(row.starts_at)
    ends_at = normalise_utc(row.ends_at)

    if status in FINISHED_BLOCK_STATES:
        raw_minutes = 0
        basis = "finished"
    elif status in ACTIVE_BLOCK_STATES:
        raw_minutes = max(0, int((current - ends_at).total_seconds() // 60))
        basis = "overrun_after_planned_end"
    else:
        raw_minutes = max(0, int((current - starts_at).total_seconds() // 60))
        basis = "late_start_after_planned_start"

    band = 60 if raw_minutes >= 60 else 30 if raw_minutes >= 30 else 15 if raw_minutes >= 15 else 0
    return {
        "rawMinutes": raw_minutes,
        "delayBandMinutes": band,
        "delayBand": "60_plus" if band == 60 else "30_59" if band == 30 else "15_29" if band == 15 else "under_15",
        "basis": basis,
        "asOf": current.isoformat(),
    }


def runtime_settings(session: Session, premises_ref: str) -> dict[str, Any]:
    row = session.exec(
        select(AutomationRuntimeConfigV22).where(AutomationRuntimeConfigV22.premises_ref == premises_ref)
    ).first()
    if row:
        return {
            "configRef": row.config_ref,
            "premisesRef": row.premises_ref,
            "mode": row.mode,
            "enabledTriggerTypes": list(row.enabled_trigger_types),
            "serviceSubject": row.service_subject,
            "serviceName": row.service_name,
            "serviceRole": row.service_role,
            "backgroundScanEnabled": row.background_scan_enabled,
            "scanIntervalSeconds": row.scan_interval_seconds,
            "version": row.version,
            "persisted": True,
        }
    default_mode = os.getenv("AUTOMATION_V22_DEFAULT_MODE", "disabled").strip().lower()
    if default_mode not in SUPPORTED_MODES:
        default_mode = "disabled"
    return {
        "configRef": None,
        "premisesRef": premises_ref,
        "mode": default_mode,
        "enabledTriggerTypes": sorted(SUPPORTED_SOURCE_TYPES),
        "serviceSubject": os.getenv("AUTOMATION_V22_SERVICE_SUBJECT", "lucyworks:automation-v22"),
        "serviceName": os.getenv("AUTOMATION_V22_SERVICE_NAME", "LucyWorks governed automation"),
        "serviceRole": os.getenv("AUTOMATION_V22_SERVICE_ROLE", "senior_clinician").strip().lower(),
        "backgroundScanEnabled": os.getenv("AUTOMATION_V22_BACKGROUND_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
        "scanIntervalSeconds": max(30, int(os.getenv("AUTOMATION_V22_SCAN_INTERVAL_SECONDS", "60"))),
        "version": 0,
        "persisted": False,
    }


def service_auth(settings: dict[str, Any]) -> AuthContext:
    role = str(settings["serviceRole"]).strip().lower()
    if role not in AUTOMATION_ROLES:
        raise HTTPException(status_code=503, detail="automation service role is not permitted")
    return AuthContext(
        subject=str(settings["serviceSubject"]),
        actor_id=str(settings["serviceSubject"]),
        actor_name=str(settings["serviceName"]),
        role=role,
        issuer="lucyworks-internal",
        auth_source="system_automation",
        verified=True,
        claims={"automationMode": settings["mode"], "premisesRef": settings["premisesRef"]},
    )


def source_descriptor(session: Session, source_type: str, source_ref: str) -> dict[str, Any]:
    if source_type == "observation":
        row = session.exec(
            select(ClinicalObservation).where(ClinicalObservation.observation_ref == source_ref)
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="recorded clinical observation not found")
        episode = require_episode(session, row.episode_ref)
        snapshot = observation_snapshot(row)
        return {
            "sourceType": source_type,
            "sourceRef": row.observation_ref,
            "sourceVersion": row.version,
            "sourceStateHash": state_hash(snapshot),
            "sourceSnapshot": snapshot,
            "episodeRef": episode.episode_ref,
            "premisesRef": episode.premises_ref,
        }

    if source_type == "critical_result":
        row = session.exec(
            select(CriticalResultAcknowledgement).where(CriticalResultAcknowledgement.result_ref == source_ref)
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="recorded critical result not found")
        episode = require_episode(session, row.referral_episode_id)
        snapshot = critical_result_snapshot(row)
        return {
            "sourceType": source_type,
            "sourceRef": row.result_ref,
            "sourceVersion": None,
            "sourceStateHash": state_hash(snapshot),
            "sourceSnapshot": snapshot,
            "episodeRef": episode.episode_ref,
            "premisesRef": episode.premises_ref,
        }

    if source_type == "evidence_gap":
        episode = require_episode(session, source_ref)
        snapshot = episode_gate_snapshot(episode)
        return {
            "sourceType": source_type,
            "sourceRef": episode.episode_ref,
            "sourceVersion": episode.version,
            "sourceStateHash": state_hash(snapshot),
            "sourceSnapshot": snapshot,
            "episodeRef": episode.episode_ref,
            "premisesRef": episode.premises_ref,
        }

    if source_type == "operational_delay":
        row = session.exec(select(OperationalBlock).where(OperationalBlock.block_ref == source_ref)).first()
        if not row:
            raise HTTPException(status_code=404, detail="recorded operational block not found")
        if not row.episode_ref:
            raise HTTPException(status_code=409, detail="operational block is not linked to a canonical episode")
        episode = require_episode(session, row.episode_ref)
        if row.patient_ref and episode.patient_ref and row.patient_ref != episode.patient_ref:
            raise HTTPException(status_code=409, detail="operational block patient does not match canonical episode")
        snapshot = block_snapshot(row)
        delay = derive_delay(row)
        snapshot = {**snapshot, "derivedDelayBand": delay["delayBand"]}
        return {
            "sourceType": source_type,
            "sourceRef": row.block_ref,
            "sourceVersion": row.version,
            "sourceStateHash": state_hash(snapshot),
            "sourceSnapshot": snapshot,
            "episodeRef": episode.episode_ref,
            "premisesRef": episode.premises_ref,
            "derivedDelay": delay,
        }

    raise HTTPException(status_code=422, detail="unsupported automation source type")


def evaluate_recorded_operational_delay(
    block_ref: str,
    payload: RecordedAutomationRequest,
    *,
    session: Session,
    auth: AuthContext,
) -> dict[str, Any]:
    row = session.exec(select(OperationalBlock).where(OperationalBlock.block_ref == block_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="recorded operational block not found")
    if not row.episode_ref:
        raise HTTPException(status_code=409, detail="operational block is not linked to a canonical episode")
    episode = require_episode(session, row.episode_ref)
    if row.patient_ref and episode.patient_ref and row.patient_ref != episode.patient_ref:
        raise HTTPException(status_code=409, detail="operational block patient does not match canonical episode")

    delay = derive_delay(row)
    snapshot = {**block_snapshot(row), "derivedDelayBand": delay["delayBand"]}
    current_hash = state_hash(snapshot)
    require_version(payload, row.version, "operational block")
    if payload.expectedStateHash is not None:
        require_hash(payload, current_hash, "operational block")

    band_minutes = int(delay["delayBandMinutes"])
    detail = (
        f"Recorded operational block {row.block_ref} is in the {delay['delayBand']} delay band "
        f"using {delay['basis']}. Procedure: {row.procedure_name}; area: {row.area_name}."
    )
    result = run_recorded(
        episode_ref=episode.episode_ref,
        trigger_type="operational_delay",
        trigger_ref=f"block-delay:{row.block_ref}:{delay['delayBand']}:v{row.version}",
        facts={
            "delayMinutes": band_minutes,
            "detail": detail,
            "sourceRecordType": "operational_block",
            "sourceRecordRef": row.block_ref,
            "sourceVersion": row.version,
            "sourceStateHash": current_hash,
            "delayBand": delay["delayBand"],
            "delayBasis": delay["basis"],
        },
        payload=payload,
        source={
            "recordType": "operational_block",
            "recordRef": row.block_ref,
            "sourceVersion": row.version,
            "sourceStateHash": current_hash,
        },
        session=session,
        auth=auth,
    )
    result["recordedDelay"] = delay
    return result


def _trigger_dict(row: AutomationTriggerV22) -> dict[str, Any]:
    return row.model_dump(mode="json")


def enqueue_source(
    source_type: str,
    source_ref: str,
    *,
    initiated_by: AuthContext | None = None,
) -> tuple[AutomationTriggerV22, bool]:
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise HTTPException(status_code=422, detail="unsupported automation source type")
    with Session(engine) as session:
        descriptor = source_descriptor(session, source_type, source_ref)
        settings = runtime_settings(session, descriptor["premisesRef"])
        mode = str(settings["mode"])
        existing = session.exec(
            select(AutomationTriggerV22)
            .where(AutomationTriggerV22.source_type == source_type)
            .where(AutomationTriggerV22.source_ref == source_ref)
            .where(AutomationTriggerV22.source_state_hash == descriptor["sourceStateHash"])
            .where(AutomationTriggerV22.mode == mode)
        ).first()
        if existing:
            return existing, False

        actor = initiated_by or AuthContext(
            subject="lucyworks:automation-listener-v22",
            actor_id="lucyworks:automation-listener-v22",
            actor_name="LucyWorks automation listener",
            role="system",
            auth_source="system_automation",
            verified=True,
        )
        enabled = source_type in set(settings["enabledTriggerTypes"])
        row = AutomationTriggerV22(
            trigger_ref=new_ref("autotrigger-v22"),
            premises_ref=descriptor["premisesRef"],
            episode_ref=descriptor["episodeRef"],
            source_type=source_type,
            source_ref=source_ref,
            source_version=descriptor.get("sourceVersion"),
            source_state_hash=descriptor["sourceStateHash"],
            mode=mode,
            status="queued" if mode != "disabled" and enabled else "skipped",
            source_snapshot=descriptor["sourceSnapshot"],
            initiated_by_subject=actor.subject,
            initiated_by_name=actor.actor_name,
            initiated_by_role=actor.role,
            processed_at=utc_now() if mode == "disabled" or not enabled else None,
            error_code="automation_disabled" if mode == "disabled" else "trigger_disabled" if not enabled else None,
            error_detail=None if enabled and mode != "disabled" else "No automation decision was requested.",
        )
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.exec(
                select(AutomationTriggerV22)
                .where(AutomationTriggerV22.source_type == source_type)
                .where(AutomationTriggerV22.source_ref == source_ref)
                .where(AutomationTriggerV22.source_state_hash == descriptor["sourceStateHash"])
                .where(AutomationTriggerV22.mode == mode)
            ).one()
            return existing, False
        session.refresh(row)
        return row, True


def _mark_trigger_failure(trigger_ref: str, error: Exception) -> AutomationTriggerV22:
    with Session(engine) as session:
        row = session.exec(select(AutomationTriggerV22).where(AutomationTriggerV22.trigger_ref == trigger_ref)).one()
        row.status = "failed"
        row.error_code = "automation_evaluation_failed"
        if isinstance(error, HTTPException):
            row.error_code = (
                str(error.detail.get("code"))
                if isinstance(error.detail, dict) and error.detail.get("code")
                else f"http_{error.status_code}"
            )
            row.error_detail = json.dumps(error.detail, default=str)[:4000]
        else:
            row.error_detail = f"{type(error).__name__}: {error}"[:4000]
        row.processed_at = utc_now()
        row.updated_at = utc_now()
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def process_trigger(trigger_ref: str, *, force: bool = False) -> AutomationTriggerV22:
    try:
        with Session(engine) as session:
            row = session.exec(select(AutomationTriggerV22).where(AutomationTriggerV22.trigger_ref == trigger_ref)).first()
            if not row:
                raise HTTPException(status_code=404, detail="automation trigger not found")
            if row.status in TERMINAL_TRIGGER_STATES and not force:
                return row

            settings = runtime_settings(session, row.premises_ref)
            if row.mode == "disabled" or row.source_type not in set(settings["enabledTriggerTypes"]):
                row.status = "skipped"
                row.error_code = "automation_disabled" if row.mode == "disabled" else "trigger_disabled"
                row.processed_at = utc_now()
                row.updated_at = utc_now()
                session.add(row)
                session.commit()
                session.refresh(row)
                return row

            if row.source_type in {"observation", "critical_result"} and str(settings["serviceRole"]).lower() not in CLINICAL_ROLES:
                raise HTTPException(status_code=503, detail="clinical automation requires a configured clinical service role")

            row.status = "processing"
            row.attempts += 1
            row.started_at = utc_now()
            row.updated_at = utc_now()
            row.error_code = None
            row.error_detail = None
            session.add(row)
            session.commit()

            auth = service_auth(settings)
            commit = row.mode == "governed_commit"
            payload = RecordedAutomationRequest(
                commitActions=commit,
                reason=(
                    f"System automation evaluated recorded {row.source_type.replace('_', ' ')} "
                    f"{row.source_ref} in {row.mode} mode."
                ),
                expectedVersion=row.source_version,
                expectedStateHash=row.source_state_hash,
            )
            if row.source_type == "observation":
                result = evaluate_recorded_observation(row.source_ref, payload, session=session, auth=auth)
            elif row.source_type == "critical_result":
                result = evaluate_recorded_critical_result(row.source_ref, payload, session=session, auth=auth)
            elif row.source_type == "evidence_gap":
                result = evaluate_recorded_evidence_gaps(row.source_ref, payload, session=session, auth=auth)
            elif row.source_type == "operational_delay":
                result = evaluate_recorded_operational_delay(row.source_ref, payload, session=session, auth=auth)
            else:
                raise HTTPException(status_code=422, detail="unsupported automation source type")

            row = session.exec(select(AutomationTriggerV22).where(AutomationTriggerV22.trigger_ref == trigger_ref)).one()
            decision = result.get("decision") or {}
            work = result.get("workItems") or []
            outcome = str(decision.get("outcome") or "no_action")
            row.decision_ref = decision.get("decision_ref") or decision.get("decisionRef")
            row.decision_outcome = outcome
            row.work_item_ids = [int(item["id"]) for item in work if item.get("id") is not None]
            row.status = "completed" if work else "previewed" if outcome == "previewed" else "no_action"
            row.processed_at = utc_now()
            row.updated_at = utc_now()
            session.add(row)
            session.commit()
            session.refresh(row)
            return row
    except Exception as error:
        return _mark_trigger_failure(trigger_ref, error)


def dispatch_source(
    source_type: str,
    source_ref: str,
    *,
    initiated_by: AuthContext | None = None,
) -> AutomationTriggerV22:
    row, created = enqueue_source(source_type, source_ref, initiated_by=initiated_by)
    if row.status == "queued" and (created or row.attempts == 0):
        return process_trigger(row.trigger_ref)
    return row


def scan_and_dispatch(
    *,
    premises_ref: str,
    operational_date: date | None = None,
    episode_ref: str | None = None,
    source_types: set[str] | None = None,
    initiated_by: AuthContext | None = None,
) -> list[AutomationTriggerV22]:
    wanted = source_types or SUPPORTED_SOURCE_TYPES
    with Session(engine) as session:
        episode_query = select(CanonicalEpisodeState).where(CanonicalEpisodeState.premises_ref == premises_ref)
        if episode_ref:
            episode_query = episode_query.where(CanonicalEpisodeState.episode_ref == episode_ref)
        episodes = session.exec(episode_query.limit(1000)).all()
        episode_refs = [row.episode_ref for row in episodes]
        refs: list[tuple[str, str]] = []
        if "evidence_gap" in wanted:
            refs.extend(("evidence_gap", value) for value in episode_refs)
        if episode_refs and "observation" in wanted:
            observations = session.exec(
                select(ClinicalObservation).where(ClinicalObservation.episode_ref.in_(episode_refs)).limit(2000)
            ).all()
            refs.extend(("observation", row.observation_ref) for row in observations)
        if episode_refs and "critical_result" in wanted:
            results = session.exec(
                select(CriticalResultAcknowledgement)
                .where(CriticalResultAcknowledgement.referral_episode_id.in_(episode_refs))
                .limit(2000)
            ).all()
            refs.extend(("critical_result", row.result_ref) for row in results)
        if "operational_delay" in wanted:
            block_query = select(OperationalBlock).where(OperationalBlock.premises_ref == premises_ref)
            if operational_date:
                block_query = block_query.where(OperationalBlock.operational_date == operational_date)
            if episode_ref:
                block_query = block_query.where(OperationalBlock.episode_ref == episode_ref)
            blocks = session.exec(block_query.limit(2000)).all()
            refs.extend(("operational_delay", row.block_ref) for row in blocks)

    output: list[AutomationTriggerV22] = []
    for source_type, source_ref in refs:
        try:
            output.append(dispatch_source(source_type, source_ref, initiated_by=initiated_by))
        except Exception as error:
            # A source may have been removed or become invalid between scan and dispatch.
            # The scan continues; source writes are never rolled back by reconciliation.
            continue
    return output


def dry_run_episode(episode_ref: str) -> dict[str, Any]:
    with Session(engine) as session:
        episode = require_episode(session, episode_ref)
        results: list[dict[str, Any]] = []

        observations = session.exec(
            select(ClinicalObservation).where(ClinicalObservation.episode_ref == episode_ref)
        ).all()
        for row in observations:
            snapshot = observation_snapshot(row)
            facts = {
                "concernLevel": row.concern_level,
                "detail": f"{row.observation_type}: {json.dumps(row.values, sort_keys=True, default=str)}",
            }
            results.append({
                "sourceType": "observation",
                "sourceRef": row.observation_ref,
                "sourceVersion": row.version,
                "sourceStateHash": state_hash(snapshot),
                "proposals": evaluate_trigger(episode, "observation", row.observation_ref, facts),
            })

        critical_rows = session.exec(
            select(CriticalResultAcknowledgement).where(
                CriticalResultAcknowledgement.referral_episode_id == episode_ref
            )
        ).all()
        for row in critical_rows:
            snapshot = critical_result_snapshot(row)
            due_at = row.due_at
            acknowledged = row.status == "acknowledged" or row.acknowledged_at is not None
            overdue = bool(not acknowledged and due_at and normalise_utc(due_at) < utc_now())
            facts = {
                "critical": row.severity.strip().lower() in {"red", "critical"},
                "acknowledged": acknowledged,
                "overdue": overdue,
                "summary": f"{row.result_type}: {row.summary}",
            }
            results.append({
                "sourceType": "critical_result",
                "sourceRef": row.result_ref,
                "sourceVersion": None,
                "sourceStateHash": state_hash(snapshot),
                "proposals": evaluate_trigger(episode, "critical_result", row.result_ref, facts),
            })

        gates = parse_gates(episode.gates_json)
        gate_snapshot = episode_gate_snapshot(episode)
        results.append({
            "sourceType": "evidence_gap",
            "sourceRef": episode.episode_ref,
            "sourceVersion": episode.version,
            "sourceStateHash": state_hash(gate_snapshot),
            "proposals": evaluate_trigger(
                episode,
                "evidence_gap",
                f"episode-gates:{episode.episode_ref}:v{episode.version}",
                {"gaps": derive_evidence_gaps(episode, gates), "detail": f"Canonical episode gates at {episode.phase}"},
            ),
        })

        blocks = session.exec(select(OperationalBlock).where(OperationalBlock.episode_ref == episode_ref)).all()
        for row in blocks:
            delay = derive_delay(row)
            snapshot = {**block_snapshot(row), "derivedDelayBand": delay["delayBand"]}
            results.append({
                "sourceType": "operational_delay",
                "sourceRef": row.block_ref,
                "sourceVersion": row.version,
                "sourceStateHash": state_hash(snapshot),
                "recordedDelay": delay,
                "proposals": evaluate_trigger(
                    episode,
                    "operational_delay",
                    f"block-delay:{row.block_ref}:{delay['delayBand']}:v{row.version}",
                    {
                        "delayMinutes": delay["delayBandMinutes"],
                        "detail": f"Recorded block {row.block_ref} is in the {delay['delayBand']} delay band.",
                    },
                ),
            })

        return {
            "episodeRef": episode.episode_ref,
            "patientRef": episode.patient_ref,
            "premisesRef": episode.premises_ref,
            "sources": results,
            "proposalCount": sum(len(item["proposals"]) for item in results),
            "workCreated": False,
        }


def trigger_dict(row: AutomationTriggerV22) -> dict[str, Any]:
    return _trigger_dict(row)
