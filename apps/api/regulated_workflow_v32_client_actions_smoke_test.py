import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_regulated_v32_client_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "regulated-v32-client-actions-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-regulated-v32-client-actions-smoke",
    "AUTH_AUDIENCE": "lucyworks-regulated-v32-client-actions-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.database import engine
from app.detailed_hospital_models import CommunicationEventV8, OwnerAccountV8, PatientClinicalRecordV8, PatientOwnerLinkV8
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app
from app.models import User
from app.regulated_workflow_v32_extension_models import PrescriptionChoiceV32
from app.regulated_workflow_v32_models import EstimateGovernanceV32

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
            OwnerAccountV8(owner_ref="OWN-V32-CLIENT-001", display_name="Client One", email="client@example.test", identity_verified=True),
            PatientClinicalRecordV8(patient_ref="PAT-V32-CLIENT-001", display_name="Bramble", species="dog", breed="Labrador"),
            PatientOwnerLinkV8(
                link_ref="LINK-V32-CLIENT-001",
                patient_ref="PAT-V32-CLIENT-001",
                owner_ref="OWN-V32-CLIENT-001",
                relationship="registered_owner",
                decision_authority=True,
                financial_responsibility=True,
                active=True,
            ),
            CanonicalEpisodeState(
                episode_ref="EP-V32-CLIENT-001",
                patient_ref="PAT-V32-CLIENT-001",
                patient_name="Bramble",
                premises_ref="reference-site",
                service_line="neurology",
                urgency="urgent",
                phase="consult",
                status="active",
                owner_role="clinician",
                owner_subject="local-user:3",
            ),
        ])
        session.commit()

    with TestClient(app) as client:
        ops = login(client, 1)
        clinician = login(client, 3)

        estimate = client.post(
            "/api/v32/episodes/EP-V32-CLIENT-001/estimates/deliver-and-issue",
            headers=ops,
            json={
                "patientRef": "PAT-V32-CLIENT-001",
                "ownerRef": "OWN-V32-CLIENT-001",
                "channel": "email",
                "lines": [{
                    "category": "imaging",
                    "description": "MRI and interpretation",
                    "quantity": 1,
                    "lowerUnitPence": 55000,
                    "upperUnitPence": 65000,
                    "taxRatePercent": 20,
                    "optional": False,
                }],
                "authorisedLimitPence": 70000,
                "ownerAcknowledged": True,
                "deliverySummary": "Written MRI estimate emailed and receipt acknowledged.",
                "reason": "Client authority and written estimate delivery proven in one command",
            },
        )
        assert estimate.status_code == 200, estimate.text
        estimate_body = estimate.json()
        assert estimate_body["estimate"]["status"] == "issued"
        assert estimate_body["governance"]["written_estimate_required"] is True
        assert estimate_body["governance"]["written_delivery_ref"]
        assert estimate_body["delivery"]["ownerAcknowledged"] is True

        prescription = client.post(
            "/api/v32/episodes/EP-V32-CLIENT-001/prescription-choice/deliver-and-record",
            headers=clinician,
            json={
                "patientRef": "PAT-V32-CLIENT-001",
                "ownerRef": "OWN-V32-CLIENT-001",
                "medicationName": "Synthetic ongoing medication",
                "writtenPrescriptionOffered": True,
                "prescriptionFeePence": 2500,
                "clientChoice": "written_prescription",
                "channel": "in_person",
                "informationSummary": "Written prescription option and fee explained; client chose a written prescription.",
                "reason": "Prescription information and client choice recorded atomically",
            },
        )
        assert prescription.status_code == 200, prescription.text
        prescription_body = prescription.json()
        assert prescription_body["prescriptionChoice"]["client_choice"] == "written_prescription"
        assert prescription_body["prescriptionChoice"]["information_delivery_ref"]
        assert prescription_body["informationDelivery"]["evidenceEventRef"] == prescription_body["prescriptionChoice"]["information_delivery_ref"]

        with Session(engine) as session:
            communications = session.exec(
                select(CommunicationEventV8).where(CommunicationEventV8.episode_ref == "EP-V32-CLIENT-001")
            ).all()
            choices = session.exec(
                select(PrescriptionChoiceV32).where(PrescriptionChoiceV32.episode_ref == "EP-V32-CLIENT-001")
            ).all()
            governance = session.exec(
                select(EstimateGovernanceV32).where(EstimateGovernanceV32.episode_ref == "EP-V32-CLIENT-001")
            ).all()
            assert len(communications) == 2, communications
            assert len(choices) == 1, choices
            assert len(governance) == 1, governance
            assert choices[0].information_delivery_ref == communications[1].evidence_event_ref

        legacy = client.post(
            "/api/v8/episodes/EP-V32-CLIENT-001/estimates",
            headers=ops,
            json={"patient_ref": "PAT-V32-CLIENT-001", "status": "issued", "lines": []},
        )
        assert legacy.status_code == 410, legacy.text

        print("Transactional estimate delivery and prescription client-choice actions v32 OK")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
