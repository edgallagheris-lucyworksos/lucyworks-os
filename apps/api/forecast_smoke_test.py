import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_forecast_smoke_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient

from app.main import app

print("\n--- RUNNING HOSPITAL FORECAST SMOKE TEST ---\n")

try:
    with TestClient(app) as client:
        response = client.get("/api/forecast/hospital", params={"hours": 6, "slot_minutes": 60})
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["window"]["hours"] == 6
        assert data["window"]["slot_minutes"] == 60
        assert len(data["slots"]) == 6

        required_summary = {
            "rooms",
            "blocked_or_cleaning_rooms",
            "schedule_blocks",
            "active_inpatients",
            "active_occupancy",
            "open_discharge_blockers",
            "pending_results",
            "staff_risks",
            "obs_due",
            "meds_due",
            "red_slots",
            "amber_slots",
        }
        assert required_summary.issubset(data["summary"]), data["summary"]

        required_groups = {"theatre", "imaging", "ward", "icu", "recovery", "ecc"}
        assert required_groups.issubset(data["groups"]), data["groups"]
        assert all(slot["risk"] in {"green", "amber", "red"} for slot in data["slots"])
        assert all("capacity" in slot and "load" in slot and "ratios" in slot for slot in data["slots"])
        assert data["next_actions"]
        print("Hospital forecast shape, slots and risk contract OK")

        invalid_hours = client.get("/api/forecast/hospital", params={"hours": 0})
        assert invalid_hours.status_code == 422, invalid_hours.text
        invalid_slot = client.get("/api/forecast/hospital", params={"slot_minutes": 10})
        assert invalid_slot.status_code == 422, invalid_slot.text
        print("Hospital forecast parameter boundaries OK")

    print("\n--- HOSPITAL FORECAST SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
