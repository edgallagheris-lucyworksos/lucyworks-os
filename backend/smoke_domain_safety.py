import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "smoke_domain_safety.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from app.main import app

print("\n--- RUNNING DOMAIN SAFETY SMOKE TEST ---\n")

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    print("Health OK")

    r = client.get("/api/episodes")
    assert r.status_code == 200, r.text
    episodes = r.json()
    assert episodes, "No seeded episodes"
    episode = next((e for e in episodes if e["episode_ref"] == "EP-1042"), episodes[0])
    episode_id = episode["id"]
    print(f"Episode OK: {episode['episode_ref']}")

    r = client.post("/api/lucyflow/triage", json={
        "episode_id": episode_id,
        "species": "dog",
        "presenting_signs": "pain, breathing difficulty and owner worried about cost",
    })
    assert r.status_code == 200, r.text
    triage = r.json()["triage"]
    assert triage["urgency"] in {"red", "amber"}
    assert triage["owner_contact_required"] is True
    print("LucyFlow signal OK")

    r = client.post("/api/lucy-ethics", json={
        "episode_id": episode_id,
        "flag_type": "financial_constraint_affecting_care",
        "severity": "high",
        "detail": "Owner cost concern may delay pain treatment",
        "clinical_reasoning": "Pain and affordability issue create welfare risk",
        "owner_state": "cost_concern",
        "decision_required": "senior clinician review",
        "escalation_path": "clinician_to_ops_manager",
        "owner_role": "clinician",
    })
    assert r.status_code == 200, r.text
    print("Lucy Ethics signal OK")

    r = client.post("/api/discharge-readiness", json={
        "episode_id": episode_id,
        "blocker_summary": "Medication and owner update incomplete",
        "urgency": "amber",
        "owner_role": "clinician",
    })
    assert r.status_code == 200, r.text
    assert r.json()["readiness_state"] == "blocked"
    print("Discharge blocker OK")

    r = client.post("/api/stock-items", json={
        "name": "IV catheter 22G safety test",
        "category": "clinical",
        "location": "main stock",
        "current_quantity": 0,
        "reorder_threshold": 5,
        "authorised_supplier": "NVS",
        "compliance_note": "Safety smoke test low stock item",
    })
    assert r.status_code == 200, r.text
    print("Low stock signal OK")

    r = client.post("/api/automation/run-domain-links")
    assert r.status_code == 200, r.text
    created = r.json()["created"]
    for key in ["owner_comms", "pharmacy_requests", "stock_orders", "work_items"]:
        assert key in created, f"Missing automation counter: {key}"
    assert created["owner_comms"] >= 1, created
    assert created["pharmacy_requests"] >= 1, created
    assert created["stock_orders"] >= 1, created
    print("Domain automation OK")

    r = client.get(f"/api/flow-readiness/{episode_id}")
    assert r.status_code == 200, r.text
    readiness = r.json()
    assert readiness["episode_id"] == episode_id
    assert readiness["ready_for_flow"] is False
    assert readiness["hard_block_count"] >= 1
    assert "hard_blocks" in readiness and "warnings" in readiness
    print("Flow readiness blocks unsafe flow OK")

    r = client.get("/api/domain-pressure")
    assert r.status_code == 200, r.text
    pressure = r.json()
    for key in ["discharge_blocked", "pharmacy_open", "stock_orders_open", "low_stock"]:
        assert key in pressure, f"Missing domain pressure: {key}"
    print("Domain pressure OK")

print("\n--- DOMAIN SAFETY SMOKE TEST PASSED ---\n")
