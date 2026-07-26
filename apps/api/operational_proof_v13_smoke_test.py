from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_operational_proof_v13_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_JWT_SECRET": "operational-proof-v13-secret-that-is-long-and-private",
    "AUTH_ISSUER": "lucyworks-operational-proof-v13",
    "AUTH_AUDIENCE": "lucyworks-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.auth import issue_local_token
from app.database import engine
from app.detailed_hospital_models import ClinicalDocumentV8, CommunicationEventV8, InpatientCarePlanV8
from app.hospital_command_models import EpisodeClosureV9
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock
from app.main import app
from app.models import AuditEvent, WorkItem

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def auth_headers(user_id: int, name: str, role: str) -> dict[str, str]:
    token, _ = issue_local_token(
        user_id=user_id,
        name=name,
        role=role,
        email=f"{role}-{user_id}@example.test",
    )
    return {"Authorization": f"Bearer {token}"}


def transition(client: TestClient, auth: dict[str, str], episode_ref: str, version: int, target: str, key: str):
    return client.post(
        f"/api/v9/episodes/{episode_ref}/transition",
        headers=auth,
        json={
            "expected_version": version,
            "target_phase": target,
            "idempotency_key": key,
            "reason": f"Operational proof transition to {target}",
        },
    )


ops = auth_headers(201, "Operational Proof Ops", "ops_manager")
admin = auth_headers(202, "Operational Proof Admin", "admin")
clinician = auth_headers(203, "Operational Proof Clinician", "clinical_director")
nurse = auth_headers(204, "Operational Proof Nurse", "nurse")

referral_payload = {
    "premisesRef": "default-premises",
    "patientName": "Operational Bramble",
    "species": "dog",
    "breed": "Labrador",
    "sex": "female",
    "dateOfBirth": "2020-04-10",
    "microchipNumber": "985141000000013",
    "ownerName": "Operational Owner",
    "ownerEmail": "operational-owner@example.test",
    "ownerPhone": "07000000013",
    "decisionAuthority": True,
    "financialResponsibility": True,
    "sourceType": "referring_vet",
    "sourceOrganisation": "Operational Referring Practice",
    "sourceContactName": "Operational Referring Vet",
    "sourceContactEmail": "referrer@example.test",
    "requestedService": "MRI neurology",
    "presentingProblem": "Acute paralysis and severe pain",
    "clinicalSummary": "Unable to walk since this morning",
    "urgency": "urgent",
    "documents": [{
        "documentType": "referral_letter",
        "filename": "operational-referral.pdf",
        "mimeType": "application/pdf",
        "storageRef": "synthetic://operational-proof/referral",
        "checksumSha256": "b" * 64,
        "sourceSystem": "synthetic_pims",
    }],
    "reason": "Connected v13 referral-to-closure operational proof",
}

