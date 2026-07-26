import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_hospital_command_v9_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "hospital-command-v9-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-command-v9-smoke",
    "AUTH_AUDIENCE": "lucyworks-command-v9-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.database import engine
from app.detailed_hospital_models import (
    ClinicalDocumentV8,
    CommunicationEventV8,
    InpatientCarePlanV8,
    OwnerAccountV8,
    PatientClinicalRecordV8,
    PatientOwnerLinkV8,
)
from app.hospital_command_models import EpisodeClosureV9, EpisodeHandoverV9, ReferralIntakeV9
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app
from app.models import User

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def headers(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def transition(client: TestClient, auth: dict[str, str], episode_ref: str, version: int, target: str, key: str):
    return client.post(
        f"/api/v9/episodes/{episode_ref}/transition",
        headers=auth,
        json={
            "expected_version": version,
            "target_phase": target,
            "idempotency_key": key,
            "reason": f"Synthetic v9 transition to {target}",
        },
    )


try:
    with Session(engine) as session:
        session.add_all([
            User(id=1, name="Olivia Ops", role="ops_manager", email="ops@example.test"),
            User(id=2, name="Nora Nurse", role="nurse", email="nurse@example.test"),
            User(id=3, name="Cal Clinician", role="clinician", email="clinician@example.test"),
            User(id=4, name="Dana Director", role="clinical_director", email="director@example.test"),
            User(id=5, name="Ari Admin", role="admin", email="admin@example.test"),
            PatientClinicalRecordV8(patient_ref="PAT-V9-001", display_name="Synthetic Spaniel", species="dog", breed="Cocker Spaniel"),
            OwnerAccountV8(owner_ref="OWN-V9-001", display_name="Synthetic Owner", email="owner@example.test", identity_verified=True),
            PatientOwnerLinkV8(
                link_ref="LINK-V9-001", patient_ref="PAT-V9-001", owner_ref="OWN-V9-001",
                relationship="registered_owner", decision_authority=True, financial_responsibility=True,
            ),
        ])
        session.commit()

    with TestClient(app) as client:
        ops = headers(client, 1)
        nurse = headers(client, 2)
        clinician = headers(client, 3)
        director = headers(client, 4)
        admin = headers(client, 5)

        referral = client.post("/api/v9/referrals", headers=ops, json={
            "episode_ref": "EP-V9-001",
            "referral_ref": "REF-V9-001",
            "patient_ref": "PAT-V9-001",
            "premises_ref": "bvs-bristol",
            "source_type": "referring_vet",
            "source_organisation": "Synthetic Primary Care",
            "requested_service": "neurology",
            "presenting_problem": "Progressive paresis",
            "clinical_summary": "Synthetic command-spine validation case",
            "urgency": "urgent",
            "reason": "Validate governed referral intake",
        })
        assert referral.status_code == 200, referral.text
        episode = referral.json()["episode"]
        assert episode["phase"] == "referral_received"

        legacy = client.post("/api/episodes/EP-V9-001/transition", headers=clinician, json={"target_state": "triage"})
        assert legacy.status_code == 410, legacy.text
        assert "/api/v9/episodes/" in legacy.json()["replacement"]

        triage = transition(client, clinician, "EP-V9-001", episode["version"], "triage", "v9-triage")
        assert triage.status_code == 200, triage.text
        assert triage.json()["ok"] is True
        triage_replay = transition(client, clinician, "EP-V9-001", episode["version"], "triage", "v9-triage")
        assert triage_replay.status_code == 200, triage_replay.text
        assert triage_replay.json()["commandRef"] == triage.json()["commandRef"]
        episode = triage.json()["episode"]

        blocked_consult = transition(client, clinician, "EP-V9-001", episode["version"], "consult", "v9-consult-blocked")
        assert blocked_consult.status_code == 200, blocked_consult.text
        assert blocked_consult.json()["ok"] is False
        assert any(item["code"] == "referral_acceptance" for item in blocked_consult.json()["guard"]["blockers"])

        accepted = client.patch("/api/v9/referrals/REF-V9-001", headers=clinician, json={
            "expected_version": 1,
            "status": "accepted",
            "reason": "Referral clinically appropriate and capacity confirmed",
        })
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["referral"]["status"] == "accepted"

        consult = transition(client, clinician, "EP-V9-001", episode["version"], "consult", "v9-consult")
        assert consult.status_code == 200 and consult.json()["ok"] is True, consult.text
        episode = consult.json()["episode"]

        no_consent = transition(client, clinician, "EP-V9-001", episode["version"], "admitted", "v9-admit-blocked")
        assert no_consent.status_code == 200 and no_consent.json()["ok"] is False, no_consent.text
        assert any(item["code"] == "consent" for item in no_consent.json()["guard"]["blockers"])

        consent = client.post("/api/v9/episodes/EP-V9-001/consents", headers=clinician, json={
            "owner_ref": "OWN-V9-001",
            "consent_type": "admission",
            "scope": {"admission": True, "initialTreatment": True},
            "maximum_authorised_pence": 350000,
            "currency": "GBP",
            "decision_maker_name": "Synthetic Owner",
            "captured_channel": "telephone",
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "reason": "Owner identity, authority, scope and financial limit confirmed",
        })
        assert consent.status_code == 200, consent.text
        assert consent.json()["consent"]["maximum_authorised_pence"] == 350000

        admitted = transition(client, clinician, "EP-V9-001", episode["version"], "admitted", "v9-admitted")
        assert admitted.status_code == 200 and admitted.json()["ok"] is True, admitted.text
        episode = admitted.json()["episode"]

        with Session(engine) as session:
            session.add(InpatientCarePlanV8(
                care_plan_ref="CARE-V9-001", patient_ref="PAT-V9-001", episode_ref="EP-V9-001",
                area_ref="ward-dog-1", acuity="high", goals=[{"goal": "neurological stability"}],
                interventions=[{"action": "serial neuro observations"}], responsible_nurse_subject="local-user:2",
            ))
            session.commit()

        handover = client.post("/api/v9/episodes/EP-V9-001/handovers", headers=clinician, json={
            "to_role": "nurse",
            "to_subject": "local-user:2",
            "to_area_ref": "ward-dog-1",
            "priority": "amber",
            "situation": "Admitted neurology patient transferring to ward",
            "background": "Progressive paresis; owner consent recorded",
            "assessment": "Stable for ward admission",
            "recommendation": "Serial neurological observations and escalation for deterioration",
            "risks": [{"risk": "neurological deterioration", "severity": "amber"}],
            "pending_actions": [{"action": "repeat neuro score", "dueMinutes": 30}],
            "reason": "Accountable clinical-to-nursing transfer",
        })
        assert handover.status_code == 200, handover.text
        handover_row = handover.json()["handover"]
        acknowledged = client.patch(f"/api/v9/handovers/{handover_row['handover_ref']}/acknowledge", headers=nurse, json={
            "expected_version": handover_row["version"],
            "reason": "Receiving nurse reviewed situation, risks and pending actions",
        })
        assert acknowledged.status_code == 200, acknowledged.text
        episode = acknowledged.json()["episode"]
        assert episode["owner_role"] == "nurse"

        ward = transition(client, nurse, "EP-V9-001", episode["version"], "ward", "v9-ward")
        assert ward.status_code == 200 and ward.json()["ok"] is True, ward.text
        episode = ward.json()["episode"]

        discharge_blocked = transition(client, clinician, "EP-V9-001", episode["version"], "discharge_ready", "v9-discharge-ready-blocked")
        assert discharge_blocked.status_code == 200 and discharge_blocked.json()["ok"] is False, discharge_blocked.text
        codes = {item["code"] for item in discharge_blocked.json()["guard"]["blockers"]}
        assert "active_inpatient_plan" in codes and "discharge_document" in codes and "owner_communication" in codes

        with Session(engine) as session:
            plan = session.exec(select(InpatientCarePlanV8).where(InpatientCarePlanV8.care_plan_ref == "CARE-V9-001")).one()
            plan.status = "completed"
            plan.version += 1
            session.add(plan)
            session.add_all([
                ClinicalDocumentV8(
                    document_ref="DOC-V9-DISCHARGE", patient_ref="PAT-V9-001", episode_ref="EP-V9-001",
                    document_type="discharge_summary", title="Synthetic discharge summary", content="Complete synthetic discharge record",
                    status="approved", author_subject="local-user:3", approved_by_subject="local-user:3",
                ),
                CommunicationEventV8(
                    communication_ref="COMM-V9-OWNER", patient_ref="PAT-V9-001", episode_ref="EP-V9-001",
                    owner_ref="OWN-V9-001", audience="owner", channel="telephone", direction="outbound",
                    subject="Discharge discussion", summary="Care, medicines, warnings and follow-up discussed",
                    outcome="owner understood", actor_subject="local-user:3",
                ),
                CommunicationEventV8(
                    communication_ref="COMM-V9-REFERRER", patient_ref="PAT-V9-001", episode_ref="EP-V9-001",
                    audience="referring_vet", channel="secure_email", direction="outbound",
                    subject="Referral outcome", summary="Discharge summary issued to referring practice",
                    outcome="sent", actor_subject="local-user:3",
                ),
            ])
            session.commit()

        discharge_ready = transition(client, clinician, "EP-V9-001", episode["version"], "discharge_ready", "v9-discharge-ready")
        assert discharge_ready.status_code == 200 and discharge_ready.json()["ok"] is True, discharge_ready.text
        episode = discharge_ready.json()["episode"]

        with Session(engine) as session:
            document = session.exec(select(ClinicalDocumentV8).where(ClinicalDocumentV8.document_ref == "DOC-V9-DISCHARGE")).one()
            document.status = "sent"
            document.sent_at = datetime.now(timezone.utc)
            document.version += 1
            session.add(document)
            session.commit()

        discharge_without_handover = transition(client, admin, "EP-V9-001", episode["version"], "discharged", "v9-discharged-blocked")
        assert discharge_without_handover.status_code == 200 and discharge_without_handover.json()["ok"] is False, discharge_without_handover.text
        assert any(item["code"] == "handover" for item in discharge_without_handover.json()["guard"]["blockers"])

        waiver = client.post("/api/v9/episodes/EP-V9-001/checkpoints", headers=director, json={
            "checkpoint_code": "handover",
            "status": "waived",
            "detail": {"emergencyDischarge": False, "reason": "same clinician completing owner transfer"},
            "reason": "Senior-approved same-operator discharge handover exception",
            "valid_until": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        })
        assert waiver.status_code == 200, waiver.text

        discharged = transition(client, admin, "EP-V9-001", episode["version"], "discharged", "v9-discharged")
        assert discharged.status_code == 200 and discharged.json()["ok"] is True, discharged.text
        assert any(item["code"] == "handover" and item.get("waivedByCheckpoint") for item in discharged.json()["guard"]["warnings"])
        episode = discharged.json()["episode"]

        closure = client.post("/api/v9/episodes/EP-V9-001/closure", headers=ops, json={
            "disposition": "discharged_home",
            "discharge_document_ref": "DOC-V9-DISCHARGE",
            "owner_communication_ref": "COMM-V9-OWNER",
            "referrer_communication_ref": "COMM-V9-REFERRER",
            "financial_status": "settled",
            "outstanding_actions": [],
            "retained_risks": [{"risk": "neurological relapse", "mitigation": "owner warning signs and referring-vet follow-up"}],
            "reason": "Prepare complete episode closure record",
        })
        assert closure.status_code == 200, closure.text
        closure_row = closure.json()["closure"]
        approved = client.patch(f"/api/v9/closures/{closure_row['closure_ref']}/approve", headers=director, json={
            "expected_version": closure_row["version"],
            "reason": "Clinical, communication and financial closure evidence reviewed",
        })
        assert approved.status_code == 200, approved.text
        assert approved.json()["closure"]["status"] == "approved"

        stale = transition(client, admin, "EP-V9-001", episode["version"] - 1, "closed", "v9-close-stale")
        assert stale.status_code == 409, stale.text

        closed = transition(client, admin, "EP-V9-001", episode["version"], "closed", "v9-closed")
        assert closed.status_code == 200 and closed.json()["ok"] is True, closed.text
        assert closed.json()["episode"]["status"] == "closed"

        view = client.get("/api/v9/episodes/EP-V9-001/command-view", headers=director)
        assert view.status_code == 200, view.text
        body = view.json()
        assert body["episode"]["phase"] == "closed"
        assert body["referral"]["status"] == "accepted"
        assert body["consents"]
        assert any(row["status"] == "acknowledged" for row in body["handovers"])
        assert body["closure"]["status"] == "completed"
        assert len(body["transitions"]) >= 7

        with Session(engine) as session:
            assert session.exec(select(ReferralIntakeV9)).all()
            assert session.exec(select(EpisodeHandoverV9)).all()
            closure_db = session.exec(select(EpisodeClosureV9).where(EpisodeClosureV9.episode_ref == "EP-V9-001")).one()
            assert closure_db.status == "completed"
            canonical = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == "EP-V9-001")).one()
            assert canonical.phase == "closed" and canonical.version >= 8

        print("Canonical referral, consent, handover, discharge and closure command spine v9 OK")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
