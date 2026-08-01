#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
API = ROOT / "apps" / "api" / "app"


@dataclass
class Finding:
    severity: str
    path: str
    rule: str
    detail: str


findings: list[Finding] = []


def add(severity: str, path: Path, rule: str, detail: str) -> None:
    findings.append(Finding(severity, str(path.relative_to(ROOT)), rule, detail))


active_date_surfaces = {
    "apps/web/components/operational-workspace-v16.tsx",
    "apps/web/components/responsive-hospital-board-v15.tsx",
    "apps/web/components/care-brief-v16.tsx",
}
public_auth_surfaces = {
    "apps/web/app/login/page.tsx",
    "apps/web/app/auth/callback/page.tsx",
}
episode_context_required = {
    "apps/web/components/hospital-command-workspace.tsx",
    "apps/web/components/detailed-patient-record-workspace.tsx",
    "apps/web/app/clinical-execution/page.tsx",
}
episode_context_markers = (
    "useSearchParams",
    "initialEpisode",
    'new URLSearchParams(window.location.search).get("episode")',
    "new URLSearchParams(window.location.search).get('episode')",
    "useParams",
    "params.episodeRef",
    "params: Promise<{ episodeRef:",
)

for path in WEB.rglob("*.tsx"):
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(ROOT))

    if "new Date().toISOString().slice(0, 10)" in text and path.name != "operational-date.ts":
        severity = "ERROR" if rel in active_date_surfaces else "WARN"
        add(severity, path, "LOCAL_DATE", "Operational dates must use the browser-local helper, not UTC truncation.")

    if "window.prompt(" in text or "window.alert(" in text:
        add("WARN", path, "MOBILE_DIALOG", "Browser prompts/alerts are weak on phone, inaccessible and provide poor evidence capture.")

    if "Raw data" in text or "JSON.stringify(data, null, 2)" in text:
        add("WARN", path, "RAW_DATA_UI", "Raw JSON or generic data presentation should not be a normal clinical/operational surface.")

    if rel in episode_context_required and not any(marker in text for marker in episode_context_markers):
        add("WARN", path, "EPISODE_CONTEXT", "Episode Command, Patient Record and Clinical Execution must load the selected episode from URL, route parameters or an explicit initial episode prop.")

    if "ModulePage" in text and any(core in rel for core in ["app/workspace/", "app/hospital-board/", "app/care/", "app/referral-intake/"]):
        add("ERROR", path, "GENERIC_CORE_SURFACE", "Core hospital work must not use the generic module renderer.")

    if rel not in public_auth_surfaces and "fetch(`${API_BASE}" in text and "lib/api" not in rel:
        add("ERROR" if "hospital-shell" in rel else "WARN", path, "AUTH_BYPASS", "Use the shared authenticated API client so cookies, CSRF and session expiry are handled consistently.")

shell = WEB / "components" / "hospital-shell.tsx"
if shell.exists():
    text = shell.read_text(encoding="utf-8")
    if "contentFor(" in text or "moduleByTitle" in text:
        add("ERROR", shell, "TITLE_SUBSTITUTION", "A shell must never replace page content based on a display title.")

workspace = API / "workspace_routes.py"
if workspace.exists():
    text = workspace.read_text(encoding="utf-8")
    if "role: str = Query" in text and "require_authenticated" not in text:
        add("ERROR", workspace, "ROLE_IMPERSONATION", "Workspace scope must come from verified identity, not a browser role query.")
    if "actor_name=f\"workspace:{role}\"" in text:
        add("ERROR", workspace, "AUDIT_ATTRIBUTION", "Audit attribution must use the verified actor name.")

required = {
    WEB / "app" / "workspace" / "page.tsx": "OperationalWorkspaceV16",
    WEB / "app" / "care" / "page.tsx": "CareBriefV16",
    WEB / "app" / "hospital-board" / "page.tsx": "ResponsiveHospitalBoardV15",
    WEB / "app" / "referral-intake" / "page.tsx": "GuidedReferralIntakeV31",
}
for path, marker in required.items():
    if not path.exists() or marker not in path.read_text(encoding="utf-8"):
        add("ERROR", path, "PRIMARY_SURFACE", f"Primary surface must use {marker}.")

print("\n--- LUCYWORKS OPERATIONAL UX AUDIT ---\n")
for severity in ("ERROR", "WARN"):
    rows = [item for item in findings if item.severity == severity]
    print(f"{severity}: {len(rows)}")
    for item in rows:
        print(f"- {item.path} [{item.rule}] {item.detail}")
    print()

errors = [item for item in findings if item.severity == "ERROR"]
if errors:
    raise SystemExit(f"Operational UX audit failed with {len(errors)} blocking finding(s)")

print("OPERATIONAL UX AUDIT PASSED\n")
