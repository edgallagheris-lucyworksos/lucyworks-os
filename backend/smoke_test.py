import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from app.main import app

print("\n--- RUNNING BACKEND SMOKE TEST ---\n")

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    assert r.json().get("entrypoint") == "main"
    print("Health OK")

    r = client.get("/api/alerts")
    assert r.status_code == 200, r.text
    alerts = r.json()
    assert "total_alerts" in alerts and "high_alerts" in alerts and "alerts" in alerts
    print("Alerts OK")

    r = client.get("/api/episodes")
    assert r.status_code == 200, r.text
    episodes = r.json()
    assert len(episodes) > 0, "No seeded episodes returned"
    ep_ref = "EP-1042"
    episode_id = next((e["id"] for e in episodes if e["episode_ref"] == ep_ref), episodes[0]["id"])
    print("Episodes OK")

    r = client.get(f"/api/episode-command/{ep_ref}")
    assert r.status_code == 200, r.text
    command = r.json()
    assert command["episode"]["episode_ref"] == ep_ref
    assert command["patient"] is not None
    for key in ["triage", "ethics_flags", "decisions", "blockers", "escalations", "care_tasks", "owner_comms_requirements"]:
        assert key in command, f"Missing episode command key: {key}"
    print("Episode command OK")

    for endpoint, label in [("/api/director-board", "Director board"), ("/api/consult-board", "Consult board"), ("/api/ward-board", "Ward board"), ("/api/theatre-board", "Theatre board")]:
        r = client.get(endpoint)
        assert r.status_code == 200, r.text
        assert "cards" in r.json()
        print(f"{label} OK")

    r = client.get("/api/dashboard/intelligence")
    assert r.status_code == 200, r.text
    dashboard = r.json()
    assert "summary" in dashboard and "slots" in dashboard and "integrity" in dashboard
    for key in ["rooms", "schedule_blocks", "active_slots", "red_slots", "amber_slots", "alerts", "conflicts", "open_work"]:
        assert key in dashboard["summary"], f"Dashboard summary missing {key}"
    assert isinstance(dashboard["slots"], list) and len(dashboard["slots"]) == 56
    print("Dashboard intelligence OK")

    r = client.get("/api/dashboard/integrity")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), dict)
    print("Dashboard integrity OK")

    r = client.get("/api/message-threads")
    assert r.status_code == 200, r.text
    threads = r.json()
    assert isinstance(threads, list), "Message threads should return a list"
    if threads:
        thread_id = threads[0]["id"]
        r = client.get(f"/api/message-threads/{thread_id}/entries")
        assert r.status_code == 200, r.text
        before_entries = r.json()
        assert isinstance(before_entries, list)

        r = client.post(
            f"/api/messages/{thread_id}",
            json={
                "sender_name": "Smoke Test",
                "direction": "outbound",
                "body": "Automated Mail Ops smoke test message",
                "material_decision_flag": True,
                "actor_name": "Smoke Test",
            },
        )
        assert r.status_code == 200, r.text
        message = r.json()
        assert message["thread_id"] == thread_id
        assert message["material_decision_flag"] is True

        r = client.get(f"/api/message-threads/{thread_id}/entries")
        assert r.status_code == 200, r.text
        after_entries = r.json()
        assert len(after_entries) == len(before_entries) + 1
        print("Mail Ops message write OK")
    else:
        print("Mail Ops message write skipped: no seeded message threads")

    r = client.post("/api/lucyflow/triage", json={"episode_id": episode_id, "species": "dog", "presenting_signs": "collapse, breathing difficulty and pain"})
    assert r.status_code == 200, r.text
    triage_created = r.json()
    assert "triage" in triage_created and "work_item" in triage_created and "decision" in triage_created

    r = client.get("/api/lucyflow/triage")
    assert r.status_code == 200, r.text
    triage_rows = r.json()
    assert len(triage_rows) > 0
    latest_triage = triage_rows[0]
    assert latest_triage["urgency"] == "red"
    assert latest_triage["handoff_required"] is True
    triage_id = latest_triage["id"]
    print("LucyFlow triage create/list OK")

    r = client.post(f"/api/lucyflow/triage/{triage_id}/resolve?note=Smoke%20triage%20resolved")
    assert r.status_code == 200, r.text
    r = client.get("/api/lucyflow/triage")
    assert r.status_code == 200, r.text
    resolved_triage = next(item for item in r.json() if item["id"] == triage_id)
    assert resolved_triage["status"] == "resolved"
    print("LucyFlow triage resolve OK")

    r = client.post("/api/lucy-ethics", json={"episode_id": episode_id, "flag_type": "consent_delay", "severity": "high", "detail": "Owner consent delayed while patient remains painful", "clinical_reasoning": "Pain and decision delay create welfare risk", "owner_state": "consent_pending", "decision_required": "senior clinician review", "escalation_path": "clinician_to_ops_manager", "owner_role": "clinician"})
    assert r.status_code == 200, r.text
    ethics_created = r.json()
    assert "ethics_flag" in ethics_created and "work_item" in ethics_created

    r = client.get("/api/lucy-ethics")
    assert r.status_code == 200, r.text
    ethics_rows = r.json()
    assert len(ethics_rows) > 0
    latest_ethics = ethics_rows[0]
    assert latest_ethics["flag_type"] == "consent_delay"
    assert latest_ethics["severity"] == "high"
    ethics_id = latest_ethics["id"]
    print("Lucy Ethics create/list OK")

    r = client.post(f"/api/lucy-ethics/{ethics_id}/resolve?note=Smoke%20ethics%20resolved")
    assert r.status_code == 200, r.text
    r = client.get("/api/lucy-ethics")
    assert r.status_code == 200, r.text
    resolved_ethics = next(item for item in r.json() if item["id"] == ethics_id)
    assert resolved_ethics["status"] == "resolved"
    print("Lucy Ethics resolve OK")

    r = client.post("/api/lucy-care/tasks", json={"episode_id": episode_id, "task_type": "observation", "care_area": "ICU", "detail": "Repeat pain score and respiratory check", "owner_role": "nurse", "escalation_required": True})
    assert r.status_code == 200, r.text
    r = client.get("/api/lucy-care/tasks")
    assert r.status_code == 200, r.text
    care_id = r.json()[0]["id"]
    print("Lucy Care create OK")

    r = client.post(f"/api/lucy-care/tasks/{care_id}/complete")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done"
    print("Lucy Care complete OK")

    r = client.post("/api/decisions", json={"episode_id": episode_id, "decision_type": "diagnostics", "decision_needed": "Confirm CT or ultrasound route", "owner_role": "clinician", "section_name": "Diagnostics", "urgency": "amber", "source": "Smoke Test"})
    assert r.status_code == 200, r.text
    r = client.get("/api/decisions")
    assert r.status_code == 200, r.text
    decision_id = r.json()[0]["id"]
    print("Decision create OK")

    r = client.post(f"/api/decisions/{decision_id}/resolve?resolution=CT%20approved")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    print("Decision resolve OK")

    r = client.post("/api/blockers", json={"episode_id": episode_id, "blocker_type": "discharge", "section_name": "Discharge", "detail": "Medication not ready", "impact": "Patient cannot leave safely", "urgency": "amber", "owner_role": "nurse"})
    assert r.status_code == 200, r.text
    r = client.get("/api/blockers")
    assert r.status_code == 200, r.text
    blocker_id = r.json()[0]["id"]
    print("Blocker create OK")

    r = client.post(f"/api/blockers/{blocker_id}/resolve")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    print("Blocker resolve OK")

    r = client.post("/api/escalations", json={"episode_id": episode_id, "escalation_type": "welfare", "severity": "high", "reason": "Pain and consent delay", "from_role": "nurse", "to_role": "clinician"})
    assert r.status_code == 200, r.text
    r = client.get("/api/escalations")
    assert r.status_code == 200, r.text
    escalation_id = r.json()[0]["id"]
    print("Escalation create OK")

    r = client.post(f"/api/escalations/{escalation_id}/resolve")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    print("Escalation resolve OK")

    r = client.post("/api/owner-comms-requirements", json={"episode_id": episode_id, "reason": "Owner update due after result review", "required_message": "Explain result and next treatment option", "owner_role": "clinician", "urgency": "amber"})
    assert r.status_code == 200, r.text
    r = client.get("/api/owner-comms-requirements")
    assert r.status_code == 200, r.text
    owner_req_id = r.json()[0]["id"]
    print("Owner comms create OK")

    r = client.post(f"/api/owner-comms-requirements/{owner_req_id}/complete")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "complete"
    print("Owner comms complete OK")

    r = client.post("/api/discharge-readiness", json={"episode_id": episode_id, "blocker_summary": "Medication and owner update incomplete", "urgency": "amber", "owner_role": "clinician"})
    assert r.status_code == 200, r.text
    r = client.get("/api/discharge-readiness")
    assert r.status_code == 200, r.text
    discharge_rows = r.json()
    discharge_id = discharge_rows[0]["id"]
    assert discharge_rows[0]["readiness_state"] == "blocked"
    print("Discharge readiness create OK")

    r = client.get("/api/discharge-readiness")
    assert r.status_code == 200, r.text
    assert len(r.json()) > 0
    print("Discharge readiness list OK")

    r = client.post(f"/api/discharge-readiness/{discharge_id}/update", json={"clinician_signoff": True, "medication_ready": True, "owner_updated": True, "admin_ready": True, "results_reviewed": True, "care_instructions_ready": True})
    assert r.status_code == 200, r.text
    assert r.json()["readiness_state"] == "ready"
    print("Discharge readiness update OK")

    r = client.post("/api/pharmacy-requests", json={"episode_id": episode_id, "medication_name": "Methadone", "request_type": "dispense", "controlled_or_legal_status": "controlled", "authorised_supplier_required": True, "quantity": "1 vial", "urgency": "amber", "owner_role": "nurse", "compliance_note": "Controlled medicine process required"})
    assert r.status_code == 200, r.text
    r = client.get("/api/pharmacy-requests")
    assert r.status_code == 200, r.text
    pharmacy_id = r.json()[0]["id"]
    print("Pharmacy request create OK")

    r = client.get("/api/pharmacy-requests")
    assert r.status_code == 200, r.text
    assert len(r.json()) > 0
    print("Pharmacy request list OK")

    r = client.post(f"/api/pharmacy-requests/{pharmacy_id}/complete")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "complete"
    print("Pharmacy request complete OK")

    r = client.post("/api/stock-items", json={"name": "IV catheter 22G", "category": "clinical", "location": "main stock", "current_quantity": 0, "reorder_threshold": 5, "authorised_supplier": "NVS", "compliance_note": "Clinical consumable"})
    assert r.status_code == 200, r.text
    r = client.get("/api/stock-items")
    assert r.status_code == 200, r.text
    stock_item_id = r.json()[0]["id"]
    print("Stock item create OK")

    r = client.get("/api/stock-items")
    assert r.status_code == 200, r.text
    assert len(r.json()) > 0
    print("Stock item list OK")

    r = client.post("/api/stock-orders", json={"stock_item_id": stock_item_id, "episode_id": episode_id, "item_name": "IV catheter 22G", "reason": "Low stock will block procedure flow", "urgency": "amber", "supplier": "NVS"})
    assert r.status_code == 200, r.text
    r = client.get("/api/stock-orders")
    assert r.status_code == 200, r.text
    stock_order_id = r.json()[0]["id"]
    print("Stock order create OK")

    r = client.get("/api/stock-orders")
    assert r.status_code == 200, r.text
    assert len(r.json()) > 0
    print("Stock order list OK")

    r = client.post(f"/api/stock-orders/{stock_order_id}/complete")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "complete"
    print("Stock order complete OK")

    r = client.get("/api/domain-pressure")
    assert r.status_code == 200, r.text
    for key in ["discharge_blocked", "pharmacy_open", "stock_orders_open", "low_stock"]:
        assert key in r.json(), f"Domain pressure missing {key}"
    print("Domain pressure OK")

    r = client.post("/api/pulse-signals", json={"signal_type": "theatre_delay", "section_name": "Theatre", "severity": "medium", "detail": "Smoke test pulse signal", "episode_id": episode_id, "source": "Smoke Test"})
    assert r.status_code == 200, r.text
    print("Pulse signal create OK")

    r = client.get("/api/pulse")
    assert r.status_code == 200, r.text
    pulse = r.json()
    for key in ["case_pressure", "resource_pressure", "staff_pressure", "capacity_pressure", "execution_pressure", "ethics_pressure", "triage_pressure", "lucy_care_pressure", "owner_comms_pressure", "system_risk_level"]:
        assert key in pulse, f"Pulse missing key {key}"
    print("Lucy Pulse OK")

    r = client.post("/api/schedule/generate", json={"episode_ref": ep_ref, "procedure_type_id": 1, "room_name": "Theatre 1", "start_time": "2026-04-24T10:00:00+00:00", "actor_name": "Smoke Test"})
    assert r.status_code == 200, r.text
    print("Schedule generated")

    r = client.get("/api/schedule-blocks")
    assert r.status_code == 200, r.text
    blocks = r.json()
    assert len(blocks) >= 5
    block_id = blocks[0]["id"]
    print("Blocks OK")

    r = client.post(f"/api/schedule/block/{block_id}/shift", json={"minutes": 15, "actor_name": "Smoke Test"})
    assert r.status_code == 200, r.text
    print("Shift OK")

    r = client.get("/api/staff")
    assert r.status_code == 200, r.text
    staff = r.json()
    assert len(staff) > 0
    staff_id = staff[0]["id"]
    print("Staff OK")

    r = client.post("/api/staff/allocate", json={"schedule_block_id": block_id, "staff_member_id": staff_id, "actor_name": "Smoke Test"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] in {"allocated", "conflict"}
    print("Staff allocation endpoint OK")

    r = client.get("/api/staff-load")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
    print("Staff load OK")

    r = client.get("/api/conflicts")
    assert r.status_code == 200, r.text
    assert "conflicts" in r.json()
    print("Conflicts OK")

    r = client.post("/api/conflicts/to-work?conflict_type=smoke_test&severity=high&detail=Smoke%20test%20conflict")
    assert r.status_code == 200, r.text
    created = r.json()
    assert "work_item" in created and "conflict_action" in created
    action_id = created["conflict_action"]["id"]
    print("Conflict to work OK")

    r = client.get("/api/conflict-actions")
    assert r.status_code == 200, r.text
    assert len(r.json()) > 0
    print("Conflict actions list OK")

    r = client.post(f"/api/conflict-actions/{action_id}/resolve?note=Smoke%20resolved")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    print("Conflict resolve OK")

    r = client.get(f"/api/episode-command/{ep_ref}")
    assert r.status_code == 200, r.text
    command = r.json()
    assert "schedule_blocks" in command and "work_items" in command and "triage" in command and "ethics_flags" in command
    print("Episode command after domain actions OK")

print("\n--- ALL TESTS PASSED ---\n")
