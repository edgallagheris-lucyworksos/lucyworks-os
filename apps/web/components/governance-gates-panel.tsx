"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type GovernanceBlock = {
  id: string;
  time: string;
  what: string;
  subject?: string | null;
  blocker?: string | null;
  next?: string | null;
  consentStatus?: string | null;
  estimateStatus?: string | null;
  insuranceStatus?: string | null;
  pharmacyReady?: boolean | null;
  ownerUpdated?: boolean | null;
  referringVetReportSent?: boolean | null;
  dischargeClear?: boolean | null;
};

type GovernanceGate = {
  type: string;
  severity: "red" | "amber" | "green" | string;
  caseId: string;
  title: string;
  detail: string;
  source?: "explicit_state" | "text_fallback" | string;
  blocks: GovernanceBlock[];
};

function label(value: string) {
  return value.replaceAll("_", " ");
}

function stateLine(block: GovernanceBlock) {
  const parts = [
    block.consentStatus ? `consent ${block.consentStatus}` : "",
    block.estimateStatus ? `estimate ${block.estimateStatus}` : "",
    block.insuranceStatus ? `insurance ${block.insuranceStatus}` : "",
    block.pharmacyReady !== null && block.pharmacyReady !== undefined ? `pharmacy ${block.pharmacyReady ? "ready" : "not ready"}` : "",
    block.ownerUpdated !== null && block.ownerUpdated !== undefined ? `owner ${block.ownerUpdated ? "updated" : "not updated"}` : "",
    block.referringVetReportSent !== null && block.referringVetReportSent !== undefined ? `ref vet ${block.referringVetReportSent ? "sent" : "not sent"}` : "",
    block.dischargeClear !== null && block.dischargeClear !== undefined ? `discharge ${block.dischargeClear ? "clear" : "not clear"}` : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

export function GovernanceGatesPanel() {
  const [gates, setGates] = useState<GovernanceGate[]>([]);
  const [status, setStatus] = useState("loading");

  async function load() {
    try {
      const response = await fetch(`${API_BASE}/api/day-control/governance-gates`);
      if (!response.ok) throw new Error("governance request failed");
      const data = await response.json();
      setGates(Array.isArray(data.gates) ? data.gates : []);
      setStatus("api");
    } catch {
      setStatus("offline");
    }
  }

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => { void load(); }, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const red = gates.filter((gate) => gate.severity === "red").length;
  const amber = gates.filter((gate) => gate.severity === "amber").length;

  return <section className="gov"><style>{css}</style><header><div><b>Clinical/admin gates</b><small>Consent, estimate, insurance, pharmacy, owner update and referring-vet report governance. Explicit state is used before text fallback.</small></div><aside><strong>{red}</strong><span>hard blocks</span><strong>{amber}</strong><span>warnings</span></aside></header>{gates.length ? <div className="govList">{gates.slice(0, 8).map((gate, index) => <article key={`${gate.caseId}-${gate.type}-${index}`} className={`gate ${gate.severity}`}><strong>{gate.title}</strong><span>{label(gate.type)} · {gate.caseId} · {gate.source || "explicit_state"}</span><p>{gate.detail}</p>{gate.blocks?.length ? <small>{gate.blocks.map((block) => `${block.time} ${block.subject || block.what}`).join(" / ")}</small> : null}{gate.blocks?.some(stateLine) ? <em>{gate.blocks.map(stateLine).filter(Boolean).join(" / ")}</em> : null}</article>)}</div> : <p className="clear">No governance gates returned. Sync: {status}</p>}</section>;
}

const css = `.gov{border:1px solid #cbd5e1;background:#f8fafc;color:#0f172a;border-radius:12px;padding:10px;margin:10px 0}.gov header{display:flex;justify-content:space-between;gap:12px;align-items:start}.gov b,.gov small,.gov strong,.gov span{display:block}.gov small{color:#475569}.gov aside{display:grid;grid-template-columns:auto auto;gap:2px 8px;text-align:right}.gov aside strong{font-size:22px}.govList{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px;margin-top:8px}.gate{border:1px solid #cbd5e1;background:white;border-radius:10px;padding:8px;border-left-width:5px}.gate strong{font-size:13px}.gate span,.gate p,.gate small,.gate em{display:block;font-size:11px;margin:2px 0}.gate em{font-style:normal;color:#334155;background:#f1f5f9;border-radius:8px;padding:4px}.gate.red{border-left-color:#dc2626}.gate.amber{border-left-color:#d97706}.clear{margin:8px 0 0;color:#475569;font-size:12px}`;
