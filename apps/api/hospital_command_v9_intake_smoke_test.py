import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_referral_intake_v9_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "referral-intake-v9-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-referral-intake-v9",
    "AUTH_AUDIENCE": "lucyworks-referral-intake-v9-api",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from app.database import engine
from app.detailed_hospital_models import PatientClinicalRecordV8
from app.main import app
from app.models import User

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def create(client: TestClient, auth: dict[str, str], number: int, service: str, urgency: str) -> dict:
    response = client.post("/api/v9/referrals", headers=auth, json={
        "episode_ref": f"EP-V9-Q-{number}",
        "referral_ref": f"REF-V9-Q-{number}",
        "patient_ref": f"PAT-V9-Q-{number}",
        "premises_ref": "bvs-bristol",
        "source_type": "referring_vet",
        "source_organisation": f"Practice {number}",
        "source_contact_name": f"Vet {number}",
        "requested_service": service,
        "presenting_problem": f"Synthetic presenting problem {number}",
        "clinical_summary": "Queue and filtering validation",
        "urgency": urgency,
        "reason": "Create canonical referral worklist row",
    })
    assert response.status_code == 200, response.text
    return response.json()


try:
    with Session(engine) as session:
        session.add_all([
            User(id=1, name="Ari Admin", role="admin", email="admin@example.test"),
            User(id=2, name="Cal Clinician", role="clinician", email="clinician@example.test"),
            PatientClinicalRecordV8(patient_ref="PAT-V9-Q-1", display_name="Queue Dog", species="dog"),
            PatientClinicalRecordV8(patient_ref="PAT-V9-Q-2", display_name="Queue Cat", species="cat"),
            PatientClinicalRecordV8(patient_ref="PAT-V9-Q-3", display_name="Queue Rabbit", species="rabbit"),
        ])
        session.commit()

    with TestClient(app) as client:
        admin = login(client, 1)
        clinician = login(client, 2)
        create(client, admin, 1, "neurology", "urgent")
        create(client, admin, 2, "internal_medicine", "routine")
        create(client, admin, 3, "neurology", "emergency")

        accepted = client.patch("/api/v9/referrals/REF-V9-Q-1", headers=clinician, json={
            "expected_version": 1,
            "status": "accepted",
            "reason": "Clinical service accepted referral",
        })
        assert accepted.status_code == 200, accepted.text
        needs_info = client.patch("/api/v9/referrals/REF-V9-Q-2", headers=clinician, json={
            "expected_version": 1,
            "status": "needs_information",
            "reason": "Previous imaging report required",
        })
        assert needs_info.status_code == 200, needs_info.text

        all_rows = client.get("/api/v9/referrals", headers=admin)
        assert all_rows.status_code == 200, all_rows.text
        assert all_rows.json()["count"] == 3
        assert {row["patientName"] for row in all_rows.json()["items"]} == {"Queue Dog", "Queue Cat", "Queue Rabbit"}

        accepted_rows = client.get("/api/v9/referrals?status=accepted", headers=clinician)
        assert accepted_rows.status_code == 200, accepted_rows.text
        assert accepted_rows.json()["count"] == 1
        assert accepted_rows.json()["items"][0]["referral_ref"] == "REF-V9-Q-1"
        assert accepted_rows.json()["items"][0]["episodePhase"] == "referral_received"

        neurology = client.get("/api/v9/referrals?requested_service=neurology", headers=admin)
        assert neurology.status_code == 200, neurology.text
        assert neurology.json()["count"] == 2

        emergency = client.get("/api/v9/referrals?urgency=emergency", headers=admin)
        assert emergency.status_code == 200, emergency.text
        assert emergency.json()["count"] == 1
        assert emergency.json()["items"][0]["patient_ref"] == "PAT-V9-Q-3"

        detail = client.get("/api/v9/referrals/REF-V9-Q-2", headers=clinician)
        assert detail.status_code == 200, detail.text
        assert detail.json()["referral"]["status"] == "needs_information"
        assert detail.json()["patient"]["display_name"] == "Queue Cat"
        assert detail.json()["episode"]["episode_ref"] == "EP-V9-Q-2"

    with TestClient(app) as anonymous_client:
        anonymous_client.cookies.clear()
        denied = anonymous_client.get("/api/v9/referrals")
        assert denied.status_code == 401, denied.text

    print("Canonical referral intake queue, filters, detail and authentication v9 OK")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
