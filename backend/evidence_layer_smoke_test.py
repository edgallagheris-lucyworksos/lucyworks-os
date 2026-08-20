from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_evidence_event_and_ai_verification_are_append_only():
    event = client.post("/api/evidence/events", json={
        "event_type": "estimate_authorisation",
        "actor_name": "Test Clinician",
        "actor_role": "clinician",
        "authority_basis": "episode_owner",
        "entity_type": "estimate",
        "entity_id": "EST-001",
        "action": "authorised",
        "state_before": {"status": "draft"},
        "state_after": {"status": "authorised", "ceiling_gbp": 2500},
        "reason": "Owner authorised treatment ceiling",
        "evidence_refs": ["consent:CONS-001"],
        "correlation_id": "episode-demo",
    })
    assert event.status_code == 200, event.text
    assert event.json()["state_before_json"] == '{"status":"draft"}'

    listed = client.get("/api/evidence/events", params={"entity_type": "estimate", "entity_id": "EST-001"})
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    generated = client.post("/api/evidence/verifications", json={
        "entity_type": "clinical_note",
        "entity_id": "NOTE-001",
        "content_type": "clinical_note",
        "original_content": "AI draft content",
        "model_name": "test-model",
        "model_version": "1",
        "provenance": "smoke-test",
    })
    assert generated.status_code == 200, generated.text
    verification_id = generated.json()["id"]
    assert generated.json()["status"] == "awaiting_verification"

    decision = client.post(f"/api/evidence/verifications/{verification_id}/decision", json={
        "status": "amended",
        "verified_by": "Test Clinician",
        "verifier_role": "clinician",
        "final_content": "Human-corrected content",
        "reason": "Corrected wording after review",
    })
    assert decision.status_code == 200, decision.text
    body = decision.json()
    assert body["original_content"] == "AI draft content"
    assert body["final_content"] == "Human-corrected content"
    assert body["status"] == "amended"

    second_decision = client.post(f"/api/evidence/verifications/{verification_id}/decision", json={
        "status": "verified",
        "verified_by": "Another Clinician",
    })
    assert second_decision.status_code == 409
