import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_regulated_v32_ext_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "regulated-v32-extension-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-regulated-v32-extension-smoke",
    "AUTH_AUDIENCE": "lucyworks-regulated-v32-extension-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from app.database import engine
from app.detailed_hospital_models import PatientClinicalRecordV8
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app
from app.models import User

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    token = response.json().get("accessToken")
    assert token
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


try:
    with Session(engine) as session:
        session.add_all([
            User(id=1, name="Olivia Ops", role="ops_manager", email="ops@example.test"),
            User(id=3, name="Cal Clinician", role="clinician", email="clinician@example.test"),
            PatientClinicalRecordV8(patient_ref="PAT-V32-EXT-001", display_name="Bramble", species="dog", breed="Labrador"),
            CanonicalEpisodeState(
                episode_ref="EP-V32-EXT-001", patient_ref="PAT-V32-EXT-001", patient_name="Bramble",
                premises_ref="reference-site", service_line="neurology", urgency="urgent", phase="consult",
                status="active", owner_role="clinician", owner_subject="local-user:3",
            ),
        ])
        session.commit()

    with TestClient(app) as client:
        ops = login(client, 1)
        clinician = login(client, 3)

        bad_third_party = client.post("/api/v32/episodes/EP-V32-EXT-001/charges", headers=ops, json={
            "patientRef": "PAT-V32-EXT-001", "category": "external_lab", "description": "External histopathology",
            "quantity": 1, "unitPence": 15000, "thirdPartyCostPence": 10000, "markupPence": 4000,
            "externalSupplier": "Reference Lab", "reason": "Reconciliation must fail",
        })
        assert bad_third_party.status_code == 409, bad_third_party.text

        charge = client.post("/api/v32/episodes/EP-V32-EXT-001/charges", headers=ops, json={
            "patientRef": "PAT-V32-EXT-001", "category": "external_lab", "description": "External histopathology",
            "quantity": 1, "unitPence": 15000, "thirdPartyCostPence": 10000, "markupPence": 5000,
            "externalSupplier": "Reference Lab", "externalReference": "LAB-EXT-001",
            "reason": "Itemised external charge recorded with cost and markup provenance",
        })
        assert charge.status_code == 200, charge.text
        assert charge.json()["charge"]["gross_pence"] == 15000

        complaint = client.post("/api/v32/complaints", headers=ops, json={
            "premisesRef": "reference-site", "episodeRef": "EP-V32-EXT-001", "patientRef": "PAT-V32-EXT-001",
            "channel": "email", "category": "communication", "severity": "standard",
            "summary": "Owner reports delayed update.", "reason": "Complaint received and assigned",
        })
        assert complaint.status_code == 200, complaint.text
        complaint_row = complaint.json()["complaint"]

        stale = client.patch(f"/api/v32/complaints/{complaint_row['complaint_ref']}", headers=ops, json={
            "expectedVersion": 99, "status": "acknowledged", "reason": "Stale write must fail",
        })
        assert stale.status_code == 409, stale.text

        resolved = client.patch(f"/api/v32/complaints/{complaint_row['complaint_ref']}", headers=ops, json={
            "expectedVersion": complaint_row["version"], "status": "resolved",
            "resolution": "Owner contacted, communication gap reviewed and follow-up completed.",
            "reason": "Complaint investigated and resolved",
        })
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["complaint"]["resolved_at"]

        missing_delivery = client.post("/api/v32/episodes/EP-V32-EXT-001/prescription-choice", headers=clinician, json={
            "patientRef": "PAT-V32-EXT-001", "medicationName": "Synthetic medication",
            "writtenPrescriptionOffered": True, "clientChoice": "hospital_supply",
            "reason": "Offer without information evidence must fail",
        })
        assert missing_delivery.status_code == 409, missing_delivery.text

        choice = client.post("/api/v32/episodes/EP-V32-EXT-001/prescription-choice", headers=clinician, json={
            "patientRef": "PAT-V32-EXT-001", "medicationName": "Synthetic medication",
            "writtenPrescriptionOffered": True, "prescriptionFeePence": 2500,
            "clientChoice": "hospital_supply", "informationDeliveryRef": "COMM-PRESCRIPTION-001",
            "reason": "Prescription choice and client information recorded",
        })
        assert choice.status_code == 200, choice.text

        ai = client.post("/api/v32/ai-provenance", headers=clinician, json={
            "episodeRef": "EP-V32-EXT-001", "patientRef": "PAT-V32-EXT-001",
            "sourceEntityType": "clinical_note", "sourceEntityRef": "DRAFT-001", "outputKind": "clinical_note",
            "provider": "test-provider", "modelName": "test-model", "clientDataUsed": True,
            "legalBasis": "clinical care", "reason": "Create unreviewed AI draft for governance snapshot",
        })
        assert ai.status_code == 200, ai.text

        snapshot = client.get("/api/v32/episodes/EP-V32-EXT-001/governance", headers=ops)
        assert snapshot.status_code == 200, snapshot.text
        body = snapshot.json()
        assert body["summary"]["chargeTotalPence"] == 15000
        assert body["summary"]["openComplaints"] == 0
        assert body["summary"]["prescriptionChoices"] == 1
        assert body["summary"]["unreviewedAI"] == 1
        assert any(item["code"] == "ai_review" for item in body["blockers"])

        print("Charge provenance, complaint lifecycle, prescription evidence and governance snapshot v32 OK")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
