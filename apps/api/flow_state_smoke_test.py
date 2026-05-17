import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "flow_state_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.flow_state_models import DischargeBlocker, OccupancyRecord, SeverityGate, StaffAssignmentRisk
from app.main import app
from app.models import Admission, Handover, ResultReview

print("\n--- RUNNING FLOW STATE REALIGNMENT SMOKE TEST ---\n")

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text

    r = client.get("/api/episodes")
    assert r.status_code == 200, r.text
    episodes = r.json()
    assert episodes, "No seeded episodes"
    episode_id = episodes[0]["id"]

    r = client.get("/api/staff")
    assert r.status_code == 200, r.text
    staff = r.json()
    assert staff, "No seeded staff"
    staff_id = staff[0]["id"]

    r = client.post("/api/flow/handovers", json={"episode_id": episode_id, "from_owner": "day_team", "to_owner": "night_team", "note": "Flow-state test handover", "actor_name": "Flow Test"})
    assert r.status_code == 200, r.text
    handover_id = r.json()["id"]

    r = client.post("/api/flow/results", json={"episode_id": episode_id, "result_type": "lab", "review_owner": "clinician", "required_action": "Review bloods before discharge", "actor_name": "Flow Test"})
    assert r.status_code == 200, r.text
    result_id = r.json()["id"]

    r = client.post("/api/flow/admissions", json={"episode_id": episode_id, "admitted_to": "ICU Bay 1", "actor_name": "Flow Test"})
    assert r.status_code == 200, r.text

    r = client.post("/api/flow/discharge-blockers", json={"episode_id": episode_id, "blocker_type": "meds_not_ready", "detail": "Discharge meds not ready", "owner_role": "pharmacy_stock", "severity": "red", "actor_name": "Flow Test"})
    assert r.status_code == 200, r.text
    blocker_id = r.json()["id"]

    r = client.post("/api/flow/occupancy", json={"episode_id": episode_id, "space_id": "ICU1", "space_type": "ICU", "actor_name": "Flow Test"})
    assert r.status_code == 200, r.text
    occupancy_id = r.json()["id"]

    r = client.post("/api/flow/severity-gates/evaluate", json={"episode_id": episode_id, "gate_name": "procedure_start", "target_entity_type": "episode", "target_entity_id": episode_id, "triage_red_flags": True, "safeguarding_escalation": False, "rota_risk": "LOW", "actor_name": "Flow Test"})
    assert r.status_code == 200, r.text
    gate = r.json()
    assert gate["severity"] == "CRITICAL"
    assert gate["status"] == "blocked"

    r = client.post("/api/flow/staff-assignment-risk", json={"episode_id": episode_id, "staff_member_id": staff_id, "role_required": "clinician", "required_skills": ["Unmatched Skill"], "current_load": 5, "max_cases_per_day": 5, "actor_name": "Flow Test"})
    assert r.status_code == 200, r.text
    risk = r.json()
    assert risk["rota_risk"] == "HIGH"
    assert risk["status"] == "review_required"

    r = client.get("/api/flow-state")
    assert r.status_code == 200, r.text
    state = r.json()
    assert state["summary"]["unacknowledged_handovers"] >= 1
    assert state["summary"]["pending_results"] >= 1
    assert state["summary"]["open_discharge_blockers"] >= 1
    assert state["summary"]["active_occupancy"] >= 1
    assert state["summary"]["blocked_live_gates"] >= 1
    assert state["summary"]["staff_assignments_requiring_review"] >= 1
    print("Flow-state summary OK")

    r = client.post(f"/api/flow/handovers/{handover_id}/ack?actor_name=Flow%20Test")
    assert r.status_code == 200, r.text
    assert r.json()["acknowledged"] is True

    r = client.post(f"/api/flow/results/{result_id}/review?actor_name=Flow%20Test")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "reviewed"

    r = client.post(f"/api/flow/discharge-blockers/{blocker_id}/resolve?note=meds%20ready&actor_name=Flow%20Test")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"

    r = client.post(f"/api/flow/occupancy/{occupancy_id}/release?actor_name=Flow%20Test")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cleaning"

    r = client.get("/api/flow/catalogues")
    assert r.status_code == 200, r.text
    catalogues = r.json()
    for key in ["discharge_blockers", "room_states", "intake_statuses", "alerts", "compliance_controls"]:
        assert key in catalogues, f"Missing catalogue {key}"

    with Session(engine) as session:
        assert session.exec(select(Handover)).first() is not None
        assert session.exec(select(ResultReview)).first() is not None
        assert session.exec(select(Admission)).first() is not None
        assert session.exec(select(DischargeBlocker)).first() is not None
        assert session.exec(select(OccupancyRecord)).first() is not None
        assert session.exec(select(SeverityGate)).first() is not None
        assert session.exec(select(StaffAssignmentRisk)).first() is not None

print("\n--- FLOW STATE REALIGNMENT TEST PASSED ---\n")
