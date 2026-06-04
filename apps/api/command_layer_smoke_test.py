import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_command_layer_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)

print("\n--- RUNNING COMMAND LAYER SMOKE TEST ---\n")

try:
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

        status = client.get("/api/command/status")
        assert status.status_code == 200, status.text
        status_payload = status.json()
        assert status_payload["available"] is True
        assert "move_episode" in status_payload["supported_commands"]
        print("Command status OK")

        episodes = client.get("/api/episodes").json()
        assert episodes, "No seeded episodes"
        episode = episodes[0]
        episode_ref = episode["episode_ref"]

        move = client.post(
            "/api/command/execute",
            json={
                "command": "move_episode",
                "actor_name": "Command Smoke Test",
                "role": "ops_manager",
                "episode_ref": episode_ref,
                "section_name": "Imaging",
                "room_name": "CT",
                "department": "Imaging",
                "metadata": {"phase": "imaging"},
                "note": "Move to CT for command smoke test",
            },
        )
        assert move.status_code == 200, move.text
        move_payload = move.json()
        assert move_payload["ok"] is True
        assert move_payload["changed"]["episode"]["current_section_name"] == "Imaging"
        assert move_payload["audit_event"]["action"] == "command_move_episode"
        assert move_payload["realtime_event"]["event_type"] == "command_executed"
        print("Move episode command OK")

        handoff = client.post(
            "/api/command/execute",
            json={
                "command": "create_handoff",
                "actor_name": "Command Smoke Test",
                "role": "ops_manager",
                "episode_ref": episode_ref,
                "owner_role": "clinician",
                "target_owner": "nurse",
                "department": "ICU",
                "note": "Handoff from clinician to nurse",
            },
        )
        assert handoff.status_code == 200, handoff.text
        handoff_payload = handoff.json()
        handoff_id = handoff_payload["changed"]["handover"]["id"]
        assert handoff_payload["ok"] is True
        print("Create handoff command OK")

        acknowledge = client.post(
            "/api/command/execute",
            json={
                "command": "acknowledge_handoff",
                "actor_name": "Command Smoke Test",
                "role": "ops_manager",
                "handover_id": handoff_id,
                "department": "ICU",
                "note": "Acknowledge command smoke handoff",
            },
        )
        assert acknowledge.status_code == 200, acknowledge.text
        assert acknowledge.json()["changed"]["handover"]["acknowledged"] is True
        print("Acknowledge handoff command OK")

        meds = client.post(
            "/api/command/execute",
            json={
                "command": "mark_meds_ready",
                "actor_name": "Command Smoke Test",
                "role": "ops_manager",
                "episode_ref": episode_ref,
                "department": "Discharge",
                "note": "Medication ready",
            },
        )
        assert meds.status_code == 200, meds.text
        assert meds.json()["changed"]["discharge_readiness"]["medication_ready"] is True
        print("Mark meds ready command OK")

        owner = client.post(
            "/api/command/execute",
            json={
                "command": "mark_owner_updated",
                "actor_name": "Command Smoke Test",
                "role": "ops_manager",
                "episode_ref": episode_ref,
                "department": "Discharge",
                "note": "Owner updated",
            },
        )
        assert owner.status_code == 200, owner.text
        assert owner.json()["changed"]["discharge_readiness"]["owner_updated"] is True
        print("Mark owner updated command OK")

        approve = client.post(
            "/api/command/execute",
            json={
                "command": "approve_discharge",
                "actor_name": "Command Smoke Test",
                "role": "ops_manager",
                "episode_ref": episode_ref,
                "department": "Discharge",
                "note": "Approve discharge",
            },
        )
        assert approve.status_code == 200, approve.text
        assert approve.json()["changed"]["discharge_readiness"]["readiness_state"] == "ready"
        print("Approve discharge command OK")

        work = client.post(
            "/api/command/execute",
            json={
                "command": "create_work_item",
                "actor_name": "Command Smoke Test",
                "role": "ops_manager",
                "episode_ref": episode_ref,
                "department": "Discharge",
                "section_name": "Discharge",
                "title": "Final owner paperwork",
                "description": "Command-created final paperwork task",
                "owner_role": "admin",
                "urgency": "amber",
            },
        )
        assert work.status_code == 200, work.text
        assert work.json()["changed"]["work_item"]["owner_role"] == "admin"
        print("Create work item command OK")

        close = client.post(
            "/api/command/execute",
            json={
                "command": "close_case",
                "actor_name": "Command Smoke Test",
                "role": "ops_manager",
                "episode_ref": episode_ref,
                "department": "Discharge",
                "note": "Close case after discharge",
            },
        )
        assert close.status_code == 200, close.text
        assert close.json()["changed"]["episode"]["status"] == "closed"
        print("Close case command OK")

        history = client.get("/api/command/history")
        assert history.status_code == 200, history.text
        history_payload = history.json()
        assert history_payload["count"] >= 7
        print("Command history OK")

        realtime = client.get("/api/realtime/events")
        assert realtime.status_code == 200, realtime.text
        published = realtime.json()["published"]
        assert any(item["event_type"] == "command_executed" for item in published)
        print("Realtime event emission OK")

    print("\n--- COMMAND LAYER SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
