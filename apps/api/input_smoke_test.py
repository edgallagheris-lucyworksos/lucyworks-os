import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "input_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models import AuditEvent, WorkItem

print("\n--- RUNNING MOBILE INPUT CAPTURE SMOKE TEST ---\n")

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text

    payload = {
        "title": "MRI owner update overdue",
        "description": "Owner has not been updated after MRI delay. Needs admin/clinician ownership.",
        "section_name": "Imaging",
        "room_name": "MRI",
        "urgency": "amber",
        "owner_role": "admin",
        "linked_patient_name": "Scout",
        "linked_episode_ref": "EP-2004",
        "actor_name": "Smoke Test",
    }
    r = client.post("/api/input/capture", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["work_item"]["title"] == payload["title"]
    assert data["work_item"]["owner_role"] == "admin"

    with Session(engine) as session:
        item = session.exec(select(WorkItem).where(WorkItem.title == payload["title"])).first()
        assert item is not None
        assert item.section_name == "Imaging"
        audit = session.exec(select(AuditEvent).where(AuditEvent.entity_type == "work_item", AuditEvent.entity_id == item.id)).first()
        assert audit is not None
        assert audit.action == "captured"

print("\n--- MOBILE INPUT CAPTURE TEST PASSED ---\n")
