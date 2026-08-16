from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

board = (ROOT / "apps/web/components/responsive-hospital-board-v15.tsx").read_text()
shell = (ROOT / "apps/web/app/hospital-board/page.tsx").read_text()
episode = (ROOT / "apps/web/components/episode-command-shell.tsx").read_text()
auth = (ROOT / "apps/web/components/auth-guard.tsx").read_text()
context = (ROOT / "apps/web/lib/operational-context.ts").read_text()
referral = (ROOT / "apps/web/components/guided-referral-intake-v31.tsx").read_text()
workspace_shell = (ROOT / "apps/web/components/workspace-professional-shell.tsx").read_text()
workspace = (ROOT / "apps/web/components/operational-workspace-v16.tsx").read_text()
care = (ROOT / "apps/web/components/care-brief-v16.tsx").read_text()

required = {
    "one responsive hospital board": "Find patient, procedure, staff or episode" in board,
    "15-minute operational grid": "15-minute operating grid" in board and "DAY_START" in board and "gridBlock" in board,
    "governed board controls": all(value in board for value in ["MoveOperationalBlock", "Save assignment", "Recorded gates", "/delay-preview", "Preview consequences", "Insert emergency"]),
    "patient-first episode finder": "Find patient or episode" in episode,
    "site context abstraction": all("useOperationalContext" in value for value in [board, shell, referral, care]),
    "role-aware hospital shell": "user.name" in shell and "user.role" in shell,
    "professional access shell": "Secure hospital access" in auth,
    "server-authorised operational context": "/api/v26/context" in context and "apiGet" in context,
    "compact management indicators": "Operating indicators" in (ROOT / "apps/web/components/hospital-value-panel.tsx").read_text(),
    "professional referral workflow": "Referral intake" in referral and "Owner & authority" in referral and "Clinical need" in referral,
    "professional patient workspace": "Patient workspace" in workspace_shell and "Find patient, episode or next action" in workspace,
    "workspace focuses on care and ownership": "My attention" in workspace and "Data quality" in workspace,
    "professional care brief": "Care brief" in care and "Controls clear" in care and "Episode control" in care,
}

forbidden = {
    "legacy desktop board fallback": "HospitalMasterBoardV11" in board,
    "automation controls on patient-flow board": "AutomationBoardDockV23" in board or "Automation controls" in board,
    "component hard-coded premises constant": "const PREMISES" in board,
    "client-controlled premises context": "localStorage" in context or "URLSearchParams" in context,
    "hard-coded referral premises": 'premisesRef: "default-premises"' in referral,
    "visible referral version banner": "GUIDED REFERRAL INTAKE V31" in referral,
    "workspace version banner": "PATIENT COMMAND V16" in workspace,
    "workspace automation presentation": "Automation evidence" in workspace or "automation failures" in workspace.lower() or "automation mode" in workspace.lower(),
    "workspace synthetic empty state": "synthetic referral" in workspace.lower(),
    "care version banner": "CARE BRIEF V16" in care,
    "care oversized demo hero": "clamp(40px,8vw,72px)" in care,
    "visible synthetic wording": '>synthetic<' in shell.lower() or '>synthetic<' in referral.lower(),
    "visible demo wording": '>demo<' in shell.lower() or '>demo<' in referral.lower(),
    "visible prototype wording": '>prototype<' in shell.lower() or '>prototype<' in referral.lower(),
    "visible development wording in access shell": "Development environment" in auth,
}

failures = [name for name, passed in required.items() if not passed]
failures += [name for name, present in forbidden.items() if present]

if failures:
    raise SystemExit("Professional UI contract failed: " + "; ".join(failures))

print("PROFESSIONAL_UI_CONTRACT=PASS")
