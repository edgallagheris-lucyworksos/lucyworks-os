import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_recorded_automation_v21_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "recorded-automation-v21-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-recorded-automation-v21-smoke",
    "AUTH_AUDIENCE": "lucyworks-recorded-automation-v21-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.clinical_execution_models import ClinicalObservation, MedicationOrder
from app.control_plane_models import CriticalResultAcknowledgement
from app.database import engine
from app.detailed_hospital_models import ClinicalNoteV8
from app.hospital_command_models import EpisodeTransitionV9
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app
from app.models import WorkItem
from app.operational_automation_v20_models import AutomationDecisionV20

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)


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


def recorded_payload(*, commit: bool, reason: str, version=None, state_hash=None, **extra):
    payload = {"commitActions": commit, "reason": reason, **extra}
    if version is not None:
        payload["expectedVersion"] = version
    if state_hash is not None:
        payload["expectedStateHash"] = state_hash
    return payload


try:
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add(CanonicalEpisodeState(
            episode_ref="EP-REC-V21-001",
            patient_ref="PAT-REC-V21-001",
            patient_name="UAT Rowan Recorded 001",
            premises_ref="reference-site",
            service_line="neurology",
            urgency="urgent",
            phase="preparation",
            status="active",
            owner_role="clinician",
            owner_subject="local-user:3",
            current_area_ref="prep-1",
            next_action="Resolve recorded readiness gates",
            gates_json=json.dumps({
                "consent": "missing",
                "estimate": "pending",
                "handover": "pending",
            }),
            version=4,
        ))
        session.add(ClinicalObservation(
            observation_ref="OBS-REC-V21-001",
            episode_ref="EP-REC-V21-001",
            area_ref="prep-1",
            observation_type="neurological_status",
            values={"mentation": "deteriorated", "painScore": 8},
            concern_level="red",
            escalation_required=True,
            escalation_status="required",
            escalation_note="Recorded deterioration requires responsible clinician review",
            recorded_by_subject="local-user:3",
            recorded_by_name="Dr Local Clinician",
            recorded_at=now,
            version=3,
        ))
        session.add(CriticalResultAcknowledgement(
            result_ref="RESULT-REC-V21-001",
            patient_case_id="PAT-REC-V21-001",
            referral_episode_id="EP-REC-V21-001",
            result_type="potassium",
            severity="red",
            summary="Synthetic recorded critical potassium result",
            status="awaiting_acknowledgement",
            assigned_to="local-user:3",
            assigned_role="clinician",
            due_at=now - timedelta(minutes=25),
            created_at=now - timedelta(minutes=40),
        ))
        session.commit()

    with TestClient(app) as client:
        clinician = login(client, 3)
        admin = login(client, 4)

        generic_preview = ok(client.post(
            "/api/v20/automation/evaluate",
            headers=admin,
            json={
                "episodeRef": "EP-REC-V21-001",
                "triggerType": "observation",
                "triggerRef": "FAKE-BROWSER-OBS",
                "facts": {"concernLevel": "red", "detail": "Browser preview only"},
                "commitActions": False,
                "reason": "Generic facts remain available for non-committing preview",
            },
        ), "generic preview")
        assert generic_preview["decision"]["outcome"] == "previewed"
        assert generic_preview["workItems"] == []

        generic_commit = client.post(
            "/api/v20/automation/evaluate",
            headers=clinician,
            json={
                "episodeRef": "EP-REC-V21-001",
                "triggerType": "observation",
                "triggerRef": "FAKE-BROWSER-OBS",
                "facts": {"concernLevel": "red", "detail": "Attempted browser commit"},
                "commitActions": True,
                "reason": "Browser facts must not commit patient work",
            },
        )
        assert generic_commit.status_code == 409, generic_commit.text
        assert generic_commit.json()["detail"]["code"] == "recorded_source_required"

        override_attempt = client.post(
            "/api/v21/automation/observations/OBS-REC-V21-001/evaluate",
            headers=clinician,
            json=recorded_payload(
                commit=True,
                reason="Attempted browser override must be rejected",
                version=3,
                facts={"concernLevel": "green"},
            ),
        )
        assert override_attempt.status_code == 422, override_attempt.text

        observation_preview = ok(client.post(
            "/api/v21/automation/observations/OBS-REC-V21-001/evaluate",
            headers=clinician,
            json=recorded_payload(
                commit=False,
                reason="Preview the currently recorded observation state",
            ),
        ), "observation preview")
        assert observation_preview["proposals"][0]["urgency"] == "red"
        assert observation_preview["sourceAuthority"]["sourceVersion"] == 3
        assert observation_preview["sourceAuthority"]["factsAcceptedFromBrowser"] is False
        observation_hash = observation_preview["sourceAuthority"]["sourceStateHash"]

        stale_observation = client.post(
            "/api/v21/automation/observations/OBS-REC-V21-001/evaluate",
            headers=clinician,
            json=recorded_payload(
                commit=True,
                reason="A stale recorded observation version must fail",
                version=2,
                state_hash=observation_hash,
            ),
        )
        assert stale_observation.status_code == 409, stale_observation.text
        assert stale_observation.json()["detail"]["code"] == "source_version_conflict"

        observation_commit_payload = recorded_payload(
            commit=True,
            reason="Commit review work from the verified recorded observation",
            version=3,
            state_hash=observation_hash,
        )
        observation_commit = ok(client.post(
            "/api/v21/automation/observations/OBS-REC-V21-001/evaluate",
            headers=clinician,
            json=observation_commit_payload,
        ), "observation commit")
        assert len(observation_commit["workItems"]) == 1
        assert observation_commit["workItems"][0]["urgency"] == "red"
        assert "neurological_status" in observation_commit["workItems"][0]["description"]
        observation_work_id = observation_commit["workItems"][0]["id"]

        observation_replay = ok(client.post(
            "/api/v21/automation/observations/OBS-REC-V21-001/evaluate",
            headers=clinician,
            json={**observation_commit_payload, "reason": "Recorded observation replay must not duplicate work"},
        ), "observation replay")
        assert observation_replay["replayProtected"] is True
        assert [row["id"] for row in observation_replay["workItems"]] == [observation_work_id]

        result_preview = ok(client.post(
            "/api/v21/automation/critical-results/RESULT-REC-V21-001/evaluate",
            headers=clinician,
            json=recorded_payload(
                commit=False,
                reason="Preview the recorded critical-result state",
            ),
        ), "critical result preview")
        result_hash = result_preview["sourceAuthority"]["sourceStateHash"]
        assert result_preview["proposals"][0]["actionCode"] == "critical-result-overdue"

        stale_result = client.post(
            "/api/v21/automation/critical-results/RESULT-REC-V21-001/evaluate",
            headers=clinician,
            json=recorded_payload(
                commit=True,
                reason="A stale result state hash must fail",
                state_hash="0" * 64,
            ),
        )
        assert stale_result.status_code == 409, stale_result.text
        assert stale_result.json()["detail"]["code"] == "source_state_conflict"

        result_commit = ok(client.post(
            "/api/v21/automation/critical-results/RESULT-REC-V21-001/evaluate",
            headers=clinician,
            json=recorded_payload(
                commit=True,
                reason="Commit review work from the recorded overdue critical result",
                state_hash=result_hash,
            ),
        ), "critical result commit")
        assert len(result_commit["workItems"]) == 1
        assert result_commit["workItems"][0]["category"] == "critical_result_review"

        gates_preview = ok(client.post(
            "/api/v21/automation/episodes/EP-REC-V21-001/evidence-gaps/evaluate",
            headers=admin,
            json=recorded_payload(
                commit=False,
                reason="Preview evidence gaps from canonical episode gates",
            ),
        ), "gates preview")
        assert {row["actionCode"] for row in gates_preview["proposals"]} == {
            "evidence-gap-consent",
            "evidence-gap-estimate_authority",
            "evidence-gap-handover",
        }
        gates_hash = gates_preview["sourceAuthority"]["sourceStateHash"]

        gates_commit = ok(client.post(
            "/api/v21/automation/episodes/EP-REC-V21-001/evidence-gaps/evaluate",
            headers=admin,
            json=recorded_payload(
                commit=True,
                reason="Commit owned work from canonical stored evidence gaps",
                version=4,
                state_hash=gates_hash,
            ),
        ), "gates commit")
        assert len(gates_commit["workItems"]) == 3
        assert all(row["linked_episode_ref"] == "EP-REC-V21-001" for row in gates_commit["workItems"])

        history = ok(client.get(
            "/api/v20/automation/episodes/EP-REC-V21-001",
            headers=clinician,
        ), "automation history")
        assert len(history["decisions"]) == 8
        assert len(history["workItems"]) == 5

        integrity = ok(client.get("/api/evidence/integrity", headers=admin), "evidence integrity")
        assert integrity["ok"] is True, integrity

    with Session(engine) as session:
        work = session.exec(
            select(WorkItem).where(WorkItem.linked_episode_ref == "EP-REC-V21-001")
        ).all()
        decisions = session.exec(
            select(AutomationDecisionV20).where(
                AutomationDecisionV20.episode_ref == "EP-REC-V21-001"
            )
        ).all()
        episode = session.exec(
            select(CanonicalEpisodeState).where(
                CanonicalEpisodeState.episode_ref == "EP-REC-V21-001"
            )
        ).one()
        observation = session.exec(
            select(ClinicalObservation).where(
                ClinicalObservation.observation_ref == "OBS-REC-V21-001"
            )
        ).one()
        result = session.exec(
            select(CriticalResultAcknowledgement).where(
                CriticalResultAcknowledgement.result_ref == "RESULT-REC-V21-001"
            )
        ).one()
        notes = session.exec(select(ClinicalNoteV8)).all()
        medication_orders = session.exec(select(MedicationOrder)).all()
        transitions = session.exec(select(EpisodeTransitionV9)).all()

        assert len(work) == 5
        assert len({row.source for row in work}) == 5
        assert len(decisions) == 8
        assert episode.version == 4
        assert episode.phase == "preparation"
        assert observation.concern_level == "red"
        assert observation.version == 3
        assert result.status == "awaiting_acknowledgement"
        assert result.acknowledged_at is None
        assert notes == []
        assert medication_orders == []
        assert transitions == []

        print("Recorded-state automation v21 source-authority proof OK")
        print("Generic fact-based commits blocked; canonical observation, result and gates used")
        print("Stale source versions/hashes rejected and replay remained idempotent")
        print("No clinical note, medication order, acknowledgement or phase transition was created")

finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
