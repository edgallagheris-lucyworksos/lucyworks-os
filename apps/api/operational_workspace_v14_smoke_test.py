import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(__file__).parent / "operational_workspace_v14_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AUTH_MODE"] = "local"
os.environ["AUTH_ENFORCEMENT"] = "required"
os.environ["AUTH_JWT_SECRET"] = "operational-workspace-v14-smoke-secret-long-enough"
os.environ["AUTH_AUDIENCE"] = "lucyworks-api"
os.environ["AUTH_ISSUER"] = "lucyworks-local"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import issue_local_token
from app.database import engine
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock
from app.main import app
from app.models import AuditEvent, WorkItem

print("\n--- RUNNING PATIENT-CENTRED WORKSPACE V14 SMOKE TEST ---\n")

ops_token, _ = issue_local_token(
    user_id=9401,
    name="Verified Ops Controller",
    role="ops_manager",
    email="ops-v14@lucyworks.local",
)
nurse_token, _ = issue_local_token(
    user_id=9402,
    name="Verified Nurse",
    role="nurse",
    email="nurse-v14@lucyworks.local",
)
ops_headers = {"Authorization": f"Bearer {ops_token}"}
nurse_headers = {"Authorization": f"Bearer {nurse_token}"}

now = datetime.now(timezone.utc)
with TestClient(app) as client:
    with Session(engine) as session:
        episode = CanonicalEpisodeState(
            episode_ref="EP-V14-001",
            patient_ref="PAT-V14-001",
            patient_name="Bramble V14",
            premises_ref="default-premises",
            service_line="neurology",
            urgency="urgent",
            phase="diagnostic_plan",
            owner_role="clinician",
            next_action="Confirm MRI plan and owner authority",
            gates_json='{"consent":"approved","estimate":"accepted"}',
        )
        block = OperationalBlock(
            block_ref="BLOCK-V14-001",
            premises_ref="default-premises",
            operational_date=date.today(),
            episode_ref="EP-V14-001",
            patient_ref="PAT-V14-001",
            patient_name="Bramble V14",
            procedure_name="MRI neurology",
            block_type="imaging",
            area_ref="mri",
            area_name="MRI",
            starts_at=now + timedelta(minutes=30),
            ends_at=now + timedelta(minutes=90),
            status="planned",
            risk_level="amber",
            lead_staff_ref="9401",
            lead_staff_name="Verified Ops Controller",
            lead_staff_role="ops_manager",
            gates_json='{"consent":"approved","estimate":"accepted"}',
        )
        linked_task = WorkItem(
            title="Confirm MRI owner update",
            input_type="operational_note",
            source="smoke_test",
            category="owner_comms",
            description="Owner update is overdue before MRI.",
            urgency="red",
            owner_role="ops_manager",
            section_name="Imaging",
            room_name="MRI",
            linked_patient_name="Bramble V14",
            linked_episode_ref="EP-V14-001",
            status="new",
            due_at=now - timedelta(minutes=10),
        )
        unlinked_task = WorkItem(
            title="Legacy task without episode",
            input_type="operational_note",
            source="legacy_seed",
            category="data_quality",
            description="This must remain visible but separate from canonical patient care.",
            urgency="amber",
            owner_role="ops_manager",
            status="new",
        )
        session.add(episode)
        session.add(block)
        session.add(linked_task)
        session.add(unlinked_task)
        session.commit()
        session.refresh(linked_task)
        linked_task_id = linked_task.id

    r = client.get(f"/api/v14/operational-workspace?operational_date={date.today().isoformat()}")
    assert r.status_code == 401, r.text

    r = client.get(
        f"/api/v14/operational-workspace?operational_date={date.today().isoformat()}",
        headers=ops_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["workspaceVersion"] == "v14"
    assert data["summary"]["activePatients"] == 1
    assert data["summary"]["boardBlocks"] == 1
    assert data["summary"]["scheduledPatients"] == 1
    assert data["summary"]["unlinkedTasks"] == len(data["unlinkedTasks"])
    assert data["summary"]["unlinkedTasks"] >= 1
    assert data["summary"]["overdueTasks"] == 1
    assert data["patientFlow"][0]["patientName"] == "Bramble V14"
    assert data["patientFlow"][0]["schedule"][0]["areaName"] == "MRI"
    assert data["tasks"][0]["linkedToCanonicalEpisode"] is True
    assert any(
        task["title"] == "Legacy task without episode" and task["linkedToCanonicalEpisode"] is False
        for task in data["unlinkedTasks"]
    )
    assert data["consistency"]["canonicalEpisodeCount"] == data["consistency"]["workspacePatientCount"]

    r = client.post(
        f"/api/v14/operational-workspace/work-items/{linked_task_id}/action",
        headers=nurse_headers,
        json={"action": "start", "expectedStatus": "new"},
    )
    assert r.status_code == 403, r.text

    r = client.post(
        f"/api/v14/operational-workspace/work-items/{linked_task_id}/action",
        headers=ops_headers,
        json={
            "action": "start",
            "expectedStatus": "new",
            "note": "Accepted accountability for owner update",
            "actorName": "Spoofed Browser Actor",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["workItem"]["status"] == "in_progress"
    assert r.json()["audit"]["actorName"] == "Verified Ops Controller"

    r = client.post(
        f"/api/v14/operational-workspace/work-items/{linked_task_id}/action",
        headers=ops_headers,
        json={"action": "complete", "expectedStatus": "new"},
    )
    assert r.status_code == 409, r.text

    r = client.post(
        f"/api/v14/operational-workspace/work-items/{linked_task_id}/action",
        headers=ops_headers,
        json={"action": "complete", "expectedStatus": "in_progress"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["workItem"]["status"] == "done"

    with Session(engine) as session:
        audit = session.exec(
            select(AuditEvent).where(
                AuditEvent.entity_type == "work_item",
                AuditEvent.entity_id == linked_task_id,
                AuditEvent.action == "workspace_start",
            )
        ).first()
        assert audit is not None
        assert audit.actor_name == "Verified Ops Controller"
        assert audit.actor_name != "Spoofed Browser Actor"

print("\n--- PATIENT-CENTRED WORKSPACE V14 TEST PASSED ---\n")
