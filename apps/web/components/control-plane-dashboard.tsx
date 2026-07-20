"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Summary = {
  pendingHandovers: number;
  overdueHandovers: number;
  redControls: number;
  overdueControls: number;
  unsafeServices: number;
  unapprovedAIModels: number;
  unacknowledgedCriticalResults: number;
  pendingApprovals: number;
};

type ControlPlaneData = {
  generatedAt?: string;
  summary: Summary;
  handovers: Array<{ id: number; handoverRef: string; referralEpisodeId: string; fromActor: string; toActor?: string; toRole: string; status: string; summary: string; dueAt?: string }>;
  controls: Array<{ id: number; controlRef: string; domain: string; title: string; responsibleRole: string; responsibleActor?: string; status: string; riskLevel: string; nextReviewAt?: string; correctiveAction?: string }>;
  services: Array<{ id: number; department: string; serviceName: string; operationalStatus: string; acceptingReferrals: boolean; staffingReady: boolean; equipmentReady: boolean; consumablesReady: boolean; limitingReason?: string }>;
  aiModels: Array<{ id: number; provider: string; modelName: string; modelVersion: string; purpose: string; riskClass: string; status: string; accountableOwner: string; humanReviewRule: string; knownLimitations?: string }>;
  criticalResults: Array<{ id: number; resultRef: string; resultType: string; severity: string; summary: string; status: string; assignedTo: string; dueAt?: string; actionTaken?: string }>;
  pendingApprovals: Array<{ id: number; reason: string; requiredRole: string; riskLevel: string; requestedBy: string; requestedAt?: string }>;
  recentEvidence: Array<{ eventRef: string; eventType: string; action: string; riskLevel: string; complianceDomain: string; actorName: string; createdAt?: string; eventHash?: string }>;
};

type Integrity = { ok: boolean; checked: number; legacyUnhashed: number; failures: Array<{ eventRef: string; type: string }>; headHash?: string };

const emptySummary: Summary = {
  pendingHandovers: 0,
  overdueHandovers: 0,
  redControls: 0,
  overdueControls: 0,
  unsafeServices: 0,
  unapprovedAIModels: 0,
  unacknowledgedCriticalResults: 0,
  pendingApprovals: 0,
};

function when(value?: string) {
  return value ? new Date(value).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "not set";
}

function tone(value?: string) {
  const normal = String(value || "").toLowerCase();
  if (["red", "failed", "non_compliant", "suspended", "unavailable", "rejected", "overdue"].includes(normal)) return "red";
  if (["amber", "pending", "not_assessed", "reduced", "draft", "awaiting_acknowledgement"].includes(normal)) return "amber";
  return "green";
}

