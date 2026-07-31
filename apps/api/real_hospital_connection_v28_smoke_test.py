import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_v28_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "real-hospital-connection-v28-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-v28-smoke",
    "AUTH_AUDIENCE": "lucyworks-v28-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
    "V26_CONTEXT_BOOTSTRAP_ENABLED": "false",
    "V27_CONFIGURATION_REQUIRED": "false",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.database import engine
from app.evidence_service import verify_event_chain
from app.hospital_ops_models import CanonicalEpisodeState
from app.models import User
from app.operational_context_v26_models import SiteMembershipV26
from app.organisation_onboarding_v27_models import OnboardingSiteV27
from app.real_hospital_connection_v28_models import (
    IntegrationConnectorV28,
    IntegrationEventV28,
    IntegrationPromotionV28,
    ReconciliationItemV28,
    SpeechProviderV28,
    SpeechSegmentV28,
    SpeechSessionV28,
)
from app.speech_capture_v19_models import SpeechCaptureV19, SpeechDraftV19
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    session.add_all([
        User(id=2801, name="V28 Hospital Director", role="hospital_director", email="director-v28@example.test"),
        User(id=2802, name="V28 Governance Lead", role="governance_lead", email="governance-v28@example.test"),
        User(id=2803, name="V28 Clinician", role="clinician", email="clinician-v28@example.test"),
        OnboardingSiteV27(
            site_ref="hospital-v28",
            organisation_ref="group-v28",
            premises_ref="premises-v28",
            name="Referral Hospital V28",
            address={"line1": "1 Hospital Way", "city": "Bristol", "postcode": "BS1 1AA"},
            regulator_premises_refs=["RCVS-V28"],
            accountable_director_subject="local-user:2801",
            accountable_director_name="V28 Hospital Director",
            clinical_governance_subject="local-user:2802",
            clinical_governance_name="V28 Governance Lead",
            status="approved",
            active_release_ref="release-v28-approved",
            updated_by_subject="local-user:2801",
            updated_by_name="V28 Hospital Director",
            updated_by_role="hospital_director",
        ),
        SiteMembershipV26(
            membership_ref="membership-v28-director",
            subject="local-user:2801",
            actor_id="2801",
            organisation_ref="group-v28",
            site_ref="hospital-v28",
            premises_ref="premises-v28",
            role="hospital_director",
            status="active",
            is_primary=True,
            granted_by_subject="local-user:2801",
        ),
        SiteMembershipV26(
            membership_ref="membership-v28-governance",
            subject="local-user:2802",
            actor_id="2802",
            organisation_ref="group-v28",
            site_ref="hospital-v28",
            premises_ref="premises-v28",
            role="governance_lead",
            status="active",
            is_primary=True,
            granted_by_subject="local-user:2801",
        ),
        SiteMembershipV26(
            membership_ref="membership-v28-clinician",
            subject="local-user:2803",
            actor_id="2803",
            organisation_ref="group-v28",
            site_ref="hospital-v28",
            premises_ref="premises-v28",
            role="clinician",
            status="active",
            is_primary=True,
            granted_by_subject="local-user:2801",
        ),
        CanonicalEpisodeState(
            episode_ref="EP-V28-001",
            patient_ref="PAT-V28-001",
            patient_name="V28 Bramble",
            premises_ref="premises-v28",
            service_line="neurology",
            urgency="urgent",
            phase="consult",
            status="active",
            owner_role="clinician",
            owner_subject="local-user:2803",
            current_area_ref="consult-1",
            next_action="Review findings",
        ),
    ])
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


