import os
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

TEST_DB = Path(__file__).parent / "workflow_action_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from app.database import engine
from app.main import app
from app.models import AuditEvent, Handover, ResultReview, RoomState, ScheduleBlock, WorkItem

print("\n--- RUNNING WORKFLOW ACTION SMOKE TEST ---\n")

with TestClient(app) as client:
    with Session(engine) as session:
        work_item = session.exec(select(WorkItem)).first()
        handover = session.exec(select(Handover)).first()
        result = session.exec(select(ResultReview)).first()
        room = session.exec(select(RoomState)).first()
        block = session.exec(select(ScheduleBlock)).first()

        assert work_item is not None
        assert handover is not None
        assert result is not None
        assert room is not None
        assert block is not None

        work_item_id = work_item.id
        handover_id = handover.id
        result_id = result.id
        room_id = room.id
        block_id = block.id

    r = client.post(f"/api/actions/work-items/{work_item_id}/complete")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["work_item"]["status"] == "done"

    r = client.post(
        f"/api/actions/work-items/{work_item_id}/assign",
        json={"owner_role": "clinician", "owner_user_id": 1},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["work_item"]["owner_role"] == "clinician"

    r = client.post(f"/api/actions/handovers/{handover_id}/acknowledge")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["handover"]["acknowledged"] is True

    r = client.post(f"/api/actions/results/{result_id}/review")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["result_review"]["status"] == "reviewed"

    r = client.post("/api/actions/rooms/release", json={"room_state_id": room_id})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["room_state"]["state"] == "available"

    r = client.post(
        f"/api/actions/schedule-blocks/{block_id}/move",
        json={
            "starts_at": "2026-01-01T10:00:00Z",
            "ends_at": "2026-01-01T10:15:00Z",
            "room_name": "MRI-1",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["schedule_block"]["room_name"] == "MRI-1"

    with Session(engine) as session:
        events = session.exec(select(AuditEvent)).all()
        assert len(events) >= 6, "Expected workflow actions to emit audit events"

print("\n--- WORKFLOW ACTION SMOKE TEST PASSED ---\n")
