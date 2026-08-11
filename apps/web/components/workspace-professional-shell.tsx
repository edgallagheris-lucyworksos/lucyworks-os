"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { getOperationalContext } from "@/lib/operational-context";

export function WorkspaceProfessionalShell({ children }: { children: ReactNode }) {
  const [{ siteName }] = useState(() => getOperationalContext());
  return <div className="workspace-shell"><style>{css}</style>
    <header className="workspace-shell__header">
      <div className="workspace-shell__identity"><Link href="/hospital-board" className="workspace-shell__mark">LW</Link><div><h1>Patient workspace</h1><span>{siteName}</span></div></div>
      <nav><Link className="primary" href="/referral-intake">New referral</Link><Link href="/hospital-board">Hospital</Link><Link href="/system-control">System</Link></nav>
    </header>
    {children}
  </div>;
}

const css = `
.workspace-shell{min-height:100vh;background:#eef2f7;color:#172033;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.workspace-shell *{box-sizing:border-box}.workspace-shell__header{position:sticky;top:0;z-index:45;display:flex;justify-content:space-between;align-items:center;gap:14px;padding:10px 18px;background:rgba(255,255,255,.98);border-bottom:1px solid #d9e1e9;box-shadow:0 4px 16px rgba(15,23,42,.05);backdrop-filter:blur(14px)}.workspace-shell__identity{display:flex;align-items:center;gap:10px}.workspace-shell__mark{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:linear-gradient(145deg,#163a57,#102a42);color:#fff;text-decoration:none;font-size:11px;font-weight:900}.workspace-shell__identity h1{margin:0;color:#142b40;font-size:16px}.workspace-shell__identity span{display:block;margin-top:2px;color:#718095;font-size:9px;font-weight:700}.workspace-shell__header nav{display:flex;gap:5px}.workspace-shell__header nav a{padding:7px 9px;border-radius:7px;color:#294761;text-decoration:none;font-size:10px;font-weight:800}.workspace-shell__header nav a.primary{background:#173f5f;color:#fff}.workspace-shell .pc{min-height:0!important;background:transparent!important;padding:12px 18px 28px!important}.workspace-shell .pc>.hero{display:none!important}.workspace-shell .pc>.kpis{grid-template-columns:repeat(4,minmax(0,1fr))!important}.workspace-shell .pc>.kpis article:nth-child(5),.workspace-shell .pc>.kpis article:nth-child(6){display:none!important}.workspace-shell .pc .patient>.automation{display:none!important}.workspace-shell .pc .empty p,.workspace-shell .pc .empty a{display:none!important}.workspace-shell .pc .kpis article,.workspace-shell .pc .patient,.workspace-shell .pc .task,.workspace-shell .pc .empty{border-radius:10px!important;box-shadow:none!important}.workspace-shell .pc .head span{color:#657589!important;font-size:9px!important;letter-spacing:.09em!important}.workspace-shell .pc .head h2{font-size:20px!important;color:#1b3247!important}.workspace-shell .pc .patient header small{color:#8793a2!important;font-size:8px!important}.workspace-shell .pc .patient header h3{font-size:17px!important}.workspace-shell .pc .five div{border-radius:7px!important}.workspace-shell .pc .tabs button,.workspace-shell .pc .toolbar button{border-radius:8px!important}.workspace-shell .pc .toolbar{border-radius:10px!important;box-shadow:none!important}
@media(max-width:760px){.workspace-shell__header{padding:9px 10px}.workspace-shell__header nav a:not(.primary){display:none}.workspace-shell .pc{padding:8px!important}.workspace-shell .pc>.kpis{grid-template-columns:1fr 1fr!important}}
`;
