import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_operational_proof_v30_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "operational-proof-v30-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-v30",
    "AUTH_AUDIENCE": "lucyworks-v30-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
    "V26_CONTEXT_BOOTSTRAP_ENABLED": "false",
    "V27_CONFIGURATION_REQUIRED": "false",
    "V28_CONNECTION_CONTROL_REQUIRED": "false",
    "V29_PILOT_CONTROL_REQUIRED": "false",
    "V30_OPERATIONAL_PROOF_REQUIRED": "false",
})

from fastapi.testclient import TestClient
from sqlalchemy import text
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
from app.evidence_service import verify_event_chain
from app.hospital_ops_models import OperationalArea, OperationalBlock, OperationalConflict
from app.hospital_ops_service import detect_constraints
from app.main import app
from app.models import ResultReview, StaffMember, User, WorkItem
from app.referral_identity_v12_models import IdentityMatchReviewV12, ReferralIdentityIntakeV12

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)
with engine.begin() as connection:
    connection.execute(text("create table if not exists alembic_version (version_num varchar(64) not null)"))
    connection.execute(text("delete from alembic_version"))
    connection.execute(text("insert into alembic_version(version_num) values ('0024_operational_proof_v30')"))


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    token = response.json().get("accessToken")
    assert token
    return {"Authorization": f"Bearer {token}"}


def ok(response, label: str):
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    return response.json()


def transition(client: TestClient, auth: dict[str, str], episode_ref: str, version: int, target: str, key: str):
    return client.post(
        f"/api/v9/episodes/{episode_ref}/transition",
        headers=auth,
        json={
            "expected_version": version,
            "target_phase": target,
            "idempotency_key": key,
            "reason": f"Operational proof v30 transition to {target}",
        },
    )


