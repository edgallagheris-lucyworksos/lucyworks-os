import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_role_queues_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)

print("\n--- RUNNING ROLE QUEUE SMOKE TEST ---\n")

try:
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

        endpoints = [
            "/api/role-queues/manager",
            "/api/role-queues/clinician",
            "/api/role-queues/nurse",
            "/api/role-queues/pca",
            "/api/role-queues/admin",
            "/api/role-queues/my-shift?role=nurse",
            "/api/role-queues/interrupts",
            "/api/role-queues/overview",
        ]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, response.text
            data = response.json()
            assert isinstance(data, dict), endpoint
            assert "generated_at" in data, endpoint
            print(f"{endpoint} OK")

        overview = client.get("/api/role-queues/overview").json()
        assert "roles" in overview
        for role in ["manager", "clinician", "nurse", "pca", "admin"]:
            assert role in overview["roles"]

    print("\n--- ROLE QUEUE SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
