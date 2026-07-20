import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_production_readiness_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_JWT_SECRET": "production-readiness-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-readiness-smoke",
    "AUTH_AUDIENCE": "lucyworks-readiness-api",
    "METRICS_API_KEY": "readiness-metrics-key-long-enough",
    "SECURITY_HEADERS_ENABLED": "true",
    "RATE_LIMIT_ENABLED": "false",
    "DEPLOYMENT_ENVIRONMENT": "test",
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


try:
    with TestClient(app) as client:
        live = client.get("/api/health/live")
        assert live.status_code == 200, live.text
        assert live.headers["x-content-type-options"] == "nosniff"
        assert live.headers["x-request-id"].startswith("req-")
        print("Liveness and security headers OK")

        metrics_denied = client.get("/api/metrics")
        assert metrics_denied.status_code == 401, metrics_denied.text
        metrics = client.get("/api/metrics", headers={"X-LucyWorks-Metrics-Key": os.environ["METRICS_API_KEY"]})
        assert metrics.status_code == 200, metrics.text
        assert "lucyworks_http_requests_total" in metrics.text
        print("Dedicated metrics authentication OK")

        senior = login(client, 1)
        clinician = login(client, 3)

        forbidden = client.get("/api/production-readiness/dashboard", headers=clinician)
        assert forbidden.status_code == 403, forbidden.text

        bootstrap = client.post("/api/production-readiness/bootstrap", headers=senior, json={})
        assert bootstrap.status_code == 200, bootstrap.text
        assert bootstrap.json()["controls"] >= 16

        dashboard = client.get("/api/production-readiness/dashboard", headers=senior)
        assert dashboard.status_code == 200, dashboard.text
        controls = dashboard.json()["controls"]
        assert any(item["controlRef"] == "privacy.dpia" for item in controls)
        assert dashboard.json()["gate"]["liveEligible"] is False
        print("Persistent readiness gate OK")

        security = client.post("/api/production-readiness/security/self-test", headers=senior, json={})
        assert security.status_code == 200, security.text
        assert security.json()["failedCount"] > 0
        print("Automated production configuration assessment OK")

        synthetic = client.post("/api/production-readiness/synthetic-hospital/seed", headers=senior, json={"premisesRef": "synthetic-smoke", "confirmation": "CREATE SYNTHETIC DATA"})
        assert synthetic.status_code == 200, synthetic.text
        assert synthetic.json()["areas"] >= 20
        assert synthetic.json()["createdStaff"] >= 60
        print("Synthetic referral hospital bootstrap OK")

        mappings = client.get("/api/production-readiness/vendor-mappings", headers=senior)
        assert mappings.status_code == 200, mappings.text
        assert mappings.json()["count"] >= 4
        print("Vendor mapping catalogue OK")

        pilot = client.post("/api/production-readiness/pilots", headers=senior, json={"phase": "shadow", "serviceLine": "neurology", "accountableOwner": "Lucy Ops", "startNow": True})
        assert pilot.status_code == 200, pilot.text
        pilot_ref = pilot.json()["pilot"]["runRef"]

        observation = client.post(f"/api/production-readiness/pilots/{pilot_ref}/observations", headers=senior, json={"severity": "red", "category": "lost_update", "summary": "Synthetic stale board observed", "expectedBehaviour": "Reject stale write", "actualBehaviour": "Test observation"})
        assert observation.status_code == 200, observation.text
        observation_ref = observation.json()["observation"]["observationRef"]

        blocked = client.get("/api/production-readiness/dashboard", headers=senior).json()
        assert blocked["gate"]["openRedObservations"] == 1
        assert next(item for item in blocked["pilots"] if item["runRef"] == pilot_ref)["status"] == "blocked"

        resolved = client.patch(f"/api/production-readiness/observations/{observation_ref}/resolve", headers=senior, json={"resolution": "Verified stale-write rejection in PostgreSQL contention test"})
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["observation"]["status"] == "resolved"
        print("Pilot red-observation blocking and resolution OK")

        control = next(item for item in blocked["controls"] if item["controlRef"] == "uat.acceptance")
        evidence = client.post("/api/production-readiness/controls/uat.acceptance/evidence", headers=senior, json={"evidenceType": "test_report", "summary": "Synthetic UAT evidence", "sourceRef": "smoke-run"})
        assert evidence.status_code == 200, evidence.text
        stale = client.patch("/api/production-readiness/controls/uat.acceptance", headers=senior, json={"expectedVersion": control["version"], "status": "passed", "evidenceSummary": "stale attempt"})
        assert stale.status_code == 409, stale.text
        print("Readiness evidence and stale-version protection OK")

        ready = client.get("/api/health/ready")
        assert ready.status_code == 200, ready.text
        print("Database readiness probe OK")

    print("\n--- PRODUCTION READINESS SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
