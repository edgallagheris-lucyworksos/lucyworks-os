import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_evidence_patient_care_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

try:
    with TestClient(app) as client:
        seed = {
            "blocks": [
                {
                    "id": "evidence-case-consent",
                    "time": "09:00",
                    "lane": "insurance",
                    "what": "Consent and estimate gate",
                    "who": "admin",
                    "where": "admin queue",
                    "how": "confirm consent, estimate and insurance",
                    "status": "amber",
                    "blocker": "consent / estimate pending",
                    "next": "procedure",
                    "route": "/patient-care",
                    "subject": "Smoke Patient",
                    "episodeRef": "smoke-referral-1",
                    "durationMinutes": 20,
                    "assignedRole": "admin",
                    "consentStatus": "pending",
                    "estimateStatus": "pending",
                    "insuranceStatus": "pending",
                    "ownerUpdated": False,
                    "referringVetReportSent": False,
                    "dischargeClear": False,
                },
                {
                    "id": "evidence-case-procedure",
                    "time": "09:45",
                    "lane": "rooms",
                    "what": "MRI pathway",
                    "who": "clinician",
                    "where": "MRI",
                    "how": "anaesthetic imaging pathway",
                    "status": "amber",
                    "blocker": "none",
                    "next": "handover / recovery / owner update",
                    "route": "/patient-care",
                    "subject": "Smoke Patient",
                    "episodeRef": "smoke-referral-1",
                    "durationMinutes": 90,
                    "assignedRole": "clinician",
                    "pharmacyReady": False,
                },
            ]
        }

        r = client.put("/api/day-control/blocks/bulk", json=seed)
        assert r.status_code == 200, r.text
        print("Patient-care seed blocks OK")

        r = client.get("/api/patient-care/cases")
        assert r.status_code == 200, r.text
        cases = r.json()["cases"]
        assert cases, r.text
        episode = cases[0]["episodes"][0]
        episode_id = episode["id"]
        patient_case_id = cases[0]["id"]
        assert episode["consentStatus"] == "pending"
        print("Patient-care sync OK")

        r = client.patch(f"/api/patient-care/episodes/{episode_id}/state", json={"ownerUpdated": True, "consentStatus": "approved", "estimateStatus": "approved", "actor": "smoke", "note": "manual state should survive resync"})
        assert r.status_code == 200, r.text
        assert r.json()["episode"]["ownerUpdated"] is True
        print("Patient-care patch OK")

        r = client.get("/api/patient-care/cases")
        assert r.status_code == 200, r.text
        refreshed_episode = r.json()["cases"][0]["episodes"][0]
        assert refreshed_episode["ownerUpdated"] is True, refreshed_episode
        assert refreshed_episode["consentStatus"] == "approved", refreshed_episode
        assert refreshed_episode["estimateStatus"] == "approved", refreshed_episode
        print("Patient-care manual state survives sync OK")

        r = client.post("/api/evidence/events", json={
            "eventType": "decision",
            "patientCaseId": patient_case_id,
            "referralEpisodeId": episode_id,
            "actorName": "Smoke Clinician",
            "actorRole": "clinician",
            "professionalRole": "vet",
            "action": "approved MRI pathway",
            "reason": "test evidence event",
            "justification": "clinical owner reviewed case",
            "aiSystem": "smoke-ai",
            "aiModel": "smoke-model",
            "aiOutputRef": "smoke-output-1",
            "humanReviewer": "Smoke Clinician",
            "humanReviewStatus": "accepted",
            "complianceDomain": "clinical_governance",
            "riskLevel": "amber",
            "sourceModule": "smoke-test",
        })
        assert r.status_code == 200, r.text
        assert r.json()["event"]["aiModel"] == "smoke-model"
        print("Evidence event OK")

        for amount in [1200, 1500]:
            r = client.post("/api/evidence/estimates", json={
                "estimateRef": "estimate-smoke-referral-1",
                "patientCaseId": patient_case_id,
                "referralEpisodeId": episode_id,
                "status": "presented",
                "lowerAmount": amount,
                "upperAmount": amount + 300,
                "assumptions": ["MRI pathway", "anaesthesia included"],
                "excludedItems": ["unexpected complications"],
                "clientDecision": "accepted" if amount == 1500 else "not_recorded",
                "clinicianJustification": "versioned estimate smoke test",
                "createdBy": "smoke",
            })
            assert r.status_code == 200, r.text
        print("Estimate versions create OK")

        r = client.get("/api/evidence/estimates/estimate-smoke-referral-1")
        assert r.status_code == 200, r.text
        versions = r.json()["versions"]
        assert len(versions) == 2, versions
        assert versions[0]["version"] == 1
        assert versions[1]["version"] == 2
        print("Estimate version history OK")

        r = client.post("/api/evidence/consents", json={
            "consentRef": "consent-smoke-referral-1",
            "patientCaseId": patient_case_id,
            "referralEpisodeId": episode_id,
            "consentType": "procedure",
            "status": "authorised",
            "scope": "MRI, anaesthesia and referral care plan",
            "risksDiscussed": ["anaesthesia", "contrast", "cost change"],
            "alternativesDiscussed": ["delay", "medical management", "referring practice follow-up"],
            "costDiscussed": True,
            "estimateRef": "estimate-smoke-referral-1",
            "clientAuthorisedBy": "Smoke Owner",
            "recordedBy": "smoke",
            "witness": "Smoke Witness",
        })
        assert r.status_code == 200, r.text
        assert r.json()["consent"]["status"] == "authorised"
        print("Consent record OK")

        r = client.get(f"/api/evidence/consents?patient_case_id={patient_case_id}")
        assert r.status_code == 200, r.text
        assert r.json()["count"] == 1
        print("Consent list OK")

        r = client.get(f"/api/evidence/events?patient_case_id={patient_case_id}")
        assert r.status_code == 200, r.text
        assert r.json()["count"] >= 1
        print("Evidence event list OK")

    print("\n--- EVIDENCE PATIENT CARE SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
