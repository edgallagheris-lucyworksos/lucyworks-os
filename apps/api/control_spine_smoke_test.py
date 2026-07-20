import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_control_spine_{os.getpid()}.db"
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
        base_event = {
            "eventType": "decision",
            "patientCaseId": "case-control-1",
            "referralEpisodeId": "episode-control-1",
            "actorName": "Smoke Clinician",
            "actorRole": "clinician",
            "professionalRole": "vet",
            "action": "recorded operational decision",
            "reason": "control spine smoke test",
            "humanReviewStatus": "not_required",
            "riskLevel": "amber",
            "sourceModule": "smoke-test",
            "idempotencyKey": "smoke-base-event",
        }
        first = client.post("/api/evidence/events", json=base_event)
        assert first.status_code == 200, first.text
        second = client.post("/api/evidence/events", json=base_event)
        assert second.status_code == 200, second.text
        assert first.json()["event"]["eventRef"] == second.json()["event"]["eventRef"]
        assert second.json()["created"] is False

        red = client.post("/api/evidence/events", json={
            **base_event,
            "action": "emergency override recorded",
            "riskLevel": "red",
            "overrideReason": "patient deterioration",
            "justification": "delay would create material clinical risk",
            "idempotencyKey": "smoke-red-event",
        })
        assert red.status_code == 200, red.text
        source_hash = red.json()["event"]["eventHash"]

        approvals = client.get("/api/evidence/approvals?status=pending")
        assert approvals.status_code == 200, approvals.text
        approval = next(item for item in approvals.json()["approvals"] if item["evidenceEventRef"] == red.json()["event"]["eventRef"])
        decision = client.patch(f"/api/evidence/approvals/{approval['id']}", json={
            "decision": "approved",
            "decidedBy": "Smoke Director",
            "decidedByRole": "clinical_director",
            "note": "override reviewed",
        })
        assert decision.status_code == 200, decision.text
        source_after = client.get("/api/evidence/events?event_type=decision")
        matching = next(item for item in source_after.json()["events"] if item["eventRef"] == red.json()["event"]["eventRef"])
        assert matching["eventHash"] == source_hash
        assert matching["effectiveApprovalStatus"] == "approved"

        estimate = client.post("/api/evidence/estimates", json={
            "estimateRef": "estimate-control-1",
            "patientCaseId": "case-control-1",
            "referralEpisodeId": "episode-control-1",
            "status": "presented",
            "lowerAmount": 2500,
            "upperAmount": 3500,
            "approvedCeiling": 3500,
            "clientDecision": "accepted",
            "clientContactMethod": "telephone",
            "createdBy": "Smoke Admin",
            "createdByRole": "admin",
            "idempotencyKey": "estimate-control-1-v1",
        })
        assert estimate.status_code == 200, estimate.text
        assert estimate.json()["estimate"]["version"] == 1
        assert estimate.json()["estimate"]["evidenceEventRef"]

        consent = client.post("/api/evidence/consents", json={
            "consentRef": "consent-control-1",
            "patientCaseId": "case-control-1",
            "referralEpisodeId": "episode-control-1",
            "status": "authorised",
            "scope": "MRI, anaesthesia and related treatment",
            "risksDiscussed": ["anaesthesia", "contrast reaction"],
            "alternativesDiscussed": ["medical management", "delay"],
            "costDiscussed": True,
            "estimateRef": "estimate-control-1",
            "clientAuthorisedBy": "Smoke Owner",
            "clientContactMethod": "telephone",
            "recordedBy": "Smoke Clinician",
            "recordedByRole": "clinician",
            "idempotencyKey": "consent-control-1-v1",
        })
        assert consent.status_code == 200, consent.text
        assert consent.json()["consent"]["evidenceEventRef"]

        handover = client.post("/api/control-plane/handovers", json={
            "handoverRef": "handover-control-1",
            "patientCaseId": "case-control-1",
            "referralEpisodeId": "episode-control-1",
            "fromActor": "Smoke Clinician",
            "fromRole": "clinician",
            "toActor": "Smoke RVN",
            "toRole": "nurse",
            "summary": "Recover after MRI and monitor airway",
            "clinicalRisks": ["post-anaesthetic airway risk"],
            "outstandingActions": ["pain score", "owner update"],
        })
        assert handover.status_code == 200, handover.text
        handover_id = handover.json()["handover"]["id"]
        accepted = client.patch(f"/api/control-plane/handovers/{handover_id}/decision", json={
            "decision": "accepted",
            "decidedBy": "Smoke RVN",
            "decidedByRole": "nurse",
            "note": "responsibility accepted",
        })
        assert accepted.status_code == 200, accepted.text

        control = client.post("/api/control-plane/controls", json={
            "controlRef": "controlled-drugs-daily",
            "domain": "medication",
            "title": "Daily controlled-drug reconciliation",
            "requirementSource": "hospital policy",
            "responsibleRole": "senior_nurse",
            "evidenceRequired": ["register checked", "discrepancies escalated"],
            "status": "not_assessed",
            "riskLevel": "amber",
        })
        assert control.status_code == 200, control.text
        control_id = control.json()["control"]["id"]
        reviewed = client.patch(f"/api/control-plane/controls/{control_id}", json={
            "status": "compliant",
            "riskLevel": "green",
            "reviewedBy": "Smoke Ops",
            "reviewedByRole": "ops_manager",
            "note": "daily reconciliation completed",
        })
        assert reviewed.status_code == 200, reviewed.text

        service = client.post("/api/control-plane/services", json={
            "serviceRef": "mri-service",
            "department": "diagnostic_imaging",
            "serviceName": "MRI",
            "operationalStatus": "reduced",
            "acceptingReferrals": False,
            "staffingReady": True,
            "equipmentReady": False,
            "consumablesReady": True,
            "limitingReason": "coil fault",
            "updatedBy": "Smoke Ops",
        })
        assert service.status_code == 200, service.text

        model = client.post("/api/control-plane/ai-models", json={
            "modelRef": "referral-summary-v1",
            "provider": "internal-test",
            "modelName": "referral-summary",
            "modelVersion": "1.0",
            "purpose": "draft referral summaries",
            "riskClass": "clinical_support",
            "approvedRoles": ["vet", "nurse"],
            "permittedData": ["clinical referral record"],
            "prohibitedData": ["HR records"],
            "trainingUseStatus": "prohibited",
            "humanReviewRule": "qualified clinician approval required",
            "knownLimitations": "may omit chronology",
            "fallbackProcess": "manual summary",
            "accountableOwner": "Clinical Director",
        })
        assert model.status_code == 200, model.text
        model_id = model.json()["model"]["id"]
        model_review = client.patch(f"/api/control-plane/ai-models/{model_id}/review", json={
            "decision": "approved",
            "reviewedBy": "Smoke Director",
            "reviewedByRole": "clinical_director",
            "validationSummary": "validated against smoke set",
            "knownLimitations": "requires source-linked review",
            "fallbackProcess": "manual summary",
        })
        assert model_review.status_code == 200, model_review.text

        critical = client.post("/api/control-plane/critical-results", json={
            "resultRef": "lab-critical-1",
            "patientCaseId": "case-control-1",
            "referralEpisodeId": "episode-control-1",
            "resultType": "potassium",
            "summary": "critical potassium result",
            "assignedTo": "Smoke Clinician",
            "assignedRole": "clinician",
        })
        assert critical.status_code == 200, critical.text
        result_id = critical.json()["result"]["id"]
        acknowledged = client.patch(f"/api/control-plane/critical-results/{result_id}/acknowledge", json={
            "acknowledgedBy": "Smoke Clinician",
            "acknowledgedByRole": "clinician",
            "actionTaken": "patient reviewed and treatment adjusted",
        })
        assert acknowledged.status_code == 200, acknowledged.text

        integrity = client.get("/api/evidence/integrity")
        assert integrity.status_code == 200, integrity.text
        assert integrity.json()["ok"] is True, integrity.text
        assert integrity.json()["checked"] >= 10

        dashboard = client.get("/api/control-plane/dashboard")
        assert dashboard.status_code == 200, dashboard.text
        summary = dashboard.json()["summary"]
        assert summary["unsafeServices"] == 1
        assert summary["unacknowledgedCriticalResults"] == 0

    print("\n--- CONTROL SPINE V2 SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
