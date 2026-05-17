import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "live_action_gate_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.flow_state_models import DischargeBlocker, SeverityGate, StaffAssignmentRisk
from app.main import app
from app.models import PharmacyRequest, ResultReview, ScheduleBlock

print("\n--- RUNNING LIVE ACTION GATE SMOKE TEST ---\n")

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text

    r = client.get("/api/episodes")
    assert r.status_code == 200, r.text
    episode_id = r.json()[0]["id"]

    r = client.get("/api/staff")
    assert r.status_code == 200, r.text
    staff_id = r.json()[0]["id"]

    # Create blockers that must prevent discharge approval.
    r = client.post("/api/flow/results", json={"episode_id": episode_id, "result_type": "lab", "review_owner": "clinician", "actor_name": "Gate Test"})
    assert r.status_code == 200, r.text
    result_id = r.json()["id"]

    r = client.post("/api/flow/discharge-blockers", json={"episode_id": episode_id, "blocker_type": "meds_not_ready", "detail": "Meds still outstanding", "owner_role": "pharmacy_stock", "severity": "red", "actor_name": "Gate Test"})
    assert r.status_code == 200, r.text
    blocker_id = r.json()["id"]

    r = client.post(f"/api/live-actions/discharge/{episode_id}/approve", json={"actor_name": "Gate Test"})
    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    assert body["blocked"] is True
    assert body["severity"] == "CRITICAL"
    assert "discharge_approval" == body["gate_name"]
    print("Discharge gate blocks correctly")

    # Clear blockers then discharge can pass.
    r = client.post(f"/api/flow/results/{result_id}/review?actor_name=Gate%20Test")
    assert r.status_code == 200, r.text
    r = client.post(f"/api/flow/discharge-blockers/{blocker_id}/resolve?note=cleared&actor_name=Gate%20Test")
    assert r.status_code == 200, r.text
    r = client.post(f"/api/live-actions/discharge/{episode_id}/approve", json={"actor_name": "Gate Test"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    print("Discharge gate passes after blockers clear")

    # Create HIGH staff risk and prove it blocks schedule start.
    with Session(engine) as session:
        block = session.exec(select(ScheduleBlock)).first()
        assert block is not None, "No schedule block found"
        block_id = block.id
        episode_for_block = block.episode_id

    r = client.post("/api/flow/staff-assignment-risk", json={"episode_id": episode_for_block, "staff_member_id": staff_id, "role_required": "clinician", "required_skills": ["Impossible Skill"], "current_load": 5, "max_cases_per_day": 5, "actor_name": "Gate Test"})
    assert r.status_code == 200, r.text
    risk_id = r.json()["id"]
    assert r.json()["rota_risk"] == "HIGH"

    r = client.post(f"/api/live-actions/schedule-blocks/{block_id}/start", json={"actor_name": "Gate Test"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["blocked"] is True
    print("Schedule start gate blocks HIGH staff risk")

    r = client.post(f"/api/live-actions/staff-assignment-risk/{risk_id}/approve", json={"actor_name": "Gate Test", "reviewer_name": "Clinical Director", "override_reason": "Reviewed and safe for test"})
    assert r.status_code == 200, r.text
    assert r.json()["staff_assignment_risk"]["status"] == "approved"
    print("Staff risk can be approved with reviewer and reason")

    # Pharmacy request completion blocks restricted item without clinician, then passes with responsible clinician.
    with Session(engine) as session:
        request = PharmacyRequest(episode_id=episode_id, medication_name="Restricted workflow item", request_type="dispense", controlled_or_legal_status="restricted", status="requested")
        session.add(request)
        session.commit()
        session.refresh(request)
        request_id = request.id

    r = client.post(f"/api/live-actions/pharmacy-requests/{request_id}/complete", json={"actor_name": "Gate Test"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["severity"] == "MODERATE"
    print("Pharmacy request gate requires responsible clinician")

    r = client.post(f"/api/live-actions/pharmacy-requests/{request_id}/complete", json={"actor_name": "Gate Test", "responsible_clinician": "Dr Test", "reviewer_name": "Dr Test", "override_reason": "Clinician signoff supplied"})
    assert r.status_code == 200, r.text
    assert r.json()["pharmacy_request"]["status"] == "completed"
    print("Pharmacy request gate passes with signoff")

    with Session(engine) as session:
        assert session.exec(select(SeverityGate)).first() is not None
        assert session.exec(select(ResultReview)).first() is not None
        assert session.exec(select(DischargeBlocker)).first() is not None
        assert session.exec(select(StaffAssignmentRisk)).first() is not None

print("\n--- LIVE ACTION GATE TEST PASSED ---\n")