export function ControlPlaneDashboard() {
  const [data, setData] = useState<ControlPlaneData>({
    summary: emptySummary,
    handovers: [],
    controls: [],
    services: [],
    aiModels: [],
    criticalResults: [],
    pendingApprovals: [],
    recentEvidence: [],
  });
  const [integrity, setIntegrity] = useState<Integrity | null>(null);
  const [status, setStatus] = useState("loading");

  async function refresh() {
    setStatus("refreshing");
    try {
      const [dashboardResponse, integrityResponse] = await Promise.all([
        apiFetch("/api/control-plane/dashboard", { cache: "no-store" }),
        apiFetch("/api/evidence/integrity", { cache: "no-store" }),
      ]);
      if (!dashboardResponse.ok || !integrityResponse.ok) throw new Error("control-plane API unavailable");
      setData(await dashboardResponse.json());
      setIntegrity(await integrityResponse.json());
      setStatus("live database");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "offline");
    }
  }

  useEffect(() => { void refresh(); }, []);

  const summary = data.summary || emptySummary;

  return <main className="controlPlane"><style>{css}</style>
    <header>
      <div><span>LucyWorks OS</span><h1>Hospital control plane</h1><p>Named responsibility, service readiness, regulatory controls, AI governance and tamper-evident operational evidence.</p></div>
      <nav><a href="/hospital-board">Board</a><a href="/patient-care">Patient care</a><a href="/approvals">Approvals</a><a href="/compliance">Compliance</a><button onClick={() => void refresh()}>Refresh</button></nav>
    </header>

    <section className="integrity">
      <b className={integrity?.ok ? "green" : "red"}>{integrity ? (integrity.ok ? "Evidence chain intact" : "Evidence integrity failure") : "Checking evidence chain"}</b>
      <span>{integrity?.checked || 0} hashed events checked · {integrity?.legacyUnhashed || 0} legacy unhashed · {status}</span>
      {integrity?.headHash ? <code>{integrity.headHash.slice(0, 20)}…</code> : null}
    </section>

    <section className="kpis">
      <article className={summary.unacknowledgedCriticalResults ? "red" : "green"}><b>{summary.unacknowledgedCriticalResults}</b><small>critical results awaiting action</small></article>
      <article className={summary.overdueHandovers ? "red" : "amber"}><b>{summary.pendingHandovers}</b><small>pending handovers · {summary.overdueHandovers} overdue</small></article>
      <article className={summary.redControls ? "red" : "amber"}><b>{summary.redControls}</b><small>red controls · {summary.overdueControls} overdue</small></article>
      <article className={summary.unsafeServices ? "red" : "green"}><b>{summary.unsafeServices}</b><small>reduced or unsafe services</small></article>
      <article className={summary.pendingApprovals ? "amber" : "green"}><b>{summary.pendingApprovals}</b><small>named approvals pending</small></article>
      <article className={summary.unapprovedAIModels ? "amber" : "green"}><b>{summary.unapprovedAIModels}</b><small>AI models not approved</small></article>
    </section>

    <section className="grid">
      <article className="panel critical">
        <h2>Critical results</h2>
        {data.criticalResults.length ? data.criticalResults.map((item) => <div className={`row ${tone(item.status)}`} key={item.id}><div><strong>{item.resultType}</strong><span>{item.resultRef} · {item.assignedTo}</span><p>{item.summary}</p></div><aside><b>{item.status.replaceAll("_", " ")}</b><small>{when(item.dueAt)}</small></aside></div>) : <p className="empty">No critical results in the control queue.</p>}
      </article>

      <article className="panel">
        <h2>Accountable handovers</h2>
        {data.handovers.length ? data.handovers.map((item) => <div className={`row ${tone(item.status)}`} key={item.id}><div><strong>{item.fromActor} → {item.toActor || item.toRole}</strong><span>{item.referralEpisodeId}</span><p>{item.summary}</p></div><aside><b>{item.status}</b><small>{when(item.dueAt)}</small></aside></div>) : <p className="empty">No accountable handovers recorded.</p>}
      </article>

      <article className="panel wide">
        <h2>Premises compliance controls</h2>
        {data.controls.length ? data.controls.map((item) => <div className={`row ${tone(item.riskLevel === "red" ? "red" : item.status)}`} key={item.id}><div><strong>{item.title}</strong><span>{item.domain} · {item.responsibleActor || item.responsibleRole}</span><p>{item.correctiveAction || "No corrective action recorded"}</p></div><aside><b>{item.status.replaceAll("_", " ")}</b><small>review {when(item.nextReviewAt)}</small></aside></div>) : <p className="empty">No premises controls registered yet.</p>}
      </article>

      <article className="panel">
        <h2>Service availability</h2>
        {data.services.length ? data.services.map((item) => <div className={`row ${tone(item.operationalStatus)}`} key={item.id}><div><strong>{item.serviceName}</strong><span>{item.department} · referrals {item.acceptingReferrals ? "open" : "closed"}</span><p>{item.limitingReason || `staff ${item.staffingReady ? "ready" : "not ready"} · equipment ${item.equipmentReady ? "ready" : "not ready"} · consumables ${item.consumablesReady ? "ready" : "not ready"}`}</p></div><aside><b>{item.operationalStatus}</b></aside></div>) : <p className="empty">No services registered.</p>}
      </article>

      <article className="panel">
        <h2>AI model register</h2>
        {data.aiModels.length ? data.aiModels.map((item) => <div className={`row ${tone(item.status)}`} key={item.id}><div><strong>{item.modelName} {item.modelVersion}</strong><span>{item.provider} · {item.riskClass} · owner {item.accountableOwner}</span><p>{item.purpose} · review: {item.humanReviewRule}</p></div><aside><b>{item.status}</b></aside></div>) : <p className="empty">No AI models registered.</p>}
      </article>

      <article className="panel">
        <h2>Approval queue</h2>
        {data.pendingApprovals.length ? data.pendingApprovals.map((item) => <div className={`row ${tone(item.riskLevel)}`} key={item.id}><div><strong>{item.reason}</strong><span>{item.requiredRole} · requested by {item.requestedBy}</span></div><aside><small>{when(item.requestedAt)}</small></aside></div>) : <p className="empty">No approvals pending.</p>}
      </article>

      <article className="panel">
        <h2>Recent evidence</h2>
        {data.recentEvidence.length ? data.recentEvidence.slice(0, 12).map((item) => <div className={`row ${tone(item.riskLevel)}`} key={item.eventRef}><div><strong>{item.action || item.eventType}</strong><span>{item.actorName} · {item.complianceDomain}</span><p>{item.eventHash ? `${item.eventHash.slice(0, 16)}…` : "legacy unhashed event"}</p></div><aside><b>{item.riskLevel}</b><small>{when(item.createdAt)}</small></aside></div>) : <p className="empty">No evidence events.</p>}
      </article>
    </section>
  </main>;
}

