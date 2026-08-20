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


require(
    "docs/OPERATING_MODEL.md",
    "Patient",
    "Client",
    "Staff",
    "Commercial",
    "canonical episode",
    "Commercial metrics must be explainable",
)

require(
    "apps/web/app/hospital-board/page.tsx",
    "Hospital operations",
    "HospitalCommandCentre",
    "Command centre",
    "Schedule control",
    "Staff detail",
    "StaffLocationGrid",
)
require(
    "apps/web/components/hospital-command-centre.tsx",
    "rooms / areas",
    "Staff load",
    "Exceptions only",
    "Patient record",
    "Patient work",
    "Episode command",
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
    "Patient episode",
    "Find patient or episode",
    "Clinical work",
)

# Staff-facing actions call high-level governed commands; they do not invent or orchestrate evidence references.
require(
    "apps/web/components/episode-client-finance-actions.tsx",
    "/estimates/deliver-and-issue",
    "/charges",
    "/complaints",
    "/prescription-choice/deliver-and-record",
    "/api/auth/me",
)
forbid(
    "apps/web/components/episode-client-finance-actions.tsx",
    "/api/v8/episodes/",
    "episode-ui:",
    "fake-evidence",
    "synthetic-evidence",
    "informationDeliveryRef",
)

# The server owns authority resolution, communication evidence and the linked estimate/prescription records.
require(
    "apps/api/app/regulated_workflow_v32_client_actions.py",
    "active_authority",
    "CommunicationEventV8",
    "client_communication_evidence",
    "v32_estimate_written_delivery",
    "deliver_and_record_prescription_choice",
    "v32_prescription_choice_information",
    "create_regulated_estimate",
    "create_prescription_choice",
)
require(
    "apps/api/regulated_workflow_v32_client_actions_smoke_test.py",
    "estimates/deliver-and-issue",
    "prescription-choice/deliver-and-record",
    "legacy.status_code == 410",
)
require(
    "apps/api/app/regulated_workflow_v32_middleware.py",
    "LEGACY_ESTIMATE_WRITE",
    "status_code=410",
    "/api/v32/episodes/",
)

require(
    "apps/api/app/regulated_workflow_v32_routes.py",
    "clinical AI output requires review by a verified clinical role",
    "reviewed AI output must link to the final human-confirmed record",
)

require(
    "apps/web/components/hospital-value-panel.tsx",
    "Clinical exceptions",
    "Patients with planned care",
    "Blocked / unassigned",
    "Bookable capacity scheduled",
)
require(
    "apps/web/components/episode-governance-panel.tsx",
    "recorded charges",
    "estimate headroom",
    "over estimate ceiling",
)

require(
    ".github/workflows/platform-regression.yml",
    "LucyWorks Platform Regression",
    "ScriptDirectory.from_config",
    "get_current_head()",
    "regulated_workflow_v32_smoke_test.py",
    "regulated_workflow_v32_extension_smoke_test.py",
    "regulated_workflow_v32_client_actions_smoke_test.py",
    "speech_capture_v19_smoke_test.py",
    "npm run build",
)

print("LUCYWORKS_SYSTEM_READY_CONTRACT_OK")
