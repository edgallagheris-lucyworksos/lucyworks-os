import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_safety_v25_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "cross-system-safety-v25-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-safety-v25-smoke",
    "AUTH_AUDIENCE": "lucyworks-safety-v25-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.database import engine
from app.evidence_event_models import EvidenceEvent
from app.evidence_service import verify_event_chain
from app.hr_models import OnCallAssignment, OvertimeRequest
from app.models import Shift, StaffMember, User
from app.patient_care_models import PatientCase, PatientWorkflowEvent, ReferralEpisode
from app.safety_control_v25_models import (
    SafetyAccessEventV25,
    SafetyActionV25,
    SafetyDecisionV25,
    SafetyEscalationV25,
    SafetyLinkV25,
    SafetyRecordV25,
)
from app.clinical_execution_models import MedicationAdministration, MedicationOrder
from app.hospital_command_models import EpisodeClosureV9, EpisodeTransitionV9
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

NOW = datetime.now(timezone.utc)
with Session(engine) as session:
    users = [
        User(id=1401, name="V25 Reporting Nurse", role="nurse", email="reporter-v25@example.test"),
        User(id=1402, name="V25 Conflicted Manager", role="ops_manager", email="conflict-v25@example.test"),
        User(id=1403, name="V25 Governance", role="governance_lead", email="governance-v25@example.test"),
        User(id=1404, name="V25 Clinician", role="clinical_director", email="clinician-v25@example.test"),
        User(id=1405, name="V25 Independent Director", role="hospital_director", email="director-v25@example.test"),
        User(id=1406, name="V25 Unrelated Nurse", role="nurse", email="other-v25@example.test"),
    ]
    session.add_all(users)
    staff = StaffMember(id=2401, user_id=1404, name="V25 Clinician", role="clinical_director", skills="neurology, anaesthesia", active=True)
    session.add(staff)
    session.add(Shift(id=3401, staff_member_id=2401, department="Neurology", starts_at=NOW - timedelta(hours=68), ends_at=NOW - timedelta(hours=8), status="completed"))
    for index in range(3):
        session.add(OnCallAssignment(staff_member_id=2401, department="Neurology", starts_at=NOW - timedelta(hours=60 - index * 12), ends_at=NOW - timedelta(hours=48 - index * 12)))
    session.add(OvertimeRequest(staff_member_id=2401, hours=13, reason="Emergency cover", status="approved"))
    session.add(PatientCase(id="case-v25", patient_name="Bramble Safety", species="dog", owner_name="Owner V25", referral_reason="Neurology referral"))
    session.add(ReferralEpisode(id="episode-v25", patient_case_id="case-v25", episode_ref="EP-V25", stage="procedure", owner_role="nurse", owner_name="V25 Reporting Nurse", current_location="MRI prep", next_action="confirm anaesthesia cover"))
    session.commit()


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    token = response.json().get("accessToken")
    assert token
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def ok(response, label: str):
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    return response.json()


