from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

board = (ROOT / "apps/web/components/responsive-hospital-board-v15.tsx").read_text()
shell = (ROOT / "apps/web/app/hospital-board/page.tsx").read_text()
episode = (ROOT / "apps/web/components/episode-command-shell.tsx").read_text()
auth = (ROOT / "apps/web/components/auth-guard.tsx").read_text()
context = (ROOT / "apps/web/lib/operational-context.ts").read_text()

required = {
    "one responsive hospital board": "Find patient, procedure, staff or episode" in board,
    "patient-first episode finder": "Find patient or episode" in episode,
    "site context abstraction": "getOperationalContext" in board and "getOperationalContext" in shell,
    "role-aware hospital shell": "user.name" in shell and "user.role" in shell,
    "professional access shell": "Secure hospital access" in auth,
    "operational context persistence": "lucyworks.premisesRef" in context,
}

forbidden = {
    "legacy desktop board fallback": "HospitalMasterBoardV11" in board,
    "automation controls on patient-flow board": "AutomationBoardDockV23" in board or "Automation controls" in board,
    "component hard-coded premises constant": "const PREMISES" in board,
    "visible prototype wording in hospital shell": any(term in shell for term in ["synthetic", "demo", "prototype", "master board v", "V11", "V15"]),
    "visible development wording in access shell": "Development environment" in auth,
}

failures = [name for name, passed in required.items() if not passed]
failures += [name for name, present in forbidden.items() if present]

if failures:
    raise SystemExit("Professional UI contract failed: " + "; ".join(failures))

print("PROFESSIONAL_UI_CONTRACT=PASS")
