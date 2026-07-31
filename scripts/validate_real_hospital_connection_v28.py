from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYTHON_FILES = [
    ROOT / "apps/api/app/real_hospital_connection_v28_models.py",
    ROOT / "apps/api/app/real_hospital_connection_v28_routes.py",
    ROOT / "apps/api/app/real_hospital_connection_v28_hardening_routes.py",
    ROOT / "apps/api/app/production_readiness_v28_patch.py",
    ROOT / "apps/api/migrations/versions/0022_real_hospital_connection_v28.py",
    ROOT / "apps/api/real_hospital_connection_v28_smoke_test.py",
    ROOT / "apps/api/real_hospital_connection_v28_authority_test.py",
]

for path in PYTHON_FILES:
    assert path.exists(), f"missing {path.relative_to(ROOT)}"
    ast.parse(path.read_text(), filename=str(path))

models = (ROOT / "apps/api/app/real_hospital_connection_v28_models.py").read_text()
for name in (
    "SpeechProviderV28", "SpeechSessionV28", "SpeechSegmentV28",
    "IntegrationConnectorV28", "IntegrationPromotionV28", "IntegrationEventV28",
    "ReconciliationItemV28",
):
    assert f"class {name}" in models, name
assert "raw_audio_retention: bool = False" in models
assert 'UniqueConstraint("session_ref", "sequence"' in models
assert 'UniqueConstraint("connector_ref", "external_event_id"' in models

routes = (ROOT / "apps/api/app/real_hospital_connection_v28_routes.py").read_text()
for route in (
    '@router.get("/control-centre")',
    '@router.post("/speech/providers")',
    '@router.post("/speech/sessions")',
    '@router.post("/speech/sessions/{session_ref}/segments")',
    '@router.post("/speech/sessions/{session_ref}/interrupt")',
    '@router.post("/speech/sessions/{session_ref}/resume")',
    '@router.post("/speech/sessions/{session_ref}/complete")',
    '@router.post("/connectors")',
    '@router.post("/connectors/{connector_ref}/promotions")',
    '@router.post("/promotions/{promotion_ref}/approve")',
    '@router.post("/reconciliation/{item_ref}/resolve")',
    '@router.post("/events/{event_ref}/replay")',
):
    assert route in routes, route
assert 'PROMOTABLE_MODES = {"shadow", "read_only"}' in routes
assert "external write-back requires a later separately governed release" in routes
assert "connector promotion requires an independent second approver" in routes
assert "create_capture(CaptureCreate(" in routes
assert "raw-audio retention is disabled" in routes
assert "sequence already exists with different content" in routes

hardening = (ROOT / "apps/api/app/real_hospital_connection_v28_hardening_routes.py").read_text()
for marker in (
    'ConfigDict(extra="forbid")',
    "speech_segment_sequence_gap",
    "expectedSequence",
    "append_speech_segment_original",
    '@router.post("/speech/sessions")',
    '@router.post("/speech/sessions/{session_ref}/segments")',
):
    assert marker in hardening, marker

migration = (ROOT / "apps/api/migrations/versions/0022_real_hospital_connection_v28.py").read_text()
assert 'revision: str = "0022_real_hospital_connection_v28"' in migration
assert 'down_revision: Union[str, None] = "0021_organisation_onboarding_v27"' in migration
assert "Destructive removal" in migration

main = (ROOT / "apps/api/app/main.py").read_text()
assert "real_hospital_connection_v28_router" in main
assert "real_hospital_connection_v28_hardening_router" in main
assert "app.include_router(real_hospital_connection_v28_hardening_router)" in main
assert main.index("app.include_router(real_hospital_connection_v28_hardening_router)") < main.index("app.include_router(real_hospital_connection_v28_router)")
assert "production_readiness_v28_patch" in main

readiness = (ROOT / "apps/api/app/production_readiness_v28_patch.py").read_text()
for marker in (
    "V28_CONNECTION_CONTROL_REQUIRED",
    "No external write-back connector mode",
    "Speech raw-audio retention disabled",
    "production-readiness-v28",
):
    assert marker in readiness, marker

web = (ROOT / "apps/web/components/deployment-control-v28.tsx").read_text()
for marker in (
    "Real hospital connection control",
    "Test microphone",
    "Start governed speech",
    "Interrupt safely",
    "Request shadow",
    "raw audio is not retained",
):
    assert marker in web, marker
assert (ROOT / "apps/web/app/deployment-control/page.tsx").exists()
assert '["/deployment-control", "Real hospital connections and speech"]' in (ROOT / "apps/web/app/system-control/page.tsx").read_text()

smoke = (ROOT / "apps/api/real_hospital_connection_v28_smoke_test.py").read_text()
for marker in (
    "Network connection dropped",
    "Self approval must fail",
    '"requestedMode": "write"',
    "reconciliation_required",
    "speech_session_v28",
):
    assert marker in smoke, marker

authority = (ROOT / "apps/api/real_hospital_connection_v28_authority_test.py").read_text()
for marker in (
    "hiddenAudioUpload",
    "speech_segment_sequence_gap",
    "initial_gap.status_code == 409",
    "later_gap.status_code == 409",
    "idempotent retry",
    "raw_audio.status_code == 409",
):
    assert marker in authority, marker

print("REAL_HOSPITAL_CONNECTION_V28_STATIC_VALIDATION_PASSED")
