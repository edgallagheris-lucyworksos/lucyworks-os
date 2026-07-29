import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_v26_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "operational-convergence-v26-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-v26-smoke",
    "AUTH_AUDIENCE": "lucyworks-v26-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
    "V26_CONTEXT_BOOTSTRAP_ENABLED": "true",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.clinical_execution_models import MedicationAdministration, MedicationOrder
from app.database import engine
from app.evidence_service import verify_event_chain
from app.hospital_command_models import EpisodeClosureV9, EpisodeTransitionV9
from app.models import User
from app.operational_context_v26_models import (
    CanonicalCommandV26,
    ContextSwitchEvidenceV26,
    OperationalImpactV26,
    OrganisationV26,
    SiteMembershipV26,
    SiteV26,
)
from app.patient_care_models import PatientCase, ReferralEpisode
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    session.add_all([
        User(id=2601, name="V26 Nurse", role="nurse", email="nurse-v26@example.test"),
        User(id=2602, name="V26 Clinical Director", role="clinical_director", email="clinical-v26@example.test"),
        User(id=2603, name="V26 Operations", role="ops_manager", email="ops-v26@example.test"),
    ])
    session.add(PatientCase(id="case-v26", patient_name="Bramble Context", species="dog", owner_name="Owner V26"))
    session.add(ReferralEpisode(
        id="episode-v26",
        patient_case_id="case-v26",
        episode_ref="EP-V26",
        stage="procedure",
        owner_role="nurse",
        owner_name="V26 Nurse",
        current_location="MRI prep",
        next_action="confirm safe progression",
    ))
    session.add(OrganisationV26(organisation_ref="org-second", name="Second Referral Group"))
    session.add(SiteV26(
        site_ref="site-second",
        organisation_ref="org-second",
        premises_ref="premises-second",
        name="Second Hospital",
        configuration_state="synthetic",
    ))
    session.add(SiteMembershipV26(
        membership_ref="membership-second-v26",
        subject="local-user:2603",
        actor_id="2603",
        organisation_ref="org-second",
        site_ref="site-second",
        premises_ref="premises-second",
        role="ops_manager",
        is_primary=False,
        granted_by_subject="test",
    ))
    session.commit()


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    token = response.json().get("accessToken")
    assert token
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def ok(response, label: str):
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    return response.json()


