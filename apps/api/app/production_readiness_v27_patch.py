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
import app.production_readiness_routes as readiness_routes
import app.production_readiness_service as readiness_service

_original_security_self_test = readiness_service.security_self_test

V27_TABLES = {
    "onboardingorganisationv27",
    "onboardingsitev27",
    "onboardingdepartmentv27",
    "onboardingservicev27",
    "onboardingroomv27",
    "onboardingequipmentv27",
    "staffimportbatchv27",
    "onboardingstaffv27",
    "staffcredentialv27",
    "staffcompetencyv27",
    "staffaccessapprovalv27",
    "sitepolicyv27",
    "configurationreleasev27",
    "configurationchangev27",
}


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def security_self_test_v27(session: Session, auth: AuthContext) -> SecurityAssessmentRun:
    run = _original_security_self_test(session, auth)
    checks: list[dict[str, Any]] = json.loads(run.checks_json or "[]")
    production_named = bool(os.getenv("DEPLOYMENT_ENVIRONMENT", "").strip())
    context_required = _env_bool("V27_CONFIGURATION_REQUIRED", False)
    checks.append({
        "key": "onboarding.configuration_required",
        "title": "Governed hospital configuration required",
        "passed": context_required,
        "detail": "V27_CONFIGURATION_REQUIRED must be true so token claims cannot create hospital access.",
        "severity": "pass" if context_required else "failure",
    })
    table_names = set(inspect(session.get_bind()).get_table_names())
    missing = sorted(V27_TABLES - table_names)
    checks.append({
        "key": "onboarding.tables",
        "title": "Organisation onboarding evidence tables",
        "passed": not missing,
        "detail": f"Missing tables: {missing}" if missing else "All v27 onboarding and release tables are present.",
        "severity": "pass" if not missing else "failure",
    })
    checks.append({
        "key": "onboarding.bootstrap_disabled",
        "title": "Synthetic context bootstrap disabled",
        "passed": not _env_bool("V26_CONTEXT_BOOTSTRAP_ENABLED", False),
        "detail": "V26_CONTEXT_BOOTSTRAP_ENABLED must be false in production.",
        "severity": "pass" if not _env_bool("V26_CONTEXT_BOOTSTRAP_ENABLED", False) else "failure",
    })
    if not production_named:
        checks.append({
            "key": "onboarding.environment_warning",
            "title": "Deployment environment identified",
            "passed": False,
            "detail": "DEPLOYMENT_ENVIRONMENT is not configured.",
            "severity": "warning",
        })

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
            f"v27 context required {context_required}; missing v27 tables {missing}"
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
            action="v27 organisation onboarding production assessment completed",
            actor_id=auth.actor_id or auth.subject,
            actor_name=auth.actor_name,
            actor_role=auth.role,
            actor_auth_source=auth.auth_source,
            new_state={
                "runRef": run.run_ref,
                "status": run.status,
                "score": run.score,
                "v27ConfigurationRequired": context_required,
                "missingV27Tables": missing,
            },
            reason=f"{failed} failed checks and {warnings} warnings after v27 onboarding controls",
            compliance_domain="information_governance",
            risk_level="green" if run.status == "passed" else "red",
            source_module="organisation-onboarding-v27",
            source_record_ref=control.control_ref,
            entity_type="readiness_control",
            entity_id=control.control_ref,
            idempotency_key=f"production-readiness-v27:{run.run_ref}",
        )
        control.evidence_ref = evidence.event_ref
        session.add(control)
    return run


readiness_service.security_self_test = security_self_test_v27
readiness_routes.security_self_test = security_self_test_v27
