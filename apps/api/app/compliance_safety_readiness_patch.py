from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlmodel import Session, select

from app import production_readiness_service as service
from app.auth import AuthContext
from app.production_readiness_models import ReadinessControl, SecurityAssessmentRun

_original_security_self_test = service.security_self_test


def _expected_head() -> str:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    return str(ScriptDirectory.from_config(config).get_current_head())


def security_self_test(session: Session, auth: AuthContext) -> SecurityAssessmentRun:
    run = _original_security_self_test(session, auth)
    checks = service.parse_json(run.checks_json, [])
    table_names = set(inspect(session.get_bind()).get_table_names())
    current = None
    if "alembic_version" in table_names:
        current = session.exec(text("select version_num from alembic_version")).first()
        if isinstance(current, tuple):
            current = current[0]
    expected = _expected_head()

    migration_check = next((item for item in checks if item.get("key") == "database.migration"), None)
    if migration_check is None:
        migration_check = {"key": "database.migration", "title": "Migration head"}
        checks.append(migration_check)
    migration_check.update({
        "passed": str(current or "") == expected,
        "detail": f"Current migration: {current or 'unknown'}; repository head: {expected}",
        "severity": "pass" if str(current or "") == expected else "failure",
    })

    required_v10 = {"safetycasev10", "safetyhazardv10", "safetyreviewv10", "deploymentprofilev10"}
    missing_v10 = sorted(required_v10 - table_names)
    table_check = next((item for item in checks if item.get("key") == "compliance_safety.tables"), None)
    if table_check is None:
        table_check = {"key": "compliance_safety.tables", "title": "Compliance and safety assurance tables"}
        checks.append(table_check)
    table_check.update({
        "passed": not missing_v10,
        "detail": f"Missing tables: {missing_v10}" if missing_v10 else "Compliance and safety assurance tables present",
        "severity": "pass" if not missing_v10 else "failure",
    })

    failed = len([item for item in checks if not item.get("passed") and item.get("severity") == "failure"])
    warnings = len([item for item in checks if not item.get("passed") and item.get("severity") == "warning"])
    passed = len([item for item in checks if item.get("passed")])
    run.status = "passed" if failed == 0 else "failed"
    run.score = round((passed / max(1, len(checks))) * 100)
    run.passed_count = passed
    run.failed_count = failed
    run.warning_count = warnings
    run.checks_json = service.json_text(checks)
    session.add(run)

    control = session.exec(select(ReadinessControl).where(ReadinessControl.control_ref == "security.self_test")).first()
    if control:
        before = service.control_dict(control)
        control.status = "passed" if run.status == "passed" else "failed"
        control.evidence_summary = f"Automated assessment {run.run_ref}: score {run.score}, failures {failed}, warnings {warnings}, migration {current or 'unknown'}"
        control.verified_by_subject = auth.subject
        control.verified_by_name = auth.actor_name
        control.verified_at = service.utc_now()
        control.expires_at = service.utc_now() + service.timedelta(days=30)
        control.version += 1
        control.updated_at = service.utc_now()
        control.evidence_ref = service._evidence_event(
            session,
            auth,
            action="production security assessment reconciled to current migration head",
            control=control,
            before=before,
            after={"runRef": run.run_ref, "status": run.status, "score": run.score, "checks": checks},
            risk="green" if run.status == "passed" else "red",
            reason=f"{failed} failed checks and {warnings} warnings at {current or 'unknown'}",
        )
        session.add(control)
    return run


service.security_self_test = security_self_test
