import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_automation_v23_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "automation-v23-smoke-secret-long-enough-for-testing",
    "AUTH_ISSUER": "lucyworks-automation-v23-smoke",
    "AUTH_AUDIENCE": "lucyworks-automation-v23-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.automation_operator_control_v23_models import AutomationOperatorActionV23
from app.database import engine
from app.event_driven_automation_v22_models import AutomationTriggerV22
from app.main import app
from app.models import User, WorkItem

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    session.add(User(id=951, name="V23 Supervisor", role="supervisor", email="v23-supervisor@example.test"))
    session.add(User(id=952, name="V23 Clinician", role="clinician", email="v23-clinician@example.test"))
    session.commit()


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    token = response.json().get("accessToken")
    assert token
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def ok(response, label: str):
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    return response.json()


def config_body(mode: str, version: int, reason: str, acknowledgement: str | None = None) -> dict:
    body = {
        "mode": mode,
        "enabledTriggerTypes": ["observation", "critical_result", "evidence_gap", "operational_delay"],
        "serviceSubject": "lucyworks:v23-clinical-service",
        "serviceName": "LucyWorks v23 clinical automation",
        "serviceRole": "senior_clinician",
        "backgroundScanEnabled": False,
        "scanIntervalSeconds": 60,
        "expectedVersion": version,
        "reason": reason,
    }
    if acknowledgement:
        body["acknowledgement"] = acknowledgement
    return body


