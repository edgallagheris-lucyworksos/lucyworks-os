import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_pilot_control_v24_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "pilot-control-v24-smoke-secret-long-enough-for-testing",
    "AUTH_ISSUER": "lucyworks-pilot-v24-smoke",
    "AUTH_AUDIENCE": "lucyworks-pilot-v24-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.database import engine
from app.evidence_event_models import EvidenceEvent
from app.hospital_command_models import EpisodeClosureV9, EpisodeTransitionV9
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app
from app.models import ClinicalNoteV8, User
from app.pilot_control_v24_models import (
    PilotApprovalV24,
    PilotAuthorityV24,
    PilotControlActionV24,
    PilotShadowComparisonV24,
    PilotUATScenarioV24,
)
from app.production_readiness_models import ReadinessControl
from app.production_readiness_service import SHADOW_REQUIRED
from app.shadow_mode_routes import ShadowRecord
from app.clinical_execution_models import MedicationAdministration, MedicationOrder

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    session.add(User(id=1201, name="V24 Operations", role="ops_manager", email="v24-ops@example.test"))
    session.add(User(id=1202, name="V24 Clinical Director", role="clinical_director", email="v24-clinical@example.test"))
    session.add(User(id=1203, name="V24 Governance", role="governance_lead", email="v24-governance@example.test"))
    session.add(User(id=1204, name="V24 Nurse", role="nurse", email="v24-nurse@example.test"))
    session.add(User(id=1205, name="V24 Hospital Director", role="hospital_director", email="v24-director@example.test"))
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


def pass_controls(client: TestClient, headers: dict[str, str], *, only: set[str] | None = None, exclude: set[str] | None = None):
    dashboard = ok(client.get("/api/production-readiness/dashboard", headers=headers), "load readiness controls")
    for control in dashboard["controls"]:
        ref = control["controlRef"]
        if only is not None and ref not in only:
            continue
        if exclude and ref in exclude:
            continue
        if control["status"] == "passed":
            continue
        ok(client.patch(
            f"/api/production-readiness/controls/{ref}",
            headers=headers,
            json={
                "expectedVersion": control["version"],
                "status": "passed",
                "evidenceSummary": f"Synthetic verified evidence for {ref}",
                "reason": f"Synthetic v24 proof passed {ref}",
                "validDays": 180,
            },
        ), f"pass readiness control {ref}")


def complete_plan(mode: str, *, owner_subject: str = "v24-ops", clinical_subject: str = "v24-clinical") -> dict:
    return {
        "requestedMode": mode,
        "premisesRef": "reference-site",
        "serviceLine": "neurology",
        "scope": {
            "includedWorkflows": ["referral_intake", "patient_command", "hospital_today", "care_brief"],
            "maxConcurrentPatients": 5,
            "operatingWindow": "08:00-18:00",
        },
        "successCriteria": {
            "measures": {
                "unresolvedRedObservations": 0,
                "lostUpdates": 0,
                "criticalWorkflowAccuracyPercent": 100,
            }
        },
        "stopCriteria": {
            "decisionOwner": "Named pilot owner or safety lead",
            "triggers": ["identity mismatch", "red observation", "data integrity failure", "clinical owner requests stop"],
        },
        "rollbackPlan": {
            "owner": "V24 Operations",
            "steps": ["Stop LucyWorks pilot writes", "Return to existing workflow", "Reconcile evidence and outstanding work"],
            "recoveryPoint": "Last verified existing-system state",
            "communications": "Notify clinical lead, operations, governance and affected staff",
        },
        "integrationScope": ["pims-shadow", "lab-shadow"],
        "automationMode": "disabled",
        "accountableOwner": {"subject": owner_subject, "name": "V24 Operations", "role": "ops_manager"},
        "clinicalOwner": {"subject": clinical_subject, "name": "V24 Clinical Director", "role": "clinical_director"},
        "reason": f"Create controlled {mode} validation plan for v24 proof",
    }