const css = `.controlPlane{min-height:100vh;background:#eef2f7;color:#111827;padding:14px;font-family:Inter,system-ui,sans-serif}.controlPlane *{box-sizing:border-box}.controlPlane header{display:flex;justify-content:space-between;gap:16px;background:#fff;border:1px solid #d7dee9;border-radius:20px;padding:18px;box-shadow:0 12px 30px rgba(15,23,42,.07)}.controlPlane header span{display:block;color:#1d4ed8;font-size:11px;font-weight:900;letter-spacing:.16em;text-transform:uppercase}.controlPlane h1{font-size:clamp(34px,7vw,68px);line-height:.94;margin:6px 0}.controlPlane p{color:#475569;margin:5px 0}.controlPlane nav{display:flex;gap:7px;flex-wrap:wrap;align-content:flex-start}.controlPlane a,.controlPlane button{border:1px solid #cbd5e1;border-radius:999px;background:#fff;color:#0f172a;padding:9px 12px;text-decoration:none;font-weight:800;cursor:pointer}.controlPlane button{background:#0f172a;color:#fff}.integrity{display:flex;align-items:center;gap:12px;flex-wrap:wrap;background:#fff;border:1px solid #d7dee9;border-radius:14px;padding:11px 14px;margin:12px 0}.integrity b{padding:5px 9px;border-radius:999px}.integrity b.green{background:#dcfce7;color:#166534}.integrity b.red{background:#fee2e2;color:#991b1b}.integrity span{color:#475569}.integrity code{margin-left:auto;color:#64748b}.kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:9px;margin-bottom:12px}.kpis article,.panel{background:#fff;border:1px solid #d7dee9;border-radius:17px;padding:13px}.kpis article{border-top:5px solid #94a3b8}.kpis article.red{border-top-color:#dc2626}.kpis article.amber{border-top-color:#f59e0b}.kpis article.green{border-top-color:#16a34a}.kpis b{font-size:32px;display:block}.kpis small{color:#64748b}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.panel.wide{grid-column:1/-1}.panel h2{margin:0 0 9px}.row{display:flex;justify-content:space-between;gap:12px;border:1px solid #e2e8f0;border-left:6px solid #64748b;border-radius:13px;padding:10px;margin-bottom:8px;background:#fff}.row.red{border-left-color:#dc2626;background:#fff7f7}.row.amber{border-left-color:#f59e0b;background:#fffbeb}.row.green{border-left-color:#16a34a;background:#f6fff8}.row strong,.row span,.row small{display:block}.row span,.row small{color:#64748b;font-size:12px;margin-top:3px}.row p{font-size:13px}.row aside{text-align:right;min-width:110px}.row aside b{text-transform:capitalize}.empty{color:#64748b}@media(max-width:1000px){.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:760px){.controlPlane{padding:9px}.controlPlane header{display:grid}.controlPlane nav a,.controlPlane nav button{flex:1;text-align:center}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.grid{grid-template-columns:1fr}.panel.wide{grid-column:auto}.row{display:grid}.row aside{text-align:left}.integrity code{margin-left:0}}`;
