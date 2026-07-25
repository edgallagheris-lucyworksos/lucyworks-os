import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_clinical_execution_{os.getpid()}.db"
if TEST_DB.exists(): TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}", "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local", "AUTH_ENFORCEMENT": "required", "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_JWT_SECRET": "clinical-execution-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-clinical-smoke", "AUTH_AUDIENCE": "lucyworks-clinical-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from app.database import engine
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


try:
    with TestClient(app) as client:
        ops = login(client, 1)
        nurse = login(client, 2)
        clinician = login(client, 3)
        now = datetime.now(timezone.utc)
        with Session(engine) as session:
            session.add(CanonicalEpisodeState(episode_ref="EP-CLIN-001", patient_ref="PAT-CLIN-001", patient_name="Anonymous Cat", premises_ref="bvs-bristol", phase="procedure", status="active", owner_role="clinician", current_area_ref="theatre-1"))
            session.add(OperationalBlock(block_ref="BLOCK-CLIN-001", premises_ref="bvs-bristol", operational_date=date.today(), episode_ref="EP-CLIN-001", patient_ref="PAT-CLIN-001", patient_name="Anonymous Cat", procedure_name="Synthetic procedure", area_ref="theatre-1", area_name="Theatre 1", starts_at=now, ends_at=now + timedelta(hours=1), status="planned"))
            session.commit()

        denied = client.post("/api/clinical-execution/medication-orders", headers=nurse, json={
            "episode_ref": "EP-CLIN-001", "medication_ref": "med-a", "medication_name": "Medication A", "dose": "1 mg", "route": "IV", "frequency": "once", "indication": "test", "starts_at": now.isoformat()
        })
        assert denied.status_code == 403, denied.text

        order = client.post("/api/clinical-execution/medication-orders", headers=clinician, json={
            "episode_ref": "EP-CLIN-001", "medication_ref": "med-a", "medication_name": "Medication A",
            "dose": "1 mg", "route": "IV", "frequency": "once", "indication": "synthetic analgesia",
            "starts_at": now.isoformat(), "scheduled_times": [now.isoformat()], "high_risk": True,
        })
        assert order.status_code == 200, order.text
        administration = order.json()["administrations"][0]

        no_witness = client.patch(f"/api/clinical-execution/administrations/{administration['administrationRef']}", headers=nurse, json={"expected_version": 1, "status": "administered", "dose_given": "1 mg", "reason": "test"})
        assert no_witness.status_code == 409, no_witness.text
        given = client.patch(f"/api/clinical-execution/administrations/{administration['administrationRef']}", headers=nurse, json={
            "expected_version": 1, "status": "administered", "dose_given": "1 mg", "route_used": "IV", "witness_subject": "local-user:3", "reason": "identity, medicine and dose checked"
        })
        assert given.status_code == 200, given.text

        retired_anaesthesia = client.post("/api/clinical-execution/anaesthesia", headers=clinician, json={
            "episode_ref": "EP-CLIN-001", "responsible_clinician_subject": "spoof", "responsible_clinician_name": "Spoof", "checklist": {}
        })
        assert retired_anaesthesia.status_code == 410, retired_anaesthesia.text
        anaesthesia = client.post("/api/clinical-execution/governed/anaesthesia", headers=clinician, json={
            "episode_ref": "EP-CLIN-001", "block_ref": "BLOCK-CLIN-001", "asa_status": "II",
            "airway_plan": "intubation", "analgesia_plan": "multimodal", "checklist": {}, "reason": "synthetic plan"
        })
        assert anaesthesia.status_code == 200, anaesthesia.text
        record = anaesthesia.json()["record"]
        assert record["responsibleClinicianName"] == "Cal Clinician"
        assert record["responsibleClinicianSubject"] == "local-user:3"
        blocked_induction = client.patch(f"/api/clinical-execution/anaesthesia/{record['recordRef']}", headers=clinician, json={"expected_version": record["version"], "status": "induced", "checklist": {}, "reason": "attempt"})
        assert blocked_induction.status_code == 409, blocked_induction.text
        induced = client.patch(f"/api/clinical-execution/anaesthesia/{record['recordRef']}", headers=clinician, json={
            "expected_version": record["version"], "status": "induced", "checklist": {"identity_checked": True, "consent_checked": True, "equipment_checked": True, "airway_plan_confirmed": True}, "reason": "checklist completed"
        })
        assert induced.status_code == 200, induced.text

        observation = client.post("/api/clinical-execution/observations", headers=nurse, json={
            "episode_ref": "EP-CLIN-001", "area_ref": "recovery", "observation_type": "recovery_observation", "values": {"temperature": 39.8, "heart_rate": 180}, "concern_level": "red", "reason": "deterioration identified"
        })
        assert observation.status_code == 200, observation.text
        governed_view = client.get("/api/clinical-execution/governed/dashboard?episode_ref=EP-CLIN-001", headers=clinician)
        assert governed_view.status_code == 200, governed_view.text
        observation_row = governed_view.json()["observations"][0]
        escalation = client.patch(f"/api/clinical-execution/governed/observations/{observation_row['observationRef']}/escalation", headers=clinician, json={
            "expected_version": observation_row["version"], "status": "escalated", "note": "senior clinician review required", "escalated_to_role": "senior_clinician"
        })
        assert escalation.status_code == 200, escalation.text
        escalated = escalation.json()["observation"]
        resolved = client.patch(f"/api/clinical-execution/governed/observations/{observation_row['observationRef']}/escalation", headers=clinician, json={
            "expected_version": escalated["version"], "status": "resolved", "note": "patient assessed and plan updated"
        })
        assert resolved.status_code == 200, resolved.text

        task = client.post("/api/clinical-execution/treatment-tasks", headers=clinician, json={
            "episode_ref": "EP-CLIN-001", "task_type": "monitoring", "title": "Repeat observations", "instructions": "Repeat full set", "due_at": (now + timedelta(minutes=15)).isoformat(), "assigned_role": "nurse", "priority": "red"
        })
        assert task.status_code == 200, task.text
        task_row = task.json()["task"]
        complete = client.patch(f"/api/clinical-execution/treatment-tasks/{task_row['taskRef']}/complete", headers=nurse, json={"expected_version": task_row["version"], "reason": "repeat observations completed"})
        assert complete.status_code == 200, complete.text

        no_cd_witness = client.post("/api/clinical-execution/controlled-drugs", headers=nurse, json={
            "medication_ref": "controlled-a", "movement_type": "received", "quantity": 10, "unit": "ml", "expected_previous_balance": 0, "reason": "stock receipt"
        })
        assert no_cd_witness.status_code == 409, no_cd_witness.text
        cd = client.post("/api/clinical-execution/controlled-drugs", headers=nurse, json={
            "medication_ref": "controlled-a", "movement_type": "received", "quantity": 10, "unit": "ml", "expected_previous_balance": 0, "reason": "stock receipt", "witness_subject": "local-user:3"
        })
        assert cd.status_code == 200, cd.text
        discrepancy = client.post("/api/clinical-execution/controlled-drugs", headers=nurse, json={
            "medication_ref": "controlled-a", "movement_type": "issued", "quantity": 1, "unit": "ml", "expected_previous_balance": 8, "reason": "synthetic discrepancy", "witness_subject": "local-user:3"
        })
        assert discrepancy.status_code == 200, discrepancy.text
        controlled_view = client.get("/api/clinical-execution/governed/dashboard", headers=ops).json()["controlledDrugEntries"]
        discrepancy_row = next(row for row in controlled_view if row["discrepancy"])
        resolved_discrepancy = client.patch(f"/api/clinical-execution/governed/controlled-drugs/{discrepancy_row['entryRef']}/discrepancy", headers=ops, json={
            "expected_version": discrepancy_row["version"], "resolution": "Count repeated and transaction corrected in source register", "witness_subject": "local-user:3"
        })
        assert resolved_discrepancy.status_code == 200, resolved_discrepancy.text

        stock = client.post("/api/clinical-execution/inventory", headers=nurse, json={
            "item_ref": "item-a", "name": "Medication A", "item_type": "medication", "quantity_on_hand": 5, "unit": "vials", "reorder_level": 3, "reason": "opening count"
        })
        assert stock.status_code == 200, stock.text
        stock_row = stock.json()["item"]
        movement = client.post("/api/clinical-execution/governed/inventory-movements", headers=nurse, json={
            "item_ref": "item-a", "movement_type": "issued", "quantity_change": -3, "expected_item_version": stock_row["version"], "reason": "issued to synthetic case", "episode_ref": "EP-CLIN-001"
        })
        assert movement.status_code == 200, movement.text
        assert movement.json()["movement"]["newQuantity"] == 2
        assert movement.json()["movement"]["lowStock"] is True

        diagnostic = client.post("/api/clinical-execution/diagnostics", headers=clinician, json={
            "episode_ref": "EP-CLIN-001", "modality": "laboratory", "requested_test": "Synthetic panel", "urgency": "urgent", "specimen_ref": "SPEC-1"
        })
        assert diagnostic.status_code == 200, diagnostic.text
        work = diagnostic.json()["workItem"]
        report = client.patch(f"/api/clinical-execution/diagnostics/{work['workRef']}", headers=clinician, json={
            "expected_version": work["version"], "status": "reported", "report_summary": "Critical synthetic result", "critical_result": True, "reason": "laboratory report received"
        })
        assert report.status_code == 200, report.text
        chain = client.post("/api/clinical-execution/sample-chain", headers=nurse, json={
            "specimen_ref": "SPEC-1", "episode_ref": "EP-CLIN-001", "event_type": "received_in_lab", "location_ref": "lab", "detail": {"sealIntact": True}
        })
        assert chain.status_code == 200, chain.text

        discharge = client.post("/api/clinical-execution/discharge-plans", headers=clinician, json={
            "episode_ref": "EP-CLIN-001", "care_instructions": "Rest and monitor", "follow_up": "Primary vet in 48 hours", "warning_signs": "Collapse or breathing difficulty"
        })
        assert discharge.status_code == 200, discharge.text
        plan = discharge.json()["plan"]
        retired_discharge = client.patch(f"/api/clinical-execution/discharge-plans/{plan['planRef']}", headers=clinician, json={"expected_version": plan["version"], "status": "approved", "reason": "unsafe path"})
        assert retired_discharge.status_code == 410, retired_discharge.text
        blocked_discharge = client.patch(f"/api/clinical-execution/governed/discharge-plans/{plan['planRef']}", headers=clinician, json={
            "expected_version": plan["version"], "status": "approved", "owner_communication_status": "completed", "referring_vet_report_status": "sent", "reason": "evidence omitted"
        })
        assert blocked_discharge.status_code == 409, blocked_discharge.text
        approved = client.patch(f"/api/clinical-execution/governed/discharge-plans/{plan['planRef']}", headers=clinician, json={
            "expected_version": plan["version"], "status": "approved", "owner_communication_status": "completed", "owner_communication_evidence_ref": "owner-call-log-001", "referring_vet_report_status": "sent", "referring_vet_report_evidence_ref": "ref-vet-report-001", "reason": "all discharge gates and evidence confirmed"
        })
        assert approved.status_code == 200, approved.text

        dashboard = client.get("/api/clinical-execution/governed/dashboard?episode_ref=EP-CLIN-001", headers=clinician)
        assert dashboard.status_code == 200, dashboard.text
        summary = dashboard.json()["summary"]
        assert summary["activeMedicationOrders"] == 1
        assert summary["redObservations"] == 0
        assert summary["criticalDiagnostics"] == 1
        assert summary["lowStockItems"] == 1
        assert summary["openControlledDrugDiscrepancies"] == 0
        assert summary["unapprovedDischarges"] == 0
        assert dashboard.json()["inventoryMovements"]
        print("Governed medication, anaesthesia, escalation, controlled-drug, inventory, diagnostics and discharge evidence gates OK")
finally:
    if TEST_DB.exists(): TEST_DB.unlink()
