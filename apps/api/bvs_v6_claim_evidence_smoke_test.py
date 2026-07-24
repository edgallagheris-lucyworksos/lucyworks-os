import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_bvs_claim_evidence_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_JWT_SECRET": "bvs-claim-evidence-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-bvs-claim-evidence",
    "AUTH_AUDIENCE": "lucyworks-bvs-claim-evidence-api",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

try:
    with TestClient(app) as client:
        login = client.post("/api/auth/dev-login", json={"user_id": 1})
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
        assert client.post("/api/bvs-v6/bootstrap", headers=headers).status_code == 200
        dashboard = client.get("/api/bvs-v6/dashboard", headers=headers).json()
        claim = next(item for item in dashboard["claims"] if item["claimRef"] == "bvs-public-theatre-count-5")
        reviewed = client.patch(
            f"/api/bvs-v6/claims/{claim['claimRef']}",
            headers=headers,
            json={
                "expectedVersion": claim["version"],
                "status": "verified",
                "evidenceRef": "approved-facilities-register-2026",
                "notes": "Facilities register confirms the public claim",
                "reason": "Authorised facilities evidence reviewed",
            },
        )
        assert reviewed.status_code == 200, reviewed.text
        output = reviewed.json()["claim"]
        assert output["reviewEvidenceRefs"] == ["approved-facilities-register-2026"], output
        refreshed = client.get("/api/bvs-v6/dashboard", headers=headers).json()
        persisted = next(item for item in refreshed["claims"] if item["claimRef"] == claim["claimRef"])
        assert persisted["reviewEvidenceRefs"] == ["approved-facilities-register-2026"], persisted
        print("BVS claim review evidence is preserved separately from original source provenance")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
