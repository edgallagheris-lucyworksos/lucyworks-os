from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    file = ROOT / path
    assert file.exists(), f"missing required system file: {path}"
    return file.read_text(encoding="utf-8")


def require(path: str, *needles: str) -> None:
    text = read(path)
    for needle in needles:
        assert needle in text, f"{path} missing required contract: {needle}"


def forbid(path: str, *needles: str) -> None:
    text = read(path)
    for needle in needles:
        assert needle not in text, f"{path} contains prohibited production shortcut: {needle}"


# One explicit operating model ties clinical, client, staff and commercial outcomes together.
require(
    "docs/OPERATING_MODEL.md",
    "Patient",
    "Client",
    "Staff",
    "Commercial",
    "canonical episode",
    "Commercial metrics must be explainable",
)

# Normal hospital staff enter through product shells rather than historical versioned components.
require(
    "apps/web/app/hospital-board/page.tsx",
    "Hospital operations",
    "HospitalValuePanel",
    "Patient flow",
    "Staff & locations",
    "StaffLocationGrid",
)
require(
    "apps/web/app/episode-command/page.tsx",
    "EpisodeCommandShell",
    "HospitalCommandWorkspace",
    "EpisodeGovernancePanel",
    "EpisodeClientFinanceActions",
    "EpisodeComplaintControl",
)
require(
    "apps/web/components/episode-command-shell.tsx",
    "Patient episode control",
    "Clinical state, authority, client communication, evidence and financial controls share one patient context.",
)

# Staff-facing finance/client actions must create real evidence rather than browser-invented references.
require(
    "apps/web/components/episode-client-finance-actions.tsx",
    "/estimates/deliver-and-issue",
    "/charges",
    "/complaints",
    "/prescription-choice",
    "/communications",
    "/api/auth/me",
)
forbid(
    "apps/web/components/episode-client-finance-actions.tsx",
    "episode-ui:",
    "fake-evidence",
    "synthetic-evidence",
)

# The server owns estimate authority/delivery evidence and keeps legacy issue writes behind the boundary.
require(
    "apps/api/app/regulated_workflow_v32_client_actions.py",
    "active_authority",
    "CommunicationEventV8",
    "v32_estimate_written_delivery",
    "create_regulated_estimate",
)
require(
    "apps/api/app/regulated_workflow_v32_middleware.py",
    "LEGACY_ESTIMATE_WRITE",
    "status_code=410",
    "/api/v32/episodes/",
)

# AI-assisted clinical output stays draft until an authorised human review links the final record.
require(
    "apps/api/app/regulated_workflow_v32_routes.py",
    "clinical AI output requires review by a verified clinical role",
    "reviewed AI output must link to the final human-confirmed record",
)

# Commercial presentation must distinguish capacity/revenue evidence from actual profit.
require(
    "apps/web/components/hospital-value-panel.tsx",
    "Commercial capacity",
    "not a claimed profit margin",
)
require(
    "apps/web/components/episode-governance-panel.tsx",
    "recorded charges",
    "estimate headroom",
    "over estimate ceiling",
)

# One authoritative platform gate follows the actual Alembic head and builds the hospital web app.
require(
    ".github/workflows/platform-regression.yml",
    "LucyWorks Platform Regression",
    "ScriptDirectory.from_config",
    "get_current_head()",
    "regulated_workflow_v32_smoke_test.py",
    "regulated_workflow_v32_extension_smoke_test.py",
    "speech_capture_v19_smoke_test.py",
    "npm run build",
)

print("LUCYWORKS_SYSTEM_READY_CONTRACT_OK")
