import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_day_control_smoke_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

try:
    with TestClient(app) as client:
        r = client.get("/api/day-control/staff-options")
        assert r.status_code == 200, r.text
        assert len(r.json()["staff"]) >= 3
        print("Day-control staff options OK")

        r = client.get("/api/day-control/resource-options")
        assert r.status_code == 200, r.text
        assert len(r.json()["resources"]) >= 3
        print("Day-control resource options OK")

        seed = {"blocks": [{"id": "smoke-block-1", "time": "08:00", "lane": "consult", "what": "Smoke consult", "who": "clinician", "where": "Consult room", "how": "confirm plan", "status": "amber", "blocker": "owner update pending", "next": "send update", "route": "/flow", "subject": "Smoke", "durationMinutes": 15, "generatedFrom": "smoke", "assignedRole": "clinician", "assignedStaffName": "Smoke Clinician", "resourceName": "Consult room"}, {"id": "smoke-block-2", "time": "08:00", "lane": "decision", "what": "Smoke decision", "who": "clinician", "where": "Consult room", "how": "review plan", "status": "amber", "blocker": "none", "next": "continue planned flow", "route": "/my-shift", "subject": "Smoke", "durationMinutes": 15, "generatedFrom": "smoke", "assignedRole": "clinician", "assignedStaffName": "Smoke Clinician", "resourceName": "Consult room"}]}

        r = client.put("/api/day-control/blocks/bulk", json=seed)
        assert r.status_code == 200, r.text
        assert r.json()["count"] == 2
        print("Day-control bulk seed OK")

        r = client.get("/api/day-control/blocks")
        assert r.status_code == 200, r.text
        blocks = r.json()["blocks"]
        assert blocks[0]["id"] in {"smoke-block-1", "smoke-block-2"}
        assert blocks[0]["assignedStaffName"] == "Smoke Clinician"
        print("Day-control list OK")

        r = client.get("/api/day-control/conflicts")
        assert r.status_code == 200, r.text
        conflicts = r.json()["conflicts"]
        assert any(item["type"] == "resource_clash" for item in conflicts)
        assert any(item["type"] == "staff_clash" for item in conflicts)
        print("Day-control conflicts OK")

        r = client.patch("/api/day-control/blocks/smoke-block-1", json={"assignedStaffName": "Smoke Nurse", "assignedRole": "nurse", "resourceName": "Room 2"})
        assert r.status_code == 200, r.text
        patched = r.json()["block"]
        assert patched["assignedStaffName"] == "Smoke Nurse"
        assert patched["resourceName"] == "Room 2"
        print("Day-control assignment patch OK")

        r = client.patch("/api/day-control/blocks/smoke-block-1", json={"assignedStaffName": None, "assignedRole": None, "resourceName": None})
        assert r.status_code == 200, r.text
        cleared = r.json()["block"]
        assert cleared["assignedStaffName"] is None
        assert cleared["assignedRole"] is None
        assert cleared["resourceName"] is None
        print("Day-control assignment clear OK")

        r = client.post("/api/day-control/blocks/smoke-block-1/actions", json={"action": "resolve", "actor": "smoke"})
        assert r.status_code == 200, r.text
        block = r.json()["block"]
        assert block["status"] == "green"
        assert block["blocker"] == "none"
        print("Day-control action OK")

        r = client.get("/api/day-control/audit")
        assert r.status_code == 200, r.text
        audit = r.json()["audit"]
        assert len(audit) >= 4
        assert any(event["action"] == "resolve" for event in audit)
        assert any(event["action"] == "update" for event in audit)
        print("Day-control audit OK")

    print("\n--- DAY CONTROL SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
