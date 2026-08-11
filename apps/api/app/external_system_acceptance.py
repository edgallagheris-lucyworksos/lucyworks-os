from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

SUPPORTED_CONNECTOR_TYPES = {"patient_management", "laboratory", "imaging"}


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _present(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _valid_time(value: Any) -> bool:
    if isinstance(value, datetime):
        return True
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _required_fields(connector_type: str, event_type: str) -> tuple[str, ...]:
    if connector_type == "patient_management":
        return ("externalPatientRef", "eventOccurredAt")
    if connector_type == "laboratory":
        return ("externalPatientRef", "resultRef", "resultStatus", "eventOccurredAt")
    if connector_type == "imaging":
        return ("externalPatientRef", "studyRef", "modality", "eventOccurredAt")
    return ()


def evaluate_external_fixture(
    *,
    connector_type: str,
    events: list[dict[str, Any]],
    known_patient_refs: set[str] | None = None,
    known_episode_refs: set[str] | None = None,
) -> dict[str, Any]:
    """Evaluate captured/synthetic vendor events before a live connector is promoted.

    This is deliberately vendor-neutral. A vendor adapter maps source payloads into this
    normalized fixture contract; this function then enforces the invariants LucyWorks
    needs for safe shadow/read-only ingestion.
    """
    if connector_type not in SUPPORTED_CONNECTOR_TYPES:
        raise ValueError(f"unsupported connector type: {connector_type}")

    known_patient_refs = known_patient_refs or set()
    known_episode_refs = known_episode_refs or set()
    blockers: list[str] = []
    warnings: list[str] = []
    findings: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    duplicate_count = 0
    conflicting_duplicate_count = 0
    reconciliation_count = 0

    if not events:
        blockers.append("At least one representative vendor event is required.")

    for index, event in enumerate(events, 1):
        external_event_id = str(event.get("externalEventId") or "").strip()
        event_type = str(event.get("eventType") or "").strip()
        payload = event.get("payload") or {}
        event_findings: list[str] = []

        if not external_event_id:
            event_findings.append("externalEventId is required")
        if not event_type:
            event_findings.append("eventType is required")
        if not isinstance(payload, dict):
            event_findings.append("payload must be an object")
            payload = {}

        for field in _required_fields(connector_type, event_type):
            if not _present(payload.get(field)):
                event_findings.append(f"missing required field {field}")

        if _present(payload.get("eventOccurredAt")) and not _valid_time(payload.get("eventOccurredAt")):
            event_findings.append("eventOccurredAt must be an ISO-8601 timestamp")

        patient_ref = payload.get("lucyPatientRef")
        episode_ref = payload.get("lucyEpisodeRef")
        if patient_ref and known_patient_refs and patient_ref not in known_patient_refs:
            event_findings.append("lucyPatientRef does not resolve to a known patient")
            reconciliation_count += 1
        if episode_ref and known_episode_refs and episode_ref not in known_episode_refs:
            event_findings.append("lucyEpisodeRef does not resolve to a known episode")
            reconciliation_count += 1
        if not patient_ref:
            warnings.append(f"event {external_event_id or index} requires patient reconciliation before episode application")
            reconciliation_count += 1

        payload_hash = _digest(payload)
        if external_event_id:
            previous = seen.get(external_event_id)
            if previous is not None:
                if previous == payload_hash:
                    duplicate_count += 1
                else:
                    conflicting_duplicate_count += 1
                    event_findings.append("same externalEventId arrived with different payload")
            else:
                seen[external_event_id] = payload_hash

        if event_findings:
            blockers.extend(f"Event {external_event_id or index}: {item}" for item in event_findings)
        findings.append({
            "index": index,
            "externalEventId": external_event_id or None,
            "eventType": event_type or None,
            "payloadHash": payload_hash,
            "passed": not event_findings,
            "findings": event_findings,
        })

    if conflicting_duplicate_count:
        blockers.append(f"{conflicting_duplicate_count} conflicting duplicate event(s) violate idempotency.")

    status = "PASS" if not blockers else "FAIL"
    return {
        "status": status,
        "connectorType": connector_type,
        "eventCount": len(events),
        "uniqueExternalEventCount": len(seen),
        "idempotentDuplicateCount": duplicate_count,
        "conflictingDuplicateCount": conflicting_duplicate_count,
        "reconciliationRequiredCount": reconciliation_count,
        "blockers": blockers,
        "warnings": sorted(set(warnings)),
        "findings": findings,
        "promotionBoundary": "PASS proves fixture-contract conformance only. Live promotion still requires the canonical bounded-pilot release gate and shadow/read-only connector approval.",
    }
