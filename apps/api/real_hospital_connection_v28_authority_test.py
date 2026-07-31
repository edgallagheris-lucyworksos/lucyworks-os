import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_v28_authority_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "real-hospital-connection-v28-authority-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-v28-authority",
    "AUTH_AUDIENCE": "lucyworks-v28-authority-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
    "V26_CONTEXT_BOOTSTRAP_ENABLED": "false",
    "V27_CONFIGURATION_REQUIRED": "false",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from app.database import engine
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app
from app.models import User
from app.operational_context_v26_models import SiteMembershipV26
from app.organisation_onboarding_v27_models import OnboardingSiteV27

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    session.add_all([
        User(id=2811, name="V28 Sequence Director", role="hospital_director", email="sequence-director@example.test"),
        User(id=2812, name="V28 Sequence Clinician", role="clinician", email="sequence-clinician@example.test"),
        OnboardingSiteV27(
            site_ref="hospital-v28-authority",
            organisation_ref="group-v28-authority",
            premises_ref="premises-v28-authority",
            name="V28 Authority Hospital",
            address={"line1": "2 Hospital Way", "city": "Bristol", "postcode": "BS1 2AA"},
            regulator_premises_refs=["RCVS-V28-AUTHORITY"],
            accountable_director_subject="local-user:2811",
            accountable_director_name="V28 Sequence Director",
            clinical_governance_subject="local-user:2811",
            clinical_governance_name="V28 Sequence Director",
            status="approved",
            active_release_ref="release-v28-authority",
            updated_by_subject="local-user:2811",
            updated_by_name="V28 Sequence Director",
            updated_by_role="hospital_director",
        ),
        SiteMembershipV26(
            membership_ref="membership-v28-authority-director",
            subject="local-user:2811",
            actor_id="2811",
            organisation_ref="group-v28-authority",
            site_ref="hospital-v28-authority",
            premises_ref="premises-v28-authority",
            role="hospital_director",
            status="active",
            is_primary=True,
            granted_by_subject="local-user:2811",
        ),
        SiteMembershipV26(
            membership_ref="membership-v28-authority-clinician",
            subject="local-user:2812",
            actor_id="2812",
            organisation_ref="group-v28-authority",
            site_ref="hospital-v28-authority",
            premises_ref="premises-v28-authority",
            role="clinician",
            status="active",
            is_primary=True,
            granted_by_subject="local-user:2811",
        ),
        CanonicalEpisodeState(
            episode_ref="EP-V28-AUTHORITY-001",
            patient_ref="PAT-V28-AUTHORITY-001",
            patient_name="V28 Sequence Patient",
            premises_ref="premises-v28-authority",
            service_line="neurology",
            urgency="urgent",
            phase="consult",
            status="active",
            owner_role="clinician",
            owner_subject="local-user:2812",
            current_area_ref="consult-2",
            next_action="Test governed speech sequence",
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
        director = login(client, 2811)
        clinician = login(client, 2812)

        provider = ok(client.post("/api/v28/deployment/speech/providers", headers=director, json={
            "organisationRef": "group-v28-authority",
            "siteRef": "hospital-v28-authority",
            "name": "Authority browser provider",
            "providerType": "browser",
            "processingRegion": "GB",
            "language": "en-GB",
            "supportsStreaming": True,
            "supportsWordConfidence": True,
            "rawAudioRetention": False,
        }), "create provider")["provider"]
        tested = ok(client.post(
            f"/api/v28/deployment/speech/providers/{provider['provider_ref']}/test",
            headers=director,
            json={"expectedVersion": provider["version"], "reason": "Test browser provider for authority proof."},
        ), "test provider")["provider"]
        approved = ok(client.post(
            f"/api/v28/deployment/speech/providers/{provider['provider_ref']}/approve",
            headers=director,
            json={"expectedVersion": tested["version"], "reason": "Approve browser provider for sequence proof."},
        ), "approve provider")["provider"]

        raw_audio = client.post("/api/v28/deployment/speech/sessions", headers=clinician, json={
            "providerRef": approved["provider_ref"],
            "siteRef": "hospital-v28-authority",
            "episodeRef": "EP-V28-AUTHORITY-001",
            "noticeAcknowledged": True,
            "rawAudioRetained": True,
        })
        assert raw_audio.status_code == 409, raw_audio.text

        unexpected = client.post("/api/v28/deployment/speech/sessions", headers=clinician, json={
            "providerRef": approved["provider_ref"],
            "siteRef": "hospital-v28-authority",
            "episodeRef": "EP-V28-AUTHORITY-001",
            "noticeAcknowledged": True,
            "rawAudioRetained": False,
            "hiddenAudioUpload": "must-not-be-accepted",
        })
        assert unexpected.status_code == 422, unexpected.text

        started = ok(client.post("/api/v28/deployment/speech/sessions", headers=clinician, json={
            "providerRef": approved["provider_ref"],
            "siteRef": "hospital-v28-authority",
            "episodeRef": "EP-V28-AUTHORITY-001",
            "noticeAcknowledged": True,
            "rawAudioRetained": False,
            "deviceDiagnostics": {"microphonePermission": "granted"},
        }), "start session")["session"]

        initial_gap = client.post(
            f"/api/v28/deployment/speech/sessions/{started['session_ref']}/segments",
            headers=clinician,
            json={
                "expectedVersion": started["version"],
                "sequence": 2,
                "text": "This must not bypass sequence one.",
                "isFinal": True,
            },
        )
        assert initial_gap.status_code == 409, initial_gap.text
        assert initial_gap.json()["detail"]["code"] == "speech_segment_sequence_gap"
        assert initial_gap.json()["detail"]["expectedSequence"] == 1

        first = ok(client.post(
            f"/api/v28/deployment/speech/sessions/{started['session_ref']}/segments",
            headers=clinician,
            json={
                "expectedVersion": started["version"],
                "sequence": 1,
                "text": "History: owner reports acute weakness.",
                "confidence": 0.94,
                "isFinal": True,
            },
        ), "append first segment")

        later_gap = client.post(
            f"/api/v28/deployment/speech/sessions/{started['session_ref']}/segments",
            headers=clinician,
            json={
                "expectedVersion": first["session"]["version"],
                "sequence": 3,
                "text": "This must not skip sequence two.",
                "isFinal": True,
            },
        )
        assert later_gap.status_code == 409, later_gap.text
        assert later_gap.json()["detail"]["expectedSequence"] == 2

        duplicate = ok(client.post(
            f"/api/v28/deployment/speech/sessions/{started['session_ref']}/segments",
            headers=clinician,
            json={
                "expectedVersion": first["session"]["version"],
                "sequence": 1,
                "text": "History: owner reports acute weakness.",
                "confidence": 0.94,
                "isFinal": True,
            },
        ), "idempotent retry")
        assert duplicate["idempotent"] is True

    print("\n--- V28 STRICT SPEECH SEQUENCE AND REQUEST AUTHORITY TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
