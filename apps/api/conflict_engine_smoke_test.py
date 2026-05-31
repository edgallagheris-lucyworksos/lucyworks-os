import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_conflict_engine_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)

print("\n--- RUNNING CONFLICT ENGINE SMOKE TEST ---\n")

try:
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200, r.text

        r = client.get("/api/conflict-engine/conflicts")
        assert r.status_code == 200, r.text
        conflicts_before = r.json()
        assert "count" in conflicts_before and "conflicts" in conflicts_before
        print("Conflict list OK")

        r = client.get("/api/conflict-engine/pulse")
        assert r.status_code == 200, r.text
        pulse_before = r.json()
        for key in ["pressure_score", "state", "conflict_count", "conflicts_by_type", "conflicts_by_department"]:
            assert key in pulse_before, f"Pulse missing {key}"
        print("Pulse OK")

        r = client.post("/api/conflict-engine/recalculate")
        assert r.status_code == 200, r.text
        recalculated = r.json()
        assert recalculated["ok"] is True
        assert recalculated["audit_event"]["action"] == "conflicts_recalculated"
        print("Recalculate OK")

        r = client.post("/api/conflict-engine/to-work-items")
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["ok"] is True
        assert "created_count" in created
        assert created["audit_event"]["action"] == "conflicts_converted_to_work_items"
        print("Conflict to work items OK")

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

        start = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
        payload = {
            "episode_id": episode["id"],
            "procedure_type_id": procedure_type["id"],
            "room_name": "Theatre 1",
            "starts_at": start,
            "actor_name": "Conflict Smoke Test",
        }
        r = client.post("/api/scheduler/chains/generate", json=payload)
        assert r.status_code == 200, r.text
        first_chain = r.json()
        assert first_chain["ok"] is True

        r = client.post("/api/scheduler/chains/generate", json=payload)
        assert r.status_code == 200, r.text
        second_chain = r.json()
        assert second_chain["ok"] is True
        print("Overlapping scheduler chains created")

        r = client.post("/api/conflict-engine/recalculate")
        assert r.status_code == 200, r.text
        after_overlap = r.json()
        assert after_overlap["count"] >= conflicts_before["count"]
        assert any(conflict.get("type") == "resource_conflict" for conflict in after_overlap["conflicts"]), after_overlap
        print("Conflict recalculation after scheduler change OK")

        r = client.get("/api/conflict-engine/pulse")
        assert r.status_code == 200, r.text
        pulse_after = r.json()
        assert pulse_after["conflict_count"] >= pulse_before["conflict_count"]
        assert pulse_after["pressure_score"] >= pulse_before["pressure_score"]
        print("Pulse recalculation after scheduler change OK")

    print("\n--- CONFLICT ENGINE SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
