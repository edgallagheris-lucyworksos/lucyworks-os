from __future__ import annotations

import json
import os
from datetime import timedelta
from typing import Any

from sqlalchemy import inspect
from sqlmodel import Session, select

from app.auth import AuthContext
from app.evidence_service import create_evidence_event
from app.hospital_pilot_v29_models import (
    HospitalPilotV29,
    IntegrationSimulatorV29,
    ReadinessAssessmentV29,
    SpeechAdapterV29,
    VeterinaryTerminologyPackV29,
)
from app.production_readiness_models import ReadinessControl, SecurityAssessmentRun
from app.production_readiness_service import utc_now
import app.production_readiness_routes as readiness_routes
import app.production_readiness_service as readiness_service
from app.hospital_pilot_v29_routes import router as hospital_pilot_v29_router

_original_security_self_test = readiness_service.security_self_test

V29_TABLES = {
    "speechadapterv29",
    "veterinaryterminologypackv29",
    "integrationsimulatorv29",
    "simulatorscenariov29",
    "simulatorrunv29",
    "readinessassessmentv29",
    "hospitalpilotv29",
    "pilotapprovalv29",
    "pilotincidentv29",
    "pilotmeasurementv29",
    "exportartifactv29",
}


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def security_self_test_v29(session: Session, auth: AuthContext) -> SecurityAssessmentRun:
    run = _original_security_self_test(session, auth)
    checks: list[dict[str, Any]] = json.loads(run.checks_json or "[]")
    required = _env_bool("V29_PILOT_CONTROL_REQUIRED", False)
    checks.append({
        "key": "v29.pilot_control_required",
        "title": "Hospital pilot control required",
        "passed": required,
        "detail": "V29_PILOT_CONTROL_REQUIRED must be true in production so pilot and simulator activity cannot bypass governed limits.",
        "severity": "pass" if required else "failure",
    })

    table_names = set(inspect(session.get_bind()).get_table_names())
    missing = sorted(V29_TABLES - table_names)
    checks.append({
        "key": "v29.tables",
        "title": "Pilot, simulator and readiness evidence tables",
        "passed": not missing,
        "detail": f"Missing tables: {missing}" if missing else "All v29 speech adapter, terminology, simulator, readiness, pilot, incident, measurement and export tables are present.",
        "severity": "pass" if not missing else "failure",
    })

    active_pilots = session.exec(select(HospitalPilotV29).where(HospitalPilotV29.status == "active")).all() if not missing else []
    unsafe_modes = [row.pilot_ref for row in active_pilots if row.mode not in {"synthetic", "shadow"}]
    missing_approvals = [row.pilot_ref for row in active_pilots if not row.operations_approved_by_subject or not row.clinical_approved_by_subject or row.operations_approved_by_subject == row.clinical_approved_by_subject]
    missing_readiness = []
    for pilot in active_pilots:
        assessment = session.exec(select(ReadinessAssessmentV29).where(ReadinessAssessmentV29.assessment_ref == pilot.readiness_assessment_ref)).first()
        if not assessment or assessment.overall_status not in {"READY", "READY_WITH_RESTRICTIONS"}:
            missing_readiness.append(pilot.pilot_ref)
    checks.extend([
        {
            "key": "v29.pilot_modes",
            "title": "Only synthetic or shadow pilot modes",
            "passed": not unsafe_modes,
            "detail": f"Unsupported active pilot modes: {unsafe_modes}" if unsafe_modes else "All active pilots are synthetic or shadow only.",
            "severity": "pass" if not unsafe_modes else "failure",
        },
        {
            "key": "v29.pilot_approvals",
            "title": "Independent operations and clinical approvals",
            "passed": not missing_approvals,
            "detail": f"Active pilots without independent approvals: {missing_approvals}" if missing_approvals else "All active pilots have independent operations and clinical approvals.",
            "severity": "pass" if not missing_approvals else "failure",
        },
        {
            "key": "v29.pilot_readiness",
            "title": "Active pilots have acceptable readiness evidence",
            "passed": not missing_readiness,
            "detail": f"Active pilots without READY evidence: {missing_readiness}" if missing_readiness else "All active pilots reference READY or READY_WITH_RESTRICTIONS assessments.",
            "severity": "pass" if not missing_readiness else "failure",
        },
    ])

    active_site_refs = sorted({row.site_ref for row in active_pilots})
    untested_adapters = []
    unapproved_terms = []
    untested_simulators = []
    for site_ref in active_site_refs:
        if not session.exec(select(SpeechAdapterV29).where(SpeechAdapterV29.site_ref == site_ref, SpeechAdapterV29.last_test_status == "passed")).first():
            untested_adapters.append(site_ref)
        if not session.exec(select(VeterinaryTerminologyPackV29).where(VeterinaryTerminologyPackV29.site_ref == site_ref, VeterinaryTerminologyPackV29.status == "approved")).first():
            unapproved_terms.append(site_ref)
        if not session.exec(select(IntegrationSimulatorV29).where(IntegrationSimulatorV29.site_ref == site_ref, IntegrationSimulatorV29.last_test_status == "passed")).first():
            untested_simulators.append(site_ref)
    checks.extend([
        {
            "key": "v29.speech_adapters",
            "title": "Active pilot sites have tested speech adapters",
            "passed": not untested_adapters,
            "detail": f"Sites without tested adapters: {untested_adapters}" if untested_adapters else "Every active pilot site has a tested speech adapter.",
            "severity": "pass" if not untested_adapters else "failure",
        },
        {
            "key": "v29.terminology",
            "title": "Active pilot sites have approved terminology",
            "passed": not unapproved_terms,
            "detail": f"Sites without approved terminology: {unapproved_terms}" if unapproved_terms else "Every active pilot site has an approved veterinary terminology release.",
            "severity": "pass" if not unapproved_terms else "failure",
        },
        {
            "key": "v29.simulators",
            "title": "Active pilot sites have tested integration simulators",
            "passed": not untested_simulators,
            "detail": f"Sites without tested simulators: {untested_simulators}" if untested_simulators else "Every active pilot site has a tested no-write simulator.",
            "severity": "pass" if not untested_simulators else "failure",
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
            f"v29 pilot control {required}; missing v29 tables {missing}; active pilots {len(active_pilots)}"
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
            action="v29 hospital pilot production assessment completed",
            actor_id=auth.actor_id or auth.subject,
            actor_name=auth.actor_name,
            actor_role=auth.role,
            actor_auth_source=auth.auth_source,
            new_state={
                "runRef": run.run_ref,
                "status": run.status,
                "score": run.score,
                "v29PilotControlRequired": required,
                "missingV29Tables": missing,
                "activePilots": [row.pilot_ref for row in active_pilots],
                "unsafePilotModes": unsafe_modes,
                "missingApprovals": missing_approvals,
                "missingReadiness": missing_readiness,
            },
            reason=f"{failed} failed checks and {warnings} warnings after v29 hospital pilot controls",
            compliance_domain="clinical_governance",
            risk_level="green" if run.status == "passed" else "red",
            source_module="hospital-pilot-integration-simulator-v29",
            source_record_ref=control.control_ref,
            entity_type="readiness_control",
            entity_id=control.control_ref,
            idempotency_key=f"production-readiness-v29:{run.run_ref}",
        )
        control.evidence_ref = evidence.event_ref
        session.add(control)
    return run


readiness_service.security_self_test = security_self_test_v29
readiness_routes.security_self_test = security_self_test_v29

# main.py has already imported the FastAPI app from main_fixed before importing
# readiness patches. Install the v29 router once without changing legacy route order.
from app import main as main_module  # noqa: E402

if not getattr(main_module.app.state, "hospital_pilot_v29_installed", False):
    main_module.app.include_router(hospital_pilot_v29_router)
    main_module.app.state.hospital_pilot_v29_installed = True
