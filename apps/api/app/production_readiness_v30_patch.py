from __future__ import annotations

import json
import os
from datetime import timedelta
from typing import Any

from sqlalchemy import inspect
from sqlmodel import Session, select

from app.auth import AuthContext
from app.evidence_service import create_evidence_event
from app.operational_proof_v30_models import OperationalProofRunV30
from app.production_readiness_models import ReadinessControl, SecurityAssessmentRun
from app.production_readiness_service import utc_now
import app.production_readiness_routes as readiness_routes
import app.production_readiness_service as readiness_service
from app import connected_surfaces_v30_patch as _connected_surfaces_v30_patch  # noqa: F401
from app.operational_proof_v30_routes import router as operational_proof_v30_router

_original_security_self_test = readiness_service.security_self_test
V30_TABLES = {
    "operationalproofrunv30",
    "operationalproofstepv30",
    "operationalproofscenariov30",
    "mobileacceptancev30",
}


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def security_self_test_v30(session: Session, auth: AuthContext) -> SecurityAssessmentRun:
    run = _original_security_self_test(session, auth)
    checks: list[dict[str, Any]] = json.loads(run.checks_json or "[]")
    required = _env_bool("V30_OPERATIONAL_PROOF_REQUIRED", False)
    checks.append({
        "key": "v30.operational_proof_required",
        "title": "Connected operational proof required",
        "passed": required,
        "detail": "V30_OPERATIONAL_PROOF_REQUIRED must be true before production readiness can rely on connected hospital journey evidence.",
        "severity": "pass" if required else "failure",
    })
    table_names = set(inspect(session.get_bind()).get_table_names())
    missing = sorted(V30_TABLES - table_names)
    checks.append({
        "key": "v30.tables",
        "title": "Operational proof evidence tables",
        "passed": not missing,
        "detail": f"Missing tables: {missing}" if missing else "All v30 connected-journey, stress and mobile evidence tables are present.",
        "severity": "pass" if not missing else "failure",
    })
    latest = session.exec(
        select(OperationalProofRunV30).order_by(OperationalProofRunV30.started_at.desc())
    ).first() if not missing else None
    acceptable = bool(latest and latest.status in {"passed", "passed_with_manual_boundary"})
    checks.append({
        "key": "v30.latest_operational_proof",
        "title": "Latest connected hospital proof",
        "passed": acceptable,
        "detail": f"Latest proof {latest.run_ref} is {latest.status}." if latest else "No connected operational proof run exists.",
        "severity": "pass" if acceptable else "failure",
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
            f"v30 proof required {required}; missing v30 tables {missing}; "
            f"latest proof {latest.run_ref if latest else 'none'} status {latest.status if latest else 'missing'}"
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
            action="v30 connected operational proof assessment completed",
            actor_id=auth.actor_id or auth.subject,
            actor_name=auth.actor_name,
            actor_role=auth.role,
            actor_auth_source=auth.auth_source,
            new_state={
                "runRef": run.run_ref,
                "status": run.status,
                "score": run.score,
                "v30OperationalProofRequired": required,
                "missingV30Tables": missing,
                "latestProofRef": latest.run_ref if latest else None,
                "latestProofStatus": latest.status if latest else None,
            },
            reason=f"{failed} failed checks and {warnings} warnings after v30 connected operational proof controls",
            compliance_domain="clinical_governance",
            risk_level="green" if run.status == "passed" else "red",
            source_module="operational-proof-demo-hospital-v30",
            source_record_ref=control.control_ref,
            entity_type="readiness_control",
            entity_id=control.control_ref,
            idempotency_key=f"production-readiness-v30:{run.run_ref}",
        )
        control.evidence_ref = evidence.event_ref
        session.add(control)
    return run


readiness_service.security_self_test = security_self_test_v30
readiness_routes.security_self_test = security_self_test_v30

from app import main as main_module  # noqa: E402

if not getattr(main_module.app.state, "operational_proof_v30_installed", False):
    main_module.app.include_router(operational_proof_v30_router)
    main_module.app.state.operational_proof_v30_installed = True
