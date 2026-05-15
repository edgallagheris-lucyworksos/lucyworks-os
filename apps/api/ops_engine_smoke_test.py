import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "ops_engine_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models import AuditEvent, Episode

print("\n--- RUNNING OPERATIONAL WORKFLOW ENGINE SMOKE TEST ---\n")

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text

    r = client.post("/api/admin/first-run")
    assert r.status_code == 200, r.text

    r = client.get("/api/ops-engine/workflows")
    assert r.status_code == 200, r.text
    assert "surgery_theatre" in r.json()["workflows"]

    r = client.get("/api/ops-engine/episodes/EP-2001")
    assert r.status_code == 200, r.text
    state = r.json()
    assert state["episode_ref"] == "EP-2001"

    r = client.post("/api/ops-engine/episodes/EP-2001/transition", json={"target_state": "procedure_in_progress", "actor_name": "Smoke Test", "note": "unsafe jump should block"})
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["allowed"] is False
    assert detail["reasons"], detail

    with Session(engine) as session:
        ep = session.exec(select(Episode).where(Episode.episode_ref == "EP-2001")).first()
        assert ep is not None
        ep.current_phase = "waiting_for_theatre"
        session.add(ep)
        session.commit()

    r = client.post("/api/ops-engine/episodes/EP-2001/transition", json={"target_state": "in_prep", "actor_name": "Smoke Test", "note": "valid theatre movement"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["allowed"] is True
    assert data["episode"]["current_phase"] == "in_prep"

    with Session(engine) as session:
        audits = session.exec(select(AuditEvent).where(AuditEvent.entity_type == "episode")).all()
        actions = {a.action for a in audits}
        assert "transition_blocked" in actions
        assert "transitioned" in actions

print("\n--- OPERATIONAL WORKFLOW ENGINE TEST PASSED ---\n")
