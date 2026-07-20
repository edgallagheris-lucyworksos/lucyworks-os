from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlmodel import Session, select

from app.auth import AuthContext
from app.evidence_service import create_evidence_event
from app.hospital_ops_service import ensure_default_premises_and_areas
from app.integration_models import IntegrationConnection
from app.models import Shift, StaffMember
from app.production_readiness_models import (
    PilotObservation,
    PilotRun,
    ReadinessControl,
    ReadinessEvidence,
    SecurityAssessmentRun,
)


CONTROL_DEFINITIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("identity.oidc", "identity", "Hospital identity configured", "OIDC login, issuer, audience and role mappings are verified against hospital identities.", "admin"),
    ("database.postgres", "database", "Managed PostgreSQL configured", "Production uses managed PostgreSQL with encrypted connections and no runtime schema creation.", "admin"),
    ("database.migrations", "database", "Migrations applied and rehearsed", "Alembic head is applied in staging and production with rollback or recovery procedure reviewed.", "admin"),
    ("backup.automatic", "resilience", "Automatic backups enabled", "Encrypted scheduled backups exist outside the application host with a documented retention period.", "admin"),
    ("backup.restore", "resilience", "Restore rehearsal passed", "A backup has been restored into an isolated database and the application smoke tests passed against it.", "admin"),
    ("monitoring.application", "operations", "Monitoring and alerting active", "API, web, database, integration and evidence-chain health are monitored with named responders.", "ops_manager"),
    ("incident.response", "operations", "Incident response approved", "Clinical, privacy, cyber and availability incidents have escalation, containment and communication procedures.", "governance_lead"),
    ("integrations.mapping", "integrations", "Vendor mappings validated", "PIMS, imaging, laboratory and HR mappings are tested with representative vendor payloads and reconciliation.", "ops_manager"),
    ("data.retention", "information_governance", "Retention and deletion policy approved", "Retention, legal hold, correction, export and deletion rules are approved for every data class.", "governance_lead"),
    ("privacy.dpia", "information_governance", "DPIA approved", "The data protection impact assessment is signed by the accountable information-governance owner.", "governance_lead"),
    ("security.pen_test", "security", "Independent penetration test passed", "High and critical findings are closed and retested; residual risks have named acceptance.", "governance_lead"),
    ("security.self_test", "security", "Automated security assessment passed", "The deployed environment passes LucyWorks configuration, identity, database and secret checks.", "admin"),
    ("users.training", "people", "Role-based training completed", "Operators, clinicians, nurses, administrators and incident responders have completed role-specific training.", "ops_manager"),
    ("uat.acceptance", "validation", "User acceptance signed", "Representative users have completed the end-to-end acceptance scripts with no unresolved critical failures.", "ops_manager"),
    ("shadow.mode", "validation", "Shadow-mode acceptance achieved", "LucyWorks has run alongside existing operations with reviewed agreement and no unresolved red observations.", "ops_manager"),
    ("pilot.bounded", "validation", "Bounded pilot approved", "A named service-line pilot has agreed scope, rollback criteria, clinical ownership and executive approval.", "hospital_director"),
)

