import os
import tempfile
from datetime import date
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_operational_proof_v30_authority_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "operational-proof-v30-authority-secret",
    "AUTH_ISSUER": "lucyworks-v30-authority",
    "AUTH_AUDIENCE": "lucyworks-v30-authority-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
    "V26_CONTEXT_BOOTSTRAP_ENABLED": "false",
    "V27_CONFIGURATION_REQUIRED": "false",
    "V28_CONNECTION_CONTROL_REQUIRED": "false",
    "V29_PILOT_CONTROL_REQUIRED": "false",
    "V30_OPERATIONAL_PROOF_REQUIRED": "false",
})

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import SQLModel, Session

from app.database import engine
from app.main import app
from app.models import User

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)
with engine.begin() as connection:
    connection.execute(text("create table if not exists alembic_version (version_num varchar(64) not null)"))
    connection.execute(text("delete from alembic_version"))
    connection.execute(text("insert into alembic_version(version_num) values ('0024_operational_proof_v30')"))

with Session(engine) as session:
    session.add_all([
        User(id=3011, name="V30 Authority Director", role="clinical_director", email="v30-authority-director@example.test"),
        User(id=3012, name="V30 Authority Clinician", role="clinician", email="v30-authority-clinician@example.test"),
    ])
    session.commit()


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


base = {
    "organisationRef": "group-v30-authority",
    "siteRef": "hospital-v30-authority",
    "premisesRef": "premises-v30-authority",
    "operationalDate": date.today().isoformat(),
    "mode": "synthetic",
    "reason": "Authority boundary proof.",
}

try:
    with TestClient(app) as client:
        director = login(client, 3011)
        clinician = login(client, 3012)

        unauthenticated = client.get("/api/v30/operational-proof/contract")
        assert unauthenticated.status_code == 401, unauthenticated.text

        role_denied = client.post("/api/v30/operational-proof/runs", headers=clinician, json=base)
        assert role_denied.status_code == 403, role_denied.text

        unknown_field = client.post(
            "/api/v30/operational-proof/runs",
            headers=director,
            json={**base, "silentlyApprove": True},
        )
        assert unknown_field.status_code == 422, unknown_field.text

        unsupported_mode = client.post(
            "/api/v30/operational-proof/runs",
            headers=director,
            json={**base, "mode": "production"},
        )
        assert unsupported_mode.status_code == 422, unsupported_mode.text

        created = client.post("/api/v30/operational-proof/runs", headers=director, json=base)
        assert created.status_code == 200, created.text
        run = created.json()["run"]
        run_ref = run["run_ref"]

        missing_episode = client.post(
            f"/api/v30/operational-proof/runs/{run_ref}/attach-episode",
            headers=director,
            json={
                "expectedVersion": run["version"],
                "episodeRef": "EP-DOES-NOT-EXIST",
                "reason": "Missing episode must not attach.",
            },
        )
        assert missing_episode.status_code == 404, missing_episode.text

        evaluate_unattached = client.post(
            f"/api/v30/operational-proof/runs/{run_ref}/evaluate",
            headers=director,
        )
        assert evaluate_unattached.status_code == 409, evaluate_unattached.text

        premature = client.post(
            f"/api/v30/operational-proof/runs/{run_ref}/complete",
            headers=director,
            json={"expectedVersion": run["version"], "reason": "Premature completion must fail."},
        )
        assert premature.status_code == 409, premature.text
        blockers = premature.json()["detail"]["blockers"]
        assert any("connected journey" in item for item in blockers)
        assert any("stress scenarios" in item for item in blockers)
        assert any("mobile" in item for item in blockers)

        unknown_scenario = client.post(
            f"/api/v30/operational-proof/runs/{run_ref}/scenarios/not_real",
            headers=director,
            json={
                "observed": {},
                "failureDetected": True,
                "accountableOwnerVisible": True,
                "nextActionVisible": True,
                "evidenceVisible": True,
                "urgentAccessPreserved": True,
                "reason": "Unknown scenario must fail.",
            },
        )
        assert unknown_scenario.status_code == 404, unknown_scenario.text

        unsafe_scenario = client.post(
            f"/api/v30/operational-proof/runs/{run_ref}/scenarios/emergency_full_schedule",
            headers=director,
            json={
                "observed": {"urgentAccess": "blocked"},
                "failureDetected": True,
                "accountableOwnerVisible": True,
                "nextActionVisible": True,
                "evidenceVisible": True,
                "urgentAccessPreserved": False,
                "reason": "Urgent access violation must make the scenario fail.",
            },
        )
        assert unsafe_scenario.status_code == 200, unsafe_scenario.text
        assert unsafe_scenario.json()["scenario"]["status"] == "blocked"
        run = unsafe_scenario.json()["run"]
        assert run["status"] == "blocked"

        bad_mobile = client.post(
            f"/api/v30/operational-proof/runs/{run_ref}/mobile-assessments",
            headers=clinician,
            json={
                "deviceLabel": "Unsafe narrow viewport",
                "operatingSystem": "Android",
                "browser": "Mobile browser",
                "viewportWidth": 240,
                "viewportHeight": 480,
                "secureContext": False,
                "online": True,
                "touchCapable": True,
                "microphoneAvailable": False,
                "checks": {"keyboardSafeSubmitControls": False},
                "manualHardwareConfirmation": False,
                "reason": "Unsafe device diagnostics must be recorded as failed.",
            },
        )
        assert bad_mobile.status_code == 200, bad_mobile.text
        assert bad_mobile.json()["assessment"]["status"] == "failed"
        assert bad_mobile.json()["manualActionRequired"] is True

        stale_complete = client.post(
            f"/api/v30/operational-proof/runs/{run_ref}/complete",
            headers=director,
            json={"expectedVersion": 1, "reason": "Stale completion must fail."},
        )
        assert stale_complete.status_code == 409, stale_complete.text
        assert stale_complete.json()["detail"]["message"] == "stale proof run"

        dashboard = client.get("/api/v30/operational-proof/dashboard", headers=clinician)
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["boundary"] == "Passing synthetic proof does not authorise real hospital deployment."

        print("OPERATIONAL_PROOF_V30_AUTHORITY_BOUNDARIES_PASSED")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
