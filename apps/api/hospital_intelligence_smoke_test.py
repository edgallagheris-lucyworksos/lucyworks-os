import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_hospital_intelligence_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_JWT_SECRET": "hospital-intelligence-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-intelligence-smoke",
    "AUTH_AUDIENCE": "lucyworks-intelligence-api",
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
        unauthenticated = client.get("/api/hospital-intelligence/summary")
        assert unauthenticated.status_code == 401, unauthenticated.text

        headers = login(client, 1)
        summary = client.get("/api/hospital-intelligence/summary", headers=headers)
        assert summary.status_code == 200, summary.text
        summary_data = summary.json()
        assert summary_data["hospitalCount"] >= 5
        assert summary_data["roleCount"] >= 30
        assert summary_data["departmentCount"] >= 20
        assert summary_data["workflowCount"] >= 10
        assert summary_data["governance"]["containsPersonalStaffRecords"] is False
        print("Hospital intelligence summary and governance OK")

        catalogue = client.get("/api/hospital-intelligence/catalogue", headers=headers)
        assert catalogue.status_code == 200, catalogue.text
        data = catalogue.json()
        assert any(item["hospitalRef"] == "bvs" for item in data["hospitals"])
        assert any(item["roleRef"] == "hospital_flow_coordinator" for item in data["roleTemplates"])
        assert any(item["roleRef"] == "insurance_administrator" for item in data["roleTemplates"])
        assert any(item["departmentRef"] == "transfusion_medicine" for item in data["departmentTemplates"])
        assert any(item["workflowRef"] == "consult_options_estimate_consent" for item in data["workflowPatterns"])
        print("Hospital, role, department and workflow catalogue OK")

        bvs = client.get("/api/hospital-intelligence/catalogue?hospital=bvs", headers=headers)
        assert bvs.status_code == 200, bvs.text
        bvs_data = bvs.json()
        assert bvs_data["counts"]["hospitals"] == 1
        assert bvs_data["hospitals"][0]["name"] == "Bristol Vet Specialists"
        assert "Five operating theatres" in bvs_data["hospitals"][0]["facilities"]
        assert any(item["roleRef"] == "referral_coordinator" for item in bvs_data["roleTemplates"])
        print("BVS evidence filter OK")

        nursing = client.get("/api/hospital-intelligence/catalogue?roleFamily=nursing", headers=headers)
        assert nursing.status_code == 200, nursing.text
        assert nursing.json()["counts"]["roles"] >= 2
        assert all(item["family"] == "nursing" for item in nursing.json()["roleTemplates"])

        search = client.get("/api/hospital-intelligence/catalogue?q=insurance", headers=headers)
        assert search.status_code == 200, search.text
        assert any(item["roleRef"] == "insurance_administrator" for item in search.json()["roleTemplates"])
        print("Role-family and text filtering OK")

    print("\n--- HOSPITAL INTELLIGENCE SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
