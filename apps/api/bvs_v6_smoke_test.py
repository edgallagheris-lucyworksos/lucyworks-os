import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_bvs_v6_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_JWT_SECRET": "bvs-v6-smoke-secret-long-enough-for-testing",
    "AUTH_ISSUER": "lucyworks-bvs-v6-smoke",
    "AUTH_AUDIENCE": "lucyworks-bvs-v6-api",
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


try:
    with TestClient(app) as client:
        ops = login(client, 1)
        clinician = login(client, 3)
        admin = login(client, 4)

        unauthenticated = client.get("/api/bvs-v6/dashboard")
        assert unauthenticated.status_code == 401, unauthenticated.text

        denied = client.post("/api/bvs-v6/bootstrap", headers=clinician)
        assert denied.status_code == 403, denied.text

        seeded = client.post("/api/bvs-v6/bootstrap", headers=ops)
        assert seeded.status_code == 200, seeded.text
        created = seeded.json()["created"]
        assert created["configuration"] >= 10
        assert created["claims"] >= 3
        assert created["tasks"] >= 10
        print("BVS draft configuration, claims and verification queue seeded")

        dashboard = client.get("/api/bvs-v6/dashboard", headers=ops)
        assert dashboard.status_code == 200, dashboard.text
        data = dashboard.json()
        theatre_claims = [item for item in data["claims"] if item["fieldName"] == "operatingTheatreCount"]
        assert {item["claimedValue"] for item in theatre_claims} == {5, 11}
        assert data["summary"]["disputedClaims"] == 2
        assert data["summary"]["shadowEligible"] is False
        print("Conflicting theatre evidence preserved without overwriting configuration")

        task = next(item for item in data["verificationTasks"] if item["taskRef"] == "facilities.theatres")
        stale = client.patch(
            f"/api/bvs-v6/verification-tasks/{task['taskRef']}",
            headers=ops,
            json={"expectedVersion": task["version"] + 1, "answer": "Five", "evidenceRefs": ["approved-room-register"], "status": "verified"},
        )
        assert stale.status_code == 409, stale.text
        answered = client.patch(
            f"/api/bvs-v6/verification-tasks/{task['taskRef']}",
            headers=ops,
            json={"expectedVersion": task["version"], "answer": "Five operational theatres confirmed", "evidenceRefs": ["approved-room-register-2026"], "status": "verified", "reason": "Facilities register reviewed"},
        )
        assert answered.status_code == 200, answered.text
        assert answered.json()["task"]["status"] == "verified"
        print("Verification task evidence and stale-write protection OK")

        profile = client.put(
            "/api/bvs-v6/workforce/nurse-icu-001",
            headers=ops,
            json={
                "displayName": "Synthetic ICU Nurse",
                "primaryRoleRef": "icu_ecc_nurse",
                "departmentRef": "emergency-critical-care",
                "gradeOrTrainingLevel": "senior_rvn",
                "contractedHoursWeekly": 37.5,
                "sourceStatus": "verified",
                "reason": "Synthetic test workforce record",
            },
        )
        assert profile.status_code == 200, profile.text
        competency = client.put(
            "/api/bvs-v6/workforce/nurse-icu-001/competencies/icu_monitoring/icu",
            headers=ops,
            json={"level": "independent", "status": "verified", "evidenceSummary": "Synthetic competency assessment passed", "reason": "Test evidence"},
        )
        assert competency.status_code == 200, competency.text
        coverage = client.get("/api/bvs-v6/coverage-assessment", headers=ops)
        assert coverage.status_code == 200, coverage.text
        icu = next(item for item in coverage.json()["results"] if item["requirement"]["requirementRef"] == "coverage.icu.nurse.24h")
        assert icu["status"] == "met", icu
        assert any(item["status"] == "gap" for item in coverage.json()["results"])
        print("Workforce, competency evidence and coverage pool assessment OK")

        referral = client.post(
            "/api/bvs-v6/referrals",
            headers=clinician,
            json={
                "urgency": "urgent",
                "referringPractice": "Synthetic Primary Care",
                "patientName": "Anon Dog",
                "species": "Dog",
                "ownerName": "Anon Owner",
                "presentingProblem": "Progressive neurological signs",
            },
        )
        assert referral.status_code == 200, referral.text
        referral_data = referral.json()["referral"]
        assert referral_data["status"] == "information_requested"
        assert "clinicalHistory" in referral_data["missingInformation"]

        decision_denied = client.patch(
            f"/api/bvs-v6/referrals/{referral_data['referralRef']}/transition",
            headers=clinician,
            json={"expectedVersion": referral_data["version"], "status": "accepted", "decisionReason": "Accept"},
        )
        assert decision_denied.status_code == 403, decision_denied.text

        updated = client.patch(
            f"/api/bvs-v6/referrals/{referral_data['referralRef']}/information",
            headers=clinician,
            json={
                "expectedVersion": referral_data["version"],
                "historySummary": "Anonymised history supplied",
                "requestedServiceRef": "neurology-neurosurgery",
                "requiredInformation": {"patientAndOwner": True, "clinicalHistory": True, "presentingProblem": True, "referringPractice": True, "requestedService": True},
                "reason": "Referring practice supplied missing history and requested service",
            },
        )
        assert updated.status_code == 200, updated.text
        ready = updated.json()["referral"]
        assert ready["status"] == "ready_for_clinical_review"
        accepted = client.patch(
            f"/api/bvs-v6/referrals/{ready['referralRef']}/transition",
            headers=admin,
            json={"expectedVersion": ready["version"], "status": "accepted", "decision": "accept", "decisionReason": "Accepted for specialist review"},
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["referral"]["status"] == "accepted"
        print("Referral completeness, authority boundary and controlled transition OK")

        timestamp = datetime.now(timezone.utc).isoformat()
        failed_replay = client.post(
            "/api/bvs-v6/historical-replays",
            headers=ops,
            json={
                "sourceDate": datetime.now(timezone.utc).date().isoformat(),
                "dataClassification": "anonymised",
                "events": [{"eventRef": "missed-1", "occurredAt": timestamp, "eventType": "capacity", "areaRef": "icu", "payload": {"occupied": 6, "safeCapacity": 4, "expectedAlert": True, "lucyworksDetected": False}}],
            },
        )
        assert failed_replay.status_code == 200, failed_replay.text
        assert failed_replay.json()["replay"]["status"] == "failed"
        assert failed_replay.json()["replay"]["metrics"]["missedAlerts"] == 1

        passed_replay = client.post(
            "/api/bvs-v6/historical-replays",
            headers=ops,
            json={
                "sourceDate": datetime.now(timezone.utc).date().isoformat(),
                "dataClassification": "anonymised",
                "events": [{"eventRef": "detected-1", "occurredAt": timestamp, "eventType": "delay", "areaRef": "mri", "payload": {"expectedAlert": True, "lucyworksDetected": True, "decisionLatencyMinutes": 5}}],
            },
        )
        assert passed_replay.status_code == 200, passed_replay.text
        assert passed_replay.json()["replay"]["status"] == "passed"
        print("Historical replay detects missed alerts and records passing runs")

        final = client.get("/api/bvs-v6/dashboard", headers=ops).json()
        assert final["summary"]["passedReplays"] == 1
        assert final["summary"]["shadowEligible"] is False
        print("Shadow mode correctly remains blocked by unresolved hospital verification")

    print("\n--- BVS CONFIGURATION WORKFORCE REFERRALS V6 SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
