"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalCommandOverview } from "@/components/hospital-command-overview";
import { HospitalPatientFlow } from "@/components/hospital-patient-flow";
import { ResponsiveHospitalBoardV15 } from "@/components/responsive-hospital-board-v15";
import { useOperationalContext } from "@/lib/operational-context";

const allowedRoles = ["admin", "clinician", "clinical_director", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"];
type BoardView = "overview" | "patients" | "resources";

export default function HospitalBoardPage() {
  const [view, setView] = useState<BoardView>("overview");
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
              <button type="button" className={view === "overview" ? "active" : ""} onClick={() => setView("overview")}>Overview</button>
              <button type="button" className={view === "patients" ? "active" : ""} onClick={() => setView("patients")}>Patient flow</button>
              <button type="button" className={view === "resources" ? "active" : ""} onClick={() => setView("resources")}>Resource grid</button>
            </nav>
            <nav className="hospital-shell__links" aria-label="Hospital navigation">
              <Link className="primary" href="/referral-intake">New referral</Link>
              <Link href="/workspace">Workspace</Link>
              <Link href="/system-control">System</Link>
              <span className="hospital-shell__user">{user.name}<small>{user.role.replaceAll("_", " ")}</small></span>
            </nav>
          </header>
          <main>
            {view === "overview" ? (
              <HospitalCommandOverview
                onOpenPatientFlow={() => setView("patients")}
                onOpenResourceGrid={() => setView("resources")}
              />
            ) : view === "patients" ? (
              <HospitalPatientFlow onOpenResourceGrid={() => setView("resources")} />
            ) : (
              <ResponsiveHospitalBoardV15 />
            )}
          </main>
        </div>
      )}
    </AuthGuard>
  );
}

const shellCss = `
.hospital-shell{min-height:100vh;background:#eef2f7;color:#172033;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.hospital-shell *{box-sizing:border-box}.hospital-shell__header{position:sticky;top:0;z-index:40;display:grid;grid-template-columns:minmax(220px,1fr) auto auto;align-items:center;gap:18px;padding:10px 18px;background:rgba(255,255,255,.98);border-bottom:1px solid #d9e1e9;box-shadow:0 4px 18px rgba(15,23,42,.05);backdrop-filter:blur(14px)}.hospital-shell__identity{display:flex;align-items:center;gap:10px;min-width:0}.hospital-shell__mark{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:linear-gradient(145deg,#163a57,#102a42);color:#fff;box-shadow:inset 0 0 0 1px rgba(255,255,255,.1)}.hospital-shell__mark span{font-size:11px;font-weight:900;letter-spacing:.03em}.hospital-shell__identity h1{margin:0;color:#13283c;font-size:17px;line-height:1.1;font-weight:780;letter-spacing:-.015em}.hospital-shell__identity>div:last-child>span{display:block;margin-top:2px;color:#6c7a8d;font-size:10px;font-weight:700}.hospital-shell__views{display:flex;align-items:center;padding:3px;background:#edf1f5;border:1px solid #d8e0e9;border-radius:9px}.hospital-shell__views button{min-height:32px;border:0;border-radius:6px;background:transparent;color:#59697b;padding:6px 11px;font:inherit;font-size:12px;font-weight:750;cursor:pointer;white-space:nowrap}.hospital-shell__views button.active{background:#fff;color:#17344e;box-shadow:0 1px 4px rgba(15,23,42,.13)}.hospital-shell__links{display:flex;align-items:center;gap:5px}.hospital-shell__links a{color:#294761;text-decoration:none;font-size:11px;font-weight:750;padding:7px 9px;border-radius:7px}.hospital-shell__links a:hover{background:#edf2f7}.hospital-shell__links a.primary{background:#173f5f;color:#fff}.hospital-shell__user{display:grid;margin-left:5px;padding-left:10px;border-left:1px solid #dce3ea;color:#253a4e;font-size:10px;font-weight:800;line-height:1.15}.hospital-shell__user small{margin-top:2px;color:#7a8797;font-size:8px;font-weight:700;text-transform:capitalize}@media(max-width:1080px){.hospital-shell__header{grid-template-columns:1fr auto;padding:9px 12px;gap:9px}.hospital-shell__views{justify-self:end}.hospital-shell__links{grid-column:1/-1;justify-content:flex-end;border-top:1px solid #edf0f3;padding-top:6px}.hospital-shell__links .hospital-shell__user{margin-right:auto;margin-left:0;padding-left:0;border-left:0}}
@media(max-width:620px){.hospital-shell__identity h1{font-size:15px}.hospital-shell__identity>div:last-child>span{font-size:9px}.hospital-shell__mark{width:31px;height:31px}.hospital-shell__header{grid-template-columns:1fr}.hospital-shell__views{justify-self:stretch;display:grid;grid-template-columns:repeat(3,1fr);width:100%}.hospital-shell__views button{font-size:10px;padding:6px 5px}.hospital-shell__links{grid-column:1}.hospital-shell__links a:not(.primary){display:none}.hospital-shell__user{display:none}}
`;