try:
    with TestClient(app) as client:
        nurse = login(client, 2601)
        clinician = login(client, 2602)
        operations = login(client, 2603)

        context = ok(client.get("/api/v26/context", headers=nurse), "load nurse context")
        assert context["context"]["siteRef"] == "bvs-bristol"
        assert context["context"]["premisesRef"] != "default-premises"
        assert len(context["sites"]) == 1

        ops_context = ok(client.get("/api/v26/context", headers=operations), "load operations context")
        assert {row["siteRef"] for row in ops_context["sites"]} == {"bvs-bristol", "site-second"}
        first_version = ops_context["context"]["version"]

        switched = ok(client.post(
            "/api/v26/context/switch",
            headers=operations,
            json={"siteRef": "site-second", "expectedVersion": first_version, "reason": "Operate the second hospital command view."},
        ), "switch authorised site")
        assert switched["context"]["siteRef"] == "site-second"
        assert switched["context"]["premisesRef"] == "premises-second"

        stale = client.post(
            "/api/v26/context/switch",
            headers=operations,
            json={"siteRef": "bvs-bristol", "expectedVersion": first_version, "reason": "Stale switch must fail."},
        )
        assert stale.status_code == 409, stale.text

        switched_back = ok(client.post(
            "/api/v26/context/switch",
            headers=operations,
            json={"siteRef": "bvs-bristol", "expectedVersion": switched["context"]["version"], "reason": "Return to the primary referral hospital."},
        ), "switch back to primary site")
        assert switched_back["context"]["siteRef"] == "bvs-bristol"

        cross_site = client.post(
            "/api/v26/commands",
            headers=operations,
            json={
                "commandType": "service_restriction",
                "idempotencyKey": "cross-site-v26",
                "payload": {"premisesRef": "premises-second", "serviceRef": "MRI", "summary": "Attempt a write outside active site context."},
            },
        )
        assert cross_site.status_code == 409, cross_site.text

        default_premises = client.post(
            "/api/v26/commands",
            headers=operations,
            json={
                "commandType": "service_restriction",
                "idempotencyKey": "default-premises-v26",
                "payload": {"premisesRef": "default-premises", "serviceRef": "MRI", "summary": "Default premises must never be accepted."},
            },
        )
        assert default_premises.status_code == 409, default_premises.text

        consent = ok(client.post(
            "/api/v26/commands",
            headers=clinician,
            json={
                "commandType": "consent_review_request",
                "sourceRecordRef": "consent-v26",
                "idempotencyKey": "consent-review-v26",
                "payload": {
                    "patientRef": "case-v26",
                    "episodeRef": "episode-v26",
                    "summary": "Procedure must remain held until consent evidence is reviewed.",
                    "severity": "amber",
                },
            },
        ), "create consent review command")
        assert consent["command"]["requiresHumanDecision"] is True
        assert consent["command"]["clinicalMutationPerformed"] is False
        assert consent["safetyRecord"]["safetyHoldRequested"] is True

        consent_repeat = ok(client.post(
            "/api/v26/commands",
            headers=clinician,
            json={
                "commandType": "consent_review_request",
                "sourceRecordRef": "consent-v26",
                "idempotencyKey": "consent-review-v26",
                "payload": {"patientRef": "case-v26", "episodeRef": "episode-v26", "summary": "Duplicate request."},
            },
        ), "deduplicate consent command")
        assert consent_repeat["created"] is False
        assert consent_repeat["command"]["commandRef"] == consent["command"]["commandRef"]

        blocked = ok(client.patch(
            "/api/patient-care/episodes/episode-v26/state",
            headers=nurse,
            json={
                "blocker": "missing anaesthesia cover",
                "status": "blocked",
                "nextAction": "clinical director and operations confirm safe cover",
                "actor": "Spoofed Browser",
                "note": "Anaesthesia competency and cover are not confirmed.",
            },
        ), "canonicalise patient blocker")
        assert blocked["event"]["actor"] == "V26 Nurse"
        assert blocked["canonicalCommand"]["commandType"] == "patient_blocker"
        assert blocked["canonicalCommand"]["siteRef"] == "bvs-bristol"

        handover = ok(client.post(
            "/api/control-plane/handovers",
            headers=nurse,
            json={
                "handoverRef": "HANDOVER-V26",
                "patientCaseId": "case-v26",
                "referralEpisodeId": "episode-v26",
                "fromActor": "Spoofed Sender",
                "fromRole": "admin",
                "toActor": "V26 Clinical Director",
                "toRole": "clinical_director",
                "summary": "MRI patient requires named acceptance of unresolved anaesthesia risk.",
                "clinicalRisks": ["Anaesthesia cover not confirmed"],
                "outstandingActions": ["Confirm competent cover"],
            },
        ), "canonicalise handover")
        assert handover["handover"]["fromActor"] == "V26 Nurse"
        assert handover["canonicalCommand"]["commandType"] == "handover_request"
        accepted = ok(client.patch(
            f"/api/control-plane/handovers/{handover['handover']['id']}/decision",
            headers=clinician,
            json={
                "decision": "accepted",
                "decidedBy": "Spoofed Recipient",
                "decidedByRole": "admin",
                "note": "Clinical director accepts the named responsibility.",
            },
        ), "record handover outcome")
        assert accepted["canonicalCommand"]["status"] == "accepted"

        critical = ok(client.post(
            "/api/control-plane/critical-results",
            headers=clinician,
            json={
                "resultRef": "RESULT-V26",
                "patientCaseId": "case-v26",
                "referralEpisodeId": "episode-v26",
                "resultType": "MRI",
                "severity": "red",
                "summary": "Imaging finding requires immediate named clinical review.",
                "assignedTo": "local-user:2602",
                "assignedRole": "clinical_director",
                "createdBy": "Spoofed Integration",
            },
        ), "canonicalise critical result")
        assert critical["canonicalCommand"]["commandType"] == "critical_result_received"
        acknowledged = ok(client.patch(
            f"/api/control-plane/critical-results/{critical['result']['id']}/acknowledge",
            headers=clinician,
            json={
                "acknowledgedBy": "Spoofed Clinician",
                "acknowledgedByRole": "admin",
                "actionTaken": "Reviewed result and documented the human clinical plan.",
                "note": "Named clinician acknowledgement.",
            },
        ), "record critical result outcome")
        assert acknowledged["canonicalCommand"]["status"] == "acknowledged"
        assert acknowledged["result"]["acknowledgedBy"] == "V26 Clinical Director"

        downtime = ok(client.post(
            "/api/v26/commands",
            headers=operations,
            json={
                "commandType": "equipment_downtime",
                "sourceRecordRef": "mri-downtime-v26",
                "idempotencyKey": "mri-downtime-v26",
                "payload": {
                    "serviceRef": "MRI",
                    "patientRefs": ["case-v26", "case-v26-2"],
                    "summary": "MRI unavailable pending engineering confirmation.",
                    "boardSummary": "MRI restricted; two patient plans require named review.",
                    "severity": "red",
                },
            },
        ), "create multi-patient downtime command")
        assert downtime["command"]["clinicalMutationPerformed"] is False

        view = ok(client.get("/api/v26/operational-view", headers=operations), "load board-safe operational view")
        assert view["summary"]["activeImpacts"] >= 5
        assert view["summary"]["affectedPatients"] >= 2
        assert any(item["impactType"] == "equipment_downtime" for item in view["impacts"])

        convergence = ok(client.get("/api/v26/convergence", headers=operations), "load convergence register")
        assert any(item["routeKey"] == "control-plane-handover-create" for item in convergence["routes"])
        assert all(item["canonicalPath"] == "/api/v26/commands" for item in convergence["routes"])

        with Session(engine) as session:
            commands = session.exec(select(CanonicalCommandV26)).all()
            assert len(commands) >= 5
            assert all(row.premises_ref != "default-premises" for row in commands)
            assert all(row.actor_name not in {"Spoofed Browser", "Spoofed Sender", "Spoofed Integration"} for row in commands)
            assert all(row.clinical_mutation_performed is False for row in commands)
            assert session.exec(select(ContextSwitchEvidenceV26)).all()
            assert session.exec(select(OperationalImpactV26)).all()
            assert not session.exec(select(MedicationOrder)).all()
            assert not session.exec(select(MedicationAdministration)).all()
            assert not session.exec(select(EpisodeTransitionV9)).all()
            assert not session.exec(select(EpisodeClosureV9)).all()
            chain = verify_event_chain(session)
            assert chain["valid"], chain

        print("Authorised organisation/site context and versioned switching OK")
        print("Default-premises and cross-site writes rejected OK")
        print("Consent, patient blocker, handover, critical result and downtime commands converged OK")
        print("Board-safe multi-patient operational impacts OK")
        print("No autonomous clinical mutation and immutable evidence chain OK")
        print("--- OPERATIONAL CONVERGENCE V26 SMOKE TEST PASSED ---")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