SHADOW_REQUIRED = {
    "identity.oidc",
    "database.postgres",
    "database.migrations",
    "backup.automatic",
    "backup.restore",
    "monitoring.application",
    "incident.response",
    "integrations.mapping",
    "data.retention",
    "privacy.dpia",
    "security.self_test",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def parse_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def control_dict(row: ReadinessControl) -> dict[str, Any]:
    return {
        "controlRef": row.control_ref,
        "category": row.category,
        "title": row.title,
        "description": row.description,
        "required": row.required,
        "status": row.status,
        "ownerRole": row.owner_role,
        "evidenceSummary": row.evidence_summary,
        "evidenceRef": row.evidence_ref,
        "verifiedBy": {"subject": row.verified_by_subject, "name": row.verified_by_name},
        "verifiedAt": row.verified_at.isoformat() if row.verified_at else None,
        "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
        "waiverReason": row.waiver_reason,
        "version": row.version,
        "updatedAt": row.updated_at.isoformat(),
    }


def evidence_dict(row: ReadinessEvidence) -> dict[str, Any]:
    return {
        "evidenceRef": row.evidence_ref,
        "controlRef": row.control_ref,
        "evidenceType": row.evidence_type,
        "summary": row.summary,
        "sourceRef": row.source_ref,
        "payloadHash": row.payload_hash,
        "recordedBy": {"subject": row.recorded_by_subject, "name": row.recorded_by_name},
        "recordedAt": row.recorded_at.isoformat(),
    }


def pilot_dict(row: PilotRun) -> dict[str, Any]:
    return {
        "runRef": row.run_ref,
        "phase": row.phase,
        "serviceLine": row.service_line,
        "premisesRef": row.premises_ref,
        "status": row.status,
        "accountableOwner": row.accountable_owner,
        "successCriteria": parse_json(row.success_criteria_json, {}),
        "metrics": parse_json(row.metrics_json, {}),
        "blockers": parse_json(row.blockers_json, []),
        "startedAt": row.started_at.isoformat() if row.started_at else None,
        "endedAt": row.ended_at.isoformat() if row.ended_at else None,
        "approvedBySubject": row.approved_by_subject,
        "approvalNote": row.approval_note,
        "createdBySubject": row.created_by_subject,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


def observation_dict(row: PilotObservation) -> dict[str, Any]:
    return {
        "observationRef": row.observation_ref,
        "runRef": row.run_ref,
        "severity": row.severity,
        "category": row.category,
        "summary": row.summary,
        "expectedBehaviour": row.expected_behaviour,
        "actualBehaviour": row.actual_behaviour,
        "ownerRole": row.owner_role,
        "status": row.status,
        "resolution": row.resolution,
        "recordedBySubject": row.recorded_by_subject,
        "createdAt": row.created_at.isoformat(),
        "resolvedAt": row.resolved_at.isoformat() if row.resolved_at else None,
    }


def seed_controls(session: Session) -> list[ReadinessControl]:
    existing = {row.control_ref: row for row in session.exec(select(ReadinessControl)).all()}
    rows: list[ReadinessControl] = []
    for control_ref, category, title, description, owner_role in CONTROL_DEFINITIONS:
        row = existing.get(control_ref)
        if not row:
            row = ReadinessControl(
                control_ref=control_ref,
                category=category,
                title=title,
                description=description,
                owner_role=owner_role,
            )
            session.add(row)
        rows.append(row)
    session.flush()
    return rows


def _evidence_event(session: Session, auth: AuthContext, *, action: str, control: ReadinessControl, before: Any, after: Any, risk: str = "amber", reason: str | None = None) -> str:
    event, _ = create_evidence_event(
        session,
        event_type="production_readiness_control",
        action=action,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=before,
        new_state=after,
        reason=reason,
        justification="Hospital production-readiness governance",
        evidence_links=[{"type": "readiness_control", "id": control.control_ref}],
        compliance_domain="information_governance",
        risk_level=risk,
        source_module="production_readiness",
        source_record_ref=control.control_ref,
        entity_type="readiness_control",
        entity_id=control.control_ref,
    )
    return event.event_ref


def update_control(session: Session, control_ref: str, payload: dict[str, Any], auth: AuthContext) -> ReadinessControl:
    row = session.exec(select(ReadinessControl).where(ReadinessControl.control_ref == control_ref).with_for_update()).first()
    if not row:
        raise ValueError("readiness control not found")
    expected_version = payload.get("expectedVersion")
    if expected_version is None or int(expected_version) != row.version:
        raise RuntimeError(f"stale readiness control: current version is {row.version}")
    status = str(payload.get("status") or row.status)
    if status not in {"not_started", "in_progress", "blocked", "failed", "passed", "waived"}:
        raise ValueError("invalid readiness status")
    if status == "waived" and not str(payload.get("waiverReason") or "").strip():
        raise ValueError("waiverReason is required")
    before = control_dict(row)
    row.status = status
    row.owner_role = str(payload.get("ownerRole") or row.owner_role)
    row.evidence_summary = payload.get("evidenceSummary", row.evidence_summary)
    row.waiver_reason = payload.get("waiverReason") if status == "waived" else None
    if status in {"passed", "waived"}:
        row.verified_by_subject = auth.subject
        row.verified_by_name = auth.actor_name
        row.verified_at = utc_now()
        valid_days = int(payload.get("validDays") or 180)
        row.expires_at = utc_now() + timedelta(days=max(1, min(valid_days, 730)))
    else:
        row.verified_by_subject = None
        row.verified_by_name = None
        row.verified_at = None
        row.expires_at = None
    row.version += 1
    row.updated_at = utc_now()
    after = control_dict(row)
    row.evidence_ref = _evidence_event(
        session,
        auth,
        action=f"readiness control marked {status}",
        control=row,
        before=before,
        after=after,
        risk="red" if status in {"failed", "waived"} else "green" if status == "passed" else "amber",
        reason=payload.get("reason") or payload.get("waiverReason") or payload.get("evidenceSummary"),
    )
    session.add(row)
    return row


def record_control_evidence(session: Session, control_ref: str, payload: dict[str, Any], auth: AuthContext) -> ReadinessEvidence:
    control = session.exec(select(ReadinessControl).where(ReadinessControl.control_ref == control_ref)).first()
    if not control:
        raise ValueError("readiness control not found")
    raw = payload.get("payload")
    payload_hash = hashlib.sha256(json_text(raw).encode("utf-8")).hexdigest() if raw is not None else None
    row = ReadinessEvidence(
        evidence_ref=make_ref("ready-evidence"),
        control_ref=control_ref,
        evidence_type=str(payload.get("evidenceType") or "manual_attestation"),
        summary=str(payload.get("summary") or "").strip(),
        source_ref=payload.get("sourceRef"),
        payload_hash=payload_hash,
        recorded_by_subject=auth.subject,
        recorded_by_name=auth.actor_name,
    )
    if not row.summary:
        raise ValueError("evidence summary is required")
    session.add(row)
    session.flush()
    control.evidence_summary = row.summary
    control.evidence_ref = row.evidence_ref
    control.updated_at = utc_now()
    control.version += 1
    session.add(control)
    _evidence_event(
        session,
        auth,
        action="production-readiness evidence recorded",
        control=control,
        before=None,
        after=evidence_dict(row),
        risk="green",
        reason=row.summary,
    )
    return row


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def security_self_test(session: Session, auth: AuthContext) -> SecurityAssessmentRun:
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
    required_tables = {"evidenceevent", "operationalblock", "canonicalepisodestate", "readinesscontrol", "pilotrun", "alembic_version"}
    missing = sorted(required_tables - table_names)
    check("database.tables", "Required tables present", not missing, f"Missing tables: {missing}" if missing else "Required tables present")
    migration = None
    if "alembic_version" in table_names:
        migration = session.exec(text("select version_num from alembic_version")).first()
        if isinstance(migration, tuple):
            migration = migration[0]
    check("database.migration", "Migration head", str(migration or "") == "0006_production_readiness", f"Current migration: {migration or 'unknown'}")

    active_connections = session.exec(select(IntegrationConnection).where(IntegrationConnection.status == "active")).all()
    missing_secrets = [row.connection_ref for row in active_connections if not os.getenv(row.secret_env, "")]
    check("integrations.secrets", "Active integration secrets loaded", not missing_secrets, f"Missing secrets for: {missing_secrets}" if missing_secrets else "All active integration secrets loaded", "warning")

    failed = len([item for item in checks if not item["passed"] and item["severity"] == "failure"])
    warnings = len([item for item in checks if not item["passed"] and item["severity"] == "warning"])
    passed = len([item for item in checks if item["passed"]])
    total = max(1, len(checks))
    score = round((passed / total) * 100)
    run = SecurityAssessmentRun(
        run_ref=make_ref("security"),
        environment_name=os.getenv("DEPLOYMENT_ENVIRONMENT", "unknown"),
        status="passed" if failed == 0 else "failed",
        score=score,
        passed_count=passed,
        failed_count=failed,
        warning_count=warnings,
        checks_json=json_text(checks),
        created_by_subject=auth.subject,
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()

    control = session.exec(select(ReadinessControl).where(ReadinessControl.control_ref == "security.self_test")).first()
    if control:
        control.status = "passed" if run.status == "passed" else "failed"
        control.evidence_summary = f"Automated assessment {run.run_ref}: score {run.score}, failures {failed}, warnings {warnings}"
        control.verified_by_subject = auth.subject
        control.verified_by_name = auth.actor_name
        control.verified_at = utc_now()
        control.expires_at = utc_now() + timedelta(days=30)
        control.version += 1
        control.updated_at = utc_now()
        control.evidence_ref = _evidence_event(
            session,
            auth,
            action="automated production security assessment completed",
            control=control,
            before=None,
            after={"runRef": run.run_ref, "status": run.status, "score": run.score, "checks": checks},
            risk="green" if run.status == "passed" else "red",
            reason=f"{failed} failed checks and {warnings} warnings",
        )
        session.add(control)
    return run


def seed_synthetic_hospital(session: Session, premises_ref: str = "synthetic-referral-hospital") -> dict[str, Any]:
    premises, areas = ensure_default_premises_and_areas(session, premises_ref)
    role_plan = [
        ("clinical_director", 2, "surgery,governance,anaesthesia"),
        ("clinician", 18, "surgery,consultation,diagnostic_imaging,anaesthesia"),
        ("nurse", 28, "nursing,anaesthesia,recovery,critical_care,inpatient"),
        ("ops_manager", 3, "operations,flow,escalation"),
        ("admin", 7, "intake,insurance,client_communications"),
        ("pca", 10, "patient_support,cleaning,stock"),
        ("radiographer", 4, "mri,ct,radiography"),
    ]
    created_staff = 0
    created_shifts = 0
    today = utc_now().date()
    for role, count, skills in role_plan:
        for index in range(1, count + 1):
            name = f"Synthetic {role.replace('_', ' ').title()} {index:02d}"
            member = session.exec(select(StaffMember).where(StaffMember.name == name)).first()
            if not member:
                member = StaffMember(name=name, role=role, skills=skills, active=True)
                session.add(member)
                session.flush()
                created_staff += 1
            starts = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=7 + ((index - 1) % 3))
            ends = starts + timedelta(hours=10)
            shift = session.exec(select(Shift).where(Shift.staff_member_id == member.id, Shift.starts_at == starts)).first()
            if not shift:
                session.add(Shift(staff_member_id=member.id or 0, department="Synthetic referral hospital", starts_at=starts, ends_at=ends, shift_type="simulation", status="planned"))
                created_shifts += 1
    session.flush()
    return {
        "premisesRef": premises.premises_ref,
        "premisesName": premises.name,
        "areas": len(areas),
        "createdStaff": created_staff,
        "createdShifts": created_shifts,
        "synthetic": True,
    }


def create_pilot(session: Session, payload: dict[str, Any], auth: AuthContext) -> PilotRun:
    phase = str(payload.get("phase") or "synthetic")
    if phase not in {"synthetic", "historical_replay", "shadow", "bounded_pilot", "scale_up"}:
        raise ValueError("invalid pilot phase")
    run = PilotRun(
        run_ref=make_ref("pilot"),
        phase=phase,
        service_line=str(payload.get("serviceLine") or "referral"),
        premises_ref=str(payload.get("premisesRef") or "default-premises"),
        status="running" if payload.get("startNow", True) else "planned",
        accountable_owner=str(payload.get("accountableOwner") or auth.actor_name),
        success_criteria_json=json_text(payload.get("successCriteria") or {}),
        metrics_json=json_text(payload.get("metrics") or {}),
        blockers_json="[]",
        started_at=utc_now() if payload.get("startNow", True) else None,
        created_by_subject=auth.subject,
    )
    session.add(run)
    return run


def add_observation(session: Session, run_ref: str, payload: dict[str, Any], auth: AuthContext) -> PilotObservation:
    run = session.exec(select(PilotRun).where(PilotRun.run_ref == run_ref)).first()
    if not run:
        raise ValueError("pilot run not found")
    severity = str(payload.get("severity") or "amber")
    if severity not in {"green", "amber", "red"}:
        raise ValueError("invalid observation severity")
    row = PilotObservation(
        observation_ref=make_ref("observation"),
        run_ref=run_ref,
        severity=severity,
        category=str(payload.get("category") or "workflow"),
        summary=str(payload.get("summary") or "").strip(),
        expected_behaviour=payload.get("expectedBehaviour"),
        actual_behaviour=payload.get("actualBehaviour"),
        owner_role=str(payload.get("ownerRole") or "ops_manager"),
        recorded_by_subject=auth.subject,
    )
    if not row.summary:
        raise ValueError("observation summary is required")
    session.add(row)
    if severity == "red":
        blockers = parse_json(run.blockers_json, [])
        blockers.append({"observationRef": row.observation_ref, "summary": row.summary})
        run.blockers_json = json_text(blockers)
        run.status = "blocked"
        run.updated_at = utc_now()
        session.add(run)
    return row


def update_pilot(session: Session, run_ref: str, payload: dict[str, Any], auth: AuthContext) -> PilotRun:
    run = session.exec(select(PilotRun).where(PilotRun.run_ref == run_ref).with_for_update()).first()
    if not run:
        raise ValueError("pilot run not found")
    if payload.get("metrics") is not None:
        metrics = parse_json(run.metrics_json, {})
        metrics.update(payload.get("metrics") or {})
        run.metrics_json = json_text(metrics)
    status = payload.get("status")
    if status:
        if status not in {"planned", "running", "blocked", "passed", "failed", "closed"}:
            raise ValueError("invalid pilot status")
        run.status = status
        if status == "running" and not run.started_at:
            run.started_at = utc_now()
        if status in {"passed", "failed", "closed"}:
            run.ended_at = utc_now()
    if payload.get("approvalNote"):
        run.approved_by_subject = auth.subject
        run.approval_note = str(payload["approvalNote"])
    run.updated_at = utc_now()
    session.add(run)
    return run


def resolve_observation(session: Session, observation_ref: str, payload: dict[str, Any], auth: AuthContext) -> PilotObservation:
    row = session.exec(select(PilotObservation).where(PilotObservation.observation_ref == observation_ref).with_for_update()).first()
    if not row:
        raise ValueError("observation not found")
    row.status = "resolved"
    row.resolution = str(payload.get("resolution") or "").strip()
    if not row.resolution:
        raise ValueError("resolution is required")
    row.resolved_at = utc_now()
    session.add(row)
    return row


def gate_summary(session: Session) -> dict[str, Any]:
    controls = seed_controls(session)
    now = utc_now()
    expired = []
    for row in controls:
        if row.expires_at and row.expires_at.replace(tzinfo=row.expires_at.tzinfo or timezone.utc) <= now and row.status == "passed":
            row.status = "blocked"
            row.updated_at = now
            row.version += 1
            expired.append(row.control_ref)
            session.add(row)
    controls_by_ref = {row.control_ref: row for row in controls}
    open_red = session.exec(select(PilotObservation).where(PilotObservation.severity == "red", PilotObservation.status != "resolved")).all()
    latest_security = session.exec(select(SecurityAssessmentRun).order_by(SecurityAssessmentRun.created_at.desc())).first()
    shadow_missing = sorted(ref for ref in SHADOW_REQUIRED if controls_by_ref.get(ref) is None or controls_by_ref[ref].status != "passed")
    live_missing = sorted(row.control_ref for row in controls if row.required and row.status != "passed")
    live_eligible = not live_missing and not open_red and bool(latest_security and latest_security.status == "passed")
    shadow_eligible = not shadow_missing and not open_red
    by_category: dict[str, dict[str, int]] = {}
    for row in controls:
        bucket = by_category.setdefault(row.category, {"total": 0, "passed": 0, "blocked": 0})
        bucket["total"] += 1
        if row.status == "passed":
            bucket["passed"] += 1
        if row.status in {"blocked", "failed", "waived"}:
            bucket["blocked"] += 1
    return {
        "shadowEligible": shadow_eligible,
        "liveEligible": live_eligible,
        "shadowMissing": shadow_missing,
        "liveMissing": live_missing,
        "openRedObservations": len(open_red),
        "expiredControls": expired,
        "latestSecurity": {
            "runRef": latest_security.run_ref,
            "status": latest_security.status,
            "score": latest_security.score,
            "completedAt": latest_security.completed_at.isoformat() if latest_security and latest_security.completed_at else None,
        } if latest_security else None,
        "byCategory": by_category,
    }


def dashboard(session: Session) -> dict[str, Any]:
    controls = seed_controls(session)
    pilots = session.exec(select(PilotRun).order_by(PilotRun.created_at.desc()).limit(50)).all()
    observations = session.exec(select(PilotObservation).order_by(PilotObservation.created_at.desc()).limit(100)).all()
    evidence = session.exec(select(ReadinessEvidence).order_by(ReadinessEvidence.recorded_at.desc()).limit(100)).all()
    security_runs = session.exec(select(SecurityAssessmentRun).order_by(SecurityAssessmentRun.created_at.desc()).limit(20)).all()
    return {
        "gate": gate_summary(session),
        "controls": [control_dict(row) for row in controls],
        "pilots": [pilot_dict(row) for row in pilots],
        "observations": [observation_dict(row) for row in observations],
        "evidence": [evidence_dict(row) for row in evidence],
        "securityRuns": [{
            "runRef": row.run_ref,
            "environmentName": row.environment_name,
            "status": row.status,
            "score": row.score,
            "passedCount": row.passed_count,
            "failedCount": row.failed_count,
            "warningCount": row.warning_count,
            "checks": parse_json(row.checks_json, []),
            "createdAt": row.created_at.isoformat(),
            "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        } for row in security_runs],
    }


def vendor_mapping_catalogue() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3] / "config" / "integrations"
    mappings = []
    if root.exists():
        for path in sorted(root.glob("*.mapping.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                mappings.append({"file": path.name, "profile": payload})
            except (OSError, ValueError) as exc:
                mappings.append({"file": path.name, "error": str(exc)})
    return {"mappings": mappings, "count": len(mappings)}
