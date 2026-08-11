from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.auth import ALL_AUTHENTICATED_ROLES, AuthContext, require_roles
from app.database import get_session
from app.hospital_pilot_v29_models import HospitalPilotV29, ReadinessAssessmentV29
from app.operational_context_v26_models import SiteMembershipV26
from app.organisation_onboarding_v27_models import OnboardingSiteV27
from app.real_hospital_connection_v28_models import IntegrationConnectorV28, ReconciliationItemV28

router = APIRouter(prefix="/api/pilot-release", tags=["pilot-release"])

REQUIRED_CONNECTOR_TYPES = {
    "patient_management",
    "laboratory",
    "imaging",
    "communications",
}
ALLOWED_PILOT_CONNECTOR_MODES = {"shadow", "read_only"}
PASSING_READINESS = {"READY", "READY_WITH_RESTRICTIONS"}
APPROVED_PILOT_STATUSES = {"approved", "active"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _database_backend() -> str:
    value = os.getenv("DATABASE_URL", "")
    return "postgresql" if value.startswith(("postgresql://", "postgres://")) else "non_postgresql"


def _connector_state(connector: IntegrationConnectorV28, now: datetime) -> dict[str, Any]:
    stale = bool(
        connector.status == "active"
        and connector.last_event_at
        and (now - connector.last_event_at).total_seconds() > connector.stale_after_seconds
    )
    healthy = (
        connector.status == "active"
        and connector.mode in ALLOWED_PILOT_CONNECTOR_MODES
        and connector.last_test_status == "passed"
        and not stale
    )
    return {
        "connectorRef": connector.connector_ref,
        "type": connector.connector_type,
        "vendor": connector.vendor_name,
        "environment": connector.environment,
        "mode": connector.mode,
        "status": connector.status,
        "lastTestStatus": connector.last_test_status,
        "lastEventAt": connector.last_event_at.isoformat() if connector.last_event_at else None,
        "stale": stale,
        "healthyForPilot": healthy,
    }


def evaluate_release_readiness(
    *,
    site: OnboardingSiteV27 | None,
    connectors: list[IntegrationConnectorV28],
    reconciliations: list[ReconciliationItemV28],
    readiness: ReadinessAssessmentV29 | None,
    pilot: HospitalPilotV29 | None,
    database_backend: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or _now()
    blockers: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    configured = bool(site and site.active_release_ref and site.status in {"approved", "changes_pending"})
    checks.append({"code": "approved_site_configuration", "passed": configured})
    if not configured:
        blockers.append("Approved hospital configuration is required.")

    postgres = database_backend == "postgresql"
    checks.append({"code": "postgresql_runtime", "passed": postgres, "observed": database_backend})
    if not postgres:
        blockers.append("Production pilot must run on PostgreSQL, not a development database.")

    connector_states = [_connector_state(row, now) for row in connectors]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for state in connector_states:
        by_type.setdefault(state["type"], []).append(state)

    for connector_type in sorted(REQUIRED_CONNECTOR_TYPES):
        candidates = by_type.get(connector_type, [])
        healthy = any(item["healthyForPilot"] for item in candidates)
        checks.append({
            "code": f"connector_{connector_type}",
            "passed": healthy,
            "candidates": candidates,
        })
        if not healthy:
            blockers.append(f"A tested, active shadow/read-only {connector_type} connector is required.")

    unsafe_write_mode = [item for item in connector_states if item["mode"] not in {"disabled", *ALLOWED_PILOT_CONNECTOR_MODES}]
    checks.append({"code": "external_write_back_disabled", "passed": not unsafe_write_mode})
    if unsafe_write_mode:
        blockers.append("External-system write-back is not authorised for the bounded pilot.")

    red_reconciliation = [
        row for row in reconciliations
        if row.status == "open" and row.severity.lower() in {"red", "critical"}
    ]
    checks.append({"code": "no_red_reconciliation", "passed": not red_reconciliation, "openRed": len(red_reconciliation)})
    if red_reconciliation:
        blockers.append(f"{len(red_reconciliation)} red/critical integration reconciliation item(s) remain open.")

    amber_reconciliation = [
        row for row in reconciliations
        if row.status == "open" and row.severity.lower() not in {"red", "critical"}
    ]
    if amber_reconciliation:
        warnings.append(f"{len(amber_reconciliation)} non-critical reconciliation item(s) remain open.")

    readiness_ok = bool(readiness and readiness.overall_status in PASSING_READINESS and readiness.evidence_chain_ok)
    checks.append({
        "code": "current_readiness_assessment",
        "passed": readiness_ok,
        "status": readiness.overall_status if readiness else None,
        "assessmentRef": readiness.assessment_ref if readiness else None,
    })
    if not readiness_ok:
        blockers.append("A current READY or READY_WITH_RESTRICTIONS assessment with a valid evidence chain is required.")

    pilot_ok = bool(
        pilot
        and pilot.status in APPROVED_PILOT_STATUSES
        and pilot.operations_approved_by_subject
        and pilot.clinical_approved_by_subject
        and pilot.accountable_owner_subject
        and pilot.clinical_owner_subject
        and pilot.rollback_plan
        and pilot.stop_criteria
        and pilot.success_criteria
    )
    checks.append({
        "code": "bounded_pilot_authority",
        "passed": pilot_ok,
        "pilotRef": pilot.pilot_ref if pilot else None,
        "pilotStatus": pilot.status if pilot else None,
    })
    if not pilot_ok:
        blockers.append("A bounded pilot with operational and clinical approval, named owners, success/stop criteria and rollback plan is required.")

    status = "GO" if not blockers else "NO_GO"
    return {
        "status": status,
        "releaseDecision": "bounded_pilot_authorised" if status == "GO" else "blocked",
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
        "connectors": connector_states,
        "principle": "Patient safety, client clarity and staff control take precedence over throughput or revenue.",
        "boundary": "This gate authorises only the configured bounded pilot. It does not authorise autonomous clinical decisions or external-system write-back.",
    }


def _require_site_access(session: Session, auth: AuthContext, site_ref: str) -> None:
    membership = session.exec(select(SiteMembershipV26).where(
        SiteMembershipV26.subject == auth.subject,
        SiteMembershipV26.site_ref == site_ref,
        SiteMembershipV26.status == "active",
    )).first()
    if not membership:
        raise HTTPException(status_code=403, detail={"code": "site_access_required", "siteRef": site_ref})


@router.get("/readiness")
def pilot_release_readiness(
    siteRef: str = Query(min_length=1),
    pilotRef: str | None = None,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ALL_AUTHENTICATED_ROLES)),
) -> dict[str, Any]:
    _require_site_access(session, auth, siteRef)

    site = session.exec(select(OnboardingSiteV27).where(OnboardingSiteV27.site_ref == siteRef)).first()
    connectors = list(session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.site_ref == siteRef)).all())
    connector_refs = [row.connector_ref for row in connectors]
    reconciliations = list(session.exec(select(ReconciliationItemV28).where(
        ReconciliationItemV28.connector_ref.in_(connector_refs),
        ReconciliationItemV28.status == "open",
    )).all()) if connector_refs else []

    readiness = session.exec(
        select(ReadinessAssessmentV29)
        .where(ReadinessAssessmentV29.site_ref == siteRef)
        .order_by(ReadinessAssessmentV29.assessed_at.desc())
    ).first()

    pilot_query = select(HospitalPilotV29).where(HospitalPilotV29.site_ref == siteRef)
    if pilotRef:
        pilot_query = pilot_query.where(HospitalPilotV29.pilot_ref == pilotRef)
    pilot = session.exec(pilot_query.order_by(HospitalPilotV29.updated_at.desc())).first()

    result = evaluate_release_readiness(
        site=site,
        connectors=connectors,
        reconciliations=reconciliations,
        readiness=readiness,
        pilot=pilot,
        database_backend=_database_backend(),
    )
    result.update({
        "siteRef": siteRef,
        "pilotRef": pilot.pilot_ref if pilot else pilotRef,
        "readinessAssessmentRef": readiness.assessment_ref if readiness else None,
    })
    return result