try:
    with TestClient(app) as client:
        director = login(client, 2801)
        governance = login(client, 2802)
        clinician = login(client, 2803)

        provider_created = ok(client.post("/api/v28/deployment/speech/providers", headers=director, json={
            "organisationRef": "group-v28",
            "siteRef": "hospital-v28",
            "name": "Approved browser speech",
            "providerType": "browser",
            "processingRegion": "GB",
            "language": "en-GB",
            "supportsStreaming": True,
            "supportsWordTimestamps": True,
            "supportsWordConfidence": True,
            "rawAudioRetention": False,
        }), "create speech provider")
        provider = provider_created["provider"]
        tested_provider = ok(client.post(
            f"/api/v28/deployment/speech/providers/{provider['provider_ref']}/test",
            headers=director,
            json={"expectedVersion": provider["version"], "reason": "Validate browser provider boundary."},
        ), "test speech provider")["provider"]
        approved_provider = ok(client.post(
            f"/api/v28/deployment/speech/providers/{provider['provider_ref']}/approve",
            headers=director,
            json={"expectedVersion": tested_provider["version"], "reason": "Approve tested browser transcription."},
        ), "approve speech provider")["provider"]
        assert approved_provider["status"] == "approved"
        assert approved_provider["raw_audio_retention"] is False

        started = ok(client.post("/api/v28/deployment/speech/sessions", headers=clinician, json={
            "providerRef": approved_provider["provider_ref"],
            "siteRef": "hospital-v28",
            "episodeRef": "EP-V28-001",
            "captureMode": "consultation_transcription",
            "noticeAcknowledged": True,
            "rawAudioRetained": False,
            "deviceDiagnostics": {"browser": "Chrome", "microphonePermission": "granted", "network": "online"},
        }), "start speech session")
        speech_session = started["session"]
        first = ok(client.post(
            f"/api/v28/deployment/speech/sessions/{speech_session['session_ref']}/segments",
            headers=clinician,
            json={
                "expectedVersion": speech_session["version"],
                "sequence": 1,
                "text": "History: owner reports acute hindlimb weakness.",
                "confidence": 0.96,
                "startedMs": 0,
                "endedMs": 3200,
                "speakerLabel": "clinician",
                "isFinal": True,
                "source": "browser",
                "words": [{"word": "hindlimb", "confidence": 0.91, "startMs": 1800, "endMs": 2400}],
            },
        ), "append first segment")
        idempotent = ok(client.post(
            f"/api/v28/deployment/speech/sessions/{speech_session['session_ref']}/segments",
            headers=clinician,
            json={
                "expectedVersion": first["session"]["version"],
                "sequence": 1,
                "text": "History: owner reports acute hindlimb weakness.",
                "confidence": 0.96,
                "startedMs": 0,
                "endedMs": 3200,
                "speakerLabel": "clinician",
                "isFinal": True,
                "source": "browser",
                "words": [{"word": "hindlimb", "confidence": 0.91, "startMs": 1800, "endMs": 2400}],
            },
        ), "idempotent segment")
        assert idempotent["idempotent"] is True

        interrupted = ok(client.post(
            f"/api/v28/deployment/speech/sessions/{speech_session['session_ref']}/interrupt",
            headers=clinician,
            json={"expectedVersion": first["session"]["version"], "reason": "Network connection dropped."},
        ), "interrupt speech session")["session"]
        assert interrupted["status"] == "interrupted"
        resumed = ok(client.post(
            f"/api/v28/deployment/speech/sessions/{speech_session['session_ref']}/resume",
            headers=clinician,
            json={"expectedVersion": interrupted["version"], "reason": "Network connection restored."},
        ), "resume speech session")["session"]
        second = ok(client.post(
            f"/api/v28/deployment/speech/sessions/{speech_session['session_ref']}/segments",
            headers=clinician,
            json={
                "expectedVersion": resumed["version"],
                "sequence": 2,
                "text": "Examination: temperature 39.2 C. Assessment: possible thoracolumbar pain. Plan: arrange MRI today.",
                "confidence": 0.68,
                "startedMs": 3201,
                "endedMs": 9800,
                "speakerLabel": "clinician",
                "isFinal": True,
                "source": "browser",
            },
        ), "append resumed segment")
        completed = ok(client.post(
            f"/api/v28/deployment/speech/sessions/{speech_session['session_ref']}/complete",
            headers=clinician,
            json={"expectedVersion": second["session"]["version"], "reason": "Complete transcript for human clinical review."},
        ), "complete speech session")
        assert completed["session"]["status"] == "ready_for_review"
        assert completed["session"]["linked_capture_ref"] == completed["capture"]["capture_ref"]
        assert completed["session"]["quality_summary"]["lowConfidenceSequences"] == [2]
        assert completed["draft"]["status"] == "proposed"

        connector_created = ok(client.post("/api/v28/deployment/connectors", headers=director, json={
            "organisationRef": "group-v28",
            "siteRef": "hospital-v28",
            "connectorType": "patient_management",
            "vendorName": "Synthetic PMS",
            "environment": "sandbox",
            "endpointHost": "pms-v28.example.test",
            "staleAfterSeconds": 900,
        }), "create connector")["connector"]
        connector_tested = ok(client.post(
            f"/api/v28/deployment/connectors/{connector_created['connector_ref']}/test",
            headers=director,
            json={"expectedVersion": connector_created["version"], "reason": "Validate sandbox read connection configuration."},
        ), "test connector")["connector"]
        blocked_write = client.post(
            f"/api/v28/deployment/connectors/{connector_created['connector_ref']}/promotions",
            headers=director,
            json={"expectedVersion": connector_tested["version"], "requestedMode": "write", "reason": "This must remain blocked.", "evidenceRefs": []},
        )
        assert blocked_write.status_code == 409, blocked_write.text
        requested = ok(client.post(
            f"/api/v28/deployment/connectors/{connector_created['connector_ref']}/promotions",
            headers=director,
            json={"expectedVersion": connector_tested["version"], "requestedMode": "shadow", "reason": "Run the connector in no-write shadow mode.", "evidenceRefs": ["test:v28"]},
        ), "request shadow promotion")
        self_approval = client.post(
            f"/api/v28/deployment/promotions/{requested['promotion']['promotion_ref']}/approve",
            headers=director,
            json={"expectedVersion": requested["promotion"]["version"], "reason": "Self approval must fail."},
        )
        assert self_approval.status_code == 409, self_approval.text
        approved = ok(client.post(
            f"/api/v28/deployment/promotions/{requested['promotion']['promotion_ref']}/approve",
            headers=governance,
            json={"expectedVersion": requested["promotion"]["version"], "reason": "Independent approval for bounded shadow use."},
        ), "approve shadow promotion")
        assert approved["connector"]["mode"] == "shadow"
        assert approved["connector"]["status"] == "active"

        ingested = ok(client.post(
            f"/api/v28/deployment/connectors/{connector_created['connector_ref']}/events",
            headers=director,
            json={
                "externalEventId": "PMS-EVENT-V28-001",
                "eventType": "patient_update",
                "payloadSummary": {"externalPatientId": "EXT-UNKNOWN", "change": "address"},
            },
        ), "ingest unresolved event")
        assert ingested["event"]["status"] == "reconciliation_required"
        assert ingested["reconciliation"]["severity"] == "red"
        duplicate = ok(client.post(
            f"/api/v28/deployment/connectors/{connector_created['connector_ref']}/events",
            headers=director,
            json={
                "externalEventId": "PMS-EVENT-V28-001",
                "eventType": "patient_update",
                "payloadSummary": {"externalPatientId": "EXT-UNKNOWN", "change": "address"},
            },
        ), "idempotent integration event")
        assert duplicate["idempotent"] is True
        resolved = ok(client.post(
            f"/api/v28/deployment/reconciliation/{ingested['reconciliation']['item_ref']}/resolve",
            headers=governance,
            json={
                "expectedVersion": ingested["reconciliation"]["version"],
                "resolution": "Matched against the canonical episode after independent review.",
                "resolvedRef": "EP-V28-001",
            },
        ), "resolve reconciliation")
        assert resolved["event"]["episode_ref"] == "EP-V28-001"
        assert resolved["event"]["patient_ref"] == "PAT-V28-001"
        replayed = ok(client.post(
            f"/api/v28/deployment/events/{resolved['event']['event_ref']}/replay",
            headers=director,
            json={"expectedVersion": 1, "reason": "Prove bounded internal replay without vendor write-back."},
        ), "replay event")
        assert replayed["event"]["direction"] == "replay"
        assert replayed["event"]["replay_of_event_ref"] == resolved["event"]["event_ref"]

        centre = ok(client.get("/api/v28/deployment/control-centre?siteRef=hospital-v28", headers=governance), "load control centre")
        assert centre["summary"]["approvedSpeechProviders"] == 1
        assert centre["summary"]["activeConnectors"] == 1
        assert centre["summary"]["openReconciliation"] == 0
        assert "No v28 route performs external-system write-back" in centre["boundary"]

        integrity = verify_event_chain(Session(engine))
        assert integrity["ok"] is True, integrity

    with Session(engine) as session:
        assert session.exec(select(SpeechProviderV28)).one().status == "approved"
        assert session.exec(select(SpeechSessionV28)).one().linked_capture_ref
        assert len(session.exec(select(SpeechSegmentV28)).all()) == 2
        assert session.exec(select(SpeechCaptureV19)).one().source_type == "speech_session_v28"
        assert session.exec(select(SpeechDraftV19)).one().status == "proposed"
        assert session.exec(select(IntegrationConnectorV28)).one().mode == "shadow"
        assert session.exec(select(IntegrationPromotionV28)).one().approved_by_subject == "local-user:2802"
        assert len(session.exec(select(IntegrationEventV28)).all()) == 2
        assert session.exec(select(ReconciliationItemV28)).one().status == "resolved"

    print("\n--- REAL HOSPITAL CONNECTION AND SPEECH V28 SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
