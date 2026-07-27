import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_medication_v18_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "medication-v18-smoke-secret-long-enough-for-testing",
    "AUTH_ISSUER": "lucyworks-medication-v18-smoke",
    "AUTH_AUDIENCE": "lucyworks-medication-v18-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.clinical_execution_models import MedicationAdministration, MedicationOrder
from app.database import engine
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app
from app.medication_foundation_v18_models import (
    DoseCalculationV18,
    MedicationProposalV18,
    MedicationProtocolV18,
    ProductImportBatchV18,
    VeterinaryProductV18,
)

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    token = response.json().get("accessToken")
    assert token
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def ok(response, label: str = "request"):
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    return response.json()


try:
    with TestClient(app) as client:
        anonymous = client.get("/api/v18/medications/catalogue")
        assert anonymous.status_code == 401, anonymous.text

        clinician = login(client, 3)
        admin = login(client, 4)

        patient = client.put("/api/v8/patients/PAT-MED-V18-001", headers=clinician, json={
            "display_name": "UAT Bramble Medication 001",
            "species": "Dog",
            "breed": "Labrador",
            "sex": "female",
            "neuter_status": "neutered",
            "date_of_birth": "2020-04-10",
            "microchip_number": "985141000009180",
            "alerts": [],
            "reason": "Synthetic medication foundation patient",
        })
        ok(patient, "create patient")

        with Session(engine) as session:
            session.add(CanonicalEpisodeState(
                episode_ref="EP-MED-V18-001",
                patient_ref="PAT-MED-V18-001",
                patient_name="UAT Bramble Medication 001",
                premises_ref="reference-site",
                service_line="neurology",
                urgency="urgent",
                phase="consult",
                status="active",
                owner_role="clinician",
                owner_subject="local-user:3",
                current_area_ref="consult-1",
                next_action="Review medication plan",
            ))
            session.commit()

        weight = ok(client.post(
            "/api/v8/patients/PAT-MED-V18-001/weights",
            headers=clinician,
            json={
                "episode_ref": "EP-MED-V18-001",
                "weight_kg": 28.4,
                "body_condition_score": "5/9",
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "reason": "Synthetic current admission weight",
            },
        ), "record weight")
        assert weight["weight"]["weight_kg"] == 28.4

        import_payload = {
            "source_name": "VMD Product Information Database",
            "source_url": "https://example.invalid/vmd-synthetic-fixture.xml",
            "source_sha256": "a" * 64,
            "source_format": "xml-fixture",
            "schema_fingerprint": "b" * 64,
            "products": [{
                "source_product_id": "Vm-SYNTHETIC-18-001",
                "territory": "GB",
                "product_name": "UAT Synthetic Analgesic 10 mg/ml solution for injection",
                "marketing_authorisation_holder": "Synthetic Holder Ltd",
                "distribution_category": "POM-V",
                "authorisation_status": "current",
                "pharmaceutical_form": "Solution for injection",
                "active_substances": ["UAT Synthetic Analgesic"],
                "target_species": ["Dog"],
                "routes": ["IV"],
                "strengths": [{"amount": 10, "unit": "mg/ml"}],
                "concentration_mg_per_ml": 10.0,
                "contraindications": [],
                "warnings": [],
                "withdrawal_periods": [],
                "spc_version": "SYNTHETIC-2026-01",
                "source_updated_at": datetime.now(timezone.utc).isoformat(),
                "source_url": "https://example.invalid/vmd-synthetic-product",
            }],
        }
        imported = ok(client.post(
            "/api/v18/medications/catalogue/import", headers=admin, json=import_payload
        ), "import product catalogue")
        assert imported["created"] is True
        assert imported["batch"]["product_count"] == 1
        assert imported["batch"]["created_count"] == 1

        repeated = ok(client.post(
            "/api/v18/medications/catalogue/import", headers=admin, json=import_payload
        ), "repeat product catalogue import")
        assert repeated["created"] is False

        catalogue = ok(client.get(
            "/api/v18/medications/catalogue?q=synthetic&species=Dog&territory=GB",
            headers=clinician,
        ), "search catalogue")
        assert catalogue["count"] == 1
        product = catalogue["products"][0]
        assert product["source_product_id"] == "Vm-SYNTHETIC-18-001"
        assert product["concentration_mg_per_ml"] == 10.0

        draft = ok(client.post(
            "/api/v18/medications/protocols", headers=clinician, json={
                "organisation_ref": "reference-tenant",
                "product_ref": product["product_ref"],
                "generic_name": "UAT Synthetic Analgesic",
                "species": "Dog",
                "indication": "Synthetic peri-procedural analgesia",
                "route": "IV",
                "recommended_mg_per_kg": 0.2,
                "minimum_mg_per_kg": 0.1,
                "maximum_mg_per_kg": 0.3,
                "maximum_single_dose_mg": 10.0,
                "interval_hours": 6,
                "source_type": "customer_approved_protocol",
                "source_reference": "UAT-MED-PROTOCOL-001",
                "source_version": "1.0",
                "review_due_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
                "reason": "Synthetic protocol creation proof",
            },
        ), "create protocol")
        assert draft["protocol"]["status"] == "draft"
        protocol_ref = draft["protocol"]["protocol_ref"]

        approved = ok(client.patch(
            f"/api/v18/medications/protocols/{protocol_ref}/approve",
            headers=clinician,
            json={"expected_version": 1, "reason": "Synthetic protocol governance approval"},
        ), "approve protocol")
        assert approved["protocol"]["status"] == "approved"
        assert approved["protocol"]["version"] == 2

        clear = ok(client.post(
            "/api/v18/medications/calculate", headers=clinician, json={
                "episode_ref": "EP-MED-V18-001",
                "product_ref": product["product_ref"],
                "protocol_ref": protocol_ref,
                "requested_mg_per_kg": 0.2,
                "rounding_increment_ml": 0.01,
                "reason": "Synthetic deterministic dose proof",
            },
        ), "calculate clear dose")
        calculation = clear["calculation"]
        assert calculation["calculated_dose_mg"] == 5.68, calculation
        assert calculation["calculated_volume_ml"] == 0.568, calculation
        assert calculation["rounded_volume_ml"] == 0.57, calculation
        assert calculation["outcome"] == "clear", calculation
        assert calculation["blockers"] == []
        assert calculation["source_snapshot"]["spcVersion"] == "SYNTHETIC-2026-01"

        blocked = ok(client.post(
            "/api/v18/medications/calculate", headers=clinician, json={
                "episode_ref": "EP-MED-V18-001",
                "product_ref": product["product_ref"],
                "protocol_ref": protocol_ref,
                "requested_mg_per_kg": 0.5,
                "rounding_increment_ml": 0.01,
                "reason": "Synthetic out-of-range proof",
            },
        ), "calculate blocked dose")
        assert blocked["calculation"]["outcome"] == "blocked"
        assert any(item["code"] == "above_protocol_range" for item in blocked["calculation"]["blockers"])

        non_prescriber_review = client.post(
            f"/api/v18/medications/calculations/{calculation['calculation_ref']}/review",
            headers=admin,
            json={"frequency": "every 6 hours", "reason": "Must be rejected for non-prescriber"},
        )
        assert non_prescriber_review.status_code == 403, non_prescriber_review.text

        reviewed = ok(client.post(
            f"/api/v18/medications/calculations/{calculation['calculation_ref']}/review",
            headers=clinician,
            json={"frequency": "every 6 hours", "reason": "Prescriber reviewed formula, sources and patient warnings"},
        ), "review calculation")
        proposal = reviewed["proposal"]
        assert proposal["status"] == "reviewed"
        assert proposal["dose_mg"] == 5.68
        assert proposal["volume_ml"] == 0.57
        assert reviewed["safetyReview"]["blocks_order"] is False

        start = datetime.now(timezone.utc) + timedelta(minutes=30)
        prescribed = ok(client.post(
            f"/api/v18/medications/proposals/{proposal['proposal_ref']}/prescribe",
            headers=clinician,
            json={
                "expected_version": proposal["version"],
                "frequency": "every 6 hours",
                "starts_at": start.isoformat(),
                "scheduled_times": [start.isoformat()],
                "reason": "Synthetic prescription issued after visible prescriber review",
            },
        ), "prescribe reviewed proposal")
        assert prescribed["proposal"]["status"] == "prescribed"
        assert prescribed["order"]["dose"] == "5.68 mg"
        assert len(prescribed["administrations"]) == 1

        stale = client.post(
            f"/api/v18/medications/proposals/{proposal['proposal_ref']}/prescribe",
            headers=clinician,
            json={
                "expected_version": proposal["version"],
                "frequency": "every 6 hours",
                "starts_at": start.isoformat(),
                "scheduled_times": [start.isoformat()],
                "reason": "Stale replay must be rejected",
            },
        )
        assert stale.status_code == 409, stale.text

        workspace = ok(client.get(
            "/api/v18/medications/episodes/EP-MED-V18-001/workspace", headers=clinician
        ), "open medication workspace")
        assert workspace["patient"]["display_name"] == "UAT Bramble Medication 001"
        assert workspace["weight"]["weight_kg"] == 28.4
        assert len(workspace["calculations"]) == 2
        assert len(workspace["proposals"]) == 1
        assert len(workspace["activeOrders"]) == 1

        with Session(engine) as session:
            assert session.exec(select(ProductImportBatchV18)).all()
            assert session.exec(select(VeterinaryProductV18)).all()
            assert session.exec(select(MedicationProtocolV18)).all()
            assert len(session.exec(select(DoseCalculationV18)).all()) == 2
            assert len(session.exec(select(MedicationProposalV18)).all()) == 1
            assert len(session.exec(select(MedicationOrder)).all()) == 1
            assert len(session.exec(select(MedicationAdministration)).all()) == 1

        print("MEDICATION_FOUNDATION_V18_SMOKE_TEST_PASSED")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