try:
    with TestClient(app) as client:
        ops = login(client, 1201)
        clinical = login(client, 1202)
        governance = login(client, 1203)
        nurse = login(client, 1204)
        director = login(client, 1205)

        contracts = ok(client.get("/api/v24/pilots/contracts", headers=ops), "load pilot contracts")
        assert contracts["authorisationAcknowledgements"]["shadow"] == "AUTHORISE SHADOW MODE ONLY"
        assert contracts["rollbackAcknowledgement"] == "INITIATE PILOT ROLLBACK"
        assert len(contracts["uatScenarios"]) >= 10

        legacy = client.post("/api/shadow-mode/import-rows", headers=ops, json={"rows": []})
        assert legacy.status_code == 409, legacy.text
        assert legacy.json()["detail"]["code"] == "canonical_pilot_route_required"

        episode = ok(client.post(
            "/api/hospital-ops/episodes",
            headers=clinical,
            json={
                "episodeRef": "EP-PILOT-V24",
                "patientRef": "PAT-PILOT-V24",
                "patientName": "Bramble Pilot Proof",
                "premisesRef": "reference-site",
                "serviceLine": "neurology",
                "urgency": "urgent",
                "gates": {},
            },
        ), "create canonical pilot episode")["episode"]
        assert episode["phase"] == "referral_received"
        original_episode_version = episode["version"]

        shadow = ok(client.post("/api/v24/pilots", headers=ops, json=complete_plan("shadow")), "create shadow authority")
        shadow_ref = shadow["authority"]["authorityRef"]
        assert shadow["authority"]["status"] == "draft"
        assert shadow["authority"]["planVersion"] == 1
        assert len(shadow["uatScenarios"]) >= 10
        assert not shadow["gate"]["eligible"]

        stale = client.put(
            f"/api/v24/pilots/{shadow_ref}",
            headers=ops,
            json={"expectedVersion": 999, "scope": shadow["authority"]["scope"], "reason": "Prove stale plan protection"},
        )
        assert stale.status_code == 409, stale.text
        assert stale.json()["detail"]["code"] == "stale_pilot_authority"

        first_approval = ok(client.post(
            f"/api/v24/pilots/{shadow_ref}/approvals",
            headers=ops,
            json={
                "approvalType": "operational",
                "decision": "approved",
                "reason": "Operational owner approves the initial shadow boundary",
                "acknowledgement": "APPROVE PILOT CONTROL BOUNDARY",
            },
        ), "approve initial shadow plan")
        assert first_approval["approval"]["planVersion"] == 1

        changed_scope = dict(shadow["authority"]["scope"])
        changed_scope["maxConcurrentPatients"] = 4
        shadow = ok(client.put(
            f"/api/v24/pilots/{shadow_ref}",
            headers=ops,
            json={
                "expectedVersion": first_approval["command"]["authority"]["version"],
                "scope": changed_scope,
                "reason": "Reduce shadow scope after operational review",
            },
        ), "change shadow plan")
        assert shadow["authority"]["planVersion"] == 2
        assert any(item["code"] == "operational_approval_missing" for item in shadow["gate"]["blockers"])

        pass_controls(client, ops, only=set(SHADOW_REQUIRED))
        shadow = ok(client.post(
            f"/api/v24/pilots/{shadow_ref}/approvals",
            headers=ops,
            json={
                "approvalType": "operational",
                "decision": "approved",
                "reason": "Operational owner approves revised shadow scope and rollback controls",
                "acknowledgement": "APPROVE PILOT CONTROL BOUNDARY",
            },
        ), "approve revised shadow plan")["command"]
        gate = ok(client.post(f"/api/v24/pilots/{shadow_ref}/validate", headers=ops, json={}), "validate shadow eligibility")
        assert gate["eligible"], gate["blockers"]

        wrong_shadow_ack = client.post(
            f"/api/v24/pilots/{shadow_ref}/authorise",
            headers=director,
            json={
                "expectedVersion": shadow["authority"]["version"],
                "mode": "shadow",
                "reason": "Attempt shadow authorisation with wrong acknowledgement",
                "acknowledgement": "AUTHORISE LIVE",
            },
        )
        assert wrong_shadow_ack.status_code == 400, wrong_shadow_ack.text

        shadow = ok(client.post(
            f"/api/v24/pilots/{shadow_ref}/authorise",
            headers=director,
            json={
                "expectedVersion": shadow["authority"]["version"],
                "mode": "shadow",
                "reason": "Hospital director authorises non-interventional shadow comparison",
                "acknowledgement": "AUTHORISE SHADOW MODE ONLY",
            },
        ), "authorise shadow")
        assert shadow["authority"]["status"] == "authorised"
        shadow = ok(client.post(
            f"/api/v24/pilots/{shadow_ref}/start",
            headers=ops,
            json={"expectedVersion": shadow["authority"]["version"], "reason": "Start approved shadow validation run"},
        ), "start shadow")
        assert shadow["authority"]["status"] == "running"

        imported = ok(client.post(
            f"/api/v24/pilots/{shadow_ref}/shadow-comparisons",
            headers=ops,
            json={
                "reason": "Compare external shadow records with canonical patient state",
                "rows": [
                    {
                        "externalRef": "EXT-MATCH-V24",
                        "canonicalEpisodeRef": "EP-PILOT-V24",
                        "sourceSystem": "synthetic-pims",
                        "externalSnapshot": {
                            "patientRef": "PAT-PILOT-V24",
                            "phase": "referral_received",
                            "status": "active",
                            "ownerRole": "reception",
                        },
                    },
                    {
                        "externalRef": "EXT-IDENTITY-MISMATCH-V24",
                        "canonicalEpisodeRef": "EP-PILOT-V24",
                        "sourceSystem": "synthetic-pims",
                        "externalSnapshot": {
                            "patientRef": "PAT-WRONG-V24",
                            "phase": "referral_received",
                            "status": "active",
                            "ownerRole": "reception",
                        },
                    },
                ],
            },
        ), "import canonical shadow comparisons")
        comparisons = imported["command"]["shadowComparisons"]
        assert any(item["status"] == "matched" for item in comparisons)
        red = next(item for item in comparisons if item["severity"] == "red")
        assert "patient_identity_mismatch" in red["mismatchCodes"]
        assert any(item["code"] == "red_shadow_mismatches" for item in imported["command"]["gate"]["blockers"])

        reviewed = ok(client.post(
            f"/api/v24/pilots/{shadow_ref}/shadow-comparisons/{red['comparisonRef']}/review",
            headers=ops,
            json={
                "expectedVersion": red["version"],
                "decision": "rejected",
                "note": "Reject invalid external patient mapping and correct the source feed",
            },
        ), "review identity mismatch")
        assert reviewed["command"]["gate"]["summary"]["unresolvedRedComparisons"] == 0

        stopped = ok(client.post(
            f"/api/v24/pilots/{shadow_ref}/observations",
            headers=nurse,
            json={
                "severity": "red",
                "category": "identity",
                "summary": "External feed displayed an unsafe duplicate-patient association",
                "expectedBehaviour": "One canonical patient identity remains visible",
                "actualBehaviour": "The external source supplied an incorrect patient reference",
                "ownerRole": "ops_manager",
            },
        ), "record red pilot observation")
        assert stopped["pilotStopped"] is True
        assert stopped["command"]["authority"]["status"] == "stopped"
        red_observation = stopped["observation"]

        resolved = ok(client.patch(
            f"/api/v24/pilots/{shadow_ref}/observations/{red_observation['observationRef']}/resolve",
            headers=ops,
            json={"resolution": "Source mapping corrected and independently rechecked against canonical identity"},
        ), "resolve red pilot observation")
        shadow = resolved["command"]
        assert shadow["gate"]["summary"]["openRedObservations"] == 0

        shadow = ok(client.post(
            f"/api/v24/pilots/{shadow_ref}/authorise",
            headers=director,
            json={
                "expectedVersion": shadow["authority"]["version"],
                "mode": "shadow",
                "reason": "Reauthorise shadow validation after verified source correction",
                "acknowledgement": "AUTHORISE SHADOW MODE ONLY",
            },
        ), "reauthorise shadow after stop")
        shadow = ok(client.post(
            f"/api/v24/pilots/{shadow_ref}/start",
            headers=ops,
            json={"expectedVersion": shadow["authority"]["version"], "reason": "Restart corrected shadow validation"},
        ), "restart shadow")
        shadow = ok(client.post(
            f"/api/v24/pilots/{shadow_ref}/complete",
            headers=director,
            json={"expectedVersion": shadow["authority"]["version"], "reason": "Shadow validation completed with no unresolved red findings"},
        ), "complete shadow")
        assert shadow["authority"]["status"] == "completed"
        readiness = ok(client.get("/api/production-readiness/dashboard", headers=ops), "check shadow readiness evidence")
        shadow_control = next(item for item in readiness["controls"] if item["controlRef"] == "shadow.mode")
        assert shadow_control["status"] == "passed"

        live = ok(client.post("/api/v24/pilots", headers=ops, json=complete_plan("bounded_live")), "create bounded live authority")
        live_ref = live["authority"]["authorityRef"]
        pass_controls(client, ops, exclude={"pilot.bounded"})

        for scenario in live["uatScenarios"]:
            result = ok(client.put(
                f"/api/v24/pilots/{live_ref}/uat/{scenario['scenarioRef']}",
                headers=nurse,
                json={
                    "expectedVersion": scenario["version"],
                    "status": "passed",
                    "evidenceSummary": f"Synthetic user completed {scenario['scenarioCode']} successfully",
                    "reason": f"Record verified UAT outcome for {scenario['scenarioCode']}",
                },
            ), f"pass UAT {scenario['scenarioCode']}")
            live = result["command"]

        live = ok(client.post(
            f"/api/v24/pilots/{live_ref}/approvals",
            headers=clinical,
            json={
                "approvalType": "clinical",
                "decision": "approved",
                "reason": "Clinical director approves the human clinical authority boundary",
                "acknowledgement": "APPROVE PILOT CONTROL BOUNDARY",
            },
        ), "record clinical approval")["command"]
        live = ok(client.post(
            f"/api/v24/pilots/{live_ref}/approvals",
            headers=ops,
            json={
                "approvalType": "operational",
                "decision": "approved",
                "reason": "Operations approves scope, staffing, stop criteria and rollback plan",
                "acknowledgement": "APPROVE PILOT CONTROL BOUNDARY",
            },
        ), "record operational approval")["command"]
        live = ok(client.post(
            f"/api/v24/pilots/{live_ref}/approvals",
            headers=governance,
            json={
                "approvalType": "governance",
                "decision": "approved",
                "reason": "Governance approves evidence, privacy, safety and recovery controls",
                "acknowledgement": "APPROVE PILOT CONTROL BOUNDARY",
            },
        ), "record governance approval")["command"]
        assert live["gate"]["eligible"], live["gate"]["blockers"]
        assert live["gate"]["summary"]["criticalUatRemaining"] == 0

        wrong_live_ack = client.post(
            f"/api/v24/pilots/{live_ref}/authorise",
            headers=director,
            json={
                "expectedVersion": live["authority"]["version"],
                "mode": "bounded_live",
                "reason": "Attempt live pilot with incomplete acknowledgement",
                "acknowledgement": "AUTHORISE PILOT",
            },
        )
        assert wrong_live_ack.status_code == 400, wrong_live_ack.text

        live = ok(client.post(
            f"/api/v24/pilots/{live_ref}/authorise",
            headers=director,
            json={
                "expectedVersion": live["authority"]["version"],
                "mode": "bounded_live",
                "reason": "Hospital director authorises the bounded live pilot within reviewed controls",
                "acknowledgement": "AUTHORISE BOUNDED LIVE PILOT WITH HUMAN CLINICAL AUTHORITY",
            },
        ), "authorise bounded live")
        live = ok(client.post(
            f"/api/v24/pilots/{live_ref}/start",
            headers=ops,
            json={"expectedVersion": live["authority"]["version"], "reason": "Start bounded live pilot under named authority"},
        ), "start bounded live")
        assert live["authority"]["status"] == "running"

        live = ok(client.post(
            f"/api/v24/pilots/{live_ref}/stop",
            headers=nurse,
            json={"reason": "Front-line safety stop requested during bounded pilot proof"},
        ), "front-line safety stop")
        assert live["authority"]["status"] == "stopped"
        assert live["stopActionCreated"] is True

        live = ok(client.post(
            f"/api/v24/pilots/{live_ref}/rollback",
            headers=governance,
            json={
                "expectedVersion": live["authority"]["version"],
                "reason": "Execute documented rollback and reconcile all pilot evidence",
                "acknowledgement": "INITIATE PILOT ROLLBACK",
            },
        ), "initiate rollback")
        assert live["authority"]["status"] == "rollback"
        assert live["authority"]["rollbackAt"]

        integrity = ok(client.get("/api/evidence/integrity", headers=governance), "verify evidence chain")
        assert integrity["ok"] is True, integrity

        with Session(engine) as session:
            authorities = session.exec(select(PilotAuthorityV24)).all()
            approvals = session.exec(select(PilotApprovalV24)).all()
            actions = session.exec(select(PilotControlActionV24)).all()
            comparisons = session.exec(select(PilotShadowComparisonV24)).all()
            scenarios = session.exec(select(PilotUATScenarioV24).where(PilotUATScenarioV24.authority_ref == live_ref)).all()
            evidence = session.exec(select(EvidenceEvent).where(EvidenceEvent.source_module == "pilot-control-v24")).all()
            canonical = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == "EP-PILOT-V24")).one()
            assert len(authorities) == 2
            assert len(approvals) >= 5
            assert any(item.action_type == "pilot_stopped" for item in actions)
            assert any(item.action_type == "pilot_rollback_initiated" for item in actions)
            assert any(item.severity == "red" for item in comparisons)
            assert scenarios and all(item.status == "passed" for item in scenarios)
            assert evidence
            assert canonical.phase == "referral_received"
            assert canonical.status == "active"
            assert canonical.version == original_episode_version
            assert session.exec(select(ShadowRecord)).all() == []
            assert session.exec(select(MedicationOrder)).all() == []
            assert session.exec(select(MedicationAdministration)).all() == []
            assert session.exec(select(ClinicalNoteV8)).all() == []
            assert session.exec(select(EpisodeTransitionV9)).all() == []
            assert session.exec(select(EpisodeClosureV9)).all() == []
            pilot_control = session.exec(select(ReadinessControl).where(ReadinessControl.control_ref == "pilot.bounded")).one()
            assert pilot_control.status != "passed"

    print("BOUNDED_PILOT_CONTROL_V24_SMOKE_PASSED")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
