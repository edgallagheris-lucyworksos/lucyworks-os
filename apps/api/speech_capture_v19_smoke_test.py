import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_speech_v19_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "speech-v19-smoke-secret-long-enough-for-testing",
    "AUTH_ISSUER": "lucyworks-speech-v19-smoke",
    "AUTH_AUDIENCE": "lucyworks-speech-v19-api",
    "LEGACY_WRITE_MODE": "block",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.database import engine
from app.detailed_hospital_models import ClinicalNoteV8, PatientClinicalRecordV8
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app
from app.medication_foundation_v18_models import ProductImportBatchV18, VeterinaryProductV18
from app.models import WorkItem
from app.speech_capture_v19_models import SpeechCaptureV19, SpeechDraftV19

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


try:
    with Session(engine) as session:
        session.add(PatientClinicalRecordV8(
            patient_ref="PAT-SPEECH-V19-001",
            display_name="UAT Bramble Speech 001",
            species="Dog",
            breed="Labrador",
            sex="female",
            alerts=[],
        ))
        session.add(CanonicalEpisodeState(
            episode_ref="EP-SPEECH-V19-001",
            patient_ref="PAT-SPEECH-V19-001",
            patient_name="UAT Bramble Speech 001",
            premises_ref="reference-site",
            service_line="neurology",
            urgency="urgent",
            phase="consult",
            status="active",
            owner_role="clinician",
            owner_subject="local-user:3",
            current_area_ref="consult-1",
            next_action="Review consultation findings",
        ))
        session.add(ProductImportBatchV18(
            batch_ref="batch-speech-v19",
            source_url="https://example.invalid/vmd-speech-fixture.xml",
            source_sha256="a" * 64,
            schema_fingerprint="b" * 64,
            product_count=1,
            created_count=1,
            imported_by_subject="local-user:4",
            imported_by_name="Synthetic Admin",
        ))
        session.add(VeterinaryProductV18(
            product_ref="product-speech-v19",
            source_product_id="Vm-SPEECH-V19-001",
            territory="GB",
            product_name="UAT Synthetic Analgesic 10 mg/ml solution for injection",
            active_substances=["UAT Synthetic Analgesic"],
            target_species=["Dog"],
            routes=["IV"],
            strengths=[{"amount": 10, "unit": "mg/ml"}],
            concentration_mg_per_ml=10.0,
            contraindications=[],
            warnings=[],
            withdrawal_periods=[],
            source_hash="c" * 64,
            imported_batch_ref="batch-speech-v19",
        ))
        session.commit()

    with TestClient(app) as client:
        anonymous = client.post("/api/v19/speech/captures", json={
            "episodeRef": "EP-SPEECH-V19-001",
            "transcript": "History: synthetic test",
            "noticeAcknowledged": True,
        })
        assert anonymous.status_code == 401, anonymous.text

        clinician = login(client, 3)
        admin = login(client, 4)

        raw_audio = client.post("/api/v19/speech/captures", headers=clinician, json={
            "episodeRef": "EP-SPEECH-V19-001",
            "captureMode": "clinical_dictation",
            "sourceType": "browser_speech",
            "transcript": "History: raw audio retention must remain disabled",
            "noticeAcknowledged": True,
            "rawAudioRetained": True,
        })
        assert raw_audio.status_code == 409, raw_audio.text

        phrase_pack = ok(client.post("/api/v19/speech/phrase-packs", headers=admin, json={
            "organisationRef": "reference-site",
            "name": "Neurology speech pack",
            "terms": ["thoracolumbar", "proprioceptive deficit"],
            "replacements": {"TL pain": "thoracolumbar pain"},
        }), "create phrase pack")
        approved_pack = ok(client.patch(
            f"/api/v19/speech/phrase-packs/{phrase_pack['phrasePack']['phrase_pack_ref']}/approve",
            headers=admin,
            json={"expectedVersion": 1, "reason": "Synthetic phrase-pack approval"},
        ), "approve phrase pack")
        assert approved_pack["phrasePack"]["status"] == "approved"

        transcript = (
            "Presenting complaint: acute hindlimb weakness. "
            "History: owner reports no vomiting and possible TL pain since this morning. "
            "Examination: temperature 39.2 C, heart rate 120 bpm and respiratory rate 32. "
            "Assessment: suspect spinal pain. "
            "Plan: UAT Synthetic Analgesic 0.2 mg/kg IV every 6 hours is a proposed option only. "
            "Please arrange MRI today and call owner with an update."
        )
        created = ok(client.post("/api/v19/speech/captures", headers=clinician, json={
            "episodeRef": "EP-SPEECH-V19-001",
            "patientRef": "SPOOFED-PATIENT-REF",
            "captureMode": "consultation_transcription",
            "sourceType": "browser_speech",
            "transcript": transcript,
            "language": "en-GB",
            "noticeVersion": "synthetic-v19",
            "noticeAcknowledged": True,
            "rawAudioRetained": False,
        }), "create speech capture")
        capture = created["capture"]
        draft = created["draft"]
        assert created["context"]["patientRef"] == "PAT-SPEECH-V19-001"
        assert capture["patient_ref"] == "PAT-SPEECH-V19-001"
        assert capture["redacted_transcript_text"] and "thoracolumbar pain" in capture["redacted_transcript_text"].lower()
        assert any("no vomiting" in row["value"].lower() for row in draft["negations"])
        assert any("possible" in row["value"].lower() or "suspect" in row["value"].lower() for row in draft["uncertainties"])
        assert any(row["value"]["kind"] == "temperature_c" and row["value"]["value"] == 39.2 for row in draft["observations"])
        assert draft["medication_proposals"], draft
        medication = draft["medication_proposals"][0]
        assert medication["value"]["doseExpression"] == "0.2 mg/kg"
        assert medication["value"]["routeExpression"].lower() == "iv"
        assert medication["value"]["calculationPerformed"] is False
        assert "Medication Foundation v18" in medication["value"]["boundary"]
        assert len(draft["task_proposals"]) >= 1
        print("Authenticated veterinary transcription, context enforcement and deterministic extraction OK")

        final_sections = dict(draft["proposed_sections"])
        final_sections["assessment"] = "Thoracolumbar pain with acute ambulatory paraparesis; differential diagnosis remains under clinician review."
        final_sections["plan"] = "Arrange MRI. Medication expression rejected from this note pending Medication Foundation v18 review."
        section_ids = [row["id"] for row in draft["suggestions"] if row["type"] == "section"]
        task_id = draft["task_proposals"][0]["id"]
        confirmed = ok(client.post(
            f"/api/v19/speech/captures/{capture['capture_ref']}/confirm",
            headers=clinician,
            json={
                "expectedCaptureVersion": capture["version"],
                "expectedDraftVersion": draft["version"],
                "finalSections": final_sections,
                "acceptedSuggestionIds": section_ids + [task_id],
                "rejectedSuggestionIds": [medication["id"]],
                "acceptedTaskIds": [task_id],
                "createClinicalNote": True,
                "noteType": "consultation",
                "noteTitle": "Reviewed synthetic neurology consultation",
                "reason": "Clinician reviewed transcript, corrected assessment and rejected unverified medication proposal",
            },
        ), "confirm speech capture")
        assert confirmed["capture"]["status"] == "confirmed"
        assert confirmed["draft"]["status"] == "confirmed"
        assert confirmed["clinicalNote"]["author_subject"] == "local-user:3"
        assert medication["id"] in confirmed["draft"]["rejected_suggestion_ids"]
        assert len(confirmed["workItems"]) == 1
        assert confirmed["workItems"][0]["linked_episode_ref"] == "EP-SPEECH-V19-001"
        print("Human review, rejected medicine suggestion, signed record and accepted task creation OK")

        stale = client.post(
            f"/api/v19/speech/captures/{capture['capture_ref']}/confirm",
            headers=clinician,
            json={
                "expectedCaptureVersion": 1,
                "expectedDraftVersion": 1,
                "finalSections": final_sections,
                "acceptedSuggestionIds": [],
                "rejectedSuggestionIds": [],
                "acceptedTaskIds": [],
                "createClinicalNote": True,
                "reason": "Stale repeat must fail",
            },
        )
        assert stale.status_code == 409, stale.text

        persisted = ok(client.get(
            f"/api/v19/speech/captures/{capture['capture_ref']}", headers=clinician
        ), "reload speech capture")
        assert persisted["capture"]["status"] == "confirmed"
        assert persisted["draft"]["clinical_note_ref"] == confirmed["clinicalNote"]["note_ref"]

        terms = ok(client.get("/api/v19/speech/terms?q=thora", headers=clinician), "predictive terms")
        assert any(row["term"] == "thoracolumbar" for row in terms["items"])

        integrity = ok(client.get("/api/evidence/integrity", headers=admin), "evidence integrity")
        assert integrity["ok"] is True, integrity

    with Session(engine) as session:
        stored_capture = session.exec(select(SpeechCaptureV19)).one()
        stored_draft = session.exec(select(SpeechDraftV19)).one()
        note = session.exec(select(ClinicalNoteV8).where(ClinicalNoteV8.note_ref == stored_draft.clinical_note_ref)).one()
        tasks = session.exec(select(WorkItem).where(WorkItem.linked_episode_ref == "EP-SPEECH-V19-001")).all()
        assert stored_capture.transcript_text == transcript
        assert "Thoracolumbar pain" in note.body
        assert "0.2 mg/kg" not in note.body
        assert len(tasks) == 1
        print("Refresh persistence, transcript separation and immutable evidence chain OK")

    print("\n--- VETERINARY SPEECH AND STRUCTURED CAPTURE V19 SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
