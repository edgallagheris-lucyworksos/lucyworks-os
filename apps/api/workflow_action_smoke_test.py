import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_workflow_actions_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)

print("\n--- RUNNING WORKFLOW ACTION SMOKE TEST ---\n")

try:
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200, r.text

        r = client.get("/api/alerts")
        assert r.status_code == 200, r.text

        r = client.get("/api/handovers")
        assert r.status_code == 200, r.text
        handovers = r.json()
        assert len(handovers) > 0, "No seeded handovers returned"
        handover_id = handovers[0]["id"]

        r = client.post(
            f"/api/actions/handovers/{handover_id}/acknowledge",
            json={"actor_name": "Workflow Smoke Test", "note": "Acknowledge handover smoke test"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        assert r.json()["handover"]["acknowledged"] is True
        assert r.json()["audit_event"]["action"] == "handover_acknowledged"
        print("Acknowledge handover OK")

        r = client.get("/api/results")
        assert r.status_code == 200, r.text
        results = r.json()
        assert len(results) > 0, "No seeded result reviews returned"
        result_id = results[0]["id"]

        r = client.post(
            f"/api/actions/results/{result_id}/review",
            json={"actor_name": "Workflow Smoke Test", "required_action": "Reviewed in smoke test"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        assert r.json()["result_review"]["status"] == "reviewed"
        assert r.json()["audit_event"]["action"] == "result_reviewed"
        print("Review result OK")

        r = client.get("/api/room-states")
        assert r.status_code == 200, r.text
        rooms = r.json()
        assert len(rooms) > 0, "No seeded room states returned"
        room_name = rooms[0]["room_name"]

        r = client.post(
            "/api/actions/rooms/release",
            json={"room_name": room_name, "actor_name": "Workflow Smoke Test", "note": "Release room smoke test"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        assert r.json()["room_state"]["state"] == "available"
        assert r.json()["audit_event"]["action"] == "room_released"
        print("Release room OK")

        r = client.get("/api/schedule-blocks")
        assert r.status_code == 200, r.text
        blocks = r.json()
        assert len(blocks) > 0, "No seeded schedule blocks returned"
        block_id = blocks[0]["id"]
        original_start = blocks[0]["starts_at"]
        new_start = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        r = client.post(
            f"/api/actions/schedule-blocks/{block_id}/move",
            json={"starts_at": new_start, "actor_name": "Workflow Smoke Test", "note": "Move schedule smoke test"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        assert r.json()["schedule_block"]["starts_at"] != original_start
        assert r.json()["audit_event"]["action"] == "schedule_block_moved"
        print("Move schedule block OK")

        r = client.post(
            f"/api/actions/schedule-blocks/{block_id}/delay-chain?minutes=15&actor_name=Workflow%20Smoke%20Test"
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        assert len(r.json()["moved_block_ids"]) >= 1
        assert r.json()["audit_event"]["action"] == "schedule_chain_delayed"
        print("Delay schedule chain OK")

        r = client.get("/api/v3/board")
        assert r.status_code == 200, r.text
        board = r.json()
        assert len(board["work_items"]) > 0, "No seeded work items returned"
        work_item_id = board["work_items"][0]["id"]

        r = client.post(
            f"/api/actions/work-items/{work_item_id}/assign",
            json={"owner_role": "nurse", "owner_user_id": None, "actor_name": "Workflow Smoke Test"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        assert r.json()["work_item"]["owner_role"] == "nurse"
        assert r.json()["audit_event"]["action"] == "work_item_assigned"
        print("Assign work item OK")

        r = client.post(
            f"/api/actions/work-items/{work_item_id}/complete",
            json={"actor_name": "Workflow Smoke Test", "note": "Complete work item smoke test"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        assert r.json()["work_item"]["status"] == "done"
        assert r.json()["audit_event"]["action"] == "work_item_completed"
        print("Complete work item OK")

        r = client.get("/api/actions/assignable-staff")
        assert r.status_code == 200, r.text
        assert "staff" in r.json()
        print("Assignable staff OK")

    print("\n--- WORKFLOW ACTION SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
