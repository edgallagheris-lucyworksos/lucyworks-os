"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalValuePanel } from "@/components/hospital-value-panel";
import { ResponsiveHospitalBoardV15 } from "@/components/responsive-hospital-board-v15";
import { StaffLocationGrid } from "@/components/staff-location-grid";
import { useOperationalContext } from "@/lib/operational-context";

const allowedRoles = ["admin", "clinician", "clinical_director", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"];
type BoardView = "operations" | "staffing";

export default function HospitalBoardPage() {
  const [view, setView] = useState<BoardView>("operations");
  const { siteName } = useOperationalContext();

  return (
    <AuthGuard allowedRoles={allowedRoles}>
      {user => (
        <div className="hospital-shell">
          <style>{shellCss}</style>
          <header className="hospital-shell__header">
            <div className="hospital-shell__identity">
              <div className="hospital-shell__mark" aria-hidden="true"><span>LW</span></div>
              <div><h1>Hospital operations</h1><span>{siteName}</span></div>
            </div>
            <nav className="hospital-shell__views" aria-label="Hospital board views">
              <button type="button" className={view === "operations" ? "active" : ""} onClick={() => setView("operations")}>Patient flow</button>
              <button type="button" className={view === "staffing" ? "active" : ""} onClick={() => setView("staffing")}>Staff & locations</button>
            </nav>
            <nav className="hospital-shell__links" aria-label="Hospital navigation">
              <Link className="primary" href="/referral-intake">New referral</Link>
              <Link href="/workspace">Workspace</Link>
              <Link href="/system-control">System</Link>
              <span className="hospital-shell__user">{user.name}<small>{user.role.replaceAll("_", " ")}</small></span>
            </nav>
          </header>
          <main>
            <HospitalValuePanel />
            {view === "operations" ? <ResponsiveHospitalBoardV15 /> : <section className="hospital-shell__staff"><StaffLocationGrid /></section>}
          </main>
        </div>
      )}
    </AuthGuard>
  );
}

const shellCss = `
.hospital-shell{min-height:100vh;background:#eef2f7;color:#172033;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.hospital-shell *{box-sizing:border-box}.hospital-shell__header{position:sticky;top:0;z-index:40;display:grid;grid-template-columns:minmax(220px,1fr) auto auto;align-items:center;gap:18px;padding:10px 18px;background:rgba(255,255,255,.98);border-bottom:1px solid #d9e1e9;box-shadow:0 4px 18px rgba(15,23,42,.05);backdrop-filter:blur(14px)}.hospital-shell__identity{display:flex;align-items:center;gap:10px;min-width:0}.hospital-shell__mark{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:linear-gradient(145deg,#163a57,#102a42);color:#fff;box-shadow:inset 0 0 0 1px rgba(255,255,255,.1)}.hospital-shell__mark span{font-size:11px;font-weight:900;letter-spacing:.03em}.hospital-shell__identity h1{margin:0;color:#13283c;font-size:17px;line-height:1.1;font-weight:780;letter-spacing:-.015em}.hospital-shell__identity>div:last-child>span{display:block;margin-top:2px;color:#6c7a8d;font-size:10px;font-weight:700}.hospital-shell__views{display:flex;align-items:center;padding:3px;background:#edf1f5;border:1px solid #d8e0e9;border-radius:9px}.hospital-shell__views button{min-height:32px;border:0;border-radius:6px;background:transparent;color:#59697b;padding:6px 11px;font:inherit;font-size:12px;font-weight:750;cursor:pointer}.hospital-shell__views button.active{background:#fff;color:#17344e;box-shadow:0 1px 4px rgba(15,23,42,.13)}.hospital-shell__links{display:flex;align-items:center;gap:5px}.hospital-shell__links a{color:#294761;text-decoration:none;font-size:11px;font-weight:750;padding:7px 9px;border-radius:7px}.hospital-shell__links a:hover{background:#edf2f7}.hospital-shell__links a.primary{background:#173f5f;color:#fff}.hospital-shell__user{display:grid;margin-left:5px;padding-left:10px;border-left:1px solid #dce3ea;color:#253a4e;font-size:10px;font-weight:800;line-height:1.15}.hospital-shell__user small{margin-top:2px;color:#7a8797;font-size:8px;font-weight:700;text-transform:capitalize}.hospital-shell__staff{padding:12px 18px 28px}.hospital-shell__staff .slg{min-height:0!important;background:transparent!important;padding:0!important}.hospital-shell__staff .slg>.topbar,.hospital-shell__staff .slg>.rule{display:none!important}.hospital-shell__staff .slg>.commandStrip{margin:0 0 10px!important;gap:8px!important}.hospital-shell__staff .slg>.commandStrip div{border-radius:10px!important;padding:11px 12px!important;box-shadow:none!important}.hospital-shell__staff .slg>.commandStrip b{font-size:22px!important;color:#17334d!important}.hospital-shell__staff .slg>.commandStrip small{font-size:10px!important}.hospital-shell__staff .slg>.modebar{padding:9px 10px;margin:10px 0 6px!important;background:#fff;border:1px solid #d9e1e9;border-radius:10px}.hospital-shell__staff .slg>.filters{padding:6px 0 8px!important}.hospital-shell__staff .slg>.filters button,.hospital-shell__staff .slg>.modebar button{border-radius:8px!important;padding:7px 10px!important;font-size:11px!important}.hospital-shell__staff .slg>.diagnostics{border-radius:10px!important}.hospital-shell__staff .slg .column{border-radius:11px!important;box-shadow:none!important}.hospital-shell__staff .slg .workcard{border-radius:9px!important}.hospital-shell__staff .slg .work b{font-size:15px!important}.hospital-shell__staff .slg .work small{font-size:10px!important}.hospital-shell__staff .slg .work em{font-size:10px!important}
@media(max-width:980px){.hospital-shell__header{grid-template-columns:1fr auto;padding:9px 12px;gap:9px}.hospital-shell__links{grid-column:1/-1;justify-content:flex-end;border-top:1px solid #edf0f3;padding-top:6px}.hospital-shell__links .hospital-shell__user{margin-right:auto;margin-left:0;padding-left:0;border-left:0}}
@media(max-width:620px){.hospital-shell__identity h1{font-size:15px}.hospital-shell__identity>div:last-child>span{font-size:9px}.hospital-shell__mark{width:31px;height:31px}.hospital-shell__views button{font-size:10px;padding:6px 8px}.hospital-shell__links a:not(.primary){display:none}.hospital-shell__staff{padding:8px}.hospital-shell__user{display:none}.hospital-shell__staff .slg>.commandStrip{grid-template-columns:1fr 1fr!important}}
`;