try:
    with TestClient(app) as client:
        intake_response = client.post("/api/v12/referrals/intake", headers=admin, json=referral_payload)
        assert intake_response.status_code == 200, intake_response.text
        intake = intake_response.json()
        assert intake["requiresIdentityReview"] is False
        patient_ref = intake["patient"]["patient_ref"]
        owner_ref = intake["owner"]["owner_ref"]
        referral_ref = intake["referral"]["referral_ref"]
        episode_ref = intake["episode"]["episode_ref"]
        triage = intake["triage"]
        assert intake["documents"][0]["checksum_sha256"] == "b" * 64
        print("v12 identity, authority, referral, episode, triage and document intake OK")

        triage_response = client.patch(
            f"/api/v12/triage/{triage['triage_ref']}",
            headers=clinician,
            json={
                "expectedVersion": triage["version"],
                "status": "acknowledged",
                "assignedSubject": "local-user:203",
                "rationale": "Urgent neurology referral reviewed",
                "reason": "Clinician accepted triage responsibility",
            },
        )
        assert triage_response.status_code == 200, triage_response.text
        assert triage_response.json()["triage"]["status"] == "acknowledged"

        decision_response = client.patch(
            f"/api/v12/referrals/{referral_ref}/decision",
            headers=clinician,
            json={
                "expectedVersion": 1,
                "status": "accepted",
                "reason": "Referral accepted for MRI and neurology assessment",
                "proposedDurationMinutes": 90,
            },
        )
        assert decision_response.status_code == 200, decision_response.text
        decision = decision_response.json()
        episode = decision["episode"]
        proposed_block = decision["proposedBlock"]
        assert decision["referral"]["status"] == "accepted"
        assert proposed_block["status"] == "proposed"
        assert proposed_block["areaRef"] == "mri"
        assert proposed_block["gates"]["consent"] == "pending"
        print("v12 clinical acceptance and canonical 15-minute board proposal OK")

        board_response = client.get(
            "/api/v11/master-board/day",
            headers=ops,
            params={
                "premises_ref": "default-premises",
                "operational_date": proposed_block["operationalDate"],
            },
        )
        assert board_response.status_code == 200, board_response.text
        board = board_response.json()
        assert board["boardVersion"] == "v11"
        assert any(block["episodeRef"] == episode_ref for block in board["blocks"])
        print("Accepted referral visible on the hospital master board OK")

        capture_response = client.post(
            "/api/input/capture",
            headers=ops,
            json={
                "title": "MRI owner update required",
                "description": "Confirm arrival instructions and expected MRI timing with the owner.",
                "section_name": "Imaging",
                "room_name": "MRI",
                "urgency": "amber",
                "owner_role": "ops_manager",
                "linked_patient_name": "Operational Bramble",
                "linked_episode_ref": episode_ref,
                "actor_name": "Spoofed mobile actor",
            },
        )
        assert capture_response.status_code == 200, capture_response.text
        work_item_id = capture_response.json()["work_item"]["id"]
        queue_response = client.get("/api/role-queues/manager", headers=ops)
        assert queue_response.status_code == 200, queue_response.text
        assert any(item["id"] == work_item_id for item in queue_response.json()["work_items"])
        print("Authenticated phone capture propagated into the manager queue OK")

        triage_phase = transition(client, clinician, episode_ref, episode["version"], "triage", "v13-triage")
        assert triage_phase.status_code == 200 and triage_phase.json()["ok"] is True, triage_phase.text
        episode = triage_phase.json()["episode"]

        consult_phase = transition(client, clinician, episode_ref, episode["version"], "consult", "v13-consult")
        assert consult_phase.status_code == 200 and consult_phase.json()["ok"] is True, consult_phase.text
        episode = consult_phase.json()["episode"]

        blocked_admission = transition(client, clinician, episode_ref, episode["version"], "admitted", "v13-admit-blocked")
        assert blocked_admission.status_code == 200 and blocked_admission.json()["ok"] is False, blocked_admission.text
        assert any(item["code"] == "consent" for item in blocked_admission.json()["guard"]["blockers"])

        consent_response = client.post(
            f"/api/v9/episodes/{episode_ref}/consents",
            headers=clinician,
            json={
                "owner_ref": owner_ref,
                "consent_type": "admission",
                "scope": {"admission": True, "initialTreatment": True},
                "maximum_authorised_pence": 350000,
                "currency": "GBP",
                "decision_maker_name": "Operational Owner",
                "captured_channel": "telephone",
                "valid_until": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "reason": "Owner identity, authority, scope and financial limit confirmed",
            },
        )
        assert consent_response.status_code == 200, consent_response.text

        admitted = transition(client, clinician, episode_ref, episode["version"], "admitted", "v13-admitted")
        assert admitted.status_code == 200 and admitted.json()["ok"] is True, admitted.text
        episode = admitted.json()["episode"]

        with Session(engine) as session:
            session.add(InpatientCarePlanV8(
                care_plan_ref="CARE-V13-001",
                patient_ref=patient_ref,
                episode_ref=episode_ref,
                area_ref="ward-dog-1",
                acuity="high",
                goals=[{"goal": "neurological stability"}],
                interventions=[{"action": "serial neuro observations"}],
                responsible_nurse_subject="local-user:204",
            ))
            session.commit()

        handover_response = client.post(
            f"/api/v9/episodes/{episode_ref}/handovers",
            headers=clinician,
            json={
                "to_role": "nurse",
                "to_subject": "local-user:204",
                "to_area_ref": "ward-dog-1",
                "priority": "amber",
                "situation": "Admitted neurology patient transferring to ward",
                "background": "Acute paralysis; governed consent recorded",
                "assessment": "Stable for ward admission",
                "recommendation": "Serial neurological observations and escalation for deterioration",
                "risks": [{"risk": "neurological deterioration", "severity": "amber"}],
                "pending_actions": [{"action": "repeat neuro score", "dueMinutes": 30}],
                "reason": "Accountable clinical-to-nursing transfer",
            },
        )
        assert handover_response.status_code == 200, handover_response.text
        handover = handover_response.json()["handover"]
        acknowledge_response = client.patch(
            f"/api/v9/handovers/{handover['handover_ref']}/acknowledge",
            headers=nurse,
            json={
                "expected_version": handover["version"],
                "reason": "Receiving nurse reviewed situation, risks and pending actions",
            },
        )
        assert acknowledge_response.status_code == 200, acknowledge_response.text
        episode = acknowledge_response.json()["episode"]

        ward_phase = transition(client, nurse, episode_ref, episode["version"], "ward", "v13-ward")
        assert ward_phase.status_code == 200 and ward_phase.json()["ok"] is True, ward_phase.text
        episode = ward_phase.json()["episode"]

        blocked_discharge = transition(client, clinician, episode_ref, episode["version"], "discharge_ready", "v13-discharge-ready-blocked")
        assert blocked_discharge.status_code == 200 and blocked_discharge.json()["ok"] is False, blocked_discharge.text
        blocker_codes = {item["code"] for item in blocked_discharge.json()["guard"]["blockers"]}
        assert {"active_inpatient_plan", "discharge_document", "owner_communication"}.issubset(blocker_codes)
        print("Discharge safety gates blocked incomplete care correctly")

        with Session(engine) as session:
            care_plan = session.exec(select(InpatientCarePlanV8).where(InpatientCarePlanV8.care_plan_ref == "CARE-V13-001")).one()
            care_plan.status = "completed"
            care_plan.version += 1
            session.add(care_plan)
            session.add_all([
                ClinicalDocumentV8(
                    document_ref="DOC-V13-DISCHARGE",
                    patient_ref=patient_ref,
                    episode_ref=episode_ref,
                    document_type="discharge_summary",
                    title="Operational discharge summary",
                    content="Complete synthetic discharge record",
                    status="approved",
                    author_subject="local-user:203",
                    approved_by_subject="local-user:203",
                ),
                CommunicationEventV8(
                    communication_ref="COMM-V13-OWNER",
                    patient_ref=patient_ref,
                    episode_ref=episode_ref,
                    owner_ref=owner_ref,
                    audience="owner",
                    channel="telephone",
                    direction="outbound",
                    subject="Discharge discussion",
                    summary="Care, medicines, warnings and follow-up discussed",
                    outcome="owner understood",
                    actor_subject="local-user:203",
                ),
                CommunicationEventV8(
                    communication_ref="COMM-V13-REFERRER",
                    patient_ref=patient_ref,
                    episode_ref=episode_ref,
                    audience="referring_vet",
                    channel="secure_email",
                    direction="outbound",
                    subject="Referral outcome",
                    summary="Discharge summary issued to referring practice",
                    outcome="sent",
                    actor_subject="local-user:203",
                ),
            ])
            session.commit()

        discharge_ready = transition(client, clinician, episode_ref, episode["version"], "discharge_ready", "v13-discharge-ready")
        assert discharge_ready.status_code == 200 and discharge_ready.json()["ok"] is True, discharge_ready.text
        episode = discharge_ready.json()["episode"]

        with Session(engine) as session:
            document = session.exec(select(ClinicalDocumentV8).where(ClinicalDocumentV8.document_ref == "DOC-V13-DISCHARGE")).one()
            document.status = "sent"
            document.sent_at = datetime.now(timezone.utc)
            document.version += 1
            session.add(document)
            session.commit()

        discharge_without_handover = transition(client, admin, episode_ref, episode["version"], "discharged", "v13-discharged-blocked")
        assert discharge_without_handover.status_code == 200 and discharge_without_handover.json()["ok"] is False, discharge_without_handover.text
        assert any(item["code"] == "handover" for item in discharge_without_handover.json()["guard"]["blockers"])

        waiver_response = client.post(
            f"/api/v9/episodes/{episode_ref}/checkpoints",
            headers=clinician,
            json={
                "checkpoint_code": "handover",
                "status": "waived",
                "detail": {"emergencyDischarge": False, "reason": "same clinician completing owner transfer"},
                "reason": "Senior-approved same-operator discharge handover exception",
                "valid_until": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            },
        )
        assert waiver_response.status_code == 200, waiver_response.text

        discharged = transition(client, admin, episode_ref, episode["version"], "discharged", "v13-discharged")
        assert discharged.status_code == 200 and discharged.json()["ok"] is True, discharged.text
        episode = discharged.json()["episode"]

        closure_response = client.post(
            f"/api/v9/episodes/{episode_ref}/closure",
            headers=ops,
            json={
                "disposition": "discharged_home",
                "discharge_document_ref": "DOC-V13-DISCHARGE",
                "owner_communication_ref": "COMM-V13-OWNER",
                "referrer_communication_ref": "COMM-V13-REFERRER",
                "financial_status": "settled",
                "outstanding_actions": [],
                "retained_risks": [{
                    "risk": "neurological relapse",
                    "mitigation": "owner warning signs and referring-vet follow-up",
                }],
                "reason": "Prepare complete episode closure record",
            },
        )
        assert closure_response.status_code == 200, closure_response.text
        closure = closure_response.json()["closure"]

        approve_response = client.patch(
            f"/api/v9/closures/{closure['closure_ref']}/approve",
            headers=clinician,
            json={
                "expected_version": closure["version"],
                "reason": "Clinical, communication and financial closure evidence reviewed",
            },
        )
        assert approve_response.status_code == 200, approve_response.text

        stale_close = transition(client, admin, episode_ref, episode["version"] - 1, "closed", "v13-close-stale")
        assert stale_close.status_code == 409, stale_close.text

        closed_response = transition(client, admin, episode_ref, episode["version"], "closed", "v13-closed")
        assert closed_response.status_code == 200 and closed_response.json()["ok"] is True, closed_response.text
        assert closed_response.json()["episode"]["status"] == "closed"

        command_view_response = client.get(f"/api/v9/episodes/{episode_ref}/command-view", headers=clinician)
        assert command_view_response.status_code == 200, command_view_response.text
        command_view = command_view_response.json()
        assert command_view["episode"]["phase"] == "closed"
        assert command_view["referral"]["status"] == "accepted"
        assert command_view["consents"]
        assert command_view["closure"]["status"] == "completed"
        assert len(command_view["transitions"]) >= 7

        integrity_response = client.get("/api/evidence/integrity", headers=ops)
        assert integrity_response.status_code == 200, integrity_response.text
        assert integrity_response.json()["ok"] is True

        with Session(engine) as session:
            work_item = session.get(WorkItem, work_item_id)
            assert work_item is not None and work_item.linked_episode_ref == episode_ref
            audit = session.exec(select(AuditEvent).where(AuditEvent.entity_type == "work_item", AuditEvent.entity_id == work_item_id)).one()
            assert audit.actor_name == "Operational Proof Ops"
            assert audit.actor_name != "Spoofed mobile actor"
            canonical = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).one()
            assert canonical.phase == "closed" and canonical.status == "closed"
            closure_db = session.exec(select(EpisodeClosureV9).where(EpisodeClosureV9.episode_ref == episode_ref)).one()
            assert closure_db.status == "completed"
            block = session.exec(select(OperationalBlock).where(OperationalBlock.episode_ref == episode_ref)).one()
            assert block.area_ref == "mri" and block.status == "proposed"

        print("Connected referral intake, board, queue, consent, ward, discharge and closure journey OK")
        print("\n--- OPERATIONAL PROOF V13 SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
