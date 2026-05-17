import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(__file__).parent / "hr_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.hr_models import CompetencyRecord, FatigueRiskRecord, LeaveRequest, OnCallAssignment, OvertimeRequest, StaffProfile
from app.main import app

print("\n--- RUNNING HR STAFFING SMOKE TEST ---\n")

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text

    r = client.get("/api/staff")
    assert r.status_code == 200, r.text
    staff = r.json()
    assert staff, "No seeded staff found"
    staff_id = staff[0]["id"]

    now = datetime.now(timezone.utc).replace(microsecond=0)

    r = client.post("/api/hr/profiles", json={
        "staff_member_id": staff_id,
        "employment_type": "employed",
        "contract_hours_per_week": 40,
        "primary_department": "ICU",
        "seniority": "senior",
        "line_manager": "Clinical Director",
        "actor_name": "HR Test",
    })
    assert r.status_code == 200, r.text
    assert r.json()["primary_department"] == "ICU"

    r = client.post("/api/hr/competencies", json={
        "staff_member_id": staff_id,
        "competency": "ICU q30 observations",
        "department": "ICU",
        "expires_at": (now + timedelta(days=365)).isoformat(),
        "evidence_note": "Signed off in supervised shift",
        "actor_name": "HR Test",
    })
    assert r.status_code == 200, r.text
    competency_id = r.json()["id"]

    r = client.post(f"/api/hr/competencies/{competency_id}/approve", json={
        "reviewer_name": "Clinical Director",
        "decision_note": "Competent for ICU observation tasks",
        "actor_name": "HR Test",
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    r = client.post("/api/hr/leave", json={
        "staff_member_id": staff_id,
        "leave_type": "annual_leave",
        "starts_at": (now + timedelta(days=10)).isoformat(),
        "ends_at": (now + timedelta(days=11)).isoformat(),
        "reason": "planned leave",
        "actor_name": "HR Test",
    })
    assert r.status_code == 200, r.text
    leave_id = r.json()["id"]

    r = client.post(f"/api/hr/leave/{leave_id}/decision", json={
        "reviewer_name": "Ops Manager",
        "approve": True,
        "decision_note": "Coverage checked",
        "actor_name": "HR Test",
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    r = client.post("/api/hr/overtime", json={
        "staff_member_id": staff_id,
        "hours": 14,
        "reason": "ICU pressure and late discharge blocker",
        "actor_name": "HR Test",
    })
    assert r.status_code == 200, r.text
    overtime_id = r.json()["id"]

    r = client.post(f"/api/hr/overtime/{overtime_id}/decision", json={
        "reviewer_name": "Ops Manager",
        "approve": True,
        "decision_note": "Approved due to ICU pressure",
        "actor_name": "HR Test",
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    for day in range(3):
        r = client.post("/api/hr/on-call", json={
            "staff_member_id": staff_id,
            "department": "ICU",
            "starts_at": (now + timedelta(hours=day * 18)).isoformat(),
            "ends_at": (now + timedelta(hours=day * 18 + 12)).isoformat(),
            "escalation_role": "icu_on_call",
            "actor_name": "HR Test",
        })
        assert r.status_code == 200, r.text

    r = client.post(f"/api/hr/fatigue/evaluate/{staff_id}?actor_name=HR%20Test")
    assert r.status_code == 200, r.text
    risk = r.json()["risk"]
    assert risk["risk_level"] in {"MED", "HIGH"}

    r = client.get("/api/hr")
    assert r.status_code == 200, r.text
    overview = r.json()
    assert len(overview["profiles"]) >= 1
    assert len(overview["competencies"]) >= 1
    assert len(overview["leave_requests"]) >= 1
    assert len(overview["overtime_requests"]) >= 1
    assert len(overview["on_call"]) >= 3
    assert len(overview["fatigue_risks"]) >= 1

    with Session(engine) as session:
        assert session.exec(select(StaffProfile)).first() is not None
        assert session.exec(select(CompetencyRecord)).first() is not None
        assert session.exec(select(LeaveRequest)).first() is not None
        assert session.exec(select(OvertimeRequest)).first() is not None
        assert session.exec(select(OnCallAssignment)).first() is not None
        assert session.exec(select(FatigueRiskRecord)).first() is not None

print("\n--- HR STAFFING TEST PASSED ---\n")
