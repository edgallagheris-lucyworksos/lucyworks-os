import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_v29_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "hospital-pilot-v29-secret-long-enough-for-tests",
    "AUTH_ISSUER": "lucyworks-v29",
    "AUTH_AUDIENCE": "lucyworks-v29-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
    "V26_CONTEXT_BOOTSTRAP_ENABLED": "false",
    "V27_CONFIGURATION_REQUIRED": "false",
    "V28_CONNECTION_CONTROL_REQUIRED": "false",
    "V29_PILOT_CONTROL_REQUIRED": "false",
})

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import SQLModel, Session, select

from app.database import engine
from app.evidence_service import verify_event_chain
from app.hospital_pilot_v29_models import (
    ExportArtifactV29,
    HospitalPilotV29,
    IntegrationSimulatorV29,
    PilotMeasurementV29,
    ReadinessAssessmentV29,
    SimulatorRunV29,
    SpeechAdapterV29,
    VeterinaryTerminologyPackV29,
)
from app.main import app
from app.models import User
from app.operational_context_v26_models import SiteMembershipV26
from app.organisation_onboarding_v27_models import OnboardingSiteV27
from app.real_hospital_connection_v28_models import IntegrationEventV28, ReconciliationItemV28, SpeechProviderV28

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)
with engine.begin() as connection:
    connection.execute(text("create table if not exists alembic_version (version_num varchar(64) not null)"))
    connection.execute(text("delete from alembic_version"))
    connection.execute(text("insert into alembic_version(version_num) values ('0023_hospital_pilot_v29')"))

