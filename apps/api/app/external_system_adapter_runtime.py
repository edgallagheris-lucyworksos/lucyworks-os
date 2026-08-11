from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlmodel import Session, select

from app.external_system_acceptance import evaluate_external_fixture
from app.hospital_ops_models import CanonicalEpisodeState
from app.real_hospital_connection_v28_models import IntegrationConnectorV28, IntegrationEventV28, ReconciliationItemV28


@dataclass(frozen=True)
class AdapterResult:
    status: str
    event_ref: str | None
    episode_ref: str | None
    patient_ref: str | None
    reconciliation_ref: str | None
    duplicate: bool = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _resolve_episode(session: Session, patient_ref: str | None, episode_ref: str | None) -> tuple[CanonicalEpisodeState | None, str | None]:
    if episode_ref:
        episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first()
        if not episode:
            return None, "episode_not_found"
        if patient_ref and episode.patient_ref and episode.patient_ref != patient_ref:
            return None, "patient_episode_mismatch"
        return episode, None
    if not patient_ref:
        return None, "patient_match_required"
    episodes = list(session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.patient_ref == patient_ref, CanonicalEpisodeState.status == "active")).all())
    if len(episodes) == 1:
        return episodes[0], None
    if not episodes:
        return None, "active_episode_not_found"
    return None, "multiple_active_episodes"


def _reconcile(session: Session, connector_ref: str, event_ref: str, external_ref: str, reason: str, candidate_refs: list[str] | None = None, severity: str = "amber") -> ReconciliationItemV28:
    row = ReconciliationItemV28(
        item_ref=_new_ref("reconcile"), connector_ref=connector_ref, event_ref=event_ref,
        entity_type="patient_episode", external_ref=external_ref, candidate_refs=candidate_refs or [],
        status="open", severity=severity, reason=reason, assigned_role="ops_manager",
    )
    session.add(row)
    return row


def ingest_normalized_event(session: Session, connector_ref: str, normalized_event: dict[str, Any]) -> AdapterResult:
    connector = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.connector_ref == connector_ref)).first()
    if not connector:
        raise ValueError("connector not found")
    if connector.status != "active" or connector.mode not in {"shadow", "read_only"}:
        raise RuntimeError("connector is not authorised for inbound shadow/read-only ingestion")

    acceptance = evaluate_external_fixture(connector_type=connector.connector_type, events=[normalized_event])
    if acceptance["status"] != "PASS":
        connector.failure_count += 1
        connector.last_event_at = _now()
        connector.updated_at = _now()
        session.add(connector)
        raise ValueError("; ".join(acceptance["blockers"]))

    external_event_id = str(normalized_event["externalEventId"]).strip()
    event_type = str(normalized_event["eventType"]).strip()
    payload = dict(normalized_event.get("payload") or {})
    payload_hash = _digest(payload)

    previous = session.exec(select(IntegrationEventV28).where(IntegrationEventV28.connector_ref == connector_ref, IntegrationEventV28.external_event_id == external_event_id)).first()
    if previous:
        connector.last_event_at = _now()
        if previous.payload_hash == payload_hash:
            session.add(connector)
            return AdapterResult("duplicate_ignored", previous.event_ref, previous.episode_ref, previous.patient_ref, None, True)
        item = _reconcile(session, connector_ref, previous.event_ref, external_event_id, "same external event id arrived with a different payload", severity="red")
        connector.status = "degraded"
        connector.failure_count += 1
        session.add(connector)
        return AdapterResult("conflicting_duplicate", previous.event_ref, previous.episode_ref, previous.patient_ref, item.item_ref)

    patient_ref = payload.get("lucyPatientRef")
    episode_ref = payload.get("lucyEpisodeRef")
    episode, match_error = _resolve_episode(session, patient_ref, episode_ref)
    occurred_at = payload.get("eventOccurredAt")
    occurred = datetime.fromisoformat(occurred_at.replace("Z", "+00:00")) if isinstance(occurred_at, str) else occurred_at

    event = IntegrationEventV28(
        event_ref=_new_ref("integration-event"), connector_ref=connector_ref, external_event_id=external_event_id,
        event_type=event_type, direction="inbound", status="reconciliation_required" if match_error else "accepted",
        patient_ref=episode.patient_ref if episode else patient_ref, episode_ref=episode.episode_ref if episode else episode_ref,
        payload_hash=payload_hash, payload_summary=payload, occurred_at=occurred,
        processed_at=_now() if not match_error else None, failure_code=match_error,
        failure_detail=match_error.replace("_", " ") if match_error else None,
    )
    session.add(event)
    session.flush()

    reconciliation_ref = None
    if match_error:
        candidates = []
        if patient_ref:
            candidates = [row.episode_ref for row in session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.patient_ref == patient_ref)).all()]
        item = _reconcile(
            session, connector_ref, event.event_ref,
            str(payload.get("externalPatientRef") or patient_ref or external_event_id),
            match_error.replace("_", " "), candidates,
            "red" if match_error == "patient_episode_mismatch" else "amber",
        )
        reconciliation_ref = item.item_ref
    else:
        connector.last_success_at = _now()

    connector.last_event_at = _now()
    connector.updated_at = _now()
    session.add(connector)
    return AdapterResult(event.status, event.event_ref, event.episode_ref, event.patient_ref, reconciliation_ref)
