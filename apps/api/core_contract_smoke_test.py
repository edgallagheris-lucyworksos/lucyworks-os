import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_core_contract_smoke_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["LUCYWORKS_LEGACY_TEST_BYPASS"] = "true"
os.environ["AUTO_CREATE_SCHEMA"] = "true"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

try:
    with TestClient(app) as client:
        response = client.get("/api/core/contract")
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["system"] == "LucyWorksOS"
        assert body["contract_version"] == "1.1.0"
        assert body["overall_state"] == "partial"

        capabilities = {item["key"]: item for item in body["capabilities"]}
        required = {
            "canonical_data",
            "workflow_engine",
            "rules_and_permissions",
            "resource_scheduler",
            "event_propagation",
            "command_surface",
            "integrations",
            "system_proof",
        }
        assert required == set(capabilities)

        workflow = capabilities["workflow_engine"]
        assert workflow["state"] == "partial"
        assert "test:hospital_command_v9_smoke_test.py" in workflow["proof"]
        assert any(item.startswith("route:/api/v9/episodes/") for item in workflow["proof"])

        system_proof = capabilities["system_proof"]
        assert system_proof["state"] == "partial"
        assert "referral creation and acceptance" in system_proof["proof"]
        assert any("synthetic SQLite" in item for item in system_proof["blockers"])
        assert any("invoice/payment integration" in item for item in system_proof["blockers"])

        assert all(item["authority"] for item in capabilities.values())
        assert "real-site validation" in body["operating_rule"]

    print("\n--- RUNTIME CORE CONTRACT TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
