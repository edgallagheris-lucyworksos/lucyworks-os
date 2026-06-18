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
        seed = {
            "blocks": [
                {
                    "id": "smoke-block-1",
                    "time": "08:00",
                    "lane": "consult",
                    "what": "Smoke consult",
                    "who": "clinician",
                    "where": "Consult room",
                    "how": "confirm plan",
                    "status": "amber",
                    "blocker": "owner update pending",
                    "next": "send update",
                    "route": "/flow",
                    "subject": "Smoke",
                    "durationMinutes": 15,
                    "generatedFrom": "smoke",
                }
            ]
        }

        r = client.put("/api/day-control/blocks/bulk", json=seed)
        assert r.status_code == 200, r.text
        assert r.json()["count"] == 1
        print("Day-control bulk seed OK")

        r = client.get("/api/day-control/blocks")
        assert r.status_code == 200, r.text
        blocks = r.json()["blocks"]
        assert blocks[0]["id"] == "smoke-block-1"
        print("Day-control list OK")

        r = client.post("/api/day-control/blocks/smoke-block-1/actions", json={"action": "resolve", "actor": "smoke"})
        assert r.status_code == 200, r.text
        block = r.json()["block"]
        assert block["status"] == "green"
        assert block["blocker"] == "none"
        print("Day-control action OK")

        r = client.get("/api/day-control/audit")
        assert r.status_code == 200, r.text
        audit = r.json()["audit"]
        assert len(audit) >= 2
        assert any(event["action"] == "resolve" for event in audit)
        print("Day-control audit OK")

    print("\n--- DAY CONTROL SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
