import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_auth_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_JWT_SECRET": "smoke-test-secret-that-is-long-and-not-for-production",
    "AUTH_ISSUER": "lucyworks-smoke",
    "AUTH_AUDIENCE": "lucyworks-smoke-api",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def login(client: TestClient, user_id: int) -> tuple[dict, dict[str, str]]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user"]["verified"] is True
    return data["user"], {"Authorization": f"Bearer {data['accessToken']}"}


try:
    with TestClient(app) as client:
        unauthenticated = client.get("/api/evidence/events")
        assert unauthenticated.status_code == 401, unauthenticated.text
        print("Protected evidence rejects anonymous caller OK")

        senior_user, senior_headers = login(client, 1)
        clinician_user, clinician_headers = login(client, 2)
        assert senior_user["role"] == "ops_manager"
        assert clinician_user["role"] == "clinician"

        me = client.get("/api/auth/me", headers=senior_headers)
        assert me.status_code == 200, me.text
        assert me.json()["user"]["authSource"] == "local_signed_token"
        print("Signed token verification OK")

        spoofed = client.post("/api/evidence/events", headers=clinician_headers, json={
            "eventType": "decision",
            "patientCaseId": "auth-case-1",
            "referralEpisodeId": "auth-episode-1",
            "actorName": "Fake Clinical Director",
            "actorRole": "clinical_director",
            "actorAuthSource": "payload_forged",
            "professionalRole": "clinical_director",
            "action": "red-risk decision",
            "reason": "identity smoke test",
            "justification": "verify server actor override",
            "riskLevel": "red",
            "supervisorRequired": True,
            "supervisorApprovalStatus": "pending",
            "sourceModule": "auth-smoke-test",
            "idempotencyKey": "auth-smoke-red-event",
        })
        assert spoofed.status_code == 200, spoofed.text
        event = spoofed.json()["event"]
        assert event["actorName"] == clinician_user["name"], event
        assert event["actorRole"] == "clinician", event
        assert event["actorAuthSource"] == "local_signed_token", event
        print("Request-body actor spoofing blocked OK")

        approvals = client.get("/api/evidence/approvals?status=pending", headers=clinician_headers)
        assert approvals.status_code == 200, approvals.text
        approval = next(item for item in approvals.json()["approvals"] if item["evidenceEventRef"] == event["eventRef"])

        blocked = client.patch(
            f"/api/evidence/approvals/{approval['id']}",
            headers=clinician_headers,
            json={"decision": "approved", "note": "clinician must not approve"},
        )
        assert blocked.status_code == 403, blocked.text
        print("Role enforcement blocks clinician approval OK")

        approved = client.patch(
            f"/api/evidence/approvals/{approval['id']}",
            headers=senior_headers,
            json={"decision": "approved", "decidedBy": "Forged Name", "decidedByRole": "clinician", "note": "senior reviewed"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["approval"]["decidedBy"] == senior_user["name"]
        assert approved.json()["approval"]["decidedByRole"] == "ops_manager"
        assert approved.json()["decisionEvent"]["actorAuthSource"] == "local_signed_token"
        print("Approval actor derived from token OK")

        tampered_token = senior_headers["Authorization"][:-2] + "xx"
        tampered = client.get("/api/auth/me", headers={"Authorization": tampered_token})
        assert tampered.status_code == 401, tampered.text
        print("Tampered token rejected OK")

    print("\n--- VERIFIED IDENTITY SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
