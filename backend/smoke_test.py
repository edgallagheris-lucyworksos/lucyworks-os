from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("\n--- RUNNING BACKEND SMOKE TEST ---\n")

# 1. Health
r = client.get("/api/health")
assert r.status_code == 200
print("Health OK")

# 2. Episodes
r = client.get("/api/episodes")
assert r.status_code == 200
episodes = r.json()
assert len(episodes) > 0
print("Episodes OK")

ep_ref = episodes[0]["episode_ref"]

# 3. Generate schedule
r = client.post("/api/schedule/generate", json={
    "episode_ref": ep_ref,
    "procedure_type_id": 1,
    "room_name": "Theatre 1",
    "start_time": "2026-04-24T10:00:00"
})
assert r.status_code == 200
print("Schedule generated")

# 4. Get blocks
r = client.get("/api/schedule-blocks")
blocks = r.json()
assert len(blocks) > 0
block_id = blocks[0]["id"]
print("Blocks OK")

# 5. Shift block
r = client.post(f"/api/schedule/block/{block_id}/shift", json={"minutes": 15})
assert r.status_code == 200
print("Shift OK")

# 6. Staff list
r = client.get("/api/staff")
staff = r.json()
assert len(staff) > 0
staff_id = staff[0]["id"]
print("Staff OK")

# 7. Allocate staff
r = client.post("/api/staff/allocate", json={
    "schedule_block_id": block_id,
    "staff_member_id": staff_id
})
assert r.status_code == 200
print("Staff allocation OK")

# 8. Episode command
r = client.get(f"/api/episode-command/{ep_ref}")
assert r.status_code == 200
print("Episode command OK")

print("\n--- ALL TESTS PASSED ---\n")
