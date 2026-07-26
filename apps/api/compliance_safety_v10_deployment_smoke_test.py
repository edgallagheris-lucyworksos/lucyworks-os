from __future__ import annotations

import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_compliance_deployment_v10_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "compliance-deployment-v10-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-compliance-deployment-v10",
    "AUTH_AUDIENCE": "lucyworks-compliance-deployment-v10-api",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from app.database import engine
from app.main import app
from app.models import User

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def approved_readiness_evidence(client: TestClient, auth: dict[str, str], control_ref: str) -> str:
    evidence = client.post(f"/api/production-readiness/controls/{control_ref}/evidence", headers=auth, json={
        "evidenceType": "deployment_assurance",
        "summary": f"Synthetic proof for {control_ref}",
        "sourceRef": f"test:{control_ref}",
        "payload": {"controlRef": control_ref, "test": True},
    })
    assert evidence.status_code == 200, evidence.text
    evidence_ref = evidence.json()["evidence"]["evidenceRef"]
    passed = client.patch(f"/api/production-readiness/controls/{control_ref}", headers=auth, json={
        "expectedVersion": 2,
        "status": "passed",
        "evidenceSummary": f"Synthetic deployment assurance passed for {control_ref}",
        "reason": "Exercise evidence binding and release controls",
        "validDays": 30,
    })
    assert passed.status_code == 200, passed.text
    return evidence_ref


try:
    with Session(engine) as session:
        session.add_all([
            User(id=1, name="Gina Governance", role="governance_lead", email="governance@example.test"),
            User(id=2, name="Cleo Clinical Director", role="clinical_director", email="clinical@example.test"),
        ])
        session.commit()

    with TestClient(app) as client:
        governance = login(client, 1)
        clinical = login(client, 2)

        ready_bootstrap = client.post("/api/production-readiness/bootstrap", headers=governance)
        assert ready_bootstrap.status_code == 200, ready_bootstrap.text
        assurance_bootstrap = client.post("/api/v10/compliance-safety/bootstrap", headers=governance)
        assert assurance_bootstrap.status_code == 200, assurance_bootstrap.text
        profile = assurance_bootstrap.json()["deploymentProfile"]
        case_ref = assurance_bootstrap.json()["safetyCase"]["safetyCaseRef"]

        tick_boxes = client.patch(f"/api/v10/compliance-safety/deployment-profile/{profile['profileRef']}", headers=governance, json={
            "expectedVersion": profile["version"],
            "target": "live",
            "dataMode": "live",
            "identityMode": "oidc",
            "vendorMode": "connected",
            "realIdentityConfirmed": True,
            "realDataGovernanceConfirmed": True,
            "realVendorConnectionsConfirmed": True,
            "clinicalSafetyOfficerConfirmed": True,
            "dpiaApproved": True,
            "penetrationTestConfirmed": True,
            "staffUatConfirmed": True,
            "reason": "Bare confirmations must not pass a live release",
        })
        assert tick_boxes.status_code == 200, tick_boxes.text
        tick_body = tick_boxes.json()
        assert tick_body["gate"]["canRelease"] is False
        blocker_codes = {item["code"] for item in tick_body["gate"]["blockers"]}
        assert "deployment_organisation" in blocker_codes
        assert "real_identity_evidence" in blocker_codes
        assert "target_safety_review" in blocker_codes
        profile = tick_body["deploymentProfile"]

        arbitrary = client.patch(f"/api/v10/compliance-safety/deployment-profile/{profile['profileRef']}/evidence", headers=governance, json={
            "expectedVersion": profile["version"],
            "organisationName": "Synthetic Deployment Organisation",
            "identityEvidenceRef": "made-up-evidence",
            "reason": "Arbitrary evidence references must be rejected",
        })
        assert arbitrary.status_code == 409, arbitrary.text

        controls = {
            "identityEvidenceRef": "identity.oidc",
            "dataGovernanceEvidenceRef": "data.retention",
            "vendorEvidenceRef": "integrations.mapping",
            "clinicalSafetyOfficerEvidenceRef": "incident.response",
            "dpiaEvidenceRef": "privacy.dpia",
            "penetrationTestEvidenceRef": "security.pen_test",
            "staffUatEvidenceRef": "uat.acceptance",
        }
        refs = {field: approved_readiness_evidence(client, governance, control_ref) for field, control_ref in controls.items()}

        bound = client.patch(f"/api/v10/compliance-safety/deployment-profile/{profile['profileRef']}/evidence", headers=governance, json={
            "expectedVersion": profile["version"],
            "organisationName": "Synthetic Deployment Organisation",
            **refs,
            "reason": "Bind each deployment confirmation to a passed readiness control",
        })
        assert bound.status_code == 200, bound.text
        bound_body = bound.json()
        assert bound_body["gate"]["canRelease"] is False
        bound_codes = {item["code"] for item in bound_body["gate"]["blockers"]}
        assert bound_codes == {"target_safety_review"}, bound_body

        before_review = client.get("/api/v10/compliance-safety/release-gate?target=live", headers=governance)
        assert before_review.status_code == 200, before_review.text
        assert before_review.json()["canRelease"] is False
        assert {item["code"] for item in before_review.json()["blockers"]} == {"target_safety_review"}

        review = client.post("/api/v10/compliance-safety/reviews", headers=clinical, json={
            "safetyCaseRef": case_ref,
            "reviewType": "target_release_review",
            "target": "live",
            "outcome": "approved_with_conditions",
            "findings": [{"code": "synthetic-proof", "status": "test-only", "detail": "This proves workflow logic, not a real hospital approval."}],
            "reason": "All control evidence gates passed in the synthetic deployment test",
        })
        assert review.status_code == 200, review.text
        assert review.json()["gate"]["canRelease"] is True, review.text

        after_review = client.get("/api/v10/compliance-safety/release-gate?target=live", headers=governance)
        assert after_review.status_code == 200, after_review.text
        assert after_review.json()["canRelease"] is True, after_review.text

        print("Deployment evidence binding and target safety-review separation v10 OK")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
