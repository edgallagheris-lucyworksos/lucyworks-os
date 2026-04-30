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

    r = client.get("/api/operating-catalogue")
    assert r.status_code == 200, r.text
    catalogue = r.json()
    assert len(catalogue["departments"]) >= 8, "Operating catalogue missing departments"
    assert len(catalogue["procedure_templates"]) >= 10, "Operating catalogue missing procedures"
    assert len(catalogue["pharmacy_governance"]) >= 5, "Operating catalogue missing pharmacy governance"
    assert "legal_and_compliance_guardrails" in catalogue, "Compliance guardrails missing"
    assert "procedure_dependency_layers" in catalogue, "Procedure dependency layers missing"
    print("Operating catalogue OK")

    r = client.get("/api/episodes")
    assert r.status_code == 200, r.text
    episodes = r.json()
    assert episodes, "No seeded episodes"
    episode = next((e for e in episodes if e["episode_ref"] == "EP-1042"), episodes[0])
    episode_id = episode["id"]
    episode_ref = episode["episode_ref"]
    print(f"Episode OK: {episode_ref}")

    r = client.post("/api/operating-catalogue/schedule-from-template", json={
        "episode_ref": episode_ref,
        "procedure_name": "CT scan",
        "room_name": "CT",
        "start_time": "2026-01-01T09:00:00+00:00",
        "actor_name": "Safety Smoke Test",
    })
    assert r.status_code == 200, r.text
    schedule = r.json()
    assert schedule["template"]["name"] == "CT scan"
    assert schedule["total_minutes"] == 105
    assert len(schedule["blocks"]) >= 4
    assert any(block["block_type"] == "anaesthesia" for block in schedule["blocks"])
    print("Catalogue schedule generation OK")

    r = client.get("/api/message-threads")
    assert r.status_code == 200, r.text
    threads = r.json()
    assert threads, "No seeded message threads"
    thread_id = threads[0]["id"]
    r = client.post(f"/api/messages/{thread_id}", json={"sender_name": "Smoke Mail Ops", "direction": "outbound", "body": "Safety smoke test owner update", "material_decision_flag": True, "actor_name": "Smoke Test"})
    assert r.status_code == 200, r.text
    assert r.json()["body"] == "Safety smoke test owner update"
    print("Mail Ops reply OK")

    r = client.get("/api/room-states")
    assert r.status_code == 200, r.text
    rooms = r.json()
    assert rooms, "No seeded room states"
    room_id = rooms[0]["id"]
    r = client.post(f"/api/room-states/{room_id}/set?state=cleaning")
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "cleaning"
    r = client.post(f"/api/room-states/{room_id}/set?state=available")
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "available"
    print("Room state controls OK")

    r = client.post("/api/lucyflow/triage", json={"episode_id": episode_id, "species": "dog", "presenting_signs": "pain, breathing difficulty and owner worried about cost"})
    assert r.status_code == 200, r.text
    triage = r.json()["triage"]
    assert triage["urgency"] in {"red", "amber"}
    assert triage["owner_contact_required"] is True
    print("LucyFlow signal OK")

    r = client.post("/api/lucy-ethics", json={"episode_id": episode_id, "flag_type": "financial_constraint_affecting_care", "severity": "high", "detail": "Owner cost concern may delay pain treatment", "clinical_reasoning": "Pain and affordability issue create welfare risk", "owner_state": "cost_concern", "decision_required": "senior clinician review", "escalation_path": "clinician_to_ops_manager", "owner_role": "clinician"})
    assert r.status_code == 200, r.text
    print("Lucy Ethics signal OK")

    r = client.post("/api/discharge-readiness", json={"episode_id": episode_id, "blocker_summary": "Medication and owner update incomplete", "urgency": "amber", "owner_role": "clinician"})
    assert r.status_code == 200, r.text
    assert r.json()["readiness_state"] == "blocked"
    print("Discharge blocker OK")

    r = client.post("/api/stock-items", json={"name": "IV catheter 22G safety test", "category": "clinical", "location": "main stock", "current_quantity": 0, "reorder_threshold": 5, "authorised_supplier": "NVS", "compliance_note": "Safety smoke test low stock item"})
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

    r = client.get(f"/api/episode-operating-readiness/{episode_ref}")
    assert r.status_code == 200, r.text
    operating_readiness = r.json()
    assert operating_readiness["episode_ref"] == episode_ref
    assert operating_readiness["procedure_count"] >= 1
    assert operating_readiness["procedures"][0]["readiness_gates"], "Operating readiness gates missing"
    print("Episode operating readiness OK")

    r = client.get("/api/dashboard/intelligence")
    assert r.status_code == 200, r.text
    dashboard = r.json()
    assert dashboard["dashboard_basis"] == "15-minute operational command grid"
    assert len(dashboard["slots"]) == 56
    assert dashboard["summary"]["schedule_blocks"] >= len(schedule["blocks"])
    active_slots = [slot for slot in dashboard["slots"] if slot["active_count"]]
    assert active_slots, "Dashboard has no active 15-minute slots"
    active_block = active_slots[0]["blocks"][0]
    assert "episode" in active_block and active_block["episode"], "Dashboard block missing episode context"
    assert "pressure" in active_block, "Dashboard block missing pressure context"
    assert "operating" in active_block, "Dashboard block missing operating context"
    print("Dashboard intelligence OK")

    r = client.get("/api/domain-pressure")
    assert r.status_code == 200, r.text
    pressure = r.json()
    for key in ["discharge_blocked", "pharmacy_open", "stock_orders_open", "low_stock"]:
        assert key in pressure, f"Missing domain pressure: {key}"
    print("Domain pressure OK")

    r = client.get("/api/audit")
    assert r.status_code == 200, r.text
    audit = r.json()
    assert any(event["entity_type"] == "message_entry" for event in audit), "Message audit missing"
    assert any(event["entity_type"] == "room_state" for event in audit), "Room state audit missing"
    assert any(event["action"] == "catalogue_schedule_generated" for event in audit), "Catalogue schedule audit missing"
    print("Audit coverage OK")

print("\n--- DOMAIN SAFETY SMOKE TEST PASSED ---\n")
