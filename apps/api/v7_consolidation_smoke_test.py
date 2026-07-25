import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_v7_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_JWT_SECRET": "v7-consolidation-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-v7-smoke",
    "AUTH_AUDIENCE": "lucyworks-v7-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from app.database import engine
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock
from app.integration_models import IntegrationConnection, IntegrationEnvelope
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def bearer_login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


try:
    with TestClient(app) as client:
        login = client.post("/api/auth/dev-login", json={"user_id": 1})
        assert login.status_code == 200, login.text
        assert client.cookies.get("lucyworks_session")
        csrf = client.cookies.get("lucyworks_csrf")
        assert csrf
        assert login.json()["tokenType"] in {"Bearer", "Cookie"}

        me = client.get("/api/auth/me")
        assert me.status_code == 200, me.text
        assert me.json()["user"]["role"] == "ops_manager"

        missing_csrf = client.post("/api/v7/events", json={"event_type": "test", "aggregate_type": "test", "aggregate_ref": "one"})
        assert missing_csrf.status_code == 403, missing_csrf.text

        headers = {"X-CSRF-Token": csrf}
        published = client.post("/api/v7/events", headers=headers, json={
            "event_type": "test_event", "aggregate_type": "test", "aggregate_ref": "one",
            "payload": {"ok": True}, "severity": "red", "idempotency_key": "v7-test-event",
        })
        assert published.status_code == 200, published.text
        event = published.json()["event"]
        assert event["sequence"] == 1

        stale_ack = client.patch(f"/api/v7/events/{event['eventRef']}/acknowledgement", headers=headers, json={"expected_version": 2, "status": "acknowledged", "note": "wrong version"})
        assert stale_ack.status_code == 409, stale_ack.text
        ack = client.patch(f"/api/v7/events/{event['eventRef']}/acknowledgement", headers=headers, json={"expected_version": 0, "status": "acknowledged", "note": "seen by operations"})
        assert ack.status_code == 200, ack.text
        assert ack.json()["acknowledgement"]["version"] == 1

        now = datetime.now(timezone.utc)
        with Session(engine) as session:
            episode = CanonicalEpisodeState(episode_ref="EP-V7-001", patient_ref="PAT-V7-001", patient_name="Anonymous Dog", premises_ref="bvs-bristol", phase="consultation", status="active", owner_role="clinician", current_area_ref="consult-1")
            block = OperationalBlock(block_ref="BLOCK-V7-001", premises_ref="bvs-bristol", operational_date=date.today(), episode_ref=episode.episode_ref, patient_ref=episode.patient_ref, patient_name=episode.patient_name, procedure_name="Consultation", area_ref="consult-1", area_name="Consult 1", starts_at=now, ends_at=now + timedelta(minutes=30), status="planned")
            session.add(episode); session.add(block); session.commit()

        shadow = client.post("/api/v7/shadow/comparisons", headers=headers, json={
            "premises_ref": "bvs-bristol", "source_system": "historical-test",
            "rows": [{"source_record_ref": "src-1", "episode_ref": "EP-V7-001", "block_ref": "BLOCK-V7-001", "patient_name": "Anonymous Dog", "phase": "consultation", "status": "planned", "area_ref": "consult-1", "starts_at": now.isoformat(), "ends_at": (now + timedelta(minutes=30)).isoformat(), "owner_role": "clinician"}],
        })
        assert shadow.status_code == 200, shadow.text
        comparison = shadow.json()["comparisons"][0]
        assert comparison["validationState"] == "matched", comparison

        stale_review = client.patch(f"/api/v7/shadow/comparisons/{comparison['comparisonRef']}", headers=headers, json={"expected_version": 99, "decision": "accept_canonical", "note": "stale"})
        assert stale_review.status_code == 409, stale_review.text
        reviewed = client.patch(f"/api/v7/shadow/comparisons/{comparison['comparisonRef']}", headers=headers, json={"expected_version": comparison["version"], "decision": "accept_canonical", "note": "verified replay match"})
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["comparison"]["reviewedBy"] == "Lucy Ops"

        with Session(engine) as session:
            connection = IntegrationConnection(connection_ref="integration-v7", integration_type="laboratory", vendor="Synthetic Lab", status="active", premises_ref="bvs-bristol", secret_env="SYNTHETIC_SECRET", accountable_owner="ops")
            envelope = IntegrationEnvelope(envelope_ref="envelope-v7", connection_ref=connection.connection_ref, message_type="result", dedupe_key="v7", payload_hash="hash", payload_json=None, status="failed", error="synthetic failure")
            session.add(connection); session.add(envelope); session.commit()

        enqueued = client.post("/api/v7/integration-retries/enqueue-failed", headers=headers)
        assert enqueued.status_code == 200, enqueued.text
        assert enqueued.json()["jobs"][0]["status"] == "dead_letter"

        retired = client.post("/api/shadow-mode/validate", headers=headers)
        assert retired.status_code == 410, retired.text
        assert retired.json()["replacement"].startswith("/api/v7/shadow")

        bearer = bearer_login(client, 1)
        bearer_event = client.post("/api/v7/events", headers=bearer, json={"event_type": "automation_event", "aggregate_type": "test", "aggregate_ref": "bearer", "payload": {}})
        assert bearer_event.status_code == 200, bearer_event.text

        logout = client.post("/api/auth/logout", headers=headers)
        assert logout.status_code == 200, logout.text
        assert client.get("/api/auth/me").status_code == 401

        print("V7 secure sessions, CSRF, durable events, acknowledgement, canonical shadow and dead-letter handling OK")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
