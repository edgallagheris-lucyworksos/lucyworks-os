import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_bvs_v6_rota_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_JWT_SECRET": "bvs-v6-rota-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-bvs-v6-rota-smoke",
    "AUTH_AUDIENCE": "lucyworks-bvs-v6-rota-api",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


try:
    with TestClient(app) as client:
        ops = login(client, 1)
        clinician = login(client, 3)

        assert client.post("/api/bvs-v6/bootstrap", headers=ops).status_code == 200
        profile = client.put(
            "/api/bvs-v6/workforce/nurse-icu-rota-001",
            headers=ops,
            json={
                "displayName": "Synthetic Rota ICU Nurse",
                "primaryRoleRef": "icu_ecc_nurse",
                "departmentRef": "emergency-critical-care",
                "maximumSafeHoursWeekly": 60,
                "sourceStatus": "verified",
                "reason": "Synthetic rota test profile",
            },
        )
        assert profile.status_code == 200, profile.text
        competency = client.put(
            "/api/bvs-v6/workforce/nurse-icu-rota-001/competencies/icu_monitoring/icu",
            headers=ops,
            json={"level": "independent", "status": "verified", "evidenceSummary": "Synthetic competency evidence"},
        )
        assert competency.status_code == 200, competency.text

        now = datetime.now(timezone.utc).replace(microsecond=0)
        previous_start = now - timedelta(hours=15)
        previous_end = now - timedelta(hours=7)
        current_start = now - timedelta(hours=1)
        current_end = now + timedelta(hours=7)

        denied = client.put(
            "/api/bvs-v6/rota/shifts/shift-denied",
            headers=clinician,
            json={"staffRef": "nurse-icu-rota-001", "departmentRef": "emergency-critical-care", "areaRef": "icu", "startsAt": iso(current_start), "endsAt": iso(current_end)},
        )
        assert denied.status_code == 403, denied.text

        previous = client.put(
            "/api/bvs-v6/rota/shifts/shift-previous",
            headers=ops,
            json={"staffRef": "nurse-icu-rota-001", "departmentRef": "emergency-critical-care", "areaRef": "icu", "startsAt": iso(previous_start), "endsAt": iso(previous_end), "status": "completed", "sourceStatus": "verified", "reason": "Synthetic previous shift"},
        )
        assert previous.status_code == 200, previous.text
        current = client.put(
            "/api/bvs-v6/rota/shifts/shift-current",
            headers=ops,
            json={"staffRef": "nurse-icu-rota-001", "departmentRef": "emergency-critical-care", "areaRef": "icu", "startsAt": iso(current_start), "endsAt": iso(current_end), "status": "active", "sourceStatus": "verified", "reason": "Synthetic active shift"},
        )
        assert current.status_code == 200, current.text
        current_data = current.json()["shift"]

        overlap = client.put(
            "/api/bvs-v6/rota/shifts/shift-overlap",
            headers=ops,
            json={"staffRef": "nurse-icu-rota-001", "departmentRef": "emergency-critical-care", "areaRef": "icu", "startsAt": iso(now), "endsAt": iso(now + timedelta(hours=4))},
        )
        assert overlap.status_code == 409, overlap.text

        stale = client.put(
            "/api/bvs-v6/rota/shifts/shift-current",
            headers=ops,
            json={"expectedVersion": current_data["version"] + 1, "status": "completed"},
        )
        assert stale.status_code == 409, stale.text

        assessment_url = f"/api/bvs-v6/rota/assessment?at={quote(iso(now))}&restThresholdHours=11"
        assessment = client.get(assessment_url, headers=ops)
        assert assessment.status_code == 200, assessment.text
        assessed = assessment.json()
        icu = next(item for item in assessed["requirements"] if item["requirement"]["requirementRef"] == "coverage.icu.nurse.24h")
        assert icu["status"] == "met", icu
        assert assessed["staffRisks"]["nurse-icu-rota-001"][0]["type"] == "short_rest"
        print("Active competent shift satisfies ICU coverage and short rest is surfaced")

        absence = client.put(
            "/api/bvs-v6/rota/availability/absence-current",
            headers=ops,
            json={"staffRef": "nurse-icu-rota-001", "startsAt": iso(now - timedelta(minutes=30)), "endsAt": iso(now + timedelta(hours=3)), "exceptionType": "sickness", "status": "approved", "sourceStatus": "verified", "detail": "Synthetic sickness exception"},
        )
        assert absence.status_code == 200, absence.text

        unavailable = client.get(assessment_url, headers=ops)
        assert unavailable.status_code == 200, unavailable.text
        unavailable_data = unavailable.json()
        icu_gap = next(item for item in unavailable_data["requirements"] if item["requirement"]["requirementRef"] == "coverage.icu.nurse.24h")
        assert icu_gap["status"] == "gap", icu_gap
        assert any("sickness" in item["reason"] for item in icu_gap["excluded"])
        assert unavailable_data["safeToOperate"] is False
        print("Approved sickness exception removes the person from live safe coverage")

        roster = client.get(f"/api/bvs-v6/rota?startsAt={quote(iso(now - timedelta(days=1)))}&endsAt={quote(iso(now + timedelta(days=1)))}", headers=ops)
        assert roster.status_code == 200, roster.text
        assert len(roster.json()["shifts"]) == 2
        assert len(roster.json()["availabilityExceptions"]) == 1
        print("Rota and availability register query OK")

    print("\n--- BVS V6 ROTA SAFE STAFFING SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
