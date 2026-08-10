"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { ResponsiveHospitalBoardV15 } from "@/components/responsive-hospital-board-v15";
import { StaffLocationGrid } from "@/components/staff-location-grid";

const allowedRoles = [
  "admin",
  "clinician",
  "clinical_director",
  "hospital_director",
  "nurse",
  "ops_manager",
  "senior_clinician",
  "supervisor",
];

type BoardView = "operations" | "staffing";

export default function HospitalBoardPage() {
  const [view, setView] = useState<BoardView>("operations");

  return (
    <AuthGuard allowedRoles={allowedRoles}>
      <div className="hospital-shell">
        <style>{shellCss}</style>
        <header className="hospital-shell__header">
          <div className="hospital-shell__identity">
            <div className="hospital-shell__mark">LW</div>
            <div>
              <span>LucyWorks OS</span>
              <h1>Hospital operations</h1>
            </div>
          </div>

          <nav className="hospital-shell__views" aria-label="Hospital board views">
            <button
              type="button"
              className={view === "operations" ? "active" : ""}
              onClick={() => setView("operations")}
            >
              Patient flow
            </button>
            <button
              type="button"
              className={view === "staffing" ? "active" : ""}
              onClick={() => setView("staffing")}
            >
              Staff & locations
            </button>
          </nav>

          <nav className="hospital-shell__links" aria-label="Hospital navigation">
            <Link href="/referral-intake">New referral</Link>
            <Link href="/workspace">Workspace</Link>
            <Link href="/system-control">System status</Link>
          </nav>
        </header>

        <div className="hospital-shell__status" role="status">
          <span className="hospital-shell__live" aria-hidden="true" />
          <strong>Operational workspace</strong>
          <span>Use patient flow for the live hospital picture. Use staff & locations to resolve ownership and capacity.</span>
        </div>

        {view === "operations" ? <ResponsiveHospitalBoardV15 /> : <StaffLocationGrid />}
      </div>
    </AuthGuard>
  );
}

const shellCss = `
.hospital-shell{min-height:100vh;background:#eef2f7;color:#172033;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.hospital-shell *{box-sizing:border-box}
.hospital-shell__header{position:sticky;top:0;z-index:40;display:grid;grid-template-columns:minmax(220px,1fr) auto auto;align-items:center;gap:18px;padding:12px 18px;background:rgba(255,255,255,.97);border-bottom:1px solid #d9e0ea;box-shadow:0 4px 18px rgba(15,23,42,.05);backdrop-filter:blur(12px)}
.hospital-shell__identity{display:flex;align-items:center;gap:11px;min-width:0}.hospital-shell__mark{display:grid;place-items:center;width:36px;height:36px;border-radius:9px;background:#12314f;color:#fff;font-size:12px;font-weight:900;letter-spacing:.06em}.hospital-shell__identity span{display:block;color:#607086;font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.hospital-shell__identity h1{margin:1px 0 0;color:#13243a;font-size:18px;line-height:1.15;font-weight:760;letter-spacing:-.015em}
.hospital-shell__views{display:flex;align-items:center;padding:3px;background:#edf1f5;border:1px solid #d8e0e9;border-radius:10px}.hospital-shell__views button{border:0;border-radius:7px;background:transparent;color:#526174;padding:8px 12px;font:inherit;font-size:13px;font-weight:700;cursor:pointer}.hospital-shell__views button.active{background:#fff;color:#15324d;box-shadow:0 1px 4px rgba(15,23,42,.13)}
.hospital-shell__links{display:flex;align-items:center;gap:6px}.hospital-shell__links a{color:#294761;text-decoration:none;font-size:12px;font-weight:700;padding:7px 9px;border-radius:7px}.hospital-shell__links a:hover{background:#edf2f7}
.hospital-shell__status{display:flex;align-items:center;gap:8px;min-height:36px;padding:7px 18px;background:#f8fafc;border-bottom:1px solid #dde4ed;color:#617083;font-size:11px}.hospital-shell__status strong{color:#24364a}.hospital-shell__live{width:7px;height:7px;border-radius:999px;background:#27855f;box-shadow:0 0 0 3px #d9f0e5}.hospital-shell__status span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:900px){.hospital-shell__header{grid-template-columns:1fr auto;padding:10px 12px;gap:9px}.hospital-shell__links{display:none}.hospital-shell__views button{padding:7px 9px;font-size:12px}.hospital-shell__status{padding:6px 12px}.hospital-shell__status span:last-child{display:none}}
@media(max-width:560px){.hospital-shell__identity h1{font-size:15px}.hospital-shell__identity span{display:none}.hospital-shell__mark{width:32px;height:32px}.hospital-shell__header{grid-template-columns:minmax(0,1fr) auto}.hospital-shell__views button{font-size:11px;padding:7px 8px}}
`;
