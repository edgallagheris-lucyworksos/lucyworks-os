import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_regulated_v32_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "regulated-workflow-v32-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-regulated-v32-smoke",
    "AUTH_AUDIENCE": "lucyworks-regulated-v32-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.database import engine
from app.detailed_hospital_models import PatientClinicalRecordV8
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app
from app.models import User
from app.regulated_workflow_v32_models import AIProvenanceV32, EstimateGovernanceV32, ServicePriceV32

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def headers(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


try:
    with Session(engine) as session:
        session.add_all([
            User(id=1, name="Olivia Ops", role="ops_manager", email="ops@example.test"),
            User(id=2, name="Cal Clinician", role="clinician", email="clinician@example.test"),
            PatientClinicalRecordV8(patient_ref="PAT-V32-001", display_name="Synthetic Spaniel", species="dog"),
            CanonicalEpisodeState(
                episode_ref="EP-V32-001",
                patient_ref="PAT-V32-001",
                patient_name="Synthetic Spaniel",
                premises_ref="bvs-bristol",
                phase="consult",
                owner_role="clinician",
            ),
        ])
        session.commit()

    with TestClient(app) as client:
        ops = headers(client, 1)
        clinician = headers(client, 2)

        price = client.post("/api/v32/prices", headers=ops, json={
            "premisesRef": "bvs-bristol",
            "serviceCode": "MRI-BRAIN",
            "serviceName": "MRI brain",
            "category": "diagnostic_imaging",
            "lowerPricePence": 60000,
            "upperPricePence": 60000,
            "vatIncluded": True,
            "standardDurationMinutes": 60,
            "inclusions": ["MRI acquisition", "specialist interpretation"],
            "exclusions": ["anaesthesia if separately required"],
            "interpretationIncluded": True,
            "status": "published",
            "reason": "Publish controlled synthetic MRI price",
        })
        assert price.status_code == 200, price.text
        price_ref = price.json()["price"]["price_ref"]
        print("Published versioned service price OK")

        legacy = client.post("/api/v8/episodes/EP-V32-001/estimates", headers=ops, json={})
        assert legacy.status_code == 410, legacy.text
        assert legacy.json()["replacement"] == "/api/v32/episodes/EP-V32-001/estimates"
        print("Legacy estimate write retired OK")

        first = client.post("/api/v32/episodes/EP-V32-001/estimates", headers=ops, json={
            "patientRef": "PAT-V32-001",
            "status": "issued",
            "ownerAuthorisationRef": "CONSENT-V32-001",
            "writtenDeliveryRef": "COMM-V32-EST-001",
            "lines": [{
                "category": "diagnostic_imaging",
                "description": "MRI brain",
                "quantity": 1,
                "lowerUnitPence": 60000,
                "upperUnitPence": 60000,
                "sourceCatalogueRef": price_ref,
            }],
            "reason": "Issue first written estimate",
        })
        assert first.status_code == 200, first.text
        assert first.json()["governance"]["written_estimate_required"] is True
        assert first.json()["governance"]["written_update_required"] is False
        print("£500 written-estimate trigger OK")

        blocked_update = client.post("/api/v32/episodes/EP-V32-001/estimates", headers=ops, json={
            "patientRef": "PAT-V32-001",
            "status": "issued",
            "ownerAuthorisationRef": "CONSENT-V32-002",
            "lines": [{
                "category": "diagnostic_imaging",
                "description": "MRI brain plus additional sequences",
                "quantity": 1,
                "lowerUnitPence": 72000,
                "upperUnitPence": 72000,
            }],
            "reason": "Attempt material estimate increase without written update evidence",
        })
        assert blocked_update.status_code == 409, blocked_update.text
        print("Material estimate increase blocked without evidence OK")

        updated = client.post("/api/v32/episodes/EP-V32-001/estimates", headers=ops, json={
            "patientRef": "PAT-V32-001",
            "status": "issued",
            "ownerAuthorisationRef": "CONSENT-V32-002",
            "writtenDeliveryRef": "COMM-V32-EST-002",
            "ownerAcknowledgementRef": "ACK-V32-002",
            "reasonForChange": "Additional sequences clinically required",
            "lines": [{
                "category": "diagnostic_imaging",
                "description": "MRI brain plus additional sequences",
                "quantity": 1,
                "lowerUnitPence": 72000,
                "upperUnitPence": 72000,
            }],
            "reason": "Issue evidenced material estimate update",
        })
        assert updated.status_code == 200, updated.text
        governance = updated.json()["governance"]
        assert governance["written_update_required"] is True
        assert governance["update_threshold_pence"] == 12000
        assert governance["increase_pence"] == 12000
        print("20 percent or £500 lower-threshold update rule OK")

        missing_basis = client.post("/api/v32/ai-provenance", headers=clinician, json={
            "episodeRef": "EP-V32-001",
            "patientRef": "PAT-V32-001",
            "sourceEntityType": "speech_capture",
            "sourceEntityRef": "CAP-V32-001",
            "outputKind": "clinical_note",
            "provider": "synthetic-provider",
            "modelName": "synthetic-model",
            "clientDataUsed": True,
        })
        assert missing_basis.status_code == 409, missing_basis.text

        training_without_consent = client.post("/api/v32/ai-provenance", headers=clinician, json={
            "episodeRef": "EP-V32-001",
            "patientRef": "PAT-V32-001",
            "sourceEntityType": "speech_capture",
            "sourceEntityRef": "CAP-V32-001",
            "outputKind": "clinical_note",
            "provider": "synthetic-provider",
            "modelName": "synthetic-model",
            "clientDataUsed": True,
            "legalBasis": "client consent for care documentation",
            "trainingUsePermitted": True,
        })
        assert training_without_consent.status_code == 409, training_without_consent.text
        print("AI client-data governance blockers OK")

        provenance = client.post("/api/v32/ai-provenance", headers=clinician, json={
            "episodeRef": "EP-V32-001",
            "patientRef": "PAT-V32-001",
            "sourceEntityType": "speech_capture",
            "sourceEntityRef": "CAP-V32-001",
            "outputKind": "clinical_note",
            "provider": "synthetic-provider",
            "modelName": "synthetic-model",
            "modelVersion": "2026-08",
            "clientDataUsed": True,
            "legalBasis": "client consent for care documentation",
            "clientConsentRef": "CONSENT-AI-V32-001",
            "trainingUsePermitted": False,
            "inputRefs": [{"type": "speech_capture", "ref": "CAP-V32-001"}],
        })
        assert provenance.status_code == 200, provenance.text
        prov = provenance.json()["provenance"]
        assert prov["status"] == "draft"

        ops_review = client.patch(f"/api/v32/ai-provenance/{prov['provenance_ref']}/review", headers=ops, json={
            "expectedVersion": prov["version"],
            "decision": "reviewed",
            "finalEntityRef": "NOTE-V32-001",
            "reason": "Ops must not sign clinical AI output",
        })
        assert ops_review.status_code == 403, ops_review.text

        clinical_review = client.patch(f"/api/v32/ai-provenance/{prov['provenance_ref']}/review", headers=clinician, json={
            "expectedVersion": prov["version"],
            "decision": "reviewed",
            "editSummary": "Corrected one clinical phrase before signing",
            "finalEntityRef": "NOTE-V32-001",
            "reason": "Clinician manually verified AI-assisted draft",
        })
        assert clinical_review.status_code == 200, clinical_review.text
        assert clinical_review.json()["provenance"]["status"] == "reviewed"
        print("AI provenance and clinical human-review boundary OK")

        with Session(engine) as session:
            assert len(session.exec(select(ServicePriceV32)).all()) == 1
            assert len(session.exec(select(EstimateGovernanceV32)).all()) == 2
            ai = session.exec(select(AIProvenanceV32)).one()
            assert ai.status == "reviewed" and ai.final_entity_ref == "NOTE-V32-001"

        print("\n--- REGULATED WORKFLOW V32 SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
