import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(__file__).parent / "care_brief_v16_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AUTH_MODE"] = "local"
os.environ["AUTH_ENFORCEMENT"] = "required"
os.environ["AUTH_JWT_SECRET"] = "care-brief-v16-smoke-secret-long-enough"
os.environ["AUTH_AUDIENCE"] = "lucyworks-api"
os.environ["AUTH_ISSUER"] = "lucyworks-local"

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import issue_local_token
from app.database import engine
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock, OperationalConflict
from app.main import app
from app.models import WorkItem

print("\n--- RUNNING CARE BRIEF V16 SMOKE TEST ---\n")

nurse_token, _ = issue_local_token(user_id=9601, name="Verified Nurse V16", role="nurse", email="nurse-v16@lucyworks.local")
ops_token, _ = issue_local_token(user_id=9602, name="Verified Ops V16", role="ops_manager", email="ops-v16@lucyworks.local")
nurse_headers = {"Authorization": f"Bearer {nurse_token}"}
ops_headers = {"Authorization": f"Bearer {ops_token}"}
now = datetime.now(timezone.utc)

with TestClient(app) as client:
    with Session(engine) as session:
        session.add(CanonicalEpisodeState(
            episode_ref="EP-V16-001",
            patient_ref="PAT-V16-001",
            patient_name="Bramble V16",
            premises_ref="default-premises",
            service_line="neurology",
            urgency="urgent",
            phase="diagnostic_plan",
            owner_role="clinician",
            owner_subject="clinician-16",
            current_area_ref="mri",
            next_action="Confirm consent and MRI readiness",
            gates_json='{"consent":"pending","estimate":"accepted"}',
            flags_json='["spinal pain progression"]',
        ))
        session.add(OperationalBlock(
            block_ref="BLOCK-V16-001",
            premises_ref="default-premises",
            operational_date=date.today(),
            episode_ref="EP-V16-001",
            patient_ref="PAT-V16-001",
            patient_name="Bramble V16",
            procedure_name="MRI neurology",
            block_type="imaging",
            area_ref="mri",
            area_name="MRI",
            starts_at=now + timedelta(minutes=20),
            ends_at=now + timedelta(minutes=80),
            status="planned",
            risk_level="amber",
            lead_staff_ref="clinician-16",
            lead_staff_name="Dr V16",
            lead_staff_role="clinician",
            blockers_json='["MRI checklist incomplete"]',
        ))
        session.add(WorkItem(
            title="Owner consent confirmation overdue",
            input_type="operational_note",
            source="smoke_test",
            category="consent",
            description="Confirm authority and consent before MRI.",
            urgency="red",
            owner_role="clinician",
            section_name="Imaging",
            room_name="MRI",
            linked_patient_name="Bramble V16",
            linked_episode_ref="EP-V16-001",
            status="new",
            due_at=now - timedelta(minutes=5),
        ))
        session.add(OperationalConflict(
            conflict_ref="CONFLICT-V16-001",
            premises_ref="default-premises",
            operational_date=date.today(),
            conflict_type="readiness",
            severity="red",
            status="open",
            primary_block_ref="BLOCK-V16-001",
            related_refs_json='[]',
            explanation="MRI cannot start until the checklist is complete",
            fingerprint="v16-readiness",
        ))
        session.commit()

    r = client.get("/api/v16/care-brief/EP-V16-001")
    assert r.status_code == 401, r.text

    r = client.get("/api/v16/care-brief/EP-V16-001", headers=nurse_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["patientName"] == "Bramble V16"
    assert data["who"]["leadName"] == "Dr V16"
    assert data["what"]["nextAction"] == "Confirm consent and MRI readiness"
    assert data["where"]["areaName"] == "MRI"
    assert data["when"]["startsAt"]
    assert data["how"]["criticalTaskCount"] == 1
    assert "Consent evidence incomplete" in data["how"]["gateGaps"]
    assert data["how"]["openConflictCount"] == 1
    assert data["recordedControlsReady"] is False
    assert data["links"]["patientRecord"].endswith("episode=EP-V16-001")

    r = client.get("/api/workspace?role=ops_manager", headers=nurse_headers)
    assert r.status_code == 403, r.text

    r = client.get("/api/workspace", headers=nurse_headers)
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "nurse"

    r = client.get("/api/workspace?role=ops_manager", headers=ops_headers)
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "ops_manager"

print("\n--- CARE BRIEF V16 TEST PASSED ---\n")