try:
    with TestClient(app) as client:
        reporter = login(client, 1401)
        conflicted = login(client, 1402)
        governance = login(client, 1403)
        clinician = login(client, 1404)
        director = login(client, 1405)
        unrelated = login(client, 1406)

        contracts = ok(client.get("/api/v25/safety/contracts", headers=reporter), "load safety contracts")
        assert "bullying" in contracts["recordTypes"]
        assert any("does not diagnose" in line for line in contracts["principles"])

        conduct = ok(client.post(
            "/api/v25/safety/records",
            headers=reporter,
            json={
                "recordType": "bullying",
                "domain": "mixed",
                "confidentiality": "standard",
                "severity": "red",
                "title": "Unsafe management pressure affecting patient cover",
                "summary": "A manager pressured staff to continue an unsafe list despite missing competent cover.",
                "description": "Reporter requests independent review and protection from retaliation.",
                "patientRef": "case-v25",
                "episodeRef": "episode-v25",
                "affectedStaffSubject": "local-user:1401",
                "affectedStaffName": "V25 Reporting Nurse",
                "conflictSubjects": ["local-user:1402"],
                "safetyHoldRequested": True,
                "protectiveSummary": "The affected clinical list requires independent safe-cover review.",
                "operationalImpact": {"service": "MRI", "requiresCoverageReview": True},
            },
        ), "create strict mixed concern")
        conduct_ref = conduct["record"]["recordRef"]
        assert conduct["record"]["confidentiality"] == "strict"
        assert conduct["record"]["status"] == "protective_action"

        hidden = client.get(f"/api/v25/safety/records/{conduct_ref}", headers=conflicted)
        assert hidden.status_code == 404, hidden.text
        unrelated_list = ok(client.get("/api/v25/safety/records", headers=unrelated), "list unrelated safety records")
        assert not any(item["recordRef"] == conduct_ref for item in unrelated_list["records"])

        board = ok(client.get("/api/v25/safety/board-indicators", headers=unrelated), "load board-safe indicators")
        indicator = next(item for item in board["indicators"] if item["recordRef"] == conduct_ref)
        assert indicator["title"] == "Restricted safety matter"
        assert "manager pressured" not in indicator["summary"].lower()
        assert indicator["summary"] == "The affected clinical list requires independent safe-cover review."

        assigned = ok(client.post(
            f"/api/v25/safety/records/{conduct_ref}/owners",
            headers=governance,
            json={
                "expectedVersion": conduct["record"]["version"],
                "owners": {
                    "accountable": {"subject": "local-user:1403", "name": "V25 Governance", "role": "governance_lead"},
                    "clinical": {"subject": "local-user:1404", "name": "V25 Clinician", "role": "clinical_director"},
                    "independent": {"subject": "local-user:1405", "name": "V25 Independent Director", "role": "hospital_director"},
                },
                "reason": "Assign independent operational, clinical and closure ownership.",
            },
        ), "assign non-conflicted owners")
        assert assigned["record"]["accountableOwner"]["subject"] == "local-user:1403"

        conflicted_assignment = client.post(
            f"/api/v25/safety/records/{conduct_ref}/owners",
            headers=governance,
            json={
                "expectedVersion": assigned["record"]["version"],
                "owners": {"accountable": {"subject": "local-user:1402", "name": "V25 Conflicted Manager", "role": "ops_manager"}},
                "reason": "Attempt conflicted assignment.",
            },
        )
        assert conflicted_assignment.status_code == 409, conflicted_assignment.text

        action = ok(client.post(
            f"/api/v25/safety/records/{conduct_ref}/actions",
            headers=governance,
            json={
                "actionType": "protective",
                "title": "Remove conflicted manager from safe-cover decision",
                "description": "Independent operations lead controls cover and communications while the concern is investigated.",
                "owner": {"subject": "local-user:1403", "name": "V25 Governance", "role": "governance_lead"},
                "requiresIndependentVerification": True,
            },
        ), "create protective action")["action"]
        completed = ok(client.patch(
            f"/api/v25/safety/records/{conduct_ref}/actions/{action['actionRef']}/complete",
            headers=governance,
            json={"expectedVersion": action["version"], "completionEvidence": "Rota authority transferred and affected staff informed without disclosing allegation details."},
        ), "complete protective action")["action"]
        assert completed["verificationStatus"] == "pending"
        verified = ok(client.patch(
            f"/api/v25/safety/records/{conduct_ref}/actions/{action['actionRef']}/verify",
            headers=director,
            json={"expectedVersion": completed["version"], "decision": "verified", "note": "Independent check confirms the conflicted manager no longer controls the affected list."},
        ), "verify protective action")["action"]
        assert verified["verificationStatus"] == "verified"

        review = ok(client.post(
            f"/api/v25/safety/records/{conduct_ref}/closure-review",
            headers=director,
            json={
                "decision": "approved",
                "reason": "Independent review confirms immediate protection, investigation findings and recurrence controls are evidenced.",
                "rootCause": "No protected escalation route separated staff-conduct concerns from operational rota authority.",
                "recurrenceControls": [
                    "Strict confidential staff-concern route with line-manager bypass",
                    "Independent safe-cover owner whenever a named conflict exists",
                ],
            },
        ), "independent closure review")
        assert review["closureGate"]["eligible"]
        closed = ok(client.post(
            f"/api/v25/safety/records/{conduct_ref}/close",
            headers=governance,
            json={
                "expectedVersion": review["record"]["version"],
                "rootCause": review["record"]["rootCause"],
                "recurrenceControls": review["record"]["recurrenceControls"],
                "reason": "All protective actions are independently verified and recurrence controls are assigned.",
            },
        ), "close mixed concern")
        assert closed["record"]["status"] == "closed"

        blocked = ok(client.patch(
            "/api/patient-care/episodes/episode-v25/state",
            headers=reporter,
            json={
                "blocker": "missing anaesthesia cover",
                "status": "blocked",
                "nextAction": "senior clinician and operations review safe cover",
                "actor": "Spoofed Browser User",
                "note": "Anaesthesia competency and safe cover are not confirmed.",
            },
        ), "bridge patient blocker")
        assert blocked["event"]["actor"] == "V25 Reporting Nurse"
        assert blocked["safetyRecord"]["recordType"] == "patient_safety"
        assert blocked["safetyRecord"]["safetyHoldRequested"] is True

        fatigue = ok(client.post("/api/hr/fatigue/evaluate/2401", headers=governance), "bridge fatigue risk")
        assert fatigue["risk"]["riskLevel"] == "HIGH"
        all_visible = ok(client.get("/api/v25/safety/records", headers=governance), "list governance records")
        fatigue_record = next(item for item in all_visible["records"] if item["sourceModule"] == "hr-fatigue")
        assert fatigue_record["confidentiality"] == "restricted"
        assert fatigue_record["operationalImpact"]["requiresCoverageReview"] is True

        handover = ok(client.post(
            "/api/control-plane/handovers",
            headers=reporter,
            json={
                "handoverRef": "HANDOVER-V25",
                "patientCaseId": "case-v25",
                "referralEpisodeId": "episode-v25",
                "fromActor": "Spoofed Sender",
                "fromRole": "admin",
                "toActor": "V25 Clinician",
                "toRole": "clinical_director",
                "summary": "MRI patient requires anaesthesia and critical-result follow-up.",
                "clinicalRisks": ["Anaesthesia cover not confirmed", "Critical result follow-up remains open"],
                "outstandingActions": ["Confirm safe cover", "Review diagnostic result"],
            },
        ), "create risk-bearing handover")
        assert handover["handover"]["fromActor"] == "V25 Reporting Nurse"
        assert handover["safetyRecord"]["severity"] == "red"
        accepted = ok(client.patch(
            f"/api/control-plane/handovers/{handover['handover']['id']}/decision",
            headers=clinician,
            json={"decision": "accepted", "decidedBy": "Spoofed Recipient", "decidedByRole": "admin", "note": "Clinical director accepts responsibility and outstanding risks."},
        ), "accept handover")
        assert accepted["handover"]["acceptedBy"] == "V25 Clinician"

        critical = ok(client.post(
            "/api/control-plane/critical-results",
            headers=clinician,
            json={
                "resultRef": "RESULT-V25",
                "patientCaseId": "case-v25",
                "referralEpisodeId": "episode-v25",
                "resultType": "MRI",
                "severity": "red",
                "summary": "Imaging finding requires immediate named clinical review.",
                "assignedTo": "local-user:1404",
                "assignedRole": "clinical_director",
                "createdBy": "Spoofed Integration",
            },
        ), "create critical result")
        assert critical["result"]["status"] == "awaiting_acknowledgement"
        acknowledged = ok(client.patch(
            f"/api/control-plane/critical-results/{critical['result']['id']}/acknowledge",
            headers=clinician,
            json={
                "acknowledgedBy": "Spoofed Clinician",
                "acknowledgedByRole": "admin",
                "actionTaken": "Patient reviewed and an authorised clinical plan recorded in the clinical record.",
                "note": "Clinical director reviewed the result and recorded the human decision separately.",
            },
        ), "acknowledge critical result")
        assert acknowledged["result"]["acknowledgedBy"] == "V25 Clinician"
        assert acknowledged["action"]["verificationStatus"] == "pending"
        assert acknowledged["safetyRecord"]["status"] != "closed"

        governance_view = ok(client.get(f"/api/v25/safety/records/{conduct_ref}?reason=Governance%20audit", headers=governance), "read strict record")
        assert governance_view["record"]["recordRef"] == conduct_ref

    with Session(engine) as session:
        assert session.exec(select(SafetyRecordV25)).all()
        assert session.exec(select(SafetyActionV25)).all()
        assert session.exec(select(SafetyDecisionV25)).all()
        assert session.exec(select(SafetyLinkV25)).all()
        assert session.exec(select(SafetyAccessEventV25)).all()
        workflow_event = session.exec(select(PatientWorkflowEvent).where(PatientWorkflowEvent.episode_id == "episode-v25").order_by(PatientWorkflowEvent.created_at.desc())).first()
        assert workflow_event and workflow_event.actor == "V25 Reporting Nurse"
        spoofed_evidence = session.exec(select(EvidenceEvent).where(EvidenceEvent.actor_name.like("Spoofed%"))).all()
        assert not spoofed_evidence, spoofed_evidence
        assert session.exec(select(MedicationOrder)).all() == []
        assert session.exec(select(MedicationAdministration)).all() == []
        assert session.exec(select(EpisodeTransitionV9)).all() == []
        assert session.exec(select(EpisodeClosureV9)).all() == []
        integrity = verify_event_chain(session)
        assert integrity["valid"], integrity

    print("CROSS_SYSTEM_SAFETY_CONTROL_V25_SMOKE_PASSED")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
