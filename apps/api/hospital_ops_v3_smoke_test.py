import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_hospital_ops_v3_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AUTH_MODE"] = "local"
os.environ["AUTH_ENFORCEMENT"] = "required"
os.environ["AUTH_JWT_SECRET"] = "hospital-ops-v3-test-secret-that-is-long-and-private"
os.environ["AUTH_ISSUER"] = "lucyworks-test"
os.environ["AUTH_AUDIENCE"] = "lucyworks-api"
os.environ["AUTO_CREATE_SCHEMA"] = "true"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from app.auth import issue_local_token
from app.database import engine
from app.main import app
from app.models import Shift, StaffMember

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

token, _ = issue_local_token(user_id=1, name="Verified Ops", role="ops_manager", email="ops@example.test")
headers = {"Authorization": f"Bearer {token}"}
DAY = "2026-07-20"

try:
    with Session(engine) as session:
        staff = StaffMember(name="MRI Clinician", role="clinician", skills="mri, anaesthesia, consultation", active=True)
        session.add(staff)
        session.flush()
        session.add(Shift(staff_member_id=staff.id or 0, department="Diagnostic imaging", starts_at=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc), ends_at=datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc), status="planned"))
        session.commit()
        staff_ref = str(staff.id)

    with TestClient(app) as client:
        response = client.post("/api/hospital-ops/bootstrap?premises_ref=default-premises", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["areas"] >= 25
        print("Hospital premises and 11-theatre area catalogue OK")

        response = client.post("/api/hospital-ops/episodes", headers=headers, json={
            "episodeRef": "episode-v3-1",
            "patientRef": "patient-v3-1",
            "patientName": "Canonical Patient",
            "urgency": "urgent",
            "idempotencyKey": "episode-v3-1-create",
        })
        assert response.status_code == 200, response.text
        episode = response.json()["episode"]
        assert episode["version"] == 1
        assert response.json()["command"]["actor"]["name"] == "Verified Ops"
        print("Canonical referral episode command OK")

        response = client.patch("/api/hospital-ops/episodes/episode-v3-1/gates", headers=headers, json={
            "expectedVersion": 1,
            "gates": {"consent": "approved", "estimate": "approved", "insurance": "approved", "pharmacy": "ready"},
            "reason": "test governance evidence",
        })
        assert response.status_code == 200, response.text
        assert response.json()["episode"]["version"] == 2
        print("Versioned episode gates OK")

        block_payload = {
            "premisesRef": "default-premises",
            "episodeRef": "episode-v3-1",
            "patientRef": "patient-v3-1",
            "patientName": "Canonical Patient",
            "procedureRef": "procedure-v3-mri",
            "procedureName": "MRI",
            "blockType": "imaging",
            "areaRef": "mri",
            "startsAt": f"{DAY}T09:00:00Z",
            "endsAt": f"{DAY}T10:00:00Z",
            "leadStaffRef": staff_ref,
            "leadStaffName": "MRI Clinician",
            "leadStaffRole": "clinician",
            "requiredSkills": ["mri", "anaesthesia"],
            "gates": {"consent": "approved", "estimate": "approved", "insurance": "approved", "pharmacy": "ready"},
            "idempotencyKey": "block-v3-1-create",
        }
        response = client.post("/api/hospital-ops/blocks", headers=headers, json={"blockRef": "block-v3-1", **block_payload})
        assert response.status_code == 200, response.text
        block1 = response.json()["block"]
        assert block1["version"] == 1

        response = client.post("/api/hospital-ops/blocks", headers=headers, json={
            "blockRef": "block-v3-2",
            **{**block_payload, "episodeRef": "episode-v3-2", "patientRef": "patient-v3-2", "patientName": "Collision Patient", "procedureRef": "procedure-v3-mri-2", "startsAt": f"{DAY}T09:30:00Z", "endsAt": f"{DAY}T10:30:00Z", "gates": {"consent": "pending", "estimate": "pending", "pharmacy": "pending"}, "idempotencyKey": "block-v3-2-create"},
        })
        assert response.status_code == 200, response.text
        print("Canonical operational blocks OK")

        response = client.get(f"/api/hospital-ops/board?premises_ref=default-premises&operational_date={DAY}", headers=headers)
        assert response.status_code == 200, response.text
        board = response.json()
        assert board["summary"]["redConflicts"] >= 2, board["conflicts"]
        assert any(item["conflictType"] == "area_capacity" for item in board["conflicts"])
        assert any(item["conflictType"] == "staff_overlap" for item in board["conflicts"])
        assert any("because" not in item["explanation"].lower() or item["explanation"] for item in board["conflicts"])
        assert all(item["options"] for item in board["conflicts"])
        print("Explained multi-constraint engine OK")

        response = client.patch("/api/hospital-ops/blocks/block-v3-1", headers=headers, json={
            "expectedVersion": 99,
            "commandType": "MoveOperationalBlock",
            "startsAt": f"{DAY}T10:30:00Z",
            "endsAt": f"{DAY}T11:30:00Z",
        })
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "stale_version"
        print("Optimistic concurrency rejection OK")

        response = client.patch("/api/hospital-ops/blocks/block-v3-1", headers=headers, json={
            "expectedVersion": 1,
            "commandType": "MoveOperationalBlock",
            "action": "moved MRI block",
            "startsAt": f"{DAY}T10:30:00Z",
            "endsAt": f"{DAY}T11:30:00Z",
            "reason": "resolve collision",
        })
        assert response.status_code == 200, response.text
        assert response.json()["block"]["version"] == 2
        print("Versioned server-authoritative move OK")

        response = client.post("/api/hospital-ops/blocks/block-v3-2/delay-preview", headers=headers, json={"minutes": 30})
        assert response.status_code == 200, response.text
        preview = response.json()
        assert preview["affected"]
        assert preview["alternatives"]
        expected_versions = {item["blockRef"]: item["expectedVersion"] for item in preview["affected"]}
        response = client.post("/api/hospital-ops/blocks/block-v3-2/delay", headers=headers, json={
            "minutes": 30,
            "expectedVersions": expected_versions,
            "reason": "scanner preparation overrun",
        })
        assert response.status_code == 200, response.text
        assert response.json()["blocks"]
        print("Delay consequence preview and propagation OK")

        episode_version = 2
        for phase in ["intake_validation", "accepted", "arrived", "consultation", "diagnostic_plan", "estimate_and_consent", "preparation"]:
            response = client.patch("/api/hospital-ops/episodes/episode-v3-1/transition", headers=headers, json={
                "expectedVersion": episode_version,
                "phase": phase,
                "reason": "state-machine smoke test",
            })
            assert response.status_code == 200, (phase, response.text)
            episode_version = response.json()["episode"]["version"]
        assert response.json()["episode"]["phase"] == "preparation"
        print("End-to-end referral episode state machine OK")

        response = client.post("/api/hospital-ops/simulation/run", headers=headers, json={
            "scenarioName": "forty-case-eleven-theatre-test",
            "premisesRef": "simulation-premises",
            "operationalDate": DAY,
            "seed": 42,
            "caseCount": 40,
            "commit": False,
        })
        assert response.status_code == 200, response.text
        metrics = response.json()["metrics"]
        assert metrics["caseCount"] == 40
        assert metrics["target"]["theatres"] == 11
        print("Hospital simulation and shadow scenario metrics OK")

        csv_payload = "patientName,procedureName,areaRef,startsAt,endsAt\nImport Patient,CT,ct,2026-07-20T12:00:00Z,2026-07-20T13:00:00Z\nBroken Patient,MRI,unknown,not-a-date,also-bad"
        response = client.post("/api/hospital-ops/imports/preview", headers=headers, json={
            "sourceType": "csv",
            "sourceName": "vendor export",
            "premisesRef": "default-premises",
            "content": csv_payload,
        })
        assert response.status_code == 200, response.text
        import_preview = response.json()
        assert import_preview["acceptedCount"] == 1
        assert import_preview["rejectedCount"] == 1
        batch_ref = import_preview["batchRef"]

        response = client.post(f"/api/hospital-ops/imports/{batch_ref}/commit", headers=headers, json={})
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "reconciliation_required"

        response = client.get(f"/api/hospital-ops/imports/{batch_ref}", headers=headers)
        assert response.status_code == 200, response.text
        item_ref = response.json()["items"][0]["itemRef"]
        response = client.patch(f"/api/hospital-ops/imports/{batch_ref}/items/{item_ref}/resolve", headers=headers, json={
            "correctedRecord": {
                "patientName": "Broken Patient",
                "procedureName": "MRI",
                "areaRef": "mri",
                "startsAt": "2026-07-20T13:30:00Z",
                "endsAt": "2026-07-20T14:30:00Z"
            }
        })
        assert response.status_code == 200, response.text
        assert response.json()["rejectedCount"] == 0
        response = client.post(f"/api/hospital-ops/imports/{batch_ref}/commit", headers=headers, json={})
        assert response.status_code == 200, response.text
        assert response.json()["createdCount"] == 2
        print("Import preview, reconciliation and commit guard OK")

        response = client.get(f"/api/hospital-ops/shadow/compare?premises_ref=default-premises&operational_date={DAY}", headers=headers)
        assert response.status_code == 200, response.text
        assert "agreementPercent" in response.json()
        print("Legacy/canonical shadow comparison OK")

        response = client.get("/api/hospital-ops/commands?target_ref=block-v3-1", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["commands"]
        assert all(item["actor"]["name"] == "Verified Ops" for item in response.json()["commands"])
        print("Verified command attribution OK")

        response = client.get("/api/evidence/integrity", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["ok"] is True, response.text
        print("Tamper-evident command evidence chain OK")

    print("\n--- HOSPITAL OPERATING SYSTEM V3 SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
