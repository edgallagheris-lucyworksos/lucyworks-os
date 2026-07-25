import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_detailed_completion_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "detailed-completion-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-detailed-completion",
    "AUTH_AUDIENCE": "lucyworks-detailed-completion-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from app.database import engine
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    token = response.json()["accessToken"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


try:
    with TestClient(app) as client:
        ops = login(client, 1)
        clinician = login(client, 3)
        now = datetime.now(timezone.utc)

        with Session(engine) as session:
            session.add(CanonicalEpisodeState(
                episode_ref="EP-COMPLETE-001", patient_ref="PAT-COMPLETE-001",
                patient_name="Anonymous Dog", premises_ref="bvs-bristol",
                phase="procedure", status="active", owner_role="clinician",
                current_area_ref="theatre-1",
            ))
            session.commit()

        patient = client.put("/api/v8/patients/PAT-COMPLETE-001", headers=clinician, json={
            "display_name": "Anonymous Dog", "species": "Dog", "breed": "Crossbreed",
            "alerts": [], "reason": "Synthetic completion patient",
        })
        assert patient.status_code == 200, patient.text
        weight = client.post("/api/v8/patients/PAT-COMPLETE-001/weights", headers=clinician, json={
            "episode_ref": "EP-COMPLETE-001", "weight_kg": 10, "reason": "Current weight",
        })
        assert weight.status_code == 200, weight.text

        medicine_a = client.put("/api/v8/formulary/medicines/med-a", headers=ops, json={
            "generic_name": "Medicine A", "routes": ["IV"], "status": "approved",
            "reason": "Synthetic formulary medicine A",
        })
        assert medicine_a.status_code == 200, medicine_a.text
        rule_a = client.put("/api/v8/formulary/dose-rules/rule-a", headers=ops, json={
            "medicine_ref": "med-a", "species": "Dog", "indication": "analgesia", "route": "IV",
            "minimum_mg_per_kg": 0.1, "maximum_mg_per_kg": 0.3,
            "maximum_single_dose_mg": 5, "minimum_interval_hours": 4,
            "source_reference": "SYNTHETIC-A", "status": "approved", "reason": "Synthetic rule A",
        })
        assert rule_a.status_code == 200, rule_a.text
        review_a = client.post("/api/v8/episodes/EP-COMPLETE-001/medication-safety-check", headers=clinician, json={
            "patient_ref": "PAT-COMPLETE-001", "medicine_ref": "med-a", "indication": "analgesia",
            "route": "IV", "dose_mg": 2, "interval_hours": 4, "reason": "Review medicine A",
        })
        assert review_a.status_code == 200, review_a.text
        review_a_row = review_a.json()["review"]
        order_a = client.post("/api/v8/episodes/EP-COMPLETE-001/medication-orders", headers=clinician, json={
            "patient_ref": "PAT-COMPLETE-001", "safety_review_ref": review_a_row["review_ref"],
            "frequency": "every 4 hours", "starts_at": now.isoformat(),
            "scheduled_times": [now.isoformat(), (now + timedelta(hours=4)).isoformat()],
            "reason": "Prescribe after completed safety review",
        })
        assert order_a.status_code == 200, order_a.text
        assert order_a.json()["created"] is True
        assert len(order_a.json()["administrations"]) == 2
        duplicate_a = client.post("/api/v8/episodes/EP-COMPLETE-001/medication-orders", headers=clinician, json={
            "patient_ref": "PAT-COMPLETE-001", "safety_review_ref": review_a_row["review_ref"],
            "frequency": "every 4 hours", "starts_at": now.isoformat(),
            "scheduled_times": [now.isoformat()], "reason": "Idempotent retry",
        })
        assert duplicate_a.status_code == 200, duplicate_a.text
        assert duplicate_a.json()["created"] is False

        medicine_b = client.put("/api/v8/formulary/medicines/med-b", headers=ops, json={
            "generic_name": "Medicine B", "routes": ["IV"], "status": "approved",
            "interactions": [{"medicineRef": "med-a", "severity": "red", "message": "Medicine A and B must not be combined"}],
            "reason": "Synthetic interacting medicine",
        })
        assert medicine_b.status_code == 200, medicine_b.text
        rule_b = client.put("/api/v8/formulary/dose-rules/rule-b", headers=ops, json={
            "medicine_ref": "med-b", "species": "Dog", "indication": "sedation", "route": "IV",
            "minimum_mg_per_kg": 0.1, "maximum_mg_per_kg": 0.3,
            "maximum_single_dose_mg": 5, "minimum_interval_hours": 4,
            "source_reference": "SYNTHETIC-B", "status": "approved", "reason": "Synthetic rule B",
        })
        assert rule_b.status_code == 200, rule_b.text
        review_b = client.post("/api/v8/episodes/EP-COMPLETE-001/medication-safety-check", headers=clinician, json={
            "patient_ref": "PAT-COMPLETE-001", "medicine_ref": "med-b", "indication": "sedation",
            "route": "IV", "dose_mg": 2, "interval_hours": 4, "reason": "Review medicine B",
        })
        assert review_b.status_code == 200, review_b.text
        blocked_interaction = client.post("/api/v8/episodes/EP-COMPLETE-001/medication-orders", headers=clinician, json={
            "patient_ref": "PAT-COMPLETE-001", "safety_review_ref": review_b.json()["review"]["review_ref"],
            "frequency": "once", "starts_at": now.isoformat(), "reason": "Attempt interacting prescription",
        })
        assert blocked_interaction.status_code == 409, blocked_interaction.text
        assert blocked_interaction.json()["detail"]["warnings"][0]["code"] == "active_medication_interaction"

        old_order = client.post("/api/clinical-execution/medication-orders", headers=clinician, json={})
        assert old_order.status_code == 410, old_order.text

        chart_response = client.post("/api/v8/episodes/EP-COMPLETE-001/anaesthesia/charts", headers=clinician, json={
            "patient_ref": "PAT-COMPLETE-001", "asa_status": "ASA II",
            "pre_anaesthetic_assessment": {"fasted": True},
            "machine_check": {"machine": True, "patient_identity": True, "consent": True, "airway": True},
            "airway_plan": "Cuffed tube", "analgesia_plan": "Multimodal", "ventilation_plan": "IPPV if required",
            "reason": "Create complete anaesthesia plan",
        })
        assert chart_response.status_code == 200, chart_response.text
        chart = chart_response.json()["chart"]
        induced = client.patch(f"/api/v8/anaesthesia/charts/{chart['chart_ref']}/transition", headers=clinician, json={
            "expected_version": chart["version"], "status": "induced", "reason": "All induction gates complete",
        })
        assert induced.status_code == 200, induced.text
        induced_chart = induced.json()["chart"]
        stale = client.patch(f"/api/v8/anaesthesia/charts/{chart['chart_ref']}/transition", headers=clinician, json={
            "expected_version": chart["version"], "status": "recovery", "reason": "Stale transition",
        })
        assert stale.status_code == 409, stale.text
        recovery = client.patch(f"/api/v8/anaesthesia/charts/{chart['chart_ref']}/transition", headers=clinician, json={
            "expected_version": induced_chart["version"], "status": "recovery", "reason": "Extubated into recovery",
        })
        assert recovery.status_code == 200, recovery.text
        recovery_chart = recovery.json()["chart"]
        missing_score = client.patch(f"/api/v8/anaesthesia/charts/{chart['chart_ref']}/transition", headers=clinician, json={
            "expected_version": recovery_chart["version"], "status": "completed", "reason": "Attempt without score",
        })
        assert missing_score.status_code == 409, missing_score.text
        completed = client.patch(f"/api/v8/anaesthesia/charts/{chart['chart_ref']}/transition", headers=clinician, json={
            "expected_version": recovery_chart["version"], "status": "completed", "recovery_score": "Ready for ward transfer",
            "reason": "Recovery criteria met",
        })
        assert completed.status_code == 200, completed.text
        assert completed.json()["chart"]["status"] == "completed"

        encounter = client.post("/api/v8/episodes/EP-COMPLETE-001/encounters", headers=clinician, json={
            "patient_ref": "PAT-COMPLETE-001", "encounter_type": "procedure_review",
            "presenting_complaint": "Post-operative review", "assessment": "Stable",
            "plan": "Discharge when criteria met", "reason": "Clinical summary source",
        })
        assert encounter.status_code == 200, encounter.text
        generated = client.post("/api/v8/episodes/EP-COMPLETE-001/documents/generate", headers=clinician, json={
            "patient_ref": "PAT-COMPLETE-001", "document_type": "discharge_summary",
            "title": "Discharge summary", "additional_text": "Review with primary vet.",
            "reason": "Generate discharge document",
        })
        assert generated.status_code == 200, generated.text
        document = generated.json()["document"]
        premature_send = client.post(f"/api/v8/documents/{document['document_ref']}/send", headers=clinician, json={
            "expected_version": document["version"], "audience": "owner", "channel": "email",
            "recipient_ref": "owner@example.invalid", "reason": "Attempt before approval",
        })
        assert premature_send.status_code == 409, premature_send.text
        approved = client.patch(f"/api/v8/documents/{document['document_ref']}/approve", headers=clinician, json={
            "expected_version": document["version"], "reason": "Clinical content reviewed",
        })
        assert approved.status_code == 200, approved.text
        approved_document = approved.json()["document"]
        sent = client.post(f"/api/v8/documents/{document['document_ref']}/send", headers=clinician, json={
            "expected_version": approved_document["version"], "audience": "owner", "channel": "email",
            "recipient_ref": "owner@example.invalid", "reason": "Send approved discharge summary",
        })
        assert sent.status_code == 200, sent.text
        assert sent.json()["document"]["status"] == "sent"
        assert sent.json()["communication"]["attachments"][0]["documentRef"] == document["document_ref"]

        print("\n--- DETAILED HOSPITAL COMPLETION GATES PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
