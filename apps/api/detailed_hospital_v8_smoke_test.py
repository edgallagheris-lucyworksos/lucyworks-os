import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_detailed_v8_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "detailed-v8-smoke-secret-long-enough-for-testing",
    "AUTH_ISSUER": "lucyworks-detailed-v8-smoke",
    "AUTH_AUDIENCE": "lucyworks-detailed-v8-api",
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
    token = response.json().get("accessToken")
    assert token
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def post(client: TestClient, path: str, headers: dict[str, str], body: dict):
    response = client.post(path, headers=headers, json=body)
    assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"
    return response.json()


try:
    with TestClient(app) as client:
        ops = login(client, 1)
        clinician = login(client, 3)
        admin = login(client, 4)

        patient = client.put("/api/v8/patients/PAT-V8-001", headers=clinician, json={
            "display_name": "Anonymous Spaniel",
            "species": "Dog",
            "breed": "Cocker Spaniel",
            "sex": "female",
            "neuter_status": "neutered",
            "date_of_birth": "2020-05-01",
            "microchip_number": "985000000000001",
            "alerts": [{"type": "handling", "message": "Noise sensitive"}],
            "reason": "Synthetic patient record",
        })
        assert patient.status_code == 200, patient.text

        owner = client.put("/api/v8/owners/OWN-V8-001", headers=admin, json={
            "display_name": "Anonymous Owner",
            "email": "owner@example.invalid",
            "phone": "00000000000",
            "address": {"postcode": "BS0 0AA"},
            "communication_preferences": {"primary": "phone"},
            "identity_verified": True,
            "reason": "Synthetic verified owner",
        })
        assert owner.status_code == 200, owner.text
        linked = post(client, "/api/v8/patients/PAT-V8-001/owners", admin, {
            "owner_ref": "OWN-V8-001", "relationship": "registered_owner",
            "decision_authority": True, "financial_responsibility": True,
            "reason": "Synthetic ownership evidence",
        })
        assert linked["created"] is True

        with Session(engine) as session:
            session.add(CanonicalEpisodeState(
                episode_ref="EP-V8-001", patient_ref="PAT-V8-001", patient_name="Anonymous Spaniel",
                premises_ref="bvs-bristol", phase="consultation", status="active",
                owner_role="clinician", current_area_ref="consult-1",
            ))
            session.commit()

        weight = post(client, "/api/v8/patients/PAT-V8-001/weights", clinician, {
            "episode_ref": "EP-V8-001", "weight_kg": 20.0, "body_condition_score": "5/9",
            "reason": "Admission weight",
        })
        assert weight["weight"]["weight_kg"] == 20.0

        allergy = post(client, "/api/v8/patients/PAT-V8-001/allergies", clinician, {
            "substance_ref": "med-penicillin", "substance_name": "Penicillin",
            "reaction": "Facial swelling", "severity": "red", "confirmed": True,
            "reason": "Confirmed referring-vet history",
        })
        assert allergy["allergy"]["severity"] == "red"

        medicine = client.put("/api/v8/formulary/medicines/med-penicillin", headers=ops, json={
            "generic_name": "Penicillin", "brand_names": [], "high_risk": False,
            "routes": ["IV"], "status": "approved", "reason": "Synthetic formulary approval",
        })
        assert medicine.status_code == 200, medicine.text
        rule = client.put("/api/v8/formulary/dose-rules/rule-penicillin-dog", headers=ops, json={
            "medicine_ref": "med-penicillin", "species": "Dog", "indication": "infection", "route": "IV",
            "minimum_mg_per_kg": 10, "maximum_mg_per_kg": 20,
            "maximum_single_dose_mg": 500, "minimum_interval_hours": 8,
            "source_reference": "SYNTHETIC-LOCAL-RULE", "status": "approved",
            "reason": "Synthetic dose rule",
        })
        assert rule.status_code == 200, rule.text
        blocked = post(client, "/api/v8/episodes/EP-V8-001/medication-safety-check", clinician, {
            "patient_ref": "PAT-V8-001", "medicine_ref": "med-penicillin", "indication": "infection",
            "route": "IV", "dose_mg": 300, "interval_hours": 8,
            "reason": "Pre-prescription safety check",
        })
        assert blocked["review"]["blocks_order"] is True
        assert any(item["code"] == "allergy_match" for item in blocked["review"]["warnings"])

        client.put("/api/v8/formulary/medicines/med-safe", headers=ops, json={
            "generic_name": "Synthetic Safe Drug", "brand_names": [], "high_risk": True,
            "routes": ["IV"], "status": "approved", "reason": "Synthetic formulary approval",
        })
        client.put("/api/v8/formulary/dose-rules/rule-safe-dog", headers=ops, json={
            "medicine_ref": "med-safe", "species": "Dog", "indication": "analgesia", "route": "IV",
            "minimum_mg_per_kg": 1, "maximum_mg_per_kg": 2,
            "maximum_single_dose_mg": 50, "minimum_interval_hours": 6,
            "source_reference": "SYNTHETIC-SAFE-RULE", "status": "approved",
            "reason": "Synthetic safe dose rule",
        })
        safe = post(client, "/api/v8/episodes/EP-V8-001/medication-safety-check", clinician, {
            "patient_ref": "PAT-V8-001", "medicine_ref": "med-safe", "indication": "analgesia",
            "route": "IV", "dose_mg": 30, "interval_hours": 8,
            "reason": "Safe medication review",
        })
        assert safe["review"]["blocks_order"] is False
        assert safe["review"]["outcome"] == "passed"

        encounter = post(client, "/api/v8/episodes/EP-V8-001/encounters", clinician, {
            "patient_ref": "PAT-V8-001", "encounter_type": "specialist_consultation",
            "service_ref": "neurology", "location_ref": "consult-1",
            "presenting_complaint": "Progressive paresis", "history": "Three-day history",
            "examination": {"mentation": "bright", "gait": "ambulatory paraparesis"},
            "assessment": "Suspected thoracolumbar disc disease", "plan": "MRI and surgery if indicated",
            "reason": "Specialist consultation",
        })
        note = post(client, "/api/v8/episodes/EP-V8-001/notes", clinician, {
            "patient_ref": "PAT-V8-001", "encounter_ref": encounter["encounter"]["encounter_ref"],
            "note_type": "consultation", "title": "Neurology consultation",
            "body": "Findings and options discussed with owner.", "reason": "Signed consultation record",
        })
        assert note["note"]["status"] == "signed"
        post(client, "/api/v8/patients/PAT-V8-001/problems", clinician, {
            "episode_ref": "EP-V8-001", "title": "Thoracolumbar myelopathy",
            "description": "Acute progressive neurological dysfunction", "reason": "Problem list update",
        })

        chart = post(client, "/api/v8/episodes/EP-V8-001/anaesthesia/charts", clinician, {
            "patient_ref": "PAT-V8-001", "asa_status": "ASA II",
            "pre_anaesthetic_assessment": {"fasted": True, "airway": "normal"},
            "machine_check": {"machine": True, "patient_identity": True, "consent": True, "airway": True},
            "airway_plan": "Cuffed endotracheal tube", "analgesia_plan": "Multimodal",
            "ventilation_plan": "Volume controlled if required", "reason": "Anaesthesia plan",
        })["chart"]
        obs = post(client, f"/api/v8/anaesthesia/charts/{chart['chart_ref']}/observations", clinician, {
            "heart_rate": 80, "mean_bp": 45, "spo2": 92, "etco2": 44, "temperature_c": 36.5,
            "reason": "Five-minute anaesthesia observation",
        })
        assert obs["observation"]["concern_level"] == "red"
        assert obs["alertReasons"]

        no_witness = client.post(f"/api/v8/anaesthesia/charts/{chart['chart_ref']}/drug-events", headers=clinician, json={
            "medicine_ref": "med-safe", "medicine_name": "Synthetic Safe Drug", "dose": "30 mg",
            "route": "IV", "event_type": "induction", "reason": "Synthetic drug administration",
        })
        assert no_witness.status_code == 409, no_witness.text
        drug = post(client, f"/api/v8/anaesthesia/charts/{chart['chart_ref']}/drug-events", clinician, {
            "medicine_ref": "med-safe", "medicine_name": "Synthetic Safe Drug", "dose": "30 mg",
            "route": "IV", "event_type": "induction", "witness_subject": "local-user:1",
            "reason": "Witnessed high-risk administration",
        })
        assert drug["drugEvent"]["witness_subject"] == "local-user:1"

        fluid_plan = post(client, "/api/v8/episodes/EP-V8-001/fluid-plans", clinician, {
            "patient_ref": "PAT-V8-001", "fluid_type": "Balanced crystalloid", "route": "IV",
            "rate_ml_per_hour": 60, "target_total_ml": 600, "indication": "Peri-operative support",
            "reason": "Fluid prescription",
        })["plan"]
        balance1 = post(client, "/api/v8/episodes/EP-V8-001/fluid-balance", clinician, {
            "patient_ref": "PAT-V8-001", "plan_ref": fluid_plan["plan_ref"], "entry_type": "input",
            "volume_ml": 120, "route_or_source": "IV crystalloid", "reason": "Two-hour input",
        })
        balance2 = post(client, "/api/v8/episodes/EP-V8-001/fluid-balance", clinician, {
            "patient_ref": "PAT-V8-001", "plan_ref": fluid_plan["plan_ref"], "entry_type": "output",
            "volume_ml": 40, "route_or_source": "urine", "reason": "Urine output",
        })
        assert balance2["balance"]["netMl"] == 80

        care = post(client, "/api/v8/episodes/EP-V8-001/care-plans", clinician, {
            "patient_ref": "PAT-V8-001", "area_ref": "icu", "acuity": "high",
            "goals": [{"goal": "Maintain perfusion"}], "interventions": [{"task": "hourly observations"}],
            "observation_schedule": {"intervalMinutes": 60}, "nutrition_plan": {"status": "NPO"},
            "mobility_plan": {"support": "sling"}, "reason": "ICU care plan",
        })["carePlan"]
        red_entry = post(client, f"/api/v8/care-plans/{care['care_plan_ref']}/entries", clinician, {
            "entry_type": "neurological_observation", "values": {"painScore": 9},
            "concern_level": "red", "note": "Acute deterioration", "reason": "Escalation observation",
        })
        assert red_entry["entry"]["concern_level"] == "red"

        procedure = post(client, "/api/v8/episodes/EP-V8-001/procedures", clinician, {
            "patient_ref": "PAT-V8-001", "procedure_name": "Hemilaminectomy",
            "assistants": [{"subject": "local-user:1", "role": "assistant"}],
            "preoperative_diagnosis": "T12-13 disc extrusion", "postoperative_diagnosis": "T12-13 disc extrusion",
            "findings": "Extruded disc material", "technique": "Left T12-13 hemilaminectomy",
            "complications": [], "specimens": [], "status": "completed", "reason": "Operative record",
        })["procedure"]
        invalid_implant = client.post(f"/api/v8/procedures/{procedure['procedure_ref']}/implants", headers=clinician, json={
            "patient_ref": "PAT-V8-001", "product_name": "Synthetic implant", "reason": "Traceability test",
        })
        assert invalid_implant.status_code == 409
        implant = post(client, f"/api/v8/procedures/{procedure['procedure_ref']}/implants", clinician, {
            "patient_ref": "PAT-V8-001", "product_name": "Synthetic implant", "manufacturer": "Synthetic Medical",
            "catalogue_number": "CAT-001", "lot_number": "LOT-2026-001", "expiry_date": "2029-01-01",
            "reason": "Implant traceability record",
        })
        assert implant["implant"]["lot_number"] == "LOT-2026-001"

        unauthorised_estimate = client.post("/api/v8/episodes/EP-V8-001/estimates", headers=ops, json={
            "patient_ref": "PAT-V8-001", "status": "issued", "lines": [{
                "category": "procedure", "description": "Surgery", "quantity": 1,
                "lower_unit_pence": 300000, "upper_unit_pence": 450000,
            }], "reason": "Estimate without owner authority",
        })
        assert unauthorised_estimate.status_code == 409
        estimate = post(client, "/api/v8/episodes/EP-V8-001/estimates", ops, {
            "patient_ref": "PAT-V8-001", "status": "issued", "authorised_limit_pence": 500000,
            "owner_authorisation_ref": linked["link"]["evidence_event_ref"],
            "lines": [
                {"category": "imaging", "description": "MRI", "quantity": 1, "lower_unit_pence": 180000, "upper_unit_pence": 220000},
                {"category": "procedure", "description": "Surgery", "quantity": 1, "lower_unit_pence": 300000, "upper_unit_pence": 450000},
            ], "reason": "Owner-authorised estimate",
        })
        assert estimate["estimate"]["lower_total_pence"] == 480000
        assert estimate["estimate"]["upper_total_pence"] == 670000

        insurance = post(client, "/api/v8/episodes/EP-V8-001/insurance", ops, {
            "patient_ref": "PAT-V8-001", "owner_ref": "OWN-V8-001", "insurer_name": "Synthetic Insurance",
            "policy_number_masked": "****1234", "cover_limit_pence": 600000, "excess_pence": 10000,
            "preauthorised_pence": 500000, "direct_claim_requested": True, "status": "preauthorised",
            "reason": "Insurance preauthorisation recorded",
        })
        assert insurance["insurance"]["shortfall_pence"] == 170000
        transaction = post(client, "/api/v8/episodes/EP-V8-001/transactions", ops, {
            "patient_ref": "PAT-V8-001", "owner_ref": "OWN-V8-001", "transaction_type": "payment",
            "amount_pence": 10000, "payment_method": "card", "external_reference": "PAY-SYNTH-001",
            "reason": "Deposit payment",
        })
        assert transaction["transaction"]["amount_pence"] == 10000

        communication = post(client, "/api/v8/episodes/EP-V8-001/communications", clinician, {
            "patient_ref": "PAT-V8-001", "owner_ref": "OWN-V8-001", "audience": "owner", "channel": "phone",
            "direction": "outbound", "subject": "Post-operative update",
            "summary": "Procedure completed and recovery discussed.", "outcome": "Owner informed",
            "consent_or_authorisation": {"estimateLimitConfirmedPence": 500000},
            "reason": "Owner update",
        })
        assert communication["communication"]["audience"] == "owner"

        document = post(client, "/api/v8/episodes/EP-V8-001/documents/generate", clinician, {
            "patient_ref": "PAT-V8-001", "document_type": "referring_vet_report",
            "title": "Neurology referral report", "additional_text": "Continue restricted exercise.",
            "reason": "Generate referring-vet report",
        })
        assert "Anonymous Spaniel" in document["document"]["content"]
        assert "Hemilaminectomy" in document["document"]["content"]

        record = client.get("/api/v8/episodes/EP-V8-001/record", headers=clinician)
        assert record.status_code == 200, record.text
        data = record.json()
        assert data["patient"]["patient_ref"] == "PAT-V8-001"
        assert len(data["encounters"]) == 1
        assert len(data["anaesthesiaCharts"]) == 1
        assert data["fluidBalance"]["netMl"] == 80
        assert len(data["procedures"]) == 1
        assert len(data["estimates"]) == 1
        assert len(data["communications"]) == 1
        assert len(data["documents"]) == 1

        dashboard = client.get("/api/v8/dashboard", headers=ops)
        assert dashboard.status_code == 200, dashboard.text
        summary = dashboard.json()["summary"]
        assert summary["activePatients"] == 1
        assert summary["redAllergies"] == 1
        assert summary["blockedMedicationReviews"] == 1
        assert summary["redAnaesthesiaObservations"] == 1
        assert summary["redInpatientEntries"] == 1

        print("\n--- DETAILED HOSPITAL RECORD V8 END-TO-END TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
