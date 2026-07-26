import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "workspace_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AUTH_MODE"] = "local"
os.environ["AUTH_JWT_SECRET"] = "workspace-smoke-test-secret-long-enough"
os.environ["AUTH_AUDIENCE"] = "lucyworks-api"
os.environ["AUTH_ISSUER"] = "lucyworks-local"

from fastapi.testclient import TestClient

from app.auth import issue_local_token
from app.main import app

print("\n--- RUNNING VERIFIED WORKSPACE ROLE QUEUE SMOKE TEST ---\n")

ops_token, _ = issue_local_token(user_id=701, name="Workspace Ops", role="ops_manager", email="workspace-ops@lucyworks.local")
clinician_token, _ = issue_local_token(user_id=702, name="Workspace Clinician", role="clinician", email="workspace-clinician@lucyworks.local")
ops_headers = {"Authorization": f"Bearer {ops_token}"}
clinician_headers = {"Authorization": f"Bearer {clinician_token}"}

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text

    r = client.get("/api/episodes")
    assert r.status_code == 200, r.text
    episode_id = r.json()[0]["id"]

    r = client.get("/api/staff")
    assert r.status_code == 200, r.text
    staff_id = r.json()[0]["id"]

    client.post("/api/flow/handovers", json={"episode_id": episode_id, "from_owner": "day_team", "to_owner": "clinician", "note": "Workspace test handover", "actor_name": "Workspace Test"})
    client.post("/api/flow/results", json={"episode_id": episode_id, "result_type": "lab", "review_owner": "clinician", "actor_name": "Workspace Test"})
    client.post("/api/flow/discharge-blockers", json={"episode_id": episode_id, "blocker_type": "review_pending", "detail": "Clinician review required", "owner_role": "clinician", "severity": "amber", "actor_name": "Workspace Test"})
    client.post("/api/flow/occupancy", json={"episode_id": episode_id, "space_id": "Ward-A1", "space_type": "ward", "actor_name": "Workspace Test"})
    client.post("/api/flow/severity-gates/evaluate", json={"episode_id": episode_id, "gate_name": "workspace_gate", "target_entity_type": "episode", "target_entity_id": episode_id, "triage_red_flags": True, "actor_name": "Workspace Test"})
    client.post("/api/flow/staff-assignment-risk", json={"episode_id": episode_id, "staff_member_id": staff_id, "role_required": "clinician", "required_skills": ["Impossible Skill"], "current_load": 5, "max_cases_per_day": 5, "actor_name": "Workspace Test"})

    r = client.get("/api/workspace?role=ops_manager", headers=ops_headers)
    assert r.status_code == 200, r.text
    ops = r.json()
    assert ops["role"] == "ops_manager"
    assert ops["summary"]["handovers"] >= 1
    assert ops["summary"]["results"] >= 1
    assert ops["summary"]["discharge_blockers"] >= 1
    assert ops["summary"]["blocked_gates"] >= 1
    assert ops["summary"]["staff_risks"] >= 1
    assert ops["summary"]["occupancy"] >= 1
    print("Verified ops workspace sees full command queue")

    r = client.get("/api/workspace?role=clinician", headers=clinician_headers)
    assert r.status_code == 200, r.text
    clinician = r.json()
    assert clinician["role"] == "clinician"
    assert clinician["summary"]["handovers"] >= 1
    assert clinician["summary"]["results"] >= 1
    assert clinician["summary"]["discharge_blockers"] >= 1
    print("Verified clinician workspace sees owned clinical queue")

    r = client.get("/api/workspace?role=ops_manager", headers=clinician_headers)
    assert r.status_code == 403, r.text
    print("Browser role spoofing is rejected")

    r = client.get(f"/api/workspace?staff_member_id={staff_id}", headers=clinician_headers)
    assert r.status_code == 403, r.text
    print("Non-senior cross-staff inspection is rejected")

    r = client.get(f"/api/workspace?staff_member_id={staff_id}", headers=ops_headers)
    assert r.status_code == 200, r.text
    personal = r.json()
    assert personal["staff_member_id"] == staff_id
    assert "summary" in personal
    assert "queues" in personal
    print("Verified senior role can inspect a staff-specific workspace")

print("\n--- VERIFIED WORKSPACE ROLE QUEUE TEST PASSED ---\n")
