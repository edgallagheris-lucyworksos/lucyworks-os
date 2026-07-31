import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_v29_authority_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "hospital-pilot-v29-authority-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-v29-authority",
    "AUTH_AUDIENCE": "lucyworks-v29-authority-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
    "V26_CONTEXT_BOOTSTRAP_ENABLED": "false",
    "V27_CONFIGURATION_REQUIRED": "false",
})

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import SQLModel, Session

from app.database import engine
from app.main import app
from app.models import User
from app.operational_context_v26_models import SiteMembershipV26
from app.organisation_onboarding_v27_models import OnboardingSiteV27
from app.real_hospital_connection_v28_models import SpeechProviderV28

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)
with engine.begin() as connection:
    connection.execute(text("create table if not exists alembic_version (version_num varchar(64) not null)"))
    connection.execute(text("delete from alembic_version"))
    connection.execute(text("insert into alembic_version(version_num) values ('0023_hospital_pilot_v29')"))

with Session(engine) as session:
    session.add_all([
        User(id=2911, name="V29 Authority Director", role="hospital_director", email="authority-director@example.test"),
        User(id=2912, name="V29 Authority Clinical", role="clinical_director", email="authority-clinical@example.test"),
        OnboardingSiteV27(
            site_ref="hospital-v29-authority",
            organisation_ref="group-v29-authority",
            premises_ref="premises-v29-authority",
            name="V29 Authority Hospital",
            address={"line1": "1 Authority Way", "city": "Bristol", "postcode": "BS1 2AA"},
            regulator_premises_refs=["RCVS-V29-AUTHORITY"],
            accountable_director_subject="local-user:2911",
            accountable_director_name="V29 Authority Director",
            clinical_governance_subject="local-user:2912",
            clinical_governance_name="V29 Authority Clinical",
            status="approved",
            active_release_ref="release-v29-authority",
            updated_by_subject="local-user:2911",
            updated_by_name="V29 Authority Director",
            updated_by_role="hospital_director",
        ),
        SiteMembershipV26(
            membership_ref="membership-v29-authority-director",
            subject="local-user:2911",
            actor_id="2911",
            organisation_ref="group-v29-authority",
            site_ref="hospital-v29-authority",
            premises_ref="premises-v29-authority",
            role="hospital_director",
            status="active",
            is_primary=True,
            granted_by_subject="local-user:2911",
        ),
        SiteMembershipV26(
            membership_ref="membership-v29-authority-clinical",
            subject="local-user:2912",
            actor_id="2912",
            organisation_ref="group-v29-authority",
            site_ref="hospital-v29-authority",
            premises_ref="premises-v29-authority",
            role="clinical_director",
            status="active",
            is_primary=True,
            granted_by_subject="local-user:2911",
        ),
        SpeechProviderV28(
            provider_ref="provider-v29-authority",
            organisation_ref="group-v29-authority",
            site_ref="hospital-v29-authority",
            name="V29 Authority Provider",
            provider_type="browser",
            processing_region="GB",
            supports_streaming=True,
            supports_word_confidence=True,
            raw_audio_retention=False,
            configuration={},
            status="approved",
            last_test_status="passed",
            created_by_subject="local-user:2911",
            updated_by_subject="local-user:2911",
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
        director = login(client, 2911)
        clinical = login(client, 2912)

        unknown_field = client.post("/api/v29/pilot-lab/speech/adapters", headers=director, json={
            "organisationRef": "group-v29-authority",
            "siteRef": "hospital-v29-authority",
            "providerRef": "provider-v29-authority",
            "name": "Strict adapter",
            "hiddenAudioUpload": "must-not-be-accepted",
        })
        assert unknown_field.status_code == 422, unknown_field.text

        terms = ok(client.post("/api/v29/pilot-lab/terminology-packs", headers=director, json={
            "organisationRef": "group-v29-authority",
            "siteRef": "hospital-v29-authority",
            "name": "Authority terminology",
            "releaseLabel": "v1",
        }), "create terminology")["pack"]
        self_approval = client.post(
            f"/api/v29/pilot-lab/terminology-packs/{terms['pack_ref']}/approve",
            headers=director,
            json={"expectedVersion": terms["version"], "reason": "Creator attempts self approval."},
        )
        assert self_approval.status_code == 403 or self_approval.status_code == 409, self_approval.text
        approved = ok(client.post(
            f"/api/v29/pilot-lab/terminology-packs/{terms['pack_ref']}/approve",
            headers=clinical,
            json={"expectedVersion": terms["version"], "reason": "Independent clinical terminology review."},
        ), "independent terminology approval")["pack"]
        assert approved["status"] == "approved"

        simulator = ok(client.post("/api/v29/pilot-lab/simulators", headers=director, json={
            "organisationRef": "group-v29-authority",
            "siteRef": "hospital-v29-authority",
            "connectorType": "laboratory",
            "name": "Authority synthetic lab",
        }), "create simulator")["simulator"]
        simulator = ok(client.post(
            f"/api/v29/pilot-lab/simulators/{simulator['simulator_ref']}/test",
            headers=director,
            json={"expectedVersion": simulator["version"], "reason": "Prove simulator isolation."},
        ), "test simulator")["simulator"]

        adapter = ok(client.post("/api/v29/pilot-lab/speech/adapters", headers=director, json={
            "organisationRef": "group-v29-authority",
            "siteRef": "hospital-v29-authority",
            "providerRef": "provider-v29-authority",
            "name": "Authority adapter",
            "adapterType": "browser",
            "processingLocation": "device",
        }), "create adapter")["adapter"]
        failed_adapter = ok(client.post(
            f"/api/v29/pilot-lab/speech/adapters/{adapter['adapter_ref']}/test",
            headers=director,
            json={
                "expectedVersion": adapter["version"],
                "deviceDiagnostics": {"microphonePermission": "denied", "secureContext": True, "online": True, "speechRecognition": True},
                "measuredLatencyMs": 100,
                "reason": "Prove denied microphone blocks adapter readiness.",
            },
        ), "failed adapter test")["adapter"]
        assert failed_adapter["last_test_status"] == "failed"

        pilot = ok(client.post("/api/v29/pilot-lab/pilots", headers=director, json={
            "organisationRef": "group-v29-authority",
            "siteRef": "hospital-v29-authority",
            "name": "Authority bounded pilot",
            "mode": "synthetic",
            "caseLimit": 1,
            "allowedProviderRefs": ["provider-v29-authority"],
            "allowedSimulatorRefs": [simulator["simulator_ref"]],
            "stopCriteria": {"maxRedIncidents": 0, "minimumAccuracy": 0.75, "minimumAccuracySamples": 5, "maxOpenReconciliation": 3},
        }), "create pilot")["pilot"]
        pilot = ok(client.post(
            f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/approve",
            headers=director,
            json={"expectedVersion": pilot["version"], "approvalType": "operations", "reason": "Operations approval."},
        ), "ops approval")["pilot"]
        same_person_clinical = client.post(
            f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/approve",
            headers=director,
            json={"expectedVersion": pilot["version"], "approvalType": "clinical", "reason": "Must not self approve both roles."},
        )
        assert same_person_clinical.status_code == 403 or same_person_clinical.status_code == 409, same_person_clinical.text
        pilot = ok(client.post(
            f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/approve",
            headers=clinical,
            json={"expectedVersion": pilot["version"], "approvalType": "clinical", "reason": "Independent clinical approval."},
        ), "clinical approval")["pilot"]

        not_ready = ok(client.post("/api/v29/pilot-lab/readiness/assess", headers=director, json={
            "siteRef": "hospital-v29-authority",
            "pilotRef": pilot["pilot_ref"],
            "deviceDiagnostics": {"microphonePermission": "denied", "secureContext": False, "online": False},
            "backupVerified": False,
            "restoreVerified": False,
        }), "not ready assessment")["assessment"]
        assert not_ready["overall_status"] == "NOT_READY"
        activation = client.post(
            f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/activate",
            headers=director,
            json={
                "expectedVersion": pilot["version"],
                "readinessAssessmentRef": not_ready["assessment_ref"],
                "restrictionsAcknowledged": True,
                "reason": "Must not activate against NOT_READY evidence.",
            },
        )
        assert activation.status_code == 409, activation.text
        assert activation.json()["detail"]["code"] == "pilot_not_ready"

        red = ok(client.post(
            f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/incidents",
            headers=clinical,
            json={
                "severity": "red",
                "category": "authority_stop_test",
                "synthetic": True,
                "description": "Controlled red incident.",
                "immediateAction": "Stop pilot activity and preserve urgent care.",
            },
        ), "red incident")
        stopped = red["pilot"]
        assert stopped["status"] == "stopped"
        urgent = ok(client.post(
            f"/api/v29/pilot-lab/pilots/{pilot['pilot_ref']}/cases/start",
            headers=clinical,
            json={"expectedVersion": stopped["version"], "episodeRef": "EP-V29-AUTH-URGENT", "patientRef": "PAT-V29-AUTH-URGENT", "urgentAccess": True},
        ), "urgent preserved")
        assert urgent["urgentAccessPreserved"] is True
        assert urgent["pilotApplied"] is False

    print("\n--- V29 STRICT AUTHORITY AND URGENT ACCESS TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