try:
    with Session(engine) as session:
        session.add_all([
            User(id=3001, name="V30 Operations Manager", role="ops_manager", email="v30-ops@example.test"),
            User(id=3002, name="V30 Ward Nurse", role="nurse", email="v30-nurse@example.test"),
            User(id=3003, name="V30 Clinician", role="clinician", email="v30-clinician@example.test"),
            User(id=3004, name="V30 Clinical Director", role="clinical_director", email="v30-director@example.test"),
            User(id=3005, name="V30 Administrator", role="admin", email="v30-admin@example.test"),
            PatientClinicalRecordV8(
                patient_ref="PAT-V30-001",
                display_name="Synthetic Border Collie",
                species="dog",
                breed="Border Collie",
            ),
            OwnerAccountV8(
                owner_ref="OWN-V30-001",
                display_name="Synthetic Owner",
                email="owner-v30@example.test",
                identity_verified=True,
            ),
            PatientOwnerLinkV8(
                link_ref="LINK-V30-001",
                patient_ref="PAT-V30-001",
                owner_ref="OWN-V30-001",
                relationship="registered_owner",
                decision_authority=True,
                financial_responsibility=True,
            ),
        ])
        session.commit()

    with TestClient(app) as client:
        ops = login(client, 3001)
        nurse = login(client, 3002)
        clinician = login(client, 3003)
        director = login(client, 3004)
        admin = login(client, 3005)

        proof = ok(client.post("/api/v30/operational-proof/runs", headers=ops, json={
            "organisationRef": "group-v30",
            "siteRef": "hospital-v30",
            "premisesRef": "premises-v30",
            "operationalDate": date.today().isoformat(),
            "mode": "synthetic",
            "reason": "Run the connected referral-to-discharge operational proof.",
        }), "create proof run")["run"]
        run_ref = proof["run_ref"]

        referral = ok(client.post("/api/v9/referrals", headers=ops, json={
            "episode_ref": "EP-V30-001",
            "referral_ref": "REF-V30-001",
            "patient_ref": "PAT-V30-001",
            "premises_ref": "premises-v30",
            "source_type": "referring_vet",
            "source_organisation": "Synthetic Primary Care",
            "requested_service": "neurology",
            "presenting_problem": "Progressive paraparesis",
            "clinical_summary": "Synthetic connected hospital proof",
            "urgency": "urgent",
            "reason": "Create governed synthetic referral for operational proof.",
        }), "create referral")
        episode = referral["episode"]

        proof = ok(client.post(
            f"/api/v30/operational-proof/runs/{run_ref}/attach-episode",
            headers=ops,
            json={
                "expectedVersion": proof["version"],
                "episodeRef": "EP-V30-001",
                "patientRef": "PAT-V30-001",
                "reason": "Bind proof evidence to the canonical patient and episode.",
            },
        ), "attach episode")["run"]

        triage = transition(client, clinician, "EP-V30-001", episode["version"], "triage", "v30-triage")
        assert triage.status_code == 200 and triage.json()["ok"] is True, triage.text
        episode = triage.json()["episode"]

        accepted = ok(client.patch("/api/v9/referrals/REF-V30-001", headers=clinician, json={
            "expected_version": 1,
            "status": "accepted",
            "reason": "Referral accepted after clinical and capacity review.",
        }), "accept referral")
        assert accepted["referral"]["status"] == "accepted"

        consult = transition(client, clinician, "EP-V30-001", episode["version"], "consult", "v30-consult")
        assert consult.status_code == 200 and consult.json()["ok"] is True, consult.text
        episode = consult.json()["episode"]

        blocked_admission = transition(client, clinician, "EP-V30-001", episode["version"], "admitted", "v30-admit-blocked")
        assert blocked_admission.status_code == 200 and blocked_admission.json()["ok"] is False
        assert any(item["code"] == "consent" for item in blocked_admission.json()["guard"]["blockers"])

        consent = ok(client.post("/api/v9/episodes/EP-V30-001/consents", headers=clinician, json={
            "owner_ref": "OWN-V30-001",
            "consent_type": "admission",
            "scope": {"admission": True, "initialTreatment": True},
            "maximum_authorised_pence": 400000,
            "currency": "GBP",
            "decision_maker_name": "Synthetic Owner",
            "captured_channel": "telephone",
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "reason": "Owner identity, decision authority, scope and financial ceiling confirmed.",
        }), "capture consent")
        assert consent["consent"]["status"] == "active"

        admitted = transition(client, clinician, "EP-V30-001", episode["version"], "admitted", "v30-admitted")
        assert admitted.status_code == 200 and admitted.json()["ok"] is True, admitted.text
        episode = admitted.json()["episode"]

        with Session(engine) as session:
            session.add(InpatientCarePlanV8(
                care_plan_ref="CARE-V30-001",
                patient_ref="PAT-V30-001",
                episode_ref="EP-V30-001",
                area_ref="ward-v30",
                acuity="high",
                goals=[{"goal": "neurological stability"}],
                interventions=[{"action": "serial neurological observations"}],
                responsible_nurse_subject="local-user:3002",
            ))
            session.commit()

        offered = ok(client.post("/api/v9/episodes/EP-V30-001/handovers", headers=clinician, json={
            "to_role": "nurse",
            "to_subject": "local-user:3002",
            "to_area_ref": "ward-v30",
            "priority": "amber",
            "situation": "Neurology patient transferring to ward.",
            "background": "Referral accepted and admission consent recorded.",
            "assessment": "Stable for ward admission.",
            "recommendation": "Serial observations and escalation for deterioration.",
            "risks": [{"risk": "neurological deterioration", "severity": "amber"}],
            "pending_actions": [{"action": "repeat neurological score", "dueMinutes": 30}],
            "reason": "Create accountable clinical-to-nursing handover.",
        }), "offer nurse handover")["handover"]

        nurse_queue_before = ok(client.get("/api/role-queues/nurse", headers=nurse), "nurse queue before handover")
        assert any(item["episode_ref"] == "EP-V30-001" for item in nurse_queue_before["canonical_episodes"])
        assert any(item["handover_ref"] == offered["handover_ref"] for item in nurse_queue_before["governed_handovers"])

        acknowledged = ok(client.patch(
            f"/api/v9/handovers/{offered['handover_ref']}/acknowledge",
            headers=nurse,
            json={
                "expected_version": offered["version"],
                "reason": "Receiving nurse reviewed the situation, risks and pending actions.",
            },
        ), "acknowledge nurse handover")
        episode = acknowledged["episode"]

        ward = transition(client, nurse, "EP-V30-001", episode["version"], "ward", "v30-ward")
        assert ward.status_code == 200 and ward.json()["ok"] is True, ward.text
        episode = ward.json()["episode"]

        blocked_discharge = transition(client, clinician, "EP-V30-001", episode["version"], "discharge_ready", "v30-discharge-blocked")
        assert blocked_discharge.status_code == 200 and blocked_discharge.json()["ok"] is False
        discharge_codes = {item["code"] for item in blocked_discharge.json()["guard"]["blockers"]}
        assert {"active_inpatient_plan", "discharge_document", "owner_communication"} <= discharge_codes

        stale = transition(client, clinician, "EP-V30-001", episode["version"] - 1, "discharge_ready", "v30-stale")
        assert stale.status_code == 409, stale.text

        admin_handover = ok(client.post("/api/v9/episodes/EP-V30-001/handovers", headers=nurse, json={
            "to_role": "admin",
            "to_subject": "local-user:3005",
            "to_area_ref": "discharge-desk",
            "priority": "amber",
            "situation": "Ward patient approaching discharge.",
            "background": "Clinical discharge checks are being completed.",
            "assessment": "Administrative handover needed before owner departure.",
            "recommendation": "Verify documents and owner communication.",
            "risks": [],
            "pending_actions": [{"action": "confirm sent discharge document"}],
            "reason": "Create accountable nursing-to-admin handover.",
        }), "offer admin handover")["handover"]
        admin_queue_before = ok(client.get("/api/role-queues/admin", headers=admin), "admin queue before handover")
        assert any(item["handover_ref"] == admin_handover["handover_ref"] for item in admin_queue_before["governed_handovers"])
        acknowledged_admin = ok(client.patch(
            f"/api/v9/handovers/{admin_handover['handover_ref']}/acknowledge",
            headers=admin,
            json={
                "expected_version": admin_handover["version"],
                "reason": "Administrator reviewed discharge dependencies.",
            },
        ), "acknowledge admin handover")
        episode = acknowledged_admin["episode"]

        with Session(engine) as session:
            plan = session.exec(select(InpatientCarePlanV8).where(InpatientCarePlanV8.care_plan_ref == "CARE-V30-001")).one()
            plan.status = "completed"
            plan.version += 1
            session.add(plan)
            session.add_all([
                ClinicalDocumentV8(
                    document_ref="DOC-V30-DISCHARGE",
                    patient_ref="PAT-V30-001",
                    episode_ref="EP-V30-001",
                    document_type="discharge_summary",
                    title="Synthetic discharge summary",
                    content="Complete synthetic discharge record.",
                    status="approved",
                    author_subject="local-user:3003",
                    approved_by_subject="local-user:3003",
                ),
                CommunicationEventV8(
                    communication_ref="COMM-V30-OWNER",
                    patient_ref="PAT-V30-001",
                    episode_ref="EP-V30-001",
                    owner_ref="OWN-V30-001",
                    audience="owner",
                    channel="telephone",
                    direction="outbound",
                    subject="Discharge discussion",
                    summary="Care, medicines, warnings and follow-up discussed.",
                    outcome="owner understood",
                    actor_subject="local-user:3003",
                ),
                CommunicationEventV8(
                    communication_ref="COMM-V30-REFERRER",
                    patient_ref="PAT-V30-001",
                    episode_ref="EP-V30-001",
                    audience="referring_vet",
                    channel="secure_email",
                    direction="outbound",
                    subject="Referral outcome",
                    summary="Discharge summary issued to referring practice.",
                    outcome="sent",
                    actor_subject="local-user:3003",
                ),
                ResultReview(
                    episode_id=1,
                    result_type="critical_mri_result",
                    review_owner="clinician",
                    status="pending_review",
                    required_action="Review before discharge.",
                ),
                StaffMember(name="Unavailable Synthetic Surgeon", role="surgeon", skills="neurology,theatre", active=False),
                WorkItem(
                    title="Reassign unavailable theatre clinician",
                    input_type="staff_unavailability",
                    source="operational_proof_v30",
                    category="manager",
                    description="Assigned clinician became unavailable.",
                    urgency="red",
                    owner_role="ops_manager",
                    linked_patient_name="Synthetic Border Collie",
                    linked_episode_ref="EP-V30-001",
                    status="new",
                    due_at=datetime.now(timezone.utc),
                ),
                ReferralIdentityIntakeV12(
                    intake_ref="INTAKE-V30-DUPLICATE",
                    premises_ref="premises-v30",
                    patient_name="Synthetic Border Collie",
                    species="dog",
                    breed="Border Collie",
                    owner_name="Synthetic Owner",
                    owner_email="owner-v30@example.test",
                    decision_authority_claimed=True,
                    financial_responsibility_claimed=True,
                    referral_payload={"synthetic": True},
                    status="needs_match_review",
                    duplicate_count=1,
                    created_by_subject="local-user:3005",
                ),
                IdentityMatchReviewV12(
                    review_ref="MATCH-V30-DUPLICATE",
                    intake_ref="INTAKE-V30-DUPLICATE",
                    candidate_patient_ref="PAT-V30-001",
                    candidate_owner_refs=["OWN-V30-001"],
                    match_score=94,
                    reasons=["same owner email", "same patient name and species"],
                    status="pending",
                ),
            ])
            session.commit()

        clinician_queue = ok(client.get("/api/role-queues/clinician", headers=clinician), "clinician queue")
        assert any(item["result_type"] == "critical_mri_result" for item in clinician_queue["pending_results"])
        manager_queue = ok(client.get("/api/role-queues/manager", headers=ops), "manager queue")
        assert any(item["linked_episode_ref"] == "EP-V30-001" for item in manager_queue["work_items"])

        discharge_ready = transition(client, clinician, "EP-V30-001", episode["version"], "discharge_ready", "v30-discharge-ready")
        assert discharge_ready.status_code == 200 and discharge_ready.json()["ok"] is True, discharge_ready.text
        episode = discharge_ready.json()["episode"]

        with Session(engine) as session:
            document = session.exec(select(ClinicalDocumentV8).where(ClinicalDocumentV8.document_ref == "DOC-V30-DISCHARGE")).one()
            document.status = "sent"
            document.sent_at = datetime.now(timezone.utc)
            document.version += 1
            session.add(document)
            session.commit()

        discharged = transition(client, admin, "EP-V30-001", episode["version"], "discharged", "v30-discharged")
        assert discharged.status_code == 200 and discharged.json()["ok"] is True, discharged.text
        episode = discharged.json()["episode"]

        closure = ok(client.post("/api/v9/episodes/EP-V30-001/closure", headers=ops, json={
            "disposition": "discharged_home",
            "discharge_document_ref": "DOC-V30-DISCHARGE",
            "owner_communication_ref": "COMM-V30-OWNER",
            "referrer_communication_ref": "COMM-V30-REFERRER",
            "financial_status": "settled",
            "outstanding_actions": [],
            "retained_risks": [{"risk": "neurological relapse", "mitigation": "owner warning signs"}],
            "reason": "Prepare complete synthetic episode closure record.",
        }), "prepare closure")["closure"]
        approved = ok(client.patch(
            f"/api/v9/closures/{closure['closure_ref']}/approve",
            headers=director,
            json={
                "expected_version": closure["version"],
                "reason": "Clinical, communication and financial closure evidence reviewed.",
            },
        ), "approve closure")
        assert approved["closure"]["status"] == "approved"

        closed = transition(client, admin, "EP-V30-001", episode["version"], "closed", "v30-closed")
        assert closed.status_code == 200 and closed.json()["ok"] is True, closed.text
        assert closed.json()["episode"]["status"] == "closed"

        today = date.today()
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)
        with Session(engine) as session:
            session.add(OperationalArea(
                area_ref="theatre-v30",
                premises_ref="premises-v30",
                name="Theatre V30",
                area_type="theatre",
                department="surgery",
                capacity=1,
                turnover_minutes=15,
                active=True,
            ))
            session.add_all([
                OperationalBlock(
                    block_ref="BLOCK-V30-A",
                    premises_ref="premises-v30",
                    operational_date=today,
                    episode_ref="EP-V30-PLANNED-A",
                    patient_ref="PAT-V30-A",
                    patient_name="Synthetic Planned A",
                    procedure_name="Planned procedure A",
                    area_ref="theatre-v30",
                    area_name="Theatre V30",
                    starts_at=start,
                    ends_at=start + timedelta(hours=2),
                    status="planned",
                    priority=30,
                    updated_by_subject="local-user:3001",
                    updated_by_name="V30 Operations Manager",
                    updated_by_role="ops_manager",
                    updated_by_auth_source="local",
                ),
                OperationalBlock(
                    block_ref="BLOCK-V30-B",
                    premises_ref="premises-v30",
                    operational_date=today,
                    episode_ref="EP-V30-PLANNED-B",
                    patient_ref="PAT-V30-B",
                    patient_name="Synthetic Planned B",
                    procedure_name="Planned procedure B",
                    area_ref="theatre-v30",
                    area_name="Theatre V30",
                    starts_at=start + timedelta(hours=1, minutes=30),
                    ends_at=start + timedelta(hours=3),
                    status="planned",
                    priority=25,
                    updated_by_subject="local-user:3001",
                    updated_by_name="V30 Operations Manager",
                    updated_by_role="ops_manager",
                    updated_by_auth_source="local",
                ),
            ])
            session.commit()
            conflicts = detect_constraints(session, "premises-v30", today, persist=True)
            session.commit()
            assert conflicts
            assert session.exec(select(OperationalConflict).where(OperationalConflict.premises_ref == "premises-v30")).all()

        emergency = ok(client.post("/api/v11/master-board/emergency/preview", headers=ops, json={
            "premisesRef": "premises-v30",
            "operationalDate": today.isoformat(),
            "episodeRef": "EP-V30-EMERGENCY",
            "patientRef": "PAT-V30-EMERGENCY",
            "patientName": "Synthetic Emergency",
            "procedureName": "Emergency decompression",
            "areaTypes": ["theatre"],
            "earliestStart": start.isoformat(),
            "latestStart": (start + timedelta(minutes=30)).isoformat(),
            "durationMinutes": 90,
            "turnoverMinutes": 15,
            "requiredSkills": [],
            "equipmentRefs": [],
            "priority": 100,
            "maxDisplacedBlocks": 6,
        }), "preview emergency insertion")
        assert emergency["canInsert"] is True
        assert any(option["displacedCount"] >= 1 for option in emergency["options"])

        board = ok(client.get(
            f"/api/v11/master-board/day?premises_ref=premises-v30&operational_date={today.isoformat()}",
            headers=ops,
        ), "load connected master board")
        assert board["connectedOperationalProofVersion"] == "v30"
        assert any(item["episode_ref"] == "EP-V30-001" for item in board["canonicalEpisodes"])
        assert board["recentCanonicalChanges"]

        with Session(engine) as session:
            duplicate_intake = session.exec(select(ReferralIdentityIntakeV12).where(
                ReferralIdentityIntakeV12.intake_ref == "INTAKE-V30-DUPLICATE"
            )).one()
            assert duplicate_intake.patient_ref is None
            assert duplicate_intake.episode_ref is None

        evaluated = ok(client.post(f"/api/v30/operational-proof/runs/{run_ref}/evaluate", headers=ops), "evaluate connected journey")
        proof = evaluated["run"]
        assert proof["passed_count"] == 12, evaluated
        assert proof["blocked_count"] == 0, evaluated

        scenario_observations = {
            "emergency_full_schedule": {
                "canInsert": emergency["canInsert"],
                "optionCount": len(emergency["options"]),
                "displacedCount": max(option["displacedCount"] for option in emergency["options"]),
                "ownerRole": "ops_manager",
                "nextAction": "Select and apply a governed emergency option.",
            },
            "theatre_imaging_overrun": {
                "conflictCount": len(conflicts),
                "ownerRole": "ops_manager",
                "nextAction": "Resolve downstream displacement before execution.",
            },
            "staff_unavailable": {
                "workItemVisible": True,
                "ownerRole": "ops_manager",
                "nextAction": "Reassign a competent clinician.",
            },
            "unacknowledged_handover": {
                "handoverRef": offered["handover_ref"],
                "receivingQueue": "nurse",
                "ownerRole": "nurse",
                "nextAction": "Acknowledge or escalate the handover.",
            },
            "overdue_critical_result": {
                "pendingResultVisible": True,
                "ownerRole": "clinician",
                "nextAction": "Review the critical MRI result.",
            },
            "discharge_medication_or_comms_block": {
                "blockerCodes": sorted(discharge_codes),
                "ownerRole": "clinician",
                "nextAction": "Complete discharge document, medication and owner communication evidence.",
            },
            "stale_concurrent_update": {
                "httpStatus": stale.status_code,
                "ownerRole": "current record owner",
                "nextAction": "Reload current state before retrying.",
            },
            "duplicate_patient_identity": {
                "reviewRef": "MATCH-V30-DUPLICATE",
                "canonicalAttachment": False,
                "ownerRole": "admin",
                "nextAction": "Resolve the identity match review.",
            },
        }
        for code, observed in scenario_observations.items():
            result = ok(client.post(
                f"/api/v30/operational-proof/runs/{run_ref}/scenarios/{code}",
                headers=ops,
                json={
                    "observed": observed,
                    "failureDetected": True,
                    "accountableOwnerVisible": True,
                    "nextActionVisible": True,
                    "evidenceVisible": True,
                    "urgentAccessPreserved": True,
                    "reason": f"Record controlled {code} stress proof.",
                },
            ), f"record scenario {code}")
            proof = result["run"]
            assert result["scenario"]["status"] == "pass"

        mobile = ok(client.post(
            f"/api/v30/operational-proof/runs/{run_ref}/mobile-assessments",
            headers=ops,
            json={
                "deviceLabel": "Synthetic Android viewport",
                "operatingSystem": "Android 16",
                "browser": "Chrome mobile",
                "viewportWidth": 412,
                "viewportHeight": 915,
                "secureContext": True,
                "online": True,
                "touchCapable": True,
                "microphoneAvailable": True,
                "checks": {
                    "noHiddenHorizontalActionArea": True,
                    "minimumTouchTargets": True,
                    "keyboardSafeSubmitControls": True,
                    "sessionAndCsrf": True,
                    "unauthenticatedCaptureRejected": True,
                    "refreshPersistence": True,
                },
                "manualHardwareConfirmation": False,
                "reason": "Record automated mobile diagnostics while preserving the real-device boundary.",
            },
        ), "record mobile assessment")
        assert mobile["assessment"]["status"] == "manual_confirmation_required"
        assert mobile["manualActionRequired"] is True

        completed = ok(client.post(
            f"/api/v30/operational-proof/runs/{run_ref}/complete",
            headers=ops,
            json={
                "expectedVersion": proof["version"],
                "reason": "Connected journey and all eight stress scenarios passed; physical Android confirmation remains explicit.",
            },
        ), "complete operational proof")
        assert completed["run"]["status"] == "passed_with_manual_boundary"
        assert completed["run"]["summary"]["realHospitalDeploymentReady"] is False

        report = ok(client.get(f"/api/v30/operational-proof/runs/{run_ref}/report", headers=director), "export proof report")
        assert "Connected journey" in report["markdown"]
        assert "External boundary" in report["markdown"]
        assert len(report["data"]["scenarios"]) == 8

        with Session(engine) as session:
            chain = verify_event_chain(session)
            assert chain["valid"] is True, chain

        print("OPERATIONAL_PROOF_V30_CONNECTED_JOURNEY_AND_STRESS_PASSED")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
