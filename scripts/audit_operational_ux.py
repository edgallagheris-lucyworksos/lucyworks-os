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

for path in WEB.rglob("*.tsx"):
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(ROOT))

    if "new Date().toISOString().slice(0, 10)" in text and path.name != "operational-date.ts":
        severity = "ERROR" if rel in active_date_surfaces else "WARN"
        add(severity, path, "LOCAL_DATE", "Operational dates must use the browser-local helper, not UTC truncation. Legacy or advanced surfaces remain visible as warnings until consolidated.")

    if "window.prompt(" in text or "window.alert(" in text:
        add("WARN", path, "MOBILE_DIALOG", "Browser prompts/alerts are weak on phone, inaccessible and provide poor evidence capture.")

    if "Raw data" in text or "JSON.stringify(data, null, 2)" in text:
        add("WARN", path, "RAW_DATA_UI", "Raw JSON or generic data presentation should not be a normal clinical/operational surface.")

    if "useState(\"\")" in text and "episodeRef" in text and "useSearchParams" not in text and "initialEpisode" not in text:
        add("WARN", path, "EPISODE_CONTEXT", "Episode-aware pages should load the episode passed in the URL instead of forcing copy/paste.")

    if "ModulePage" in text and any(core in rel for core in ["app/workspace/", "app/hospital-board/", "app/care/", "app/referral-intake/"]):
        add("ERROR", path, "GENERIC_CORE_SURFACE", "Core hospital work must not use the generic module renderer.")

    if "fetch(`${API_BASE}" in text and "lib/api" not in rel:
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

print("OPERATIONAL UX AUDIT PASSED (warnings remain visible for planned consolidation)\n")
