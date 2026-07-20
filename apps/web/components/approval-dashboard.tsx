"use client";

import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { getSession, type SessionUser } from "@/lib/session";

type ApprovalTask = {
  id: number;
  evidenceEventRef: string;
  patientCaseId?: string | null;
  referralEpisodeId?: string | null;
  status: string;
  requiredRole: string;
  reason: string;
  riskLevel: string;
  requestedBy?: string | null;
  requestedAt?: string | null;
  decidedBy?: string | null;
  decidedByRole?: string | null;
  decisionNote?: string | null;
  event?: {
    action?: string;
    actorName?: string;
    professionalRole?: string | null;
    aiSystem?: string | null;
    aiModel?: string | null;
    humanReviewStatus?: string | null;
    overrideReason?: string | null;
    complianceDomain?: string | null;
  } | null;
};

async function decideApproval(id: number, body: unknown) {
  const response = await apiFetch(`/api/evidence/approvals/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `approval failed: ${response.status}`);
  return data;
}

export function ApprovalDashboard() {
  const [approvals, setApprovals] = useState<ApprovalTask[]>([]);
  const [status, setStatus] = useState("loading");
  const [filter, setFilter] = useState("pending");
  const [approver, setApprover] = useState<SessionUser | null>(null);
  const [note, setNote] = useState("reviewed; responsibility retained by the verified approver");

  async function refresh() {
    try {
      const query = filter === "all" ? "" : `?status=${filter}`;
      const response = await apiFetch(`/api/evidence/approvals${query}`, { cache: "no-store" });
      if (!response.ok) throw new Error("approval queue unavailable");
      const data = await response.json();
      setApprovals(Array.isArray(data.approvals) ? data.approvals : []);
      setStatus("online");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "offline");
    }
  }

  useEffect(() => {
    setApprover(getSession()?.user || null);
    void refresh();
  }, [filter]);

  async function decide(item: ApprovalTask, decision: "approved" | "rejected") {
    setStatus(`${decision}...`);
    try {
      await decideApproval(item.id, { decision, note });
      await refresh();
      setStatus(`approval ${decision}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "approval failed");
    }
  }

  const counts = useMemo(() => ({
    total: approvals.length,
    pending: approvals.filter((item) => item.status === "pending").length,
    red: approvals.filter((item) => item.riskLevel === "red").length,
    ai: approvals.filter((item) => item.event?.aiSystem || item.event?.aiModel).length,
  }), [approvals]);

  return <main className="approvalDash"><style>{css}</style>
    <header>
      <div>
        <span>LucyWorks governance</span>
        <h1>Supervisor approvals</h1>
        <p>Sign-off queue for red-risk evidence, overrides, supervisor-required decisions and AI-linked events without completed human review.</p>
      </div>
      <nav><a href="/patient-care">Patient care</a><a href="/compliance">Compliance</a><a href="/hospital-board">Board</a></nav>
    </header>

    <section className="kpis"><article><b>{counts.total}</b><small>{filter} tasks</small></article><article><b>{counts.pending}</b><small>pending</small></article><article><b>{counts.red}</b><small>red risk</small></article><article><b>{counts.ai}</b><small>AI-linked</small></article></section>

    <section className="controls"><label>Filter<select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="pending">pending</option><option value="approved">approved</option><option value="rejected">rejected</option><option value="all">all</option></select></label><label>Verified approver<input value={approver ? `${approver.name} · ${approver.role}` : "verified login required"} readOnly /></label><label>Decision note<textarea value={note} onChange={(event) => setNote(event.target.value)} /></label><button onClick={() => void refresh()}>Refresh</button><small>{status}</small></section>

    <section className="queue">
      {approvals.length ? approvals.map((item) => <article key={item.id} className={item.status}>
        <div>
          <span>{item.riskLevel} · {item.status}</span>
          <h2>{item.event?.action || item.evidenceEventRef}</h2>
          <p>{item.reason}</p>
          <small>Case {item.patientCaseId || "not linked"} · Episode {item.referralEpisodeId || "not linked"} · Required {item.requiredRole}</small>
          <small>Evidence {item.evidenceEventRef} · Requested by {item.requestedBy || "system"}</small>
          {item.event?.aiSystem || item.event?.aiModel ? <small>AI: {item.event.aiSystem || "AI"} {item.event.aiModel || ""} · human review {item.event.humanReviewStatus || "not recorded"}</small> : null}
          {item.event?.overrideReason ? <small>Override: {item.event.overrideReason}</small> : null}
          {item.status !== "pending" ? <small>Decision: {item.status} by {item.decidedBy || "unknown"} / {item.decidedByRole || "role unknown"}. {item.decisionNote || "No note."}</small> : null}
        </div>
        {item.status === "pending" ? <div className="actions"><button onClick={() => void decide(item, "approved")}>Approve</button><button onClick={() => void decide(item, "rejected")}>Reject</button></div> : null}
      </article>) : <section className="empty"><h2>No approval tasks</h2><p>Approval tasks are generated from evidence events that are red-risk, override-based, supervisor-required or AI-linked without completed human review.</p></section>}
    </section>
  </main>;
}

const css = `.approvalDash{min-height:100vh;background:#f5f7fb;color:#111827;padding:14px;font-family:Inter,system-ui,sans-serif}.approvalDash *{box-sizing:border-box}.approvalDash header{display:flex;justify-content:space-between;gap:14px;background:white;border:1px solid #d8e0ec;border-radius:18px;padding:16px;box-shadow:0 10px 28px rgba(15,23,42,.06)}.approvalDash header span,.queue span{display:block;text-transform:uppercase;letter-spacing:.14em;color:#7c3aed;font-size:11px;font-weight:900}.approvalDash h1{font-size:clamp(34px,7vw,64px);line-height:.95;margin:6px 0}.approvalDash p{color:#475569;margin:6px 0 0}.approvalDash nav{display:flex;gap:8px;flex-wrap:wrap}.approvalDash a,.controls button,.actions button{border:1px solid #cbd5e1;background:white;color:#0f172a;border-radius:999px;padding:9px 12px;text-decoration:none;font-weight:800;cursor:pointer}.approvalDash a:first-child,.actions button:first-child{background:#0f172a;color:white;border-color:#0f172a}.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:12px 0}.kpis article,.controls,.queue article,.empty{background:white;border:1px solid #d8e0ec;border-radius:18px;padding:14px}.kpis b{font-size:32px;display:block}.kpis small,.queue small,.controls small{display:block;color:#64748b;margin-top:4px}.controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:9px;margin-bottom:12px;align-items:end}.controls label{display:grid;gap:4px;color:#475569;font-size:12px;font-weight:800}.controls input,.controls select,.controls textarea{width:100%;border:1px solid #cbd5e1;border-radius:10px;padding:9px;background:white;color:#0f172a;font:inherit}.controls input[readonly]{background:#f1f5f9}.controls textarea{min-height:56px}.queue{display:grid;gap:10px}.queue article{display:grid;grid-template-columns:1fr auto;gap:12px;border-left:7px solid #f59e0b}.queue article.approved{border-left-color:#16a34a}.queue article.rejected{border-left-color:#dc2626}.queue h2{margin:4px 0;font-size:24px}.actions{display:flex;gap:8px;align-items:start}.empty{text-align:center}@media(max-width:760px){.approvalDash{padding:10px}.approvalDash header{display:grid}.approvalDash nav{justify-content:stretch}.approvalDash a,.actions button,.controls button{width:100%;text-align:center}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.queue article{grid-template-columns:1fr}.actions{display:grid}}`;
