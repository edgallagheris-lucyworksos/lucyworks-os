from __future__ import annotations

import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_compliance_safety_v10_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "compliance-safety-v10-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-compliance-safety-v10",
    "AUTH_AUDIENCE": "lucyworks-compliance-safety-v10-api",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.compliance_safety_models import DeploymentProfileV10, SafetyCaseV10, SafetyHazardV10
from app.database import engine
from app.main import app
from app.models import User

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


try:
    with Session(engine) as session:
        session.add_all([
            User(id=1, name="Ari Admin", role="admin", email="admin@example.test"),
            User(id=2, name="Cleo Clinical Director", role="clinical_director", email="clinical@example.test"),
            User(id=3, name="Gina Governance", role="governance_lead", email="governance@example.test"),
            User(id=4, name="Hugo Hospital Director", role="hospital_director", email="director@example.test"),
        ])
        session.commit()

    with TestClient(app) as client:
        admin = login(client, 1)
        clinical = login(client, 2)
        governance = login(client, 3)

        bootstrap = client.post("/api/v10/compliance-safety/bootstrap", headers=admin)
        assert bootstrap.status_code == 200, bootstrap.text
        boot = bootstrap.json()
        assert boot["hazards"] == 19, boot
        assert boot["deploymentProfile"]["status"] == "synthetic_ready", boot
        assert boot["syntheticGate"]["canRelease"] is True, boot

        baseline = client.get("/api/v10/compliance-safety/baseline", headers=governance)
        assert baseline.status_code == 200, baseline.text
        body = baseline.json()
        assert body["baselineId"] == "uk-veterinary-compliance-safety-v10"
        statuses = {row["code"] for row in body["sourceStatuses"]}
        assert {"law_in_force", "binding_professional_duty", "draft_future_requirement", "government_policy_proposal", "best_practice_adaptation"} <= statuses
        obligations = {row["code"]: row for row in body["obligations"]}
        assert obligations["MED-001"]["status"] == "law_in_force"
        assert obligations["CMA-001"]["status"] == "draft_future_requirement"
        assert obligations["SAFE-001"]["status"] == "best_practice_adaptation"
        assert len(body["identityGroups"]) >= 10
        assert len(body["vendorContracts"]) == 6
        assert body["dpia"]["status"] == "draft_baseline_requires_controller_approval"

        cma = client.get("/api/v10/compliance-safety/baseline?status=draft_future_requirement", headers=governance)
        assert cma.status_code == 200, cma.text
        assert {row["code"] for row in cma.json()["obligations"]} == {"CMA-001", "CMA-002", "CMA-003", "CMA-004"}

        safety_case = client.get("/api/v10/compliance-safety/safety-case", headers=clinical)
        assert safety_case.status_code == 200, safety_case.text
        case_body = safety_case.json()
        assert len(case_body["hazards"]) == 19
        assert max(item["residualRisk"] for item in case_body["hazards"]) < 16
        case_ref = case_body["safetyCase"]["safetyCaseRef"]
        hazard = next(item for item in case_body["hazards"] if item["code"] == "HZ-001")

        stale = client.patch(f"/api/v10/compliance-safety/hazards/{hazard['hazardRef']}", headers=clinical, json={
            "expectedVersion": 999,
            "status": "verified",
            "residualSeverity": 5,
            "residualLikelihood": 1,
            "controls": hazard["controls"],
            "verification": hazard["verification"],
            "evidenceRefs": ["test:wrong-patient-negative"],
            "reason": "Stale write must be rejected",
        })
        assert stale.status_code == 409, stale.text

        unsafe_accept = client.patch(f"/api/v10/compliance-safety/hazards/{hazard['hazardRef']}", headers=clinical, json={
            "expectedVersion": hazard["version"],
            "status": "verified",
            "residualSeverity": 4,
            "residualLikelihood": 4,
            "controls": hazard["controls"],
            "verification": hazard["verification"],
            "evidenceRefs": [],
            "reason": "Risk 16 must not be accepted",
        })
        assert unsafe_accept.status_code == 409, unsafe_accept.text

        verified = client.patch(f"/api/v10/compliance-safety/hazards/{hazard['hazardRef']}", headers=clinical, json={
            "expectedVersion": hazard["version"],
            "status": "verified",
            "residualSeverity": 5,
            "residualLikelihood": 1,
            "controls": hazard["controls"],
            "verification": hazard["verification"],
            "evidenceRefs": ["test:wrong-patient-negative", "test:duplicate-name-scenario"],
            "reason": "Synthetic negative tests passed",
        })
        assert verified.status_code == 200, verified.text
        assert verified.json()["hazard"]["status"] == "verified"

        synthetic_gate = client.get("/api/v10/compliance-safety/release-gate?target=synthetic", headers=admin)
        assert synthetic_gate.status_code == 200, synthetic_gate.text
        assert synthetic_gate.json()["canRelease"] is True

        historical_gate = client.get("/api/v10/compliance-safety/release-gate?target=historical_replay", headers=admin)
        assert historical_gate.status_code == 200, historical_gate.text
        assert historical_gate.json()["canRelease"] is True

        shadow_gate = client.get("/api/v10/compliance-safety/release-gate?target=shadow", headers=governance)
        assert shadow_gate.status_code == 200, shadow_gate.text
        shadow_body = shadow_gate.json()
        assert shadow_body["canRelease"] is False
        shadow_codes = {item["code"] for item in shadow_body["blockers"]}
        assert {"real_identity", "data_governance", "vendor_connections", "clinical_safety_officer", "dpia_approval"} <= shadow_codes

        live_gate = client.get("/api/v10/compliance-safety/release-gate?target=live", headers=governance)
        assert live_gate.status_code == 200, live_gate.text
        assert live_gate.json()["canRelease"] is False
        live_codes = {item["code"] for item in live_gate.json()["blockers"]}
        assert {"penetration_test", "staff_uat"} <= live_codes

        profile_response = client.get("/api/v10/compliance-safety/deployment-profile", headers=admin)
        assert profile_response.status_code == 200, profile_response.text
        profile = profile_response.json()["deploymentProfile"]
        assert profile["target"] == "synthetic"
        assert profile_response.json()["gates"]["synthetic"]["canRelease"] is True
        assert profile_response.json()["gates"]["live"]["canRelease"] is False

        review = client.post("/api/v10/compliance-safety/reviews", headers=clinical, json={
            "safetyCaseRef": case_ref,
            "reviewType": "developer_safety_baseline",
            "target": "synthetic",
            "outcome": "approved",
            "findings": [{"code": "scope-boundary", "status": "accepted", "detail": "No live hospital approval claimed"}],
            "reason": "Synthetic release gate and baseline hazard controls passed",
        })
        assert review.status_code == 200, review.text
        assert review.json()["safetyCase"]["approvedForTarget"] == "synthetic"

        prohibited_live_review = client.post("/api/v10/compliance-safety/reviews", headers=clinical, json={
            "safetyCaseRef": case_ref,
            "reviewType": "live_release",
            "target": "live",
            "outcome": "approved",
            "findings": [],
            "reason": "This must remain blocked without deployment evidence",
        })
        assert prohibited_live_review.status_code == 409, prohibited_live_review.text

        summary = client.get("/api/v10/compliance-safety/summary", headers=governance)
        assert summary.status_code == 200, summary.text
        assert summary.json()["hazards"]["total"] == 19
        assert summary.json()["gates"]["synthetic"]["canRelease"] is True
        assert summary.json()["gates"]["live"]["canRelease"] is False

    with TestClient(app) as anonymous:
        denied = anonymous.get("/api/v10/compliance-safety/baseline")
        assert denied.status_code == 401, denied.text

    with Session(engine) as session:
        assert session.exec(select(SafetyCaseV10)).first() is not None
        assert len(session.exec(select(SafetyHazardV10)).all()) == 19
        assert session.exec(select(DeploymentProfileV10)).first().status == "synthetic_ready"

    print("UK veterinary compliance baseline, safety case, hazard log and release gates v10 OK")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
