import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_protected_time_{os.getpid()}.db"
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
        seed = {"blocks": [
            {"id": "pt-1", "time": "09:00", "lane": "theatre", "what": "Major surgery", "who": "surgeon", "where": "Theatre 1", "how": "procedure", "status": "amber", "blocker": "none", "next": "recover patient", "subject": "Referral A", "durationMinutes": 150, "episodeRef": "a", "assignedRole": "surgeon", "assignedStaffName": "Dr Buffer", "resourceName": "Theatre 1"},
            {"id": "pt-2", "time": "11:30", "lane": "consult", "what": "Referral consult", "who": "clinician", "where": "Consult room", "how": "review", "status": "amber", "blocker": "none", "next": "owner update", "subject": "Referral B", "durationMinutes": 45, "episodeRef": "b", "assignedRole": "clinician", "assignedStaffName": "Dr Buffer", "resourceName": "Consult room"}
        ]}
        r = client.put("/api/day-control/blocks/bulk", json=seed)
        assert r.status_code == 200, r.text
        r = client.get("/api/day-control/conflicts")
        assert r.status_code == 200, r.text
        conflicts = r.json()["conflicts"]
        assert any(item["type"] == "staff_protected_time_overlap" for item in conflicts), conflicts
        assert any("protectedStart" in block for item in conflicts for block in item.get("blocks", [])), conflicts
        print("PROTECTED TIME SMOKE TEST PASSED")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
