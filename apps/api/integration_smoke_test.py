import hashlib
import hmac
import json
import os
import tempfile
import time
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_integrations_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_JWT_SECRET": "integration-smoke-auth-secret-that-is-not-production",
    "AUTH_ISSUER": "lucyworks-integration-smoke",
    "AUTH_AUDIENCE": "lucyworks-integration-smoke-api",
    "PIMS_WEBHOOK_SECRET": "pims-smoke-signing-secret",
    "IMAGING_WEBHOOK_SECRET": "imaging-smoke-signing-secret",
    "LAB_WEBHOOK_SECRET": "laboratory-smoke-signing-secret",
    "HR_WEBHOOK_SECRET": "hr-smoke-signing-secret",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def signed_webhook(client: TestClient, connection_ref: str, secret: str, payload: dict) -> object:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = hmac.new(secret.encode("utf-8"), timestamp.encode("utf-8") + b"." + raw, hashlib.sha256).hexdigest()
    return client.post(
        f"/api/integrations/webhooks/{connection_ref}",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-LucyWorks-Timestamp": timestamp,
            "X-LucyWorks-Signature": f"sha256={signature}",
        },
    )


try:
    with TestClient(app) as client:
        senior_headers = login(client, 1)
        clinician_headers = login(client, 3)

        unauthenticated = client.post("/api/integrations/connections", json={})
        assert unauthenticated.status_code == 401, unauthenticated.text
        blocked = client.post("/api/integrations/connections", headers=clinician_headers, json={})
        assert blocked.status_code == 403, blocked.text
        print("Integration administration role guard OK")

        definitions = [
            ("pims-main", "pims", "Referral PIMS", "PIMS_WEBHOOK_SECRET"),
            ("imaging-main", "imaging", "Imaging PACS", "IMAGING_WEBHOOK_SECRET"),
            ("lab-main", "laboratory", "Reference Laboratory", "LAB_WEBHOOK_SECRET"),
            ("hr-main", "hr", "Hospital HR", "HR_WEBHOOK_SECRET"),
        ]
        for connection_ref, integration_type, vendor, secret_env in definitions:
            response = client.post("/api/integrations/connections", headers=senior_headers, json={
                "connectionRef": connection_ref,
                "integrationType": integration_type,
                "vendor": vendor,
                "status": "active",
                "secretEnv": secret_env,
                "storePayload": False,
                "accountableOwner": "Hospital Operations",
            })
            assert response.status_code == 200, response.text
            connection = response.json()["connection"]
            assert connection["createdBy"] == "Lucy Ops"
            assert connection["storePayload"] is False
        print("Governed integration connections created OK")

        pims_payload = {
            "event_id": "pims-event-1",
            "event_type": "referral.created",
            "patient_case_id": "case-integration-1",
            "referral_episode_id": "episode-integration-1",
            "data": {"referring_practice": "Smoke Vets", "reason": "neurology referral"},
            "entity": {
                "type": "patient",
                "id": "pims-patient-99",
                "internalType": "patient_case",
                "internalId": "case-integration-1",
            },
        }
        pims = signed_webhook(client, "pims-main", os.environ["PIMS_WEBHOOK_SECRET"], pims_payload)
        assert pims.status_code == 200, pims.text
        assert pims.json()["created"] is True
        assert pims.json()["envelope"]["status"] == "processed"
        assert pims.json()["envelope"]["payloadStored"] is False

        duplicate = signed_webhook(client, "pims-main", os.environ["PIMS_WEBHOOK_SECRET"], pims_payload)
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()["created"] is False
        assert duplicate.json()["envelope"]["envelopeRef"] == pims.json()["envelope"]["envelopeRef"]
        print("PIMS message normalisation and deduplication OK")

        imaging = signed_webhook(client, "imaging-main", os.environ["IMAGING_WEBHOOK_SECRET"], {
            "event_id": "imaging-status-1",
            "event_type": "service.status",
            "data": {
                "service_ref": "mri-main",
                "department": "diagnostic_imaging",
                "service_name": "MRI",
                "operational_status": "reduced",
                "accepting_referrals": False,
                "staffing_ready": True,
                "equipment_ready": False,
                "consumables_ready": True,
                "limiting_reason": "coil fault",
            },
        })
        assert imaging.status_code == 200, imaging.text
        assert imaging.json()["envelope"]["internalRecordType"] == "service_availability"
        assert imaging.json()["envelope"]["internalRecordRef"] == "mri-main"
        print("Imaging service readiness adapter OK")

        laboratory = signed_webhook(client, "lab-main", os.environ["LAB_WEBHOOK_SECRET"], {
            "event_id": "lab-critical-1",
            "event_type": "result.final",
            "patient_case_id": "case-integration-1",
            "referral_episode_id": "episode-integration-1",
            "data": {
                "result_ref": "external-potassium-1",
                "result_type": "potassium",
                "severity": "critical",
                "summary": "critical potassium result",
                "assigned_to": "Duty Clinician",
                "assigned_role": "clinician",
            },
        })
        assert laboratory.status_code == 200, laboratory.text
        assert laboratory.json()["envelope"]["internalRecordType"] == "critical_result"
        print("Laboratory critical-result adapter OK")

        hr = signed_webhook(client, "hr-main", os.environ["HR_WEBHOOK_SECRET"], {
            "event_id": "hr-status-1",
            "event_type": "staff.status",
            "data": {"staff_id": "staff-17", "status": "fatigued", "department": "ICU"},
        })
        assert hr.status_code == 200, hr.text
        print("HR workforce-risk adapter OK")

        raw = b'{"event_id":"bad-signature","event_type":"result.final"}'
        invalid = client.post(
            "/api/integrations/webhooks/lab-main",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-LucyWorks-Timestamp": str(int(time.time())),
                "X-LucyWorks-Signature": "sha256=not-valid",
            },
        )
        assert invalid.status_code == 401, invalid.text
        print("Invalid webhook signature rejected OK")

        dashboard = client.get("/api/integrations/dashboard", headers=senior_headers)
        assert dashboard.status_code == 200, dashboard.text
        summary = dashboard.json()["summary"]
        assert summary["connections"] == 4
        assert summary["activeConnections"] == 4
        assert summary["processedMessages"] == 4
        assert summary["failedMessages"] == 0

        control_plane = client.get("/api/control-plane/dashboard", headers=senior_headers)
        assert control_plane.status_code == 200, control_plane.text
        assert control_plane.json()["summary"]["unsafeServices"] >= 1
        assert control_plane.json()["summary"]["unacknowledgedCriticalResults"] >= 1

        evidence = client.get("/api/evidence/events?limit=100", headers=senior_headers)
        assert evidence.status_code == 200, evidence.text
        integration_events = [row for row in evidence.json()["events"] if row["sourceModule"] == "integration-gateway"]
        assert len(integration_events) == 4, integration_events
        assert all(row["actorAuthSource"] == "hmac_verified_integration" for row in integration_events)
        assert any(row["complianceDomain"] == "workforce" and row["riskLevel"] == "red" for row in integration_events)
        print("Integration evidence and control-plane propagation OK")

    print("\n--- GOVERNED INTEGRATION SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
