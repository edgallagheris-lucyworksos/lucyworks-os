from __future__ import annotations

from datetime import datetime, timezone

from app.hospital_pilot_v29_models import HospitalPilotV29, ReadinessAssessmentV29
from app.organisation_onboarding_v27_models import OnboardingSiteV27
from app.pilot_release_readiness import evaluate_release_readiness
from app.real_hospital_connection_v28_models import IntegrationConnectorV28, ReconciliationItemV28

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)


def site() -> OnboardingSiteV27:
    return OnboardingSiteV27(
        site_ref="site-bvs",
        organisation_ref="org-bvs",
        premises_ref="prem-bvs",
        name="Referral Hospital",
        status="approved",
        active_release_ref="release-1",
        updated_by_subject="ops-1",
        updated_by_name="Ops",
        updated_by_role="ops_manager",
    )


def connector(kind: str) -> IntegrationConnectorV28:
    return IntegrationConnectorV28(
        connector_ref=f"connector-{kind}",
        organisation_ref="org-bvs",
        site_ref="site-bvs",
        premises_ref="prem-bvs",
        connector_type=kind,
        vendor_name="Test Vendor",
        environment="production",
        mode="read_only",
        status="active",
        last_test_status="passed",
        last_event_at=NOW,
        created_by_subject="admin-1",
        updated_by_subject="admin-1",
    )


def assessment() -> ReadinessAssessmentV29:
    return ReadinessAssessmentV29(
        assessment_ref="assessment-1",
        organisation_ref="org-bvs",
        site_ref="site-bvs",
        premises_ref="prem-bvs",
        overall_status="READY",
        score=100,
        evidence_chain_ok=True,
        assessed_by_subject="ops-1",
        assessed_by_name="Ops",
        assessed_by_role="ops_manager",
    )


def pilot() -> HospitalPilotV29:
    return HospitalPilotV29(
        pilot_ref="pilot-1",
        organisation_ref="org-bvs",
        site_ref="site-bvs",
        premises_ref="prem-bvs",
        name="Referral bounded pilot",
        mode="bounded_live",
        status="approved",
        success_criteria={"safeCompletionRate": 1.0},
        stop_criteria={"redIncident": True},
        rollback_plan={"action": "return_to_standard_workflow"},
        operations_approved_by_subject="ops-director",
        clinical_approved_by_subject="clinical-director",
        accountable_owner_subject="ops-director",
        accountable_owner_name="Operations Director",
        clinical_owner_subject="clinical-director",
        clinical_owner_name="Clinical Director",
        created_by_subject="ops-director",
        updated_by_subject="ops-director",
    )


required = [connector(kind) for kind in ("patient_management", "laboratory", "imaging", "communications")]

go = evaluate_release_readiness(
    site=site(),
    connectors=required,
    reconciliations=[],
    readiness=assessment(),
    pilot=pilot(),
    database_backend="postgresql",
    now=NOW,
)
assert go["status"] == "GO", go
assert not go["blockers"], go
assert all(check["passed"] for check in go["checks"]), go

missing_imaging = evaluate_release_readiness(
    site=site(),
    connectors=[row for row in required if row.connector_type != "imaging"],
    reconciliations=[],
    readiness=assessment(),
    pilot=pilot(),
    database_backend="postgresql",
    now=NOW,
)
assert missing_imaging["status"] == "NO_GO"
assert any("imaging" in blocker for blocker in missing_imaging["blockers"])

red_item = ReconciliationItemV28(
    item_ref="recon-red",
    connector_ref="connector-laboratory",
    event_ref="event-1",
    entity_type="patient",
    external_ref="external-patient",
    severity="red",
    reason="patient identity uncertain",
)
blocked_reconciliation = evaluate_release_readiness(
    site=site(),
    connectors=required,
    reconciliations=[red_item],
    readiness=assessment(),
    pilot=pilot(),
    database_backend="postgresql",
    now=NOW,
)
assert blocked_reconciliation["status"] == "NO_GO"
assert any("reconciliation" in blocker.lower() for blocker in blocked_reconciliation["blockers"])

sqlite_blocked = evaluate_release_readiness(
    site=site(),
    connectors=required,
    reconciliations=[],
    readiness=assessment(),
    pilot=pilot(),
    database_backend="non_postgresql",
    now=NOW,
)
assert sqlite_blocked["status"] == "NO_GO"
assert any("PostgreSQL" in blocker for blocker in sqlite_blocked["blockers"])

unsafe = connector("pharmacy")
unsafe.mode = "write"
write_blocked = evaluate_release_readiness(
    site=site(),
    connectors=required + [unsafe],
    reconciliations=[],
    readiness=assessment(),
    pilot=pilot(),
    database_backend="postgresql",
    now=NOW,
)
assert write_blocked["status"] == "NO_GO"
assert any("write-back" in blocker for blocker in write_blocked["blockers"])

print("PILOT_RELEASE_READINESS_PASSED")
