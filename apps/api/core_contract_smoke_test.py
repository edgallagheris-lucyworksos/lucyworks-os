import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_core_contract_smoke_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["LUCYWORKS_LEGACY_TEST_BYPASS"] = "true"

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

        assert body["system"] == "LucyWorks OS"
        assert body["contract_version"] == "1.0.0"
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
        assert capabilities["system_proof"]["state"] == "missing"
        assert capabilities["system_proof"]["blockers"]
        assert all(item["authority"] for item in capabilities.values())
        assert "No module may claim ready" in body["operating_rule"]

    print("\n--- CORE CONTRACT SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
