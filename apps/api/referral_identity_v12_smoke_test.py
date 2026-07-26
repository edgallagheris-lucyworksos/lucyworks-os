from __future__ import annotations

import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_referral_identity_v12_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AUTH_MODE"] = "local"
os.environ["AUTH_ENFORCEMENT"] = "required"
os.environ["AUTH_JWT_SECRET"] = "referral-identity-v12-test-secret-that-is-long-and-private"
os.environ["AUTH_ISSUER"] = "lucyworks-test"
os.environ["AUTH_AUDIENCE"] = "lucyworks-api"
os.environ["AUTO_CREATE_SCHEMA"] = "true"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.auth import issue_local_token
from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

admin_token, _ = issue_local_token(user_id=101, name="Intake Admin", role="admin", email="admin@example.test")
clinician_token, _ = issue_local_token(user_id=102, name="Referral Clinician", role="clinical_director", email="clinician@example.test")
nurse_token, _ = issue_local_token(user_id=103, name="Referral Nurse", role="nurse", email="nurse@example.test")
admin = {"Authorization": f"Bearer {admin_token}"}
clinician = {"Authorization": f"Bearer {clinician_token}"}
nurse = {"Authorization": f"Bearer {nurse_token}"}
checksum = "a" * 64

payload = {
    "premisesRef": "default-premises",
    "patientName": "Synthetic Bramble",
    "species": "dog",
    "breed": "Labrador",
    "sex": "female",
    "dateOfBirth": "2020-04-10",
    "microchipNumber": "985141000000001",
    "ownerName": "Synthetic Owner",
    "ownerEmail": "owner@example.test",
    "ownerPhone": "07000000001",
    "decisionAuthority": True,
    "financialResponsibility": True,
    "sourceType": "referring_vet",
    "sourceOrganisation": "Synthetic Referring Practice",
    "sourceContactName": "Synthetic Vet",
    "sourceContactEmail": "vet@example.test",
    "requestedService": "MRI neurology",
    "presentingProblem": "Acute paralysis and severe pain",
    "clinicalSummary": "Unable to walk since this morning",
    "urgency": "urgent",
    "documents": [{
        "documentType": "referral_letter",
        "filename": "synthetic-referral.pdf",
        "mimeType": "application/pdf",
        "storageRef": "synthetic://referrals/bramble/letter",
        "checksumSha256": checksum,
        "sourceSystem": "synthetic_pims",
    }],
    "reason": "Synthetic governed referral identity journey",
}

try:
    with TestClient(app) as client:
        response = client.post("/api/v12/referrals/intake", headers=admin, json=payload)
        assert response.status_code == 200, response.text
        created = response.json()
        assert created["requiresIdentityReview"] is False
        assert created["patient"]["display_name"] == "Synthetic Bramble"
        assert created["owner"]["display_name"] == "Synthetic Owner"
        assert created["referral"]["status"] == "received"
        assert created["triage"]["category"] == "urgent"
        assert created["documents"][0]["checksum_sha256"] == checksum
        patient_ref = created["patient"]["patient_ref"]
        referral_ref = created["referral"]["referral_ref"]
        print("Atomic owner, patient, authority, referral, episode, triage and document creation OK")

        response = client.post("/api/v12/referrals/intake", headers=nurse, json={
            **payload,
            "ownerPhone": "07000000002",
            "sourceOrganisation": "Second Synthetic Practice",
            "reason": "Second referral should enter duplicate review",
        })
        assert response.status_code == 200, response.text
        duplicate = response.json()
        assert duplicate["requiresIdentityReview"] is True
        assert duplicate["identityReviews"]
        assert duplicate["identityReviews"][0]["candidate_patient_ref"] == patient_ref
        intake_ref = duplicate["intake"]["intake_ref"]
        intake_version = duplicate["intake"]["version"]
        print("Exact-microchip duplicate hold and ranked identity review OK")

        response = client.post(f"/api/v12/identity-intakes/{intake_ref}/resolve", headers=admin, json={
            "expectedVersion": intake_version,
            "decision": "link_existing",
            "patientRef": patient_ref,
            "reason": "Microchip and clinical identity confirmed as the existing patient",
        })
        assert response.status_code == 200, response.text
        resolved = response.json()
        assert resolved["patient"]["patient_ref"] == patient_ref
        assert resolved["referral"]["referral_ref"] != referral_ref
        print("Governed duplicate resolution and existing-patient linkage OK")

        response = client.get("/api/v12/triage?status=pending", headers=clinician)
        assert response.status_code == 200, response.text
        triage_items = response.json()["items"]
        assert len(triage_items) >= 2
        triage = next(item for item in triage_items if item["referral_ref"] == referral_ref)
        response = client.patch(f"/api/v12/triage/{triage['triage_ref']}", headers=clinician, json={
            "expectedVersion": triage["version"],
            "status": "acknowledged",
            "assignedSubject": "clinician-102",
            "rationale": "Urgent neurology referral reviewed",
            "reason": "Clinician accepted triage responsibility",
        })
        assert response.status_code == 200, response.text
        assert response.json()["triage"]["status"] == "acknowledged"
        print("Versioned triage acknowledgement and SLA queue OK")

        response = client.patch(f"/api/v12/referrals/{referral_ref}/decision", headers=clinician, json={
            "expectedVersion": 1,
            "status": "accepted",
            "reason": "Referral accepted for neurology MRI assessment",
            "proposedDurationMinutes": 90,
        })
        assert response.status_code == 200, response.text
        decision = response.json()
        assert decision["referral"]["status"] == "accepted"
        assert decision["proposedBlock"]["status"] == "proposed"
        assert decision["proposedBlock"]["areaRef"] == "mri"
        assert decision["proposedBlock"]["gates"]["consent"] == "pending"
        print("Accepted referral converted into proposed canonical operational block OK")

        response = client.patch(f"/api/v12/referrals/{referral_ref}/decision", headers=clinician, json={
            "expectedVersion": 1,
            "status": "accepted",
            "reason": "Stale repeat",
        })
        assert response.status_code == 409, response.text
        print("Stale referral decision rejected OK")

        response = client.post("/api/v12/access-reviews", headers=admin, json={
            "subjectRef": "staff-synthetic-1",
            "subjectName": "Synthetic Staff Member",
            "platformRole": "clinician",
            "identityGroup": "referral_clinician",
            "requestedCapabilities": ["clinical.record", "referral.accept", "board.view"],
            "restrictedCapabilities": ["deployment.approve"],
            "dueDays": 14,
            "reason": "Initial role and capability review",
        })
        assert response.status_code == 200, response.text
        access = response.json()["accessReview"]
        response = client.patch(f"/api/v12/access-reviews/{access['review_ref']}", headers=clinician, json={
            "expectedVersion": access["version"],
            "decision": "restricted",
            "restrictedCapabilities": ["deployment.approve", "controlled_drug.reconcile"],
            "reason": "Clinical access approved with senior-only governance restrictions",
        })
        assert response.status_code == 200, response.text
        assert response.json()["accessReview"]["status"] == "completed"
        print("Evidence-backed access review decision OK")

        response = client.get("/api/evidence/integrity", headers=admin)
        assert response.status_code == 200, response.text
        assert response.json()["ok"] is True, response.text
        print("Tamper-evident v12 assurance chain OK")

    print("\n--- REFERRAL IDENTITY AND ASSURANCE V12 SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
