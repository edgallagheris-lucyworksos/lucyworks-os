import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_automation_v22_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "automation-v22-smoke-secret-long-enough-for-testing",
    "AUTH_ISSUER": "lucyworks-automation-v22-smoke",
    "AUTH_AUDIENCE": "lucyworks-automation-v22-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.clinical_execution_models import ClinicalObservation
from app.control_plane_models import CriticalResultAcknowledgement
from app.database import engine
from app.event_driven_automation_v22_models import AutomationRuntimeConfigV22, AutomationTriggerV22
from app.event_driven_automation_v22_service import dispatch_source
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock
from app.main import app
from app.models import User, WorkItem
from app.operational_automation_v20_models import AutomationDecisionV20

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    session.add(User(id=901, name="V22 Supervisor", role="supervisor", email="v22-supervisor@example.test"))
    session.add(User(id=902, name="V22 Clinician", role="clinician", email="v22-clinician@example.test"))
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


def set_config(client: TestClient, headers: dict[str, str], *, mode: str, expected_version: int | None):
    body = {
        "mode": mode,
        "enabledTriggerTypes": ["observation", "critical_result", "evidence_gap", "operational_delay"],
        "serviceSubject": "lucyworks:v22-clinical-service",
        "serviceName": "LucyWorks v22 clinical automation",
        "serviceRole": "senior_clinician",
        "backgroundScanEnabled": False,
        "scanIntervalSeconds": 60,
    }
    if expected_version is not None:
        body["expectedVersion"] = expected_version
    return ok(client.put(
        "/api/v22/automation/config/reference-site",
        headers=headers,
        json=body,
    ), f"set {mode} configuration")


def trigger_for(source_type: str, source_ref: str, mode: str) -> AutomationTriggerV22:
    with Session(engine) as session:
        row = session.exec(
            select(AutomationTriggerV22)
            .where(AutomationTriggerV22.source_type == source_type)
            .where(AutomationTriggerV22.source_ref == source_ref)
            .where(AutomationTriggerV22.mode == mode)
        ).first()
        assert row, (source_type, source_ref, mode)
        return row


