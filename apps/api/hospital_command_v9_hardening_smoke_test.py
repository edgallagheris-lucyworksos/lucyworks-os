import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_hospital_command_v9_hardening_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "hospital-command-v9-hardening-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-command-v9-hardening",
    "AUTH_AUDIENCE": "lucyworks-command-v9-hardening-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.database import engine
from app.detailed_hospital_models import CommunicationEventV8, OwnerAccountV8, PatientClinicalRecordV8, PatientOwnerLinkV8
from app.hospital_command_models import EpisodeClosureV9
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app
from app.models import User

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def create_referral(client: TestClient, auth: dict[str, str], *, episode_ref: str, referral_ref: str, patient_ref: str):
    response = client.post("/api/v9/referrals", headers=auth, json={
        "episode_ref": episode_ref,
        "referral_ref": referral_ref,
        "patient_ref": patient_ref,
        "premises_ref": "bvs-bristol",
        "source_type": "referring_vet",
        "source_organisation": "Synthetic Primary Care",
        "requested_service": "internal_medicine",
        "presenting_problem": "Synthetic referral",
        "urgency": "routine",
        "reason": "Hardening validation referral",
    })
    assert response.status_code == 200, response.text
    return response.json()


try:
    with Session(engine) as session:
        session.add_all([
            User(id=1, name="Olivia Ops", role="ops_manager", email="ops@example.test"),
            User(id=2, name="Cal Clinician", role="clinician", email="clinician@example.test"),
            User(id=3, name="Dana Director", role="clinical_director", email="director@example.test"),
            User(id=4, name="Ari Admin", role="admin", email="admin@example.test"),
            PatientClinicalRecordV8(patient_ref="PAT-V9-H1", display_name="Hardening Patient One", species="dog"),
            PatientClinicalRecordV8(patient_ref="PAT-V9-H2", display_name="Hardening Patient Two", species="cat"),
            OwnerAccountV8(owner_ref="OWN-V9-H1", display_name="Clinical Authority Only", identity_verified=True),
            OwnerAccountV8(owner_ref="OWN-V9-H2", display_name="Financial Authority", identity_verified=True),
            PatientOwnerLinkV8(
                link_ref="LINK-V9-H1", patient_ref="PAT-V9-H1", owner_ref="OWN-V9-H1",
                decision_authority=True, financial_responsibility=False,
            ),
            PatientOwnerLinkV8(
                link_ref="LINK-V9-H2", patient_ref="PAT-V9-H2", owner_ref="OWN-V9-H2",
                decision_authority=True, financial_responsibility=True,
            ),
        ])
        session.commit()

    with TestClient(app) as client:
        ops = login(client, 1)
        clinician = login(client, 2)
        director = login(client, 3)
        admin = login(client, 4)

        first = create_referral(client, ops, episode_ref="EP-V9-H1", referral_ref="REF-V9-H1", patient_ref="PAT-V9-H1")
        accepted = client.patch("/api/v9/referrals/REF-V9-H1", headers=clinician, json={
            "expected_version": 1, "status": "accepted", "reason": "Accepted for hardening test",
        })
        assert accepted.status_code == 200, accepted.text
        episode = first["episode"]
        triage = client.post("/api/v9/episodes/EP-V9-H1/transition", headers=clinician, json={
            "expected_version": episode["version"], "target_phase": "triage",
            "idempotency_key": "hardening-triage", "reason": "Begin triage",
        })
        assert triage.status_code == 200 and triage.json()["ok"] is True, triage.text
        episode = triage.json()["episode"]
        consult = client.post("/api/v9/episodes/EP-V9-H1/transition", headers=clinician, json={
            "expected_version": episode["version"], "target_phase": "consult",
            "idempotency_key": "hardening-consult", "reason": "Begin consult",
        })
        assert consult.status_code == 200 and consult.json()["ok"] is True, consult.text

        no_financial_authority = client.post("/api/v9/episodes/EP-V9-H1/consents", headers=clinician, json={
            "owner_ref": "OWN-V9-H1",
            "consent_type": "admission",
            "scope": {"admission": True},
            "maximum_authorised_pence": 100000,
            "currency": "GBP",
            "decision_maker_name": "Clinical Authority Only",
            "captured_channel": "telephone",
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "reason": "Should fail financial responsibility check",
        })
        assert no_financial_authority.status_code == 409, no_financial_authority.text

        clinical_only = client.post("/api/v9/episodes/EP-V9-H1/consents", headers=clinician, json={
            "owner_ref": "OWN-V9-H1",
            "consent_type": "admission",
            "scope": {"admission": True},
            "maximum_authorised_pence": None,
            "currency": "GBP",
            "decision_maker_name": "Clinical Authority Only",
            "captured_channel": "telephone",
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "reason": "Clinical authority without financial authorisation",
        })
        assert clinical_only.status_code == 200, clinical_only.text

        guard = client.get("/api/v9/episodes/EP-V9-H1/transition-guard/admitted", headers=clinician)
        assert guard.status_code == 200, guard.text
        assert guard.json()["canTransition"] is True

        non_waivable = client.post("/api/v9/episodes/EP-V9-H1/checkpoints", headers=director, json={
            "checkpoint_code": "transition_graph",
            "status": "waived",
            "detail": {},
            "reason": "Must never be accepted",
            "valid_until": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        })
        assert non_waivable.status_code == 409, non_waivable.text

        no_expiry = client.post("/api/v9/episodes/EP-V9-H1/checkpoints", headers=director, json={
            "checkpoint_code": "handover",
            "status": "waived",
            "detail": {},
            "reason": "Expiry deliberately omitted",
        })
        assert no_expiry.status_code == 422, no_expiry.text

        too_long = client.post("/api/v9/episodes/EP-V9-H1/checkpoints", headers=director, json={
            "checkpoint_code": "handover",
            "status": "waived",
            "detail": {},
            "reason": "Duration deliberately too long",
            "valid_until": (datetime.now(timezone.utc) + timedelta(hours=25)).isoformat(),
        })
        assert too_long.status_code == 422, too_long.text

        valid_waiver = client.post("/api/v9/episodes/EP-V9-H1/checkpoints", headers=director, json={
            "checkpoint_code": "handover",
            "status": "waived",
            "detail": {"bounded": True},
            "reason": "Time-bounded senior exception",
            "valid_until": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        })
        assert valid_waiver.status_code == 200, valid_waiver.text

        second = create_referral(client, ops, episode_ref="EP-V9-H2", referral_ref="REF-V9-H2", patient_ref="PAT-V9-H2")
        declined = client.patch("/api/v9/referrals/REF-V9-H2", headers=clinician, json={
            "expected_version": 1,
            "status": "declined",
            "reason": "Service not appropriate; referring practice advised of alternative pathway",
        })
        assert declined.status_code == 200, declined.text
        with Session(engine) as session:
            session.add(CommunicationEventV8(
                communication_ref="COMM-V9-H2-REFERRER",
                patient_ref="PAT-V9-H2",
                episode_ref="EP-V9-H2",
                audience="referring_vet",
                channel="secure_email",
                direction="outbound",
                subject="Referral decision",
                summary="Referral declined with reason and alternative pathway",
                outcome="sent",
                actor_subject="local-user:2",
            ))
            session.commit()

        closure = client.post("/api/v9/episodes/EP-V9-H2/closure", headers=ops, json={
            "disposition": "referral_declined",
            "referrer_communication_ref": "COMM-V9-H2-REFERRER",
            "financial_status": "no_charge",
            "outstanding_actions": [],
            "retained_risks": [{"risk": "care delay", "mitigation": "alternative service communicated"}],
            "reason": "Prepare declined-referral closure",
        })
        assert closure.status_code == 200, closure.text
        row = closure.json()["closure"]
        approved = client.patch(f"/api/v9/closures/{row['closure_ref']}/approve", headers=director, json={
            "expected_version": row["version"],
            "reason": "Referral decision, communication and no-charge status reviewed",
        })
        assert approved.status_code == 200, approved.text
        assert approved.json()["earlyClosure"] is True

        close = client.post("/api/v9/episodes/EP-V9-H2/transition", headers=admin, json={
            "expected_version": second["episode"]["version"],
            "target_phase": "closed",
            "idempotency_key": "hardening-early-close",
            "reason": "Close declined referral without false discharge evidence",
        })
        assert close.status_code == 200 and close.json()["ok"] is True, close.text
        assert close.json()["guard"]["earlyClosure"] is True

        with Session(engine) as session:
            canonical = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == "EP-V9-H2")).one()
            closure_db = session.exec(select(EpisodeClosureV9).where(EpisodeClosureV9.episode_ref == "EP-V9-H2")).one()
            assert canonical.phase == "closed"
            assert closure_db.status == "completed"

        print("UTC normalisation, bounded waiver, financial authority and early referral closure v9 OK")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
