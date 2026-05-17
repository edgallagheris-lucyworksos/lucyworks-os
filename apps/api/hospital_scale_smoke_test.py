import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_hospital_scale_smoke_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.inpatient_models import FinancialConsentStatus, InpatientStay, MedicationDue, NightHandover, ObservationTask
from app.main import app
from app.models import ProcedureType, Room, ScheduleBlock, StaffMember

# Start from a clean schema even if a prior local/Codex run left SQLite state behind.
SQLModel.metadata.drop_all(engine)

print("\n--- RUNNING HOSPITAL SCALE / OVERNIGHT SMOKE TEST ---\n")

try:
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200, r.text

        r = client.post("/api/admin/seed-hospital-scale")
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True

        with Session(engine) as session:
            rooms = session.exec(select(Room)).all()
            theatre_rooms = [r for r in rooms if r.room_type == "theatre"]
            room_names = {r.name for r in rooms}
            staff = session.exec(select(StaffMember)).all()
            procedures = session.exec(select(ProcedureType)).all()
            blocks = session.exec(select(ScheduleBlock)).all()
            stays = session.exec(select(InpatientStay)).all()
            obs = session.exec(select(ObservationTask)).all()
            meds = session.exec(select(MedicationDue)).all()
            handovers = session.exec(select(NightHandover)).all()
            finance = session.exec(select(FinancialConsentStatus)).all()

            assert len(theatre_rooms) >= 11, f"Expected at least 11 theatres, found {len(theatre_rooms)}"
            for required in ["MRI", "CT", "X-ray", "Ultrasound", "Dispensary", "Controlled Drug Cabinet", "Cold Chain Fridge", "Insurance / Estimate Desk", "ICU Bay 1", "High Dependency Ward", "Surgical Ward"]:
                assert required in room_names, f"Missing required room: {required}"
            assert len(staff) >= 20, f"Expected hospital-scale staff, found {len(staff)}"
            assert len(procedures) >= 20, f"Expected procedure catalogue seeded, found {len(procedures)}"
            assert len(blocks) >= 30, f"Expected schedule chain blocks, found {len(blocks)}"
            assert len(stays) >= 6, f"Expected overnight inpatient stays, found {len(stays)}"
            assert len(obs) >= 20, f"Expected timed overnight observations, found {len(obs)}"
            assert len(meds) >= 10, f"Expected medication due rows, found {len(meds)}"
            assert len(handovers) >= 6, f"Expected night handovers, found {len(handovers)}"
            assert len(finance) >= 6, f"Expected finance/insurance statuses, found {len(finance)}"

        r = client.get("/api/overnight-board")
        assert r.status_code == 200, r.text
        board = r.json()
        assert board["summary"]["active_inpatients"] >= 6
        assert board["summary"]["unacknowledged_handovers"] >= 1
        assert board["summary"]["finance_or_insurance_blocks"] >= 1
        assert len(board["room_groups"]) >= 4
        print("Overnight board OK")

        r = client.get("/api/overnight-grid")
        assert r.status_code == 200, r.text
        grid = r.json()
        assert grid["basis"] == "15-minute overnight inpatient grid"
        assert len(grid["slots"]) == 48
        assert any(slot["observation_tasks"] or slot["medications_due"] for slot in grid["slots"]), "Overnight grid has no timed work"
        print("15-minute overnight grid OK")

        r = client.get("/api/dashboard/intelligence")
        assert r.status_code == 200, r.text
        dashboard = r.json()
        assert dashboard["summary"]["rooms"] >= 40
        assert dashboard["summary"]["schedule_blocks"] >= 30
        print("Dashboard sees hospital-scale rooms and schedule blocks OK")

    print("\n--- HOSPITAL SCALE / OVERNIGHT TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
