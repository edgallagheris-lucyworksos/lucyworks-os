from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "models": ROOT / "apps/api/app/safety_control_v25_models.py",
    "service": ROOT / "apps/api/app/safety_control_v25_service.py",
    "routes": ROOT / "apps/api/app/safety_control_v25_routes_core.py",
    "bridge": ROOT / "apps/api/app/safety_bridge_v25_routes.py",
    "attribution": ROOT / "apps/api/app/verified_actor_attribution_v25.py",
    "auth": ROOT / "apps/api/app/auth_scope_v25_patch.py",
    "migration": ROOT / "apps/api/migrations/versions/0019_cross_system_safety_control_v25.py",
    "ui": ROOT / "apps/web/components/cross-system-safety-control-v25-core.tsx",
    "page": ROOT / "apps/web/app/safety-control/page.tsx",
    "system_control": ROOT / "apps/web/app/system-control/page.tsx",
    "audit": ROOT / "docs/CROSS_SYSTEM_SAFETY_AUDIT_V25.md",
    "proof": ROOT / "apps/api/cross_system_safety_control_v25_smoke_test.py",
}

for label, path in FILES.items():
    assert path.exists(), f"missing {label}: {path}"

text = {label: path.read_text(encoding="utf-8") for label, path in FILES.items()}

required_model_markers = [
    "class SafetyRecordV25",
    "class SafetyActionV25",
    "class SafetyDecisionV25",
    "class SafetyLinkV25",
    "class SafetyEscalationV25",
    "class SafetyAccessEventV25",
    "confidentiality",
    "conflict_subjects",
    "requires_independent_verification",
]
for marker in required_model_markers:
    assert marker in text["models"], marker

required_service_markers = [
    "def can_view",
    "def is_conflicted",
    "def create_record",
    "def assign_owners",
    "def create_action",
    "def complete_action",
    "def verify_action",
    "def create_escalation",
    "def evaluate_overdue",
    "def closure_gate",
    "independent_closure_review_missing",
    "recurrence_controls_missing",
]
for marker in required_service_markers:
    assert marker in text["service"], marker

for marker in [
    "/records",
    "/board-indicators",
    "/owners",
    "/ownership-decision",
    "/conflicts",
    "/actions",
    "/escalations",
    "/closure-review",
    "/close",
    "/reopen",
    "/access-log",
]:
    assert marker in text["routes"], marker

for marker in [
    "/api/hr/fatigue/evaluate/{staff_member_id}",
    "/api/patient-care/episodes/{episode_id}/state",
    "/api/control-plane/handovers",
    "/api/control-plane/critical-results",
    "patient-care-blocker",
    "hr-fatigue",
    "control-plane-handover",
    "control-plane-critical-result",
]:
    assert marker in text["bridge"], marker

for marker in ["createdBy", "recordedBy", "acknowledgedBy", "fromActor", "auth.actor_name", "auth.auth_source"]:
    assert marker in text["attribution"], marker

assert 'path.startswith("/api/hr")' in text["auth"]
assert 'path.startswith("/api/patient-care")' in text["auth"]
assert 'path.startswith("/api/v25/safety")' in text["auth"]
assert "0019_cross_system_safety_control_v25" in text["migration"]
assert "0018_bounded_pilot_control_v24" in text["migration"]
assert "/safety-control" in text["system_control"]
assert "Protect first. Name the owner. Prove the fix." in text["ui"]

sections = [
    "Identity and attribution",
    "Access and confidentiality",
    "Staff welfare and fatigue",
    "Competence and scope of practice",
    "Absence and capacity",
    "Conduct, bullying and retaliation",
    "Patient deterioration and blockers",
    "Referral and triage",
    "Consent",
    "Estimates, insurance and financial communication",
    "Medication and pharmacy",
    "Diagnostics and critical results",
    "Handover",
    "Scheduling, rooms and equipment",
    "Discharge and owner communication",
    "Safeguarding and complaints",
    "Automation and AI",
    "Integrations and data integrity",
    "Downtime and recovery",
    "Incident investigation and closure",
    "Reporting and board visibility",
]
for section in sections:
    assert section in text["audit"], section

for forbidden in [
    "create medication order automatically",
    "administer medication automatically",
    "acknowledge result automatically",
    "autonomous diagnosis",
    "automatic discharge",
    "automatic admission",
]:
    assert forbidden not in (text["service"] + text["routes"] + text["bridge"]).lower(), forbidden

for proof_marker in [
    "Spoofed Browser User",
    "conflicted_assignment.status_code == 409",
    "indicator[\"title\"] == \"Restricted safety matter\"",
    "verificationStatus\"] == \"verified\"",
    "CROSS_SYSTEM_SAFETY_CONTROL_V25_SMOKE_PASSED",
]:
    assert proof_marker in text["proof"], proof_marker

print("CROSS_SYSTEM_SAFETY_CONTROL_V25_AUDIT_PASSED")
