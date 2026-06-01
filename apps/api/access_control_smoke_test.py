import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_access_control_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)

print("\n--- RUNNING ACCESS CONTROL SMOKE TEST ---\n")

try:
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

        r = client.get("/api/access/permissions")
        assert r.status_code == 200, r.text
        permissions = r.json()
        assert "ops_manager" in permissions["roles"]
        assert "admin_override" in permissions["roles"]["ops_manager"]
        print("Permissions OK")

        r = client.get("/api/access/me?role=nurse&department=ICU")
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["role"] == "nurse"
        assert me["department_scope_ok"] is True
        print("Me OK")

        r = client.post("/api/access/check", json={"role": "nurse", "permission": "manage_care_tasks", "department": "ICU", "entity_type": "episode"})
        assert r.status_code == 200, r.text
        check = r.json()
        assert check["allowed"] is True
        assert check["sensitive"] is True
        print("Allowed check OK")

        r = client.post("/api/access/check", json={"role": "pca", "permission": "clinical_decision", "department": "ICU", "entity_type": "episode"})
        assert r.status_code == 200, r.text
        denied = r.json()
        assert denied["allowed"] is False
        print("Denied check OK")

        r = client.post(
            "/api/access/audit-view",
            json={"actor_name": "Access Smoke Test", "role": "nurse", "entity_type": "episode", "entity_id": 1, "department": "ICU", "reason": "care review"},
        )
        assert r.status_code == 200, r.text
        audit_view = r.json()
        assert audit_view["ok"] is True
        assert audit_view["audit_event"]["action"] == "sensitive_view_audited"
        print("Audit view OK")

        r = client.post(
            "/api/access/admin-override",
            json={"actor_name": "Access Smoke Test", "role": "ops_manager", "target_action": "force_room_release", "entity_type": "room", "entity_id": 1, "department": "Surgery", "reason": "smoke test override"},
        )
        assert r.status_code == 200, r.text
        override = r.json()
        assert override["ok"] is True
        assert override["audit_event"]["action"] == "admin_override_logged"
        print("Admin override OK")

        r = client.post(
            "/api/access/admin-override",
            json={"actor_name": "Access Smoke Test", "role": "nurse", "target_action": "force_room_release", "entity_type": "room", "entity_id": 1, "department": "Surgery", "reason": "should fail"},
        )
        assert r.status_code == 403, r.text
        print("Denied override OK")

        r = client.get("/api/access/audit-summary")
        assert r.status_code == 200, r.text
        summary = r.json()
        assert summary["sensitive_view_count"] >= 1
        assert summary["admin_override_count"] >= 1
        assert "by_action" in summary
        print("Audit summary OK")

    print("\n--- ACCESS CONTROL SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
