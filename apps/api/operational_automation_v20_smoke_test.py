import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_automation_v20_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "automation-v20-smoke-secret-long-enough-for-testing",
    "AUTH_ISSUER": "lucyworks-automation-v20-smoke",
    "AUTH_AUDIENCE": "lucyworks-automation-v20-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.clinical_execution_models import MedicationOrder
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


def request(
    *,
    trigger_type: str,
    trigger_ref: str,
    facts: dict,
    commit: bool,
    reason: str,
) -> dict:
    return {
        "episodeRef": "EP-AUTO-V20-001",
        "patientRef": "SPOOFED-PATIENT-REF",
        "triggerType": trigger_type,
        "triggerRef": trigger_ref,
        "facts": facts,
        "commitActions": commit,
        "reason": reason,
    }


try:
    with Session(engine) as session:
        session.add(CanonicalEpisodeState(
            episode_ref="EP-AUTO-V20-001",
            patient_ref="PAT-AUTO-V20-001",
            patient_name="UAT Bramble Automation 001",
            premises_ref="reference-site",
            service_line="neurology",
            urgency="urgent",
            phase="consult",
            status="active",
            owner_role="clinician",
            owner_subject="local-user:3",
            current_area_ref="consult-1",
            next_action="Review current findings",
            version=1,
        ))
        session.commit()

    with TestClient(app) as client:
        anonymous = client.post("/api/v20/automation/evaluate", json=request(
            trigger_type="observation",
            trigger_ref="OBS-AUTO-V20-001",
            facts={"concernLevel": "red", "detail": "Synthetic red concern"},
            commit=False,
            reason="Anonymous preview must be rejected",
        ))
        assert anonymous.status_code == 401, anonymous.text

        clinician = login(client, 3)
        admin = login(client, 4)

        preview = ok(client.post(
            "/api/v20/automation/evaluate",
            headers=admin,
            json=request(
                trigger_type="observation",
                trigger_ref="OBS-AUTO-V20-001",
                facts={"concernLevel": "red", "detail": "Synthetic red concern"},
                commit=False,
                reason="Preview recorded concern before any work is created",
            ),
        ), "preview red observation")
        assert preview["decision"]["outcome"] == "previewed"
        assert preview["context"]["patientRef"] == "PAT-AUTO-V20-001"
        assert preview["workItems"] == []
        assert preview["proposals"][0]["urgency"] == "red"
        assert preview["proposals"][0]["humanAuthorityRequired"] is True

        forbidden = client.post(
            "/api/v20/automation/evaluate",
            headers=admin,
            json=request(
                trigger_type="observation",
                trigger_ref="OBS-AUTO-V20-001",
                facts={"concernLevel": "red", "detail": "Synthetic red concern"},
                commit=True,
                reason="Non-clinical role must not commit a clinical escalation",
            ),
        )
        assert forbidden.status_code == 403, forbidden.text

        observation_payload = request(
            trigger_type="observation",
            trigger_ref="OBS-AUTO-V20-001",
            facts={"concernLevel": "red", "detail": "Synthetic red concern"},
            commit=True,
            reason="Clinician confirms that accountable review work is required",
        )
        committed = ok(client.post(
            "/api/v20/automation/evaluate",
            headers=clinician,
            json=observation_payload,
        ), "commit red observation")
        assert committed["decision"]["outcome"] == "committed"
        assert committed["decision"]["committed"] is True
        assert committed["context"]["patientRef"] == "PAT-AUTO-V20-001"
        assert len(committed["workItems"]) == 1
        assert committed["workItems"][0]["urgency"] == "red"
        assert committed["workItems"][0]["owner_role"] == "clinician"
        assert committed["workItems"][0]["linked_episode_ref"] == "EP-AUTO-V20-001"
        observation_work_id = committed["workItems"][0]["id"]

        replayed = ok(client.post(
            "/api/v20/automation/evaluate",
            headers=clinician,
            json={**observation_payload, "reason": "Repeated delivery must return existing work without duplication"},
        ), "replay red observation")
        assert replayed["replayProtected"] is True
        assert replayed["decision"]["outcome"] == "replayed"
        assert [row["id"] for row in replayed["workItems"]] == [observation_work_id]

        critical = ok(client.post(
            "/api/v20/automation/evaluate",
            headers=clinician,
            json=request(
                trigger_type="critical_result",
                trigger_ref="RESULT-AUTO-V20-001",
                facts={
                    "critical": True,
                    "acknowledged": False,
                    "overdue": True,
                    "summary": "Synthetic critical potassium result",
                },
                commit=True,
                reason="Clinician confirms overdue critical-result review work",
            ),
        ), "commit critical result")
        assert len(critical["workItems"]) == 1
        assert critical["workItems"][0]["category"] == "critical_result_review"
        assert "acknowledge" in critical["workItems"][0]["description"].lower()

        delay = ok(client.post(
            "/api/v20/automation/evaluate",
            headers=admin,
            json=request(
                trigger_type="operational_delay",
                trigger_ref="BLOCK-AUTO-V20-001",
                facts={
                    "delayMinutes": 65,
                    "detail": "MRI overrun with downstream theatre dependency",
                },
                commit=True,
                reason="Operations confirms coordination and communication review are required",
            ),
        ), "commit operational delay")
        assert len(delay["workItems"]) == 2
        assert {row["owner_role"] for row in delay["workItems"]} == {"ops_manager", "clinician"}
        assert any("No schedule" in row["description"] for row in delay["workItems"])

        gaps = ok(client.post(
            "/api/v20/automation/evaluate",
            headers=admin,
            json=request(
                trigger_type="evidence_gap",
                trigger_ref="GATES-AUTO-V20-001",
                facts={"gaps": ["consent", "handover", "discharge"]},
                commit=True,
                reason="Recorded evidence gaps require accountable completion work",
            ),
        ), "commit evidence gaps")
        assert len(gaps["workItems"]) == 3
        assert {row["category"] for row in gaps["workItems"]} == {
            "consent_evidence",
            "handover",
            "discharge_evidence",
        }
        assert all(
            "cannot mark" in row["description"].lower() or "authorised" in row["description"].lower()
            for row in gaps["workItems"]
        )

        green = ok(client.post(
            "/api/v20/automation/evaluate",
            headers=clinician,
            json=request(
                trigger_type="observation",
                trigger_ref="OBS-AUTO-V20-002",
                facts={"concernLevel": "green", "detail": "Synthetic observation within recorded limits"},
                commit=True,
                reason="Green recorded observation requires no generated review work",
            ),
        ), "green observation")
        assert green["decision"]["outcome"] == "no_action"
        assert green["decision"]["committed"] is False
        assert green["workItems"] == []

        history = ok(client.get(
            "/api/v20/automation/episodes/EP-AUTO-V20-001",
            headers=clinician,
        ), "automation history")
        assert history["context"]["patientRef"] == "PAT-AUTO-V20-001"
        assert len(history["decisions"]) == 7
        assert len(history["workItems"]) == 7

        integrity = ok(client.get("/api/evidence/integrity", headers=admin), "evidence integrity")
        assert integrity["ok"] is True, integrity

    with Session(engine) as session:
        decisions = session.exec(select(AutomationDecisionV20)).all()
        work = session.exec(
            select(WorkItem).where(WorkItem.linked_episode_ref == "EP-AUTO-V20-001")
        ).all()
        episode = session.exec(
            select(CanonicalEpisodeState).where(
                CanonicalEpisodeState.episode_ref == "EP-AUTO-V20-001"
            )
        ).one()
        notes = session.exec(select(ClinicalNoteV8)).all()
        medication_orders = session.exec(select(MedicationOrder)).all()
        transitions = session.exec(select(EpisodeTransitionV9)).all()

        assert len(decisions) == 7
        assert len(work) == 7
        assert len({row.source for row in work}) == 7
        assert all(row.source.startswith("automation-v20:") for row in work)
        assert episode.patient_ref == "PAT-AUTO-V20-001"
        assert episode.phase == "consult"
        assert episode.version == 1
        assert notes == []
        assert medication_orders == []
        assert transitions == []

        print("Operational automation v20 preview, authority, idempotency and evidence proof OK")
        print("Observation, critical result, delay and evidence-gap work creation OK")
        print("No diagnosis, medication order, clinical note or episode transition was created")

finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
