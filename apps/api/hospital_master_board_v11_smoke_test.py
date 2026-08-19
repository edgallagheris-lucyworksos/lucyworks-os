import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_master_board_v11_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AUTH_MODE"] = "local"
os.environ["AUTH_ENFORCEMENT"] = "required"
os.environ["AUTH_JWT_SECRET"] = "master-board-v11-test-secret-that-is-long-and-private"
os.environ["AUTH_ISSUER"] = "lucyworks-test"
os.environ["AUTH_AUDIENCE"] = "lucyworks-api"
os.environ["AUTO_CREATE_SCHEMA"] = "true"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.auth import issue_local_token
from app.clinical_execution_models import ClinicalObservation, DiagnosticWorkItem, TreatmentTask
from app.control_plane_models import CriticalResultAcknowledgement
from app.database import engine
from app.hospital_ops_models import OperationalArea
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

ops_token, _ = issue_local_token(
    user_id=1101,
    name="Verified Hospital Controller",
    role="ops_manager",
    email="ops-v11@example.test",
)
nurse_token, _ = issue_local_token(
    user_id=1102,
    name="Ward Nurse",
    role="nurse",
    email="nurse-v11@example.test",
)
clinician_token, _ = issue_local_token(
    user_id=1103,
    name="Duty Clinician",
    role="clinician",
    email="clinician-v11@example.test",
)
ops_headers = {"Authorization": f"Bearer {ops_token}"}
nurse_headers = {"Authorization": f"Bearer {nurse_token}"}
clinician_headers = {"Authorization": f"Bearer {clinician_token}"}
DAY = "2026-07-27"
PREMISES = "bvs-bristol"


def block_payload(block_ref: str, patient: str, start: str, end: str) -> dict:
    return {
        "blockRef": block_ref,
        "premisesRef": PREMISES,
        "patientName": patient,
        "procedureName": "Planned referral procedure",
        "blockType": "procedure",
        "areaRef": "theatre-1",
        "startsAt": start,
        "endsAt": end,
        "status": "planned",
        "riskLevel": "green",
        "priority": 40,
        "leadStaffRef": "clinician-planned",
        "leadStaffName": "Planned Clinician",
        "leadStaffRole": "clinician",
        "requiredSkills": ["surgical", "anaesthesia"],
        "idempotencyKey": f"create:{block_ref}",
    }