try:
    with TestClient(app) as client:
        supervisor = login(client, 901)
        clinician = login(client, 902)

        created_config = set_config(client, supervisor, mode="disabled", expected_version=None)
        assert created_config["configuration"]["version"] == 1

        episode_a = ok(client.post(
            "/api/hospital-ops/episodes",
            headers=clinician,
            json={
                "episodeRef": "EP-AUTO-V22-A",
                "patientRef": "PAT-AUTO-V22-A",
                "patientName": "Bramble Event Automation",
                "premisesRef": "reference-site",
                "serviceLine": "neurology",
                "urgency": "urgent",
                "gates": {},
            },
        ), "create source episode A")["episode"]
        assert episode_a["version"] == 1
        disabled_episode_trigger = trigger_for("evidence_gap", "EP-AUTO-V22-A", "disabled")
        assert disabled_episode_trigger.status == "skipped"
        assert disabled_episode_trigger.decision_ref is None

        disabled_observation = ok(client.post(
            "/api/clinical-execution/observations",
            headers=clinician,
            json={
                "episode_ref": "EP-AUTO-V22-A",
                "area_ref": "consult-1",
                "observation_type": "temperature",
                "values": {"celsius": 38.1},
                "concern_level": "green",
                "reason": "Control observation recorded while automation is disabled",
            },
        ), "record disabled-mode observation")["observation"]
        disabled_ref = disabled_observation["observationRef"]
        assert trigger_for("observation", disabled_ref, "disabled").status == "skipped"

        preview_config = set_config(client, supervisor, mode="preview_only", expected_version=1)
        assert preview_config["configuration"]["version"] == 2

        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent = list(pool.map(
                lambda _: dispatch_source("observation", disabled_ref),
                range(2),
            ))
        assert len({row.trigger_ref for row in concurrent}) == 1
        preview_green = trigger_for("observation", disabled_ref, "preview_only")
        assert preview_green.status == "no_action"
        with Session(engine) as session:
            unique_preview_rows = session.exec(
                select(AutomationTriggerV22)
                .where(AutomationTriggerV22.source_type == "observation")
                .where(AutomationTriggerV22.source_ref == disabled_ref)
                .where(AutomationTriggerV22.mode == "preview_only")
            ).all()
            assert len(unique_preview_rows) == 1

        amber = ok(client.post(
            "/api/clinical-execution/observations",
            headers=clinician,
            json={
                "episode_ref": "EP-AUTO-V22-A",
                "area_ref": "consult-1",
                "observation_type": "heart_rate",
                "values": {"beatsPerMinute": 154},
                "concern_level": "amber",
                "reason": "Amber observation for automatic preview proof",
            },
        ), "record preview-mode amber observation")["observation"]
        amber_ref = amber["observationRef"]
        amber_trigger = trigger_for("observation", amber_ref, "preview_only")
        assert amber_trigger.status == "previewed"
        assert amber_trigger.decision_outcome == "previewed"
        assert amber_trigger.work_item_ids == []

        governed_config = set_config(client, supervisor, mode="governed_commit", expected_version=2)
        assert governed_config["configuration"]["version"] == 3

        red = ok(client.post(
            "/api/clinical-execution/observations",
            headers=clinician,
            json={
                "episode_ref": "EP-AUTO-V22-A",
                "area_ref": "consult-1",
                "observation_type": "respiratory_rate",
                "values": {"breathsPerMinute": 58},
                "concern_level": "red",
                "reason": "Red observation must create accountable review work automatically",
            },
        ), "record governed red observation")["observation"]
        red_ref = red["observationRef"]
        red_trigger = trigger_for("observation", red_ref, "governed_commit")
        assert red_trigger.status == "completed"
        assert len(red_trigger.work_item_ids) == 1
        replay = ok(client.post(
            "/api/v22/automation/dispatch",
            headers=supervisor,
            json={"sourceType": "observation", "sourceRef": red_ref},
        ), "replay recorded red observation")["trigger"]
        assert replay["trigger_ref"] == red_trigger.trigger_ref
        assert replay["work_item_ids"] == red_trigger.work_item_ids

        diagnostic = ok(client.post(
            "/api/clinical-execution/diagnostics",
            headers=clinician,
            json={
                "episode_ref": "EP-AUTO-V22-A",
                "modality": "laboratory",
                "requested_test": "potassium",
                "urgency": "urgent",
                "assigned_service": "laboratory",
            },
        ), "create diagnostic request")["workItem"]
        diagnostic_ref = diagnostic["workRef"]
        ok(client.patch(
            f"/api/clinical-execution/diagnostics/{diagnostic_ref}",
            headers=clinician,
            json={
                "expected_version": 1,
                "status": "reported",
                "report_summary": "Synthetic critical potassium result",
                "critical_result": True,
                "reason": "Critical result recorded through the normal diagnostic route",
            },
        ), "record critical diagnostic result")
        critical_trigger = trigger_for("critical_result", diagnostic_ref, "governed_commit")
        assert critical_trigger.status == "completed"
        assert len(critical_trigger.work_item_ids) == 1

        episode_b = ok(client.post(
            "/api/hospital-ops/episodes",
            headers=clinician,
            json={
                "episodeRef": "EP-AUTO-V22-B",
                "patientRef": "PAT-AUTO-V22-B",
                "patientName": "Moss Evidence Automation",
                "premisesRef": "reference-site",
                "serviceLine": "surgery",
                "urgency": "urgent",
                "gates": {"consent": "missing", "estimate": "pending", "handover": "pending"},
            },
        ), "create episode with stored evidence gaps")["episode"]
        evidence_trigger = trigger_for("evidence_gap", "EP-AUTO-V22-B", "governed_commit")
        assert evidence_trigger.status == "completed"
        assert len(evidence_trigger.work_item_ids) == 3

        ok(client.post(
            "/api/hospital-ops/bootstrap?premises_ref=reference-site",
            headers=supervisor,
        ), "bootstrap operational areas")
        now = datetime.now(timezone.utc)
        block = ok(client.post(
            "/api/hospital-ops/blocks",
            headers=clinician,
            json={
                "blockRef": "BLOCK-AUTO-V22-001",
                "premisesRef": "reference-site",
                "episodeRef": "EP-AUTO-V22-B",
                "procedureName": "MRI under anaesthesia",
                "blockType": "procedure",
                "areaRef": "mri",
                "startsAt": (now - timedelta(minutes=70)).isoformat(),
                "endsAt": (now + timedelta(minutes=20)).isoformat(),
                "status": "planned",
                "riskLevel": "amber",
                "reason": "Synthetic late-start block recorded through the normal board route",
            },
        ), "create delayed operational block")["block"]
        assert block["version"] == 1
        delay_trigger = trigger_for("operational_delay", "BLOCK-AUTO-V22-001", "governed_commit")
        assert delay_trigger.status == "completed"
        assert len(delay_trigger.work_item_ids) == 2

        generic_delay = client.post(
            "/api/v20/automation/evaluate",
            headers=supervisor,
            json={
                "episodeRef": "EP-AUTO-V22-B",
                "triggerType": "operational_delay",
                "triggerRef": "browser-delay-spoof",
                "facts": {"delayMinutes": 120, "detail": "Browser supplied delay"},
                "commitActions": True,
                "reason": "Generic browser delay commit must be rejected by v22",
            },
        )
        assert generic_delay.status_code == 409, generic_delay.text
        assert generic_delay.json()["detail"]["code"] == "recorded_source_required"

        dry_run = ok(client.get(
            "/api/v22/automation/episodes/EP-AUTO-V22-B/dry-run",
            headers=clinician,
        ), "episode dry run")
        assert dry_run["workCreated"] is False
        assert dry_run["proposalCount"] >= 5

        with Session(engine) as session:
            config = session.exec(
                select(AutomationRuntimeConfigV22).where(
                    AutomationRuntimeConfigV22.premises_ref == "reference-site"
                )
            ).one()
            config.service_role = "ops_manager"
            session.add(config)
            session.commit()

        failed_source = ok(client.post(
            "/api/clinical-execution/observations",
            headers=clinician,
            json={
                "episode_ref": "EP-AUTO-V22-A",
                "area_ref": "consult-1",
                "observation_type": "blood_pressure",
                "values": {"systolic": 70},
                "concern_level": "red",
                "reason": "Source write must survive a deliberately invalid automation service role",
            },
        ), "record source despite automation service failure")["observation"]
        failed_ref = failed_source["observationRef"]
        failed_trigger = trigger_for("observation", failed_ref, "governed_commit")
        assert failed_trigger.status == "failed"
        assert failed_trigger.error_code in {"http_503", "automation_evaluation_failed"}

        integrity = ok(client.get("/api/evidence/integrity", headers=supervisor), "evidence integrity")
        assert integrity["ok"] is True, integrity

    with Session(engine) as session:
        observations = session.exec(select(ClinicalObservation)).all()
        critical_results = session.exec(select(CriticalResultAcknowledgement)).all()
        blocks = session.exec(select(OperationalBlock)).all()
        episodes = session.exec(select(CanonicalEpisodeState)).all()
        decisions = session.exec(select(AutomationDecisionV20)).all()
        triggers = session.exec(select(AutomationTriggerV22)).all()
        work = session.exec(select(WorkItem).where(WorkItem.source.startswith("automation-v20:"))).all()

        assert any(row.observation_ref == failed_ref for row in observations), "source observation was rolled back"
        assert any(row.result_ref == diagnostic_ref for row in critical_results)
        assert any(row.block_ref == "BLOCK-AUTO-V22-001" for row in blocks)
        assert {row.episode_ref for row in episodes} >= {"EP-AUTO-V22-A", "EP-AUTO-V22-B"}
        assert len({(row.source_type, row.source_ref, row.source_state_hash, row.mode) for row in triggers}) == len(triggers)
        assert any(row.status == "failed" for row in triggers)
        assert any(row.outcome == "previewed" for row in decisions)
        assert len(work) >= 7
        assert all(row.status in {"new", "in_progress", "done", "blocked"} for row in work)

        print("Event-driven automation v22 modes, outbox and source authority proof OK")
        print("Normal observation, diagnostic, episode and board writes triggered automation OK")
        print("Concurrent duplicate trigger delivery created one durable trigger OK")
        print("Automation failure remained visible and did not roll back the source record")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
