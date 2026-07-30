from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlmodel import Session, select

from app.auth import AuthContext
from app.evidence_service import create_evidence_event
from app.integration_models import IntegrationConnection
from app.production_readiness_models import ReadinessControl, SecurityAssessmentRun
from app.production_readiness_service import make_ref, utc_now
import app.production_readiness_routes as readiness_routes
import app.production_readiness_service as readiness_service


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _expected_migration_head() -> str:
    configured = os.getenv("EXPECTED_MIGRATION_HEAD", "").strip()
    if configured:
        return configured
    config_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    config = Config(str(config_path))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"LucyWorks requires one Alembic head; found {heads}")
    return str(heads[0])


def security_self_test_v24(session: Session, auth: AuthContext) -> SecurityAssessmentRun:
    database_url = os.getenv("DATABASE_URL", "")
    checks: list[dict[str, Any]] = []

    def check(key: str, title: str, passed: bool, detail: str, severity: str = "failure") -> None:
        checks.append({"key": key, "title": title, "passed": passed, "detail": detail, "severity": "pass" if passed else severity})

    check("auth.mode", "OIDC mode", os.getenv("AUTH_MODE", "local").lower() == "oidc", "AUTH_MODE must be oidc in production")
    check("auth.enforcement", "Authentication enforcement", os.getenv("AUTH_ENFORCEMENT", "audit").lower() == "required", "AUTH_ENFORCEMENT must be required")
    check("auth.dev_login", "Development login disabled", not _env_bool("AUTH_DEV_LOGIN_ENABLED", False), "AUTH_DEV_LOGIN_ENABLED must be false")
    check("auth.role_map", "Role mapping configured", bool(os.getenv("AUTH_ROLE_MAP", "").strip()), "AUTH_ROLE_MAP is empty")
    for name in ("OIDC_ISSUER", "OIDC_JWKS_URL", "OIDC_AUTHORIZATION_URL", "OIDC_TOKEN_URL", "OIDC_CLIENT_ID"):
        check(f"oidc.{name.lower()}", name, bool(os.getenv(name, "").strip()), f"{name} is not configured")
    check("database.postgres", "PostgreSQL database", database_url.startswith("postgresql"), "DATABASE_URL is not PostgreSQL")
    check("database.schema_creation", "Runtime schema creation disabled", not _env_bool("AUTO_CREATE_SCHEMA", True), "AUTO_CREATE_SCHEMA must be false")
    check("test.bypass", "Legacy test bypass disabled", not _env_bool("LUCYWORKS_LEGACY_TEST_BYPASS", False), "LUCYWORKS_LEGACY_TEST_BYPASS must be false")
    check("security.headers", "Security headers enabled", _env_bool("SECURITY_HEADERS_ENABLED", True), "SECURITY_HEADERS_ENABLED is false")
    check("security.rate_limit", "Rate limiting enabled", _env_bool("RATE_LIMIT_ENABLED", False), "RATE_LIMIT_ENABLED is false", "warning")
    check("backup.destination", "Backup destination configured", bool(os.getenv("BACKUP_DIRECTORY", "").strip()), "BACKUP_DIRECTORY is not configured", "warning")
    check("monitoring.environment", "Deployment environment named", bool(os.getenv("DEPLOYMENT_ENVIRONMENT", "").strip()), "DEPLOYMENT_ENVIRONMENT is not configured", "warning")

    inspector = inspect(session.get_bind())
    table_names = set(inspector.get_table_names())
    required_tables = {
        "evidenceevent",
        "operationalblock",
        "canonicalepisodestate",
        "readinesscontrol",
        "pilotrun",
        "pilotauthorityv24",
        "pilotapprovalv24",
        "pilotcontrolactionv24",
        "pilotshadowcomparisonv24",
        "pilotuatscenariov24",
        "alembic_version",
    }
    missing = sorted(required_tables - table_names)
    check("database.tables", "Required tables present", not missing, f"Missing tables: {missing}" if missing else "Required tables present")
    current_migration = None
    if "alembic_version" in table_names:
        current_migration = session.exec(text("select version_num from alembic_version")).first()
        if isinstance(current_migration, tuple):
            current_migration = current_migration[0]
    expected_migration = _expected_migration_head()
    check(
        "database.migration",
        "Migration head",
        str(current_migration or "") == expected_migration,
        f"Current migration: {current_migration or 'unknown'}; expected: {expected_migration}",
    )

    active_connections = session.exec(select(IntegrationConnection).where(IntegrationConnection.status == "active")).all()
    missing_secrets = [row.connection_ref for row in active_connections if not os.getenv(row.secret_env, "")]
    check("integrations.secrets", "Active integration secrets loaded", not missing_secrets, f"Missing secrets for: {missing_secrets}" if missing_secrets else "All active integration secrets loaded", "warning")

    failed = len([item for item in checks if not item["passed"] and item["severity"] == "failure"])
    warnings = len([item for item in checks if not item["passed"] and item["severity"] == "warning"])
    passed = len([item for item in checks if item["passed"]])
    total = max(1, len(checks))
    run = SecurityAssessmentRun(
        run_ref=make_ref("security"),
        environment_name=os.getenv("DEPLOYMENT_ENVIRONMENT", "unknown"),
        status="passed" if failed == 0 else "failed",
        score=round((passed / total) * 100),
        passed_count=passed,
        failed_count=failed,
        warning_count=warnings,
        checks_json=json.dumps(checks, sort_keys=True, default=str, separators=(",", ":")),
        created_by_subject=auth.subject,
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()

    control = session.exec(select(ReadinessControl).where(ReadinessControl.control_ref == "security.self_test")).first()
    if control:
        control.status = "passed" if run.status == "passed" else "failed"
        control.evidence_summary = f"Automated assessment {run.run_ref}: score {run.score}, failures {failed}, warnings {warnings}; migration {current_migration or 'unknown'}"
        control.verified_by_subject = auth.subject
        control.verified_by_name = auth.actor_name
        control.verified_at = utc_now()
        control.expires_at = utc_now() + timedelta(days=30)
        control.version += 1
        control.updated_at = utc_now()
        evidence, _ = create_evidence_event(
            session,
            event_type="production_readiness_control",
            action="automated production security assessment completed",
            actor_id=auth.actor_id,
            actor_name=auth.actor_name,
            actor_role=auth.role,
            actor_auth_source=auth.auth_source,
            previous_state=None,
            new_state={"runRef": run.run_ref, "status": run.status, "score": run.score, "checks": checks},
            reason=f"{failed} failed checks and {warnings} warnings",
            justification="Hospital production-readiness governance",
            evidence_links=[{"type": "readiness_control", "id": control.control_ref}],
            compliance_domain="information_governance",
            risk_level="green" if run.status == "passed" else "red",
            source_module="production_readiness",
            source_record_ref=control.control_ref,
            entity_type="readiness_control",
            entity_id=control.control_ref,
        )
        control.evidence_ref = evidence.event_ref
        session.add(control)
    return run


readiness_service.security_self_test = security_self_test_v24
readiness_routes.security_self_test = security_self_test_v24

# v28 composes v27 organisation authority with governed speech providers,
# shadow/read-only connectors, two-person promotion and reconciliation controls.
from app import production_readiness_v28_patch as _production_readiness_v28_patch  # noqa: E402,F401
