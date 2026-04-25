import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from app.main import app

print("\n--- RUNNING BACKEND SMOKE TEST ---\n")

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    print("Health OK")

    r = client.get("/api/episodes")
    assert r.status_code == 200, r.text
    episodes = r.json()
    assert len(episodes) > 0, "No seeded episodes returned"
    print("Episodes OK")

    ep_ref = "EP-1042"

    r = client.get(f"/api/episode-command/{ep_ref}")
    assert r.status_code == 200, r.text
    command = r.json()
    assert command["episode"]["episode_ref"] == ep_ref
    assert command["patient"] is not None
    print("Episode command OK")

    r = client.get("/api/director-board")
    assert r.status_code == 200, r.text
    assert "cards" in r.json()
    print("Director board OK")

    r = client.get("/api/consult-board")
    assert r.status_code == 200, r.text
    assert "room_groups" in r.json()
    print("Consult board OK")

    r = client.get("/api/ward-board")
    assert r.status_code == 200, r.text
    assert "room_groups" in r.json()
    print("Ward board OK")

    r = client.get("/api/theatre-board")
    assert r.status_code == 200, r.text
    assert "room_groups" in r.json()
    print("Theatre board OK")

    r = client.post("/api/schedule/generate", json={
        "episode_ref": ep_ref,
        "procedure_type_id": 1,
        "room_name": "Theatre 1",
        "start_time": "2026-04-24T10:00:00",
        "actor_name": "Smoke Test"
    })
    assert r.status_code == 200, r.text
    print("Schedule generated")

    r = client.get("/api/schedule-blocks")
    assert r.status_code == 200, r.text
    blocks = r.json()
    assert len(blocks) >= 5, "Schedule generation did not create expected block chain"
    block_id = blocks[0]["id"]
    print("Blocks OK")

    r = client.post(f"/api/schedule/block/{block_id}/shift", json={"minutes": 15, "actor_name": "Smoke Test"})
    assert r.status_code == 200, r.text
    print("Shift OK")

    r = client.get("/api/staff")
    assert r.status_code == 200, r.text
    staff = r.json()
    assert len(staff) > 0, "No seeded staff returned"
    staff_id = staff[0]["id"]
    print("Staff OK")

    r = client.post("/api/staff/allocate", json={
        "schedule_block_id": block_id,
        "staff_member_id": staff_id,
        "actor_name": "Smoke Test"
    })
    assert r.status_code == 200, r.text
    allocation = r.json()
    assert allocation["status"] in {"allocated", "conflict"}
    print("Staff allocation endpoint OK")

    r = client.get("/api/conflicts")
    assert r.status_code == 200, r.text
    assert "conflicts" in r.json()
    print("Conflicts OK")

    r = client.post("/api/conflicts/to-work?conflict_type=smoke_test&severity=high&detail=Smoke%20test%20conflict")
    assert r.status_code == 200, r.text
    assert "work_item" in r.json()
    print("Conflict to work OK")

    r = client.get(f"/api/episode-command/{ep_ref}")
    assert r.status_code == 200, r.text
    command = r.json()
    assert "schedule_blocks" in command
    assert "work_items" in command
    print("Episode command after actions OK")

print("\n--- ALL TESTS PASSED ---\n")