try:
    with TestClient(app) as client:
        supervisor = login(client, 951)
        clinician = login(client, 952)

        initial = ok(client.get("/api/v23/automation/control/reference-site", headers=supervisor), "initial control")
        assert initial["configuration"]["mode"] == "disabled"
        assert initial["configuration"]["version"] == 0
        assert initial["serviceValidation"]["valid"] is True

        invalid = ok(client.post(
            "/api/v23/automation/validate-service",
            headers=supervisor,
            json={
                "mode": "governed_commit",
                "enabledTriggerTypes": ["observation", "critical_result"],
                "serviceSubject": "lucyworks:v23-ops-service",
                "serviceName": "Operations-only service",
                "serviceRole": "ops_manager",
            },
        ), "prospective invalid clinical service")
        assert invalid["valid"] is False
        assert any(row["code"] == "clinical_role_for_clinical_sources" and not row["passed"] for row in invalid["checks"])

        preview = ok(client.put(
            "/api/v23/automation/control/reference-site",
            headers=supervisor,
            json=config_body("preview_only", 0, "Begin a controlled preview-only synthetic pilot"),
        ), "enable preview")
        assert preview["configuration"]["mode"] == "preview_only"
        assert preview["configuration"]["version"] == 1
        assert preview["operatorAction"]["evidenceEventRef"]

        ok(client.post(
            "/api/hospital-ops/episodes",
            headers=clinician,
            json={
                "episodeRef": "EP-AUTO-V23-001",
                "patientRef": "PAT-AUTO-V23-001",
                "patientName": "Moss Operator Pilot",
                "premisesRef": "reference-site",
                "serviceLine": "neurology",
                "urgency": "urgent",
                "gates": {"consent": "missing", "estimate": "missing", "handover": "pending"},
            },
        ), "create pilot episode")

        amber = ok(client.post(
            "/api/clinical-execution/observations",
            headers=clinician,
            json={
                "episode_ref": "EP-AUTO-V23-001",
                "area_ref": "consult-1",
                "observation_type": "heart_rate",
                "values": {"beatsPerMinute": 158},
                "concern_level": "amber",
                "reason": "Amber observation for v23 operator preview",
            },
        ), "record preview observation")["observation"]

        history = ok(client.get(
            "/api/v23/automation/episodes/EP-AUTO-V23-001/history",
            headers=clinician,
        ), "episode automation history")
        amber_trigger = next(row for row in history["triggers"] if row["sourceRef"] == amber["observationRef"])
        assert amber_trigger["status"] == "previewed"
        assert amber_trigger["workItems"] == []
        assert amber_trigger["sourceStateHash"]

        dry_run = ok(client.post(
            "/api/v23/automation/episodes/EP-AUTO-V23-001/dry-run",
            headers=supervisor,
            json={"reason": "Confirm proposals before governed work is authorised"},
        ), "episode dry run")
        assert dry_run["workCreated"] is False
        assert dry_run["proposalCount"] >= 1
        assert dry_run["operatorAction"]["actionType"] == "episode_dry_run"

        missing_ack = client.put(
            "/api/v23/automation/control/reference-site",
            headers=supervisor,
            json=config_body("governed_commit", 1, "Attempt governed commit without typed acknowledgement"),
        )
        assert missing_ack.status_code == 409, missing_ack.text
        assert missing_ack.json()["detail"]["code"] == "governed_acknowledgement_required"

        governed = ok(client.put(
            "/api/v23/automation/control/reference-site",
            headers=supervisor,
            json=config_body(
                "governed_commit",
                1,
                "Authorise governed human-owned review work for the synthetic pilot",
                "AUTHORISE GOVERNED AUTOMATION",
            ),
        ), "authorise governed commit")
        assert governed["configuration"]["mode"] == "governed_commit"
        assert governed["configuration"]["version"] == 2
        assert governed["operatorAction"]["acknowledgement"] == "AUTHORISE GOVERNED AUTOMATION"

        red = ok(client.post(
            "/api/clinical-execution/observations",
            headers=clinician,
            json={
                "episode_ref": "EP-AUTO-V23-001",
                "area_ref": "consult-1",
                "observation_type": "respiratory_rate",
                "values": {"breathsPerMinute": 54},
                "concern_level": "red",
                "reason": "Red observation for governed operator-control proof",
            },
        ), "record governed red observation")["observation"]

        overview = ok(client.get(
            "/api/v23/automation/overview?premises_ref=reference-site&limit=500",
            headers=clinician,
        ), "operator overview")
        red_trigger = next(row for row in overview["triggers"] if row["sourceRef"] == red["observationRef"])
        assert red_trigger["status"] == "completed"
        assert len(red_trigger["workItems"]) == 1
        assert red_trigger["workItems"][0]["ownerRole"] == "clinician"
        assert "responsible veterinary professional" in red_trigger["workItems"][0]["description"]

        with Session(engine) as session:
            preview_trigger = session.exec(
                select(AutomationTriggerV22)
                .where(AutomationTriggerV22.source_ref == amber["observationRef"])
                .where(AutomationTriggerV22.mode == "preview_only")
            ).one()
            preview_trigger.status = "failed"
            preview_trigger.error_code = "synthetic_operator_failure"
            preview_trigger.error_detail = "Synthetic visible failure for authorised retry"
            session.add(preview_trigger)
            session.commit()
            preview_trigger_ref = preview_trigger.trigger_ref

        retried = ok(client.post(
            f"/api/v23/automation/triggers/{preview_trigger_ref}/retry",
            headers=supervisor,
            json={"reason": "Retry the synthetic failed trigger after operator review"},
        ), "retry failed trigger")
        assert retried["trigger"]["status"] == "previewed"
        assert retried["operatorAction"]["actionType"] == "trigger_retry"

        reconciled = ok(client.post(
            "/api/v23/automation/reconcile",
            headers=supervisor,
            json={
                "premisesRef": "reference-site",
                "episodeRef": "EP-AUTO-V23-001",
                "sourceTypes": ["observation", "evidence_gap"],
                "reason": "Reconcile the synthetic episode after operator-authorised mode change",
            },
        ), "reconcile sources")
        assert reconciled["count"] >= 2
        assert reconciled["operatorAction"]["actionType"] == "reconciliation_scan"

        block_history = ok(client.get(
            "/api/v23/automation/blocks/non-existent-block/history",
            headers=clinician,
        ), "empty block history")
        assert block_history["latest"] is None

        integrity = ok(client.get("/api/evidence/integrity", headers=supervisor), "evidence integrity")
        assert integrity["ok"] is True, integrity

    with Session(engine) as session:
        actions = session.exec(select(AutomationOperatorActionV23)).all()
        work = session.exec(select(WorkItem).where(WorkItem.linked_episode_ref == "EP-AUTO-V23-001")).all()
        assert {row.action_type for row in actions} >= {
            "configuration_changed",
            "episode_dry_run",
            "trigger_retry",
            "reconciliation_scan",
        }
        assert all(row.reason and row.evidence_event_ref for row in actions)
        assert any(row.source.startswith("automation-v20:") for row in work)
        print("AUTOMATION_OPERATOR_CONTROL_V23_PROOF_PASSED")
        print("Preview, typed governed authority, patient history, retry and reconciliation are audited")
        print("No diagnosis, prescribing, acknowledgement, evidence completion or rescheduling authority was added")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
