from __future__ import annotations

import json
import os
from datetime import timedelta
from typing import Any

from sqlalchemy import inspect
from sqlmodel import Session, select

from app.auth import AuthContext
from app.evidence_service import create_evidence_event
from app.production_readiness_models import ReadinessControl, SecurityAssessmentRun
from app.production_readiness_service import utc_now
from app.real_hospital_connection_v28_models import IntegrationConnectorV28, SpeechProviderV28
import app.production_readiness_routes as readiness_routes
import app.production_readiness_service as readiness_service
from app import production_readiness_v27_patch as _production_readiness_v27_patch  # noqa: F401

_original_security_self_test = readiness_service.security_self_test

V28_TABLES = {
    "speechproviderv28",
    "speechsessionv28",
    "speechsegmentv28",
    "integrationconnectorv28",
    "integrationpromotionv28",
    "integrationeventv28",
    "reconciliationitemv28",
}


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def security_self_test_v28(session: Session, auth: AuthContext) -> SecurityAssessmentRun:
    run = _original_security_self_test(session, auth)
    checks: list[dict[str, Any]] = json.loads(run.checks_json or "[]")
    connection_control_required = _env_bool("V28_CONNECTION_CONTROL_REQUIRED", False)
    checks.append({
        "key": "v28.connection_control_required",
        "title": "Real-hospital connection control required",
        "passed": connection_control_required,
        "detail": "V28_CONNECTION_CONTROL_REQUIRED must be true in production so vendor links cannot bypass governed promotion.",
        "severity": "pass" if connection_control_required else "failure",
    })

    table_names = set(inspect(session.get_bind()).get_table_names())
    missing = sorted(V28_TABLES - table_names)
    checks.append({
        "key": "v28.tables",
        "title": "Speech and integration evidence tables",
        "passed": not missing,
        "detail": f"Missing tables: {missing}" if missing else "All v28 speech, connector, promotion, event and reconciliation tables are present.",
        "severity": "pass" if not missing else "failure",
    })

    active_connectors = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.status == "active")).all() if not missing else []
    unsafe_modes = [row.connector_ref for row in active_connectors if row.mode not in {"shadow", "read_only"}]
    untested = [row.connector_ref for row in active_connectors if row.last_test_status != "passed"]
    missing_connector_secrets = [
        row.connector_ref for row in active_connectors
        if row.secret_env and not os.getenv(row.secret_env, "")
    ]
    checks.extend([
        {
            "key": "v28.connector_modes",
            "title": "No external write-back connector mode",
            "passed": not unsafe_modes,
            "detail": f"Unsupported active modes: {unsafe_modes}" if unsafe_modes else "All active v28 connectors are shadow or read-only.",
            "severity": "pass" if not unsafe_modes else "failure",
        },
        {
            "key": "v28.connector_tests",
            "title": "Active connectors passed configuration testing",
            "passed": not untested,
            "detail": f"Active connectors without passed tests: {untested}" if untested else "All active connectors have a passed configuration test.",
            "severity": "pass" if not untested else "failure",
        },
        {
            "key": "v28.connector_secrets",
            "title": "Active connector secrets loaded",
            "passed": not missing_connector_secrets,
            "detail": f"Missing secrets for: {missing_connector_secrets}" if missing_connector_secrets else "Configured active connector secrets are loaded.",
            "severity": "pass" if not missing_connector_secrets else "failure",
        },
    ])

    approved_providers = session.exec(select(SpeechProviderV28).where(SpeechProviderV28.status == "approved")).all() if not missing else []
    unsafe_audio = [row.provider_ref for row in approved_providers if row.raw_audio_retention]
    untested_providers = [row.provider_ref for row in approved_providers if row.last_test_status != "passed"]
    missing_provider_secrets = [
        row.provider_ref for row in approved_providers
        if row.provider_type != "browser" and row.secret_env and not os.getenv(row.secret_env, "")
    ]
    checks.extend([
        {
            "key": "v28.speech_audio_retention",
            "title": "Speech raw-audio retention disabled",
            "passed": not unsafe_audio,
            "detail": f"Approved providers retaining raw audio: {unsafe_audio}" if unsafe_audio else "Approved speech providers do not retain raw audio in LucyWorks.",
            "severity": "pass" if not unsafe_audio else "failure",
        },
        {
            "key": "v28.speech_provider_tests",
            "title": "Approved speech providers passed testing",
            "passed": not untested_providers,
            "detail": f"Approved providers without passed tests: {untested_providers}" if untested_providers else "All approved speech providers have a passed configuration test.",
            "severity": "pass" if not untested_providers else "failure",
        },
        {
            "key": "v28.speech_provider_secrets",
            "title": "External speech provider secrets loaded",
            "passed": not missing_provider_secrets,
            "detail": f"Missing secrets for: {missing_provider_secrets}" if missing_provider_secrets else "Configured external speech provider secrets are loaded.",
            "severity": "pass" if not missing_provider_secrets else "failure",
        },
    ])

    failed = len([item for item in checks if not item["passed"] and item["severity"] == "failure"])
    warnings = len([item for item in checks if not item["passed"] and item["severity"] == "warning"])
    passed = len([item for item in checks if item["passed"]])
    total = max(1, len(checks))
    run.status = "passed" if failed == 0 else "failed"
    run.score = round((passed / total) * 100)
    run.passed_count = passed
    run.failed_count = failed
    run.warning_count = warnings
    run.checks_json = json.dumps(checks, sort_keys=True, default=str, separators=(",", ":"))
    session.add(run)
    session.flush()

    control = session.exec(select(ReadinessControl).where(ReadinessControl.control_ref == "security.self_test")).first()
    if control:
        control.status = "passed" if run.status == "passed" else "failed"
        control.evidence_summary = (
            f"Automated assessment {run.run_ref}: score {run.score}, failures {failed}, warnings {warnings}; "
            f"v28 connection control {connection_control_required}; missing v28 tables {missing}; "
            f"unsafe connector modes {unsafe_modes}"
        )
        control.verified_by_subject = auth.subject
        control.verified_by_name = auth.actor_name
        control.verified_at = utc_now()
        control.expires_at = utc_now() + timedelta(days=30)
        control.version += 1
        control.updated_at = utc_now()
        evidence, _ = create_evidence_event(
            session,
            event_type="production_readiness_control",
            action="v28 real-hospital connection production assessment completed",
            actor_id=auth.actor_id or auth.subject,
            actor_name=auth.actor_name,
            actor_role=auth.role,
            actor_auth_source=auth.auth_source,
            new_state={
                "runRef": run.run_ref,
                "status": run.status,
                "score": run.score,
                "v28ConnectionControlRequired": connection_control_required,
                "missingV28Tables": missing,
                "unsafeConnectorModes": unsafe_modes,
                "untestedConnectors": untested,
                "unsafeAudioProviders": unsafe_audio,
            },
            reason=f"{failed} failed checks and {warnings} warnings after v28 connection controls",
            compliance_domain="information_governance",
            risk_level="green" if run.status == "passed" else "red",
            source_module="real-hospital-connection-v28",
            source_record_ref=control.control_ref,
            entity_type="readiness_control",
            entity_id=control.control_ref,
            idempotency_key=f"production-readiness-v28:{run.run_ref}",
        )
        control.evidence_ref = evidence.event_ref
        session.add(control)
    return run


readiness_service.security_self_test = security_self_test_v28
readiness_routes.security_self_test = security_self_test_v28

from app import production_readiness_v29_patch as _production_readiness_v29_patch  # noqa: E402,F401
