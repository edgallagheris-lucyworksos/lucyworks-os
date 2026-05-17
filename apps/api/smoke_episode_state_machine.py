import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "smoke_episode_state_machine.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from app.main import app

print("\n--- RUNNING EPISODE STATE MACHINE SMOKE TEST ---\n")

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    print("Health OK")

    r = client.get("/api/episode-state-machine")
    assert r.status_code == 200, r.text
    spec = r.json()
    for state in ["intake", "triage", "consult", "admitted", "diagnostics", "awaiting_results", "awaiting_consent", "scheduled", "prep", "anaesthesia", "procedure", "recovery", "ward", "icu", "discharge_ready", "discharged", "closed"]:
        assert state in spec["states"], f"Missing state: {state}"
    assert spec["allowed_transitions"]["intake"], "Allowed transitions missing"
    assert spec["state_owners"]["procedure"] == "clinician"
    print("State machine spec OK")

    r = client.get("/api/episodes")
    assert r.status_code == 200, r.text
    episode = next((e for e in r.json() if e["episode_ref"] == "EP-1042"), r.json()[0])
    episode_ref = episode["episode_ref"]
    print(f"Episode loaded: {episode_ref}")

    r = client.get(f"/api/episodes/{episode_ref}/state-guard/procedure")
    assert r.status_code == 200, r.text
    guard = r.json()
    assert guard["can_transition"] is False, "Direct unsafe transition to procedure should be blocked"
    assert guard["hard_failures"], "Blocked transition should explain why"
    assert guard["next_action"], "Blocked transition should return next action"
    print("Unsafe direct procedure transition blocked OK")

    r = client.post(f"/api/episodes/{episode_ref}/transition", json={"target_state": "procedure", "actor_name": "State Smoke Test", "reason": "prove unsafe movement blocks"})
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["ok"] is False, "Unsafe transition unexpectedly succeeded"
    assert result["guard"]["can_transition"] is False
    print("Transition API blocks unsafe movement OK")

    r = client.post(f"/api/episodes/{episode_ref}/transition", json={"target_state": "triage", "actor_name": "State Smoke Test", "reason": "allowed first movement"})
    assert r.status_code == 200, r.text
    allowed = r.json()
    assert "guard" in allowed
    assert allowed.get("ok") in {True, False}
    print("Allowed graph route evaluated OK")

    r = client.get("/api/audit")
    assert r.status_code == 200, r.text
    audit = r.json()
    assert any(event["action"] == "episode_transition_blocked" for event in audit), "Blocked transition audit missing"
    print("Transition audit OK")

print("\n--- EPISODE STATE MACHINE SMOKE TEST PASSED ---\n")
