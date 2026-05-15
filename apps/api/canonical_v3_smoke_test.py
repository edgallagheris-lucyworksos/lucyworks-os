import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "canonical_v3_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models import AuditEvent, WorkItem

print("\n--- RUNNING CANONICAL V3 TRIAGE SMOKE TEST ---\n")

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text

    collapse_payload = {
        "patient_name": "Bella",
        "species": "dog",
        "owner_name": "Owner A",
        "presenting_problem": "collapse",
        "symptoms_text": "Collapsed at home and now weak",
        "duration_days": 0,
        "actor_name": "Canonical Test",
    }
    r = client.post("/api/v3/cases", json=collapse_payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["triage"]["triage_result"] == "emergency"
    assert data["triage"]["urgency"] == "red"
    assert data["triage"]["handoff"] == "required"

    urgent_payload = {
        "patient_name": "Milo",
        "species": "cat",
        "owner_name": "Owner B",
        "presenting_problem": "vomiting",
        "symptoms_text": "Vomiting since this morning",
        "duration_days": 1,
        "actor_name": "Canonical Test",
    }
    r = client.post("/api/v3/cases", json=urgent_payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["triage"]["triage_result"] == "urgent"
    assert data["triage"]["urgency"] == "amber"

    ethics_payload = {
        "patient_name": "Scout",
        "species": "dog",
        "owner_name": "Owner C",
        "presenting_problem": "routine check",
        "financial_constraint": True,
        "actor_name": "Canonical Test",
    }
    r = client.post("/api/v3/cases", json=ethics_payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["triage"]["triage_result"] == "review_required"
    assert data["triage"]["urgency"] == "amber"
    assert "FINANCIAL_CONSTRAINT" in data["triage"]["ethics_flags"]

    with Session(engine) as session:
        work = session.exec(select(WorkItem)).all()
        assert len(work) >= 3
        audits = session.exec(select(AuditEvent)).all()
        actions = {a.action for a in audits}
        assert "case_created" in actions
        assert "handoff_required" in actions
        assert any(a.action == "ethics_flag:FINANCIAL_CONSTRAINT" for a in audits)

print("\n--- CANONICAL V3 TRIAGE TEST PASSED ---\n")
