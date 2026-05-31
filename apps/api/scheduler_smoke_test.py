import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_scheduler_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)

print("\n--- RUNNING SCHEDULER SMOKE TEST ---\n")

try:
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200, r.text

        r = client.get("/api/episodes")
        assert r.status_code == 200, r.text
        episodes = r.json()
        assert len(episodes) > 0, "No seeded episodes"
        episode = episodes[0]

        r = client.get("/api/procedure-types")
        assert r.status_code == 200, r.text
        procedure_types = r.json()
        assert len(procedure_types) > 0, "No seeded procedure types"
        procedure_type = procedure_types[0]

        start = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        r = client.post(
            "/api/scheduler/chains/generate",
            json={
                "episode_id": episode["id"],
                "procedure_type_id": procedure_type["id"],
                "room_name": "Theatre 1",
                "starts_at": start,
                "actor_name": "Scheduler Smoke Test",
            },
        )
        assert r.status_code == 200, r.text
        generated = r.json()
        assert generated["ok"] is True
        assert len(generated["blocks"]) == 5
        case_procedure_id = generated["case_procedure"]["id"]
        first_start = generated["blocks"][0]["starts_at"]
        assert generated["audit_event"]["action"] == "scheduler_chain_generated"
        print("Generate chain OK")

        r = client.get(f"/api/scheduler/chains/{case_procedure_id}")
        assert r.status_code == 200, r.text
        chain = r.json()
        assert len(chain["blocks"]) == 5
        print("Get chain OK")

        moved_start = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
        r = client.post(
            f"/api/scheduler/chains/{case_procedure_id}/move",
            json={"starts_at": moved_start, "actor_name": "Scheduler Smoke Test"},
        )
        assert r.status_code == 200, r.text
        moved = r.json()
        assert moved["ok"] is True
        assert moved["blocks"][0]["starts_at"] != first_start
        assert moved["audit_event"]["action"] == "scheduler_chain_moved"
        print("Move chain OK")

        before_delay = moved["blocks"][0]["starts_at"]
        r = client.post(
            f"/api/scheduler/chains/{case_procedure_id}/delay",
            json={"minutes": 15, "actor_name": "Scheduler Smoke Test"},
        )
        assert r.status_code == 200, r.text
        delayed = r.json()
        assert delayed["ok"] is True
        assert delayed["blocks"][0]["starts_at"] != before_delay
        assert delayed["audit_event"]["action"] == "scheduler_chain_delayed"
        print("Delay chain OK")

        r = client.get("/api/scheduler/status")
        assert r.status_code == 200, r.text
        status = r.json()
        for key in ["case_procedure_count", "schedule_block_count", "active_block_count", "rooms_in_schedule", "conflict_count", "conflicts", "blocks"]:
            assert key in status, f"Missing scheduler status key {key}"
        assert status["schedule_block_count"] >= 5
        print("Scheduler status OK")

    print("\n--- SCHEDULER SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