try:
    with TestClient(app) as client:
        response = client.post(
            f"/api/hospital-ops/bootstrap?premises_ref={PREMISES}",
            headers=ops_headers,
        )
        assert response.status_code == 200, response.text

        with Session(engine) as session:
            theatres = session.exec(
                select(OperationalArea).where(
                    OperationalArea.premises_ref == PREMISES,
                    OperationalArea.area_type == "theatre",
                )
            ).all()
            assert len(theatres) == 4
            for theatre in theatres:
                theatre.active = theatre.area_ref == "theatre-1"
                session.add(theatre)
            session.commit()

        response = client.post(
            "/api/hospital-ops/episodes",
            headers=ops_headers,
            json={
                "episodeRef": "episode-v11-coordination",
                "patientRef": "patient-v11-coordination",
                "patientName": "Coordination Patient",
                "premisesRef": PREMISES,
                "urgency": "urgent",
                "idempotencyKey": "episode-v11-coordination-create",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["episode"]["version"] == 1

        coordination_update = {
            "premisesRef": PREMISES,
            "expectedVersion": 1,
            "ownerRole": "nurse",
            "currentAreaRef": "icu",
            "nextAction": "Complete observations and clinical review",
            "reason": "Ward and ICU coordination test",
            "idempotencyKey": "episode-v11-coordination-update",
        }
        response = client.patch(
            "/api/v11/master-board/episodes/episode-v11-coordination/operational",
            headers=ops_headers,
            json=coordination_update,
        )
        assert response.status_code == 200, response.text
        assert response.json()["episode"]["version"] == 2
        assert response.json()["episode"]["currentAreaRef"] == "icu"

        replay = client.patch(
            "/api/v11/master-board/episodes/episode-v11-coordination/operational",
            headers=ops_headers,
            json=coordination_update,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["episode"]["version"] == 2
        print("Idempotent patient owner, location and next-action update OK")

        handover_payload = {
            "premisesRef": PREMISES,
            "toRole": "nurse",
            "toActor": "Ward Nurse",
            "summary": "Continue ICU observations and escalate deterioration",
            "clinicalRisks": ["respiratory deterioration"],
            "outstandingActions": ["repeat observations", "clinical review"],
            "idempotencyKey": "handover-v11-coordination",
        }
        response = client.post(
            "/api/v11/master-board/episodes/episode-v11-coordination/handovers",
            headers=ops_headers,
            json=handover_payload,
        )
        assert response.status_code == 200, response.text
        handover_id = response.json()["handover"]["id"]
        assert response.json()["created"] is True
        replay = client.post(
            "/api/v11/master-board/episodes/episode-v11-coordination/handovers",
            headers=ops_headers,
            json=handover_payload,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["created"] is False

        with Session(engine) as session:
            now = datetime.now(timezone.utc)
            session.add(DiagnosticWorkItem(
                work_ref="diagnostic-v11-critical",
                episode_ref="episode-v11-coordination",
                modality="laboratory",
                requested_test="potassium",
                urgency="urgent",
                status="reported",
                requested_by_subject="clinician-v11",
                assigned_service="laboratory",
                reported_at=now,
                report_summary="Critical potassium",
                critical_result=True,
            ))
            session.add(CriticalResultAcknowledgement(
                result_ref="diagnostic-v11-critical",
                patient_case_id="patient-v11-coordination",
                referral_episode_id="episode-v11-coordination",
                result_type="potassium",
                severity="red",
                summary="Critical potassium",
                status="awaiting_acknowledgement",
                assigned_to="Duty Clinician",
                assigned_role="clinician",
                due_at=now + timedelta(minutes=10),
            ))
            session.add(TreatmentTask(
                task_ref="task-v11-overdue",
                episode_ref="episode-v11-coordination",
                task_type="observation",
                title="Repeat ICU observations",
                instructions="Record and escalate deterioration",
                due_at=now - timedelta(minutes=5),
                assigned_role="nurse",
                status="due",
                priority="red",
            ))
            session.add(ClinicalObservation(
                observation_ref="observation-v11-red",
                episode_ref="episode-v11-coordination",
                area_ref="icu",
                observation_type="respiratory_rate",
                values={"value": 44},
                concern_level="red",
                escalation_required=True,
                escalation_status="pending",
                escalated_to_role="clinician",
                recorded_by_subject="nurse-v11",
                recorded_by_name="Ward Nurse",
            ))
            session.commit()

        response = client.get(
            f"/api/v11/master-board/coordination?premises_ref={PREMISES}",
            headers=ops_headers,
        )
        assert response.status_code == 200, response.text
        coordination = response.json()
        assert coordination["summary"] == {
            "pendingHandovers": 1,
            "unacknowledgedCriticalResults": 1,
            "overdueTasks": 1,
            "redObservations": 1,
        }
        result_id = coordination["criticalResults"][0]["id"]
        assert coordination["diagnostics"][0]["status"] == "reported"

        denied = client.patch(
            f"/api/v11/master-board/critical-results/{result_id}/acknowledge",
            headers=nurse_headers,
            json={"premisesRef": PREMISES, "actionTaken": "not authorised"},
        )
        assert denied.status_code == 403, denied.text
        acknowledged = client.patch(
            f"/api/v11/master-board/critical-results/{result_id}/acknowledge",
            headers=clinician_headers,
            json={"premisesRef": PREMISES, "actionTaken": "Patient reviewed and treatment adjusted"},
        )
        assert acknowledged.status_code == 200, acknowledged.text
        assert acknowledged.json()["result"]["status"] == "acknowledged"

        accepted = client.patch(
            f"/api/v11/master-board/handovers/{handover_id}/decision",
            headers=nurse_headers,
            json={"premisesRef": PREMISES, "decision": "accepted", "note": "Responsibility accepted"},
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["handover"]["status"] == "accepted"

        cross_site = client.get(
            "/api/v11/master-board/coordination?premises_ref=another-hospital",
            headers=ops_headers,
        )
        assert cross_site.status_code == 403, cross_site.text
        print("Ward/ICU handover, overdue care, diagnostic result and site authority OK")

        response = client.post(
            "/api/hospital-ops/blocks",
            headers=ops_headers,
            json=block_payload("planned-a", "Planned A", f"{DAY}T09:00:00Z", f"{DAY}T10:00:00Z"),
        )
        assert response.status_code == 200, response.text
        response = client.post(
            "/api/hospital-ops/blocks",
            headers=ops_headers,
            json=block_payload("planned-b", "Planned B", f"{DAY}T10:00:00Z", f"{DAY}T11:00:00Z"),
        )
        assert response.status_code == 200, response.text
        print("Canonical planned theatre sequence created")

        emergency_request = {
            "premisesRef": PREMISES,
            "operationalDate": DAY,
            "patientName": "Emergency Patient",
            "procedureName": "Emergency laparotomy",
            "areaTypes": ["theatre"],
            "earliestStart": f"{DAY}T09:15:00Z",
            "latestStart": f"{DAY}T09:15:00Z",
            "durationMinutes": 60,
            "turnoverMinutes": 20,
            "requiredSkills": ["surgical", "anaesthesia"],
            "equipmentRefs": [],
            "leadStaffRef": "clinician-emergency",
            "leadStaffName": "Emergency Clinician",
            "leadStaffRole": "clinician",
            "priority": 100,
            "maxDisplacedBlocks": 6,
        }

        response = client.post(
            "/api/v11/master-board/emergency/preview",
            headers=nurse_headers,
            json=emergency_request,
        )
        assert response.status_code == 403, response.text
        print("Emergency insertion authority boundary OK")

        response = client.post(
            "/api/v11/master-board/emergency/preview",
            headers=ops_headers,
            json=emergency_request,
        )
        assert response.status_code == 200, response.text
        first_preview = response.json()
        assert first_preview["canInsert"] is True
        option = first_preview["options"][0]
        assert option["areaRef"] == "theatre-1"
        assert option["displacedCount"] == 2, option
        assert option["affected"][0]["blockRef"] == "planned-a"
        assert option["affected"][1]["blockRef"] == "planned-b"
        print("Ranked emergency displacement preview OK")

        response = client.patch(
            "/api/hospital-ops/blocks/planned-a",
            headers=ops_headers,
            json={
                "expectedVersion": 1,
                "commandType": "RecordOperationalNote",
                "notes": "Updated after emergency preview",
                "action": "updated plan evidence",
                "reason": "prove stale emergency plan rejection",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["block"]["version"] == 2

        stale_apply = {
            **emergency_request,
            "areaRef": option["areaRef"],
            "startsAt": option["startsAt"],
            "optionRef": option["optionRef"],
            "expectedVersions": {
                item["blockRef"]: item["expectedVersion"] for item in option["affected"]
            },
            "reason": "stale plan must not apply",
            "idempotencyKey": "emergency-v11-stale",
        }
        response = client.post(
            "/api/v11/master-board/emergency/apply",
            headers=ops_headers,
            json=stale_apply,
        )
        assert response.status_code == 409, response.text
        print("Stale emergency displacement plan rejected")

        response = client.post(
            "/api/v11/master-board/emergency/preview",
            headers=ops_headers,
            json=emergency_request,
        )
        assert response.status_code == 200, response.text
        option = response.json()["options"][0]
        apply_payload = {
            **emergency_request,
            "areaRef": option["areaRef"],
            "startsAt": option["startsAt"],
            "optionRef": option["optionRef"],
            "expectedVersions": {
                item["blockRef"]: item["expectedVersion"] for item in option["affected"]
            },
            "reason": "life-threatening emergency accepted by hospital controller",
            "idempotencyKey": "emergency-v11-apply",
        }
        response = client.post(
            "/api/v11/master-board/emergency/apply",
            headers=ops_headers,
            json=apply_payload,
        )
        assert response.status_code == 200, response.text
        applied = response.json()
        assert applied["created"] is True
        assert applied["emergencyBlock"]["blockType"] == "emergency"
        assert applied["emergencyBlock"]["riskLevel"] == "red"
        assert len(applied["displaced"]) == 2
        assert all(item["block"]["version"] >= 2 for item in applied["displaced"])
        print("Emergency insertion and transactional displacement OK")

        response = client.get(
            f"/api/v11/master-board/day?premises_ref={PREMISES}&operational_date={DAY}",
            headers=ops_headers,
        )
        assert response.status_code == 200, response.text
        board = response.json()
        assert board["boardVersion"] == "v11"
        assert board["operatingContext"]["premisesRef"] == PREMISES
        emergency_blocks = [item for item in board["blocks"] if item["blockType"] == "emergency"]
        assert len(emergency_blocks) == 1
        versions_before_replay = {item["blockRef"]: item["version"] for item in board["blocks"]}
        print("Master board v11 day view OK")

        response = client.get(
            f"/api/v11/master-board/day?premises_ref=another-hospital&operational_date={DAY}",
            headers=ops_headers,
        )
        assert response.status_code == 403, response.text
        assert response.json()["detail"]["code"] == "site_not_authorised"
        print("Cross-premises board access rejected")

        response = client.post(
            "/api/v11/master-board/emergency/apply",
            headers=ops_headers,
            json=apply_payload,
        )
        assert response.status_code == 200, response.text
        replay = response.json()
        assert replay["createCommandRef"] == applied["createCommandRef"]

        response = client.get(
            f"/api/v11/master-board/day?premises_ref={PREMISES}&operational_date={DAY}",
            headers=ops_headers,
        )
        assert response.status_code == 200, response.text
        versions_after_replay = {
            item["blockRef"]: item["version"] for item in response.json()["blocks"]
        }
        assert versions_after_replay == versions_before_replay
        print("Emergency command idempotent replay OK")

    print("\n--- HOSPITAL MASTER BOARD V11 SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