with Session(engine) as session:
    session.add_all([
        User(id=2901, name="V29 Operations Director", role="hospital_director", email="v29-ops@example.test"),
        User(id=2902, name="V29 Clinical Director", role="clinical_director", email="v29-clinical@example.test"),
        User(id=2903, name="V29 Pilot Clinician", role="clinician", email="v29-clinician@example.test"),
        OnboardingSiteV27(
            site_ref="hospital-v29",
            organisation_ref="group-v29",
            premises_ref="premises-v29",
            name="V29 Referral Hospital",
            address={"line1": "29 Hospital Way", "city": "Bristol", "postcode": "BS1 1AA"},
            regulator_premises_refs=["RCVS-V29"],
            accountable_director_subject="local-user:2901",
            accountable_director_name="V29 Operations Director",
            clinical_governance_subject="local-user:2902",
            clinical_governance_name="V29 Clinical Director",
            status="approved",
            active_release_ref="release-v29",
            updated_by_subject="local-user:2901",
            updated_by_name="V29 Operations Director",
            updated_by_role="hospital_director",
        ),
        SiteMembershipV26(
            membership_ref="membership-v29-ops",
            subject="local-user:2901",
            actor_id="2901",
            organisation_ref="group-v29",
            site_ref="hospital-v29",
            premises_ref="premises-v29",
            role="hospital_director",
            status="active",
            is_primary=True,
            granted_by_subject="local-user:2901",
        ),
        SiteMembershipV26(
            membership_ref="membership-v29-clinical",
            subject="local-user:2902",
            actor_id="2902",
            organisation_ref="group-v29",
            site_ref="hospital-v29",
            premises_ref="premises-v29",
            role="clinical_director",
            status="active",
            is_primary=True,
            granted_by_subject="local-user:2901",
        ),
        SiteMembershipV26(
            membership_ref="membership-v29-clinician",
            subject="local-user:2903",
            actor_id="2903",
            organisation_ref="group-v29",
            site_ref="hospital-v29",
            premises_ref="premises-v29",
            role="clinician",
            status="active",
            is_primary=True,
            granted_by_subject="local-user:2901",
        ),
        SpeechProviderV28(
            provider_ref="provider-v29-browser",
            organisation_ref="group-v29",
            site_ref="hospital-v29",
            name="V29 approved browser provider",
            provider_type="browser",
            processing_region="GB",
            language="en-GB",
            supports_streaming=True,
            supports_word_confidence=True,
            raw_audio_retention=False,
            configuration={},
            status="approved",
            last_test_status="passed",
            last_test_detail="Approved v28 browser provider for v29 proof",
            approved_by_subject="local-user:2901",
            created_by_subject="local-user:2901",
            updated_by_subject="local-user:2901",
        ),
    ])
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
        ops = login(client, 2901)
        clinical = login(client, 2902)
        clinician = login(client, 2903)

        adapter = ok(client.post("/api/v29/pilot-lab/speech/adapters", headers=ops, json={
            "organisationRef": "group-v29",
            "siteRef": "hospital-v29",
            "providerRef": "provider-v29-browser",
            "name": "V29 browser streaming adapter",
            "adapterType": "browser",
            "processingLocation": "device",
            "protocol": "browser_recognition",
            "reconnectEnabled": True,
            "maxReconnectAttempts": 5,
            "reconnectBackoffMs": 1000,
            "minimumConfidence": 0.78,
            "maximumLatencyMs": 2000,
            "networkRequirements": {"minimumMbps": 2},
            "configuration": {"rawAudioRetention": False},
        }), "create adapter")["adapter"]
        adapter = ok(client.post(
            f"/api/v29/pilot-lab/speech/adapters/{adapter['adapter_ref']}/test",
            headers=ops,
            json={
                "expectedVersion": adapter["version"],
                "deviceDiagnostics": {
                    "microphonePermission": "granted",
                    "secureContext": True,
                    "online": True,
                    "speechRecognition": True,
                    "audioDeviceLabel": "Synthetic microphone",
                },
                "measuredLatencyMs": 250,
                "reason": "Prove device, provider, latency, privacy and reconnect controls.",
            },
        ), "test adapter")["adapter"]
        assert adapter["last_test_status"] == "passed"

        terms = ok(client.post("/api/v29/pilot-lab/terminology-packs", headers=ops, json={
            "organisationRef": "group-v29",
            "siteRef": "hospital-v29",
            "name": "V29 referral terminology",
            "releaseLabel": "v1",
            "language": "en-GB",
            "categories": {},
            "correctionRules": [],
            "abbreviations": {},
            "siteTerms": ["V29 Neurology"],
            "evidenceRefs": ["terms-source-v29"],
        }), "create terms")["pack"]
        terms = ok(client.post(
            f"/api/v29/pilot-lab/terminology-packs/{terms['pack_ref']}/approve",
            headers=clinical,
            json={"expectedVersion": terms["version"], "reason": "Independent clinical review completed."},
        ), "approve terms")["pack"]
        assert terms["status"] == "approved"
        normalised = ok(client.post("/api/v29/pilot-lab/terminology/normalise", headers=clinician, json={
            "siteRef": "hospital-v29",
            "text": "Owner reports meta cam and a hemi laminectomy was discussed.",
        }), "normalise terminology")
        assert "Metacam" in normalised["proposedText"]
        assert "hemilaminectomy" in normalised["proposedText"]
        assert normalised["requiresHumanReview"] is True

        simulator = ok(client.post("/api/v29/pilot-lab/simulators", headers=ops, json={
            "organisationRef": "group-v29",
            "siteRef": "hospital-v29",
            "connectorType": "patient_management",
            "name": "V29 synthetic PMS",
            "seed": 29,
            "defaultLatencyMs": 50,
            "configuration": {"syntheticOnly": True, "writeBack": False},
        }), "create simulator")["simulator"]
        simulator = ok(client.post(
            f"/api/v29/pilot-lab/simulators/{simulator['simulator_ref']}/test",
            headers=ops,
            json={"expectedVersion": simulator["version"], "reason": "Prove synthetic isolation and no-write controls."},
        ), "test simulator")["simulator"]
        assert simulator["last_test_status"] == "passed"

        scenario = ok(client.post(
            f"/api/v29/pilot-lab/simulators/{simulator['simulator_ref']}/scenarios",
            headers=ops,
            json={
                "scenarioCode": "incorrect-id-v29",
                "title": "Incorrect patient identifier",
                "faultType": "incorrect_identifier",
                "eventType": "synthetic_patient_update",
                "eventCount": 1,
                "parameters": {},
                "expectedDetection": "Visible reconciliation without canonical attachment.",
                "critical": True,
            },
        ), "create scenario")["scenario"]
        run = ok(client.post(
            f"/api/v29/pilot-lab/scenarios/{scenario['scenario_ref']}/run",
            headers=ops,
            json={"reason": "Prove incorrect synthetic identifiers cannot attach to a patient."},
        ), "run scenario")["run"]
        assert run["detection_status"] == "passed"
        assert run["result"]["canonicalAttachmentCount"] == 0

        pilot = ok(client.post("/api/v29/pilot-lab/pilots", headers=ops, json={
            "organisationRef": "group-v29",
            "siteRef": "hospital-v29",
            "name": "V29 bounded referral pilot",
            "department": "referral",
            "serviceLine": "neurology",
            "mode": "synthetic",
            "caseLimit": 3,
            "allowedDeviceRefs": ["Synthetic microphone"],
            "allowedProviderRefs": ["provider-v29-browser"],
            "allowedSimulatorRefs": [simulator["simulator_ref"]],
            "successCriteria": {"minimumAccuracy": 0.9, "minimumAverageSecondsSaved": 60},
            "stopCriteria": {"maxRedIncidents": 0, "minimumAccuracy": 0.75, "minimumAccuracySamples": 5, "maxOpenReconciliation": 3},
            "rollbackPlan": {"action": "Return to existing hospital workflow", "urgentAccess": "preserved"},
            "clinicalOwnerSubject": "local-user:2902",
            "clinicalOwnerName": "V29 Clinical Director",
        }), "create pilot")["pilot"]
        pilot = ok(client.post(
            f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/approve",
            headers=ops,
            json={"expectedVersion": pilot["version"], "approvalType": "operations", "reason": "Operations scope and rollback approved."},
        ), "ops approve")["pilot"]
        pilot = ok(client.post(
            f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/approve",
            headers=clinical,
            json={"expectedVersion": pilot["version"], "approvalType": "clinical", "reason": "Clinical safety and review boundaries approved."},
        ), "clinical approve")["pilot"]

        readiness = ok(client.post("/api/v29/pilot-lab/readiness/assess", headers=ops, json={
            "siteRef": "hospital-v29",
            "pilotRef": pilot["pilot_ref"],
            "deviceDiagnostics": {
                "microphonePermission": "granted",
                "secureContext": True,
                "online": True,
                "speechRecognition": True,
                "audioDeviceLabel": "Synthetic microphone",
            },
            "backupVerified": True,
            "restoreVerified": True,
        }), "readiness")["assessment"]
        assert readiness["overall_status"] in {"READY", "READY_WITH_RESTRICTIONS"}, readiness
        pilot = ok(client.post(
            f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/activate",
            headers=ops,
            json={
                "expectedVersion": pilot["version"],
                "readinessAssessmentRef": readiness["assessment_ref"],
                "restrictionsAcknowledged": True,
                "reason": "Activate against recorded independent approvals and readiness.",
            },
        ), "activate pilot")["pilot"]
        assert pilot["status"] == "active"

        started = ok(client.post(
            f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/cases/start",
            headers=clinician,
            json={"expectedVersion": pilot["version"], "episodeRef": "EP-V29-001", "patientRef": "PAT-V29-001", "urgentAccess": False},
        ), "start pilot case")
        assert started["pilotApplied"] is True
        pilot = started["pilot"]

        for index in range(5):
            measured = ok(client.post(
                f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/measurements",
                headers=clinician,
                json={
                    "episodeRef": f"EP-V29-{index + 1:03d}",
                    "synthetic": True,
                    "metricType": "transcription_accuracy",
                    "value": 0.60,
                    "unit": "ratio",
                    "metadata": {"reviewed": True},
                },
            ), f"measurement {index + 1}")
            pilot = measured["pilot"]
        assert pilot["status"] == "stopped"
        assert "accuracy" in (pilot["stopped_reason"] or "")

        urgent = ok(client.post(
            f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/cases/start",
            headers=clinician,
            json={"expectedVersion": pilot["version"], "episodeRef": "EP-V29-URGENT", "patientRef": "PAT-V29-URGENT", "urgentAccess": True},
        ), "urgent bypass")
        assert urgent["pilotApplied"] is False
        assert urgent["urgentAccessPreserved"] is True

        dashboard = ok(client.get(f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/dashboard", headers=ops), "dashboard")
        assert dashboard["summary"]["averageTranscriptionAccuracy"] == 0.6
        vendor = ok(client.post("/api/v29/pilot-lab/exports/vendor-spec", headers=ops, json={"siteRef": "hospital-v29", "pilotRef": pilot["pilot_ref"]}), "vendor export")["artifact"]
        deployment = ok(client.post("/api/v29/pilot-lab/exports/deployment-pack", headers=ops, json={"siteRef": "hospital-v29", "pilotRef": pilot["pilot_ref"]}), "deployment export")["artifact"]
        assert vendor["content"]["safetyBoundary"]["writeBack"] is False
        assert deployment["content"]["stopProcedure"]["urgentPatientAccess"].startswith("preserved")

        centre = ok(client.get("/api/v29/pilot-lab/control-centre?siteRef=hospital-v29", headers=ops), "control centre")
        assert centre["summary"]["testedAdapters"] == 1
        assert centre["summary"]["approvedTerminologyPacks"] == 1
        assert centre["summary"]["testedSimulators"] == 1
        assert centre["summary"]["stoppedPilots"] == 1

        integrity = verify_event_chain(Session(engine))
        assert integrity["ok"] is True, integrity

    with Session(engine) as session:
        assert session.exec(select(SpeechAdapterV29)).one().last_test_status == "passed"
        assert session.exec(select(VeterinaryTerminologyPackV29)).one().status == "approved"
        assert session.exec(select(IntegrationSimulatorV29)).one().last_test_status == "passed"
        assert session.exec(select(SimulatorRunV29)).one().detection_status == "passed"
        assert session.exec(select(ReadinessAssessmentV29)).one().overall_status in {"READY", "READY_WITH_RESTRICTIONS"}
        assert session.exec(select(HospitalPilotV29)).one().status == "stopped"
        assert len(session.exec(select(PilotMeasurementV29)).all()) == 5
        assert len(session.exec(select(ExportArtifactV29)).all()) == 2
        events = session.exec(select(IntegrationEventV28)).all()
        assert events and all(row.patient_ref is None and row.episode_ref is None and row.direction == "simulated_inbound" for row in events)
        reconciliations = session.exec(select(ReconciliationItemV28)).all()
        assert reconciliations and all(row.entity_type == "synthetic_test_entity" for row in reconciliations)

    print("\n--- HOSPITAL PILOT AND INTEGRATION SIMULATOR V29 SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
