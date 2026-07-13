"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

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

type ApprovalQueuePanelProps = {
  patientCaseId: string;
  referralEpisodeId?: string;
  onDecision?: () => void | Promise<void>;
};

async function patchApproval(id: number, body: unknown) {
  const response = await fetch(`${API_BASE}/api/evidence/approvals/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`approval failed: ${response.status}`);
  return response.json();
}

export function ApprovalQueuePanel({ patientCaseId, referralEpisodeId, onDecision }: ApprovalQueuePanelProps) {
  const [approvals, setApprovals] = useState<ApprovalTask[]>([]);
  const [status, setStatus] = useState("idle");
  const [decidedBy, setDecidedBy] = useState("Clinical Director");
  const [decidedByRole, setDecidedByRole] = useState("clinical_director");
  const [note, setNote] = useState("reviewed and approved with responsibility retained by named supervisor");

  async function refresh() {
    if (!patientCaseId) return;
    try {
      const query = new URLSearchParams({ patient_case_id: patientCaseId });
      if (referralEpisodeId) query.set("referral_episode_id", referralEpisodeId);
      const response = await fetch(`${API_BASE}/api/evidence/approvals?${query.toString()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("approval queue unavailable");
      const data = await response.json();
      setApprovals(Array.isArray(data.approvals) ? data.approvals : []);
      setStatus("approvals online");
    } catch {
      setStatus("approvals offline");
    }
  }

  useEffect(() => { void refresh(); }, [patientCaseId, referralEpisodeId]);

  async function decide(item: ApprovalTask, decision: "approved" | "rejected") {
    setStatus(`${decision}...`);
    try {
      await patchApproval(item.id, { decision, decidedBy, decidedByRole, note });
      await refresh();
      await onDecision?.();
      setStatus(`approval ${decision}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "approval failed");
    }
  }

  const pending = approvals.filter((item) => item.status === "pending");
  const decided = approvals.filter((item) => item.status !== "pending");

  return <section className="approvalPanel"><style>{css}</style>
    <div className="approvalHead">
      <div>
        <span>Supervisor sign-off</span>
        <h3>Approval queue</h3>
        <p>{pending.length} pending · {decided.length} decided · {status}</p>
      </div>
      <button type="button" onClick={() => void refresh()}>Refresh approvals</button>
    </div>

    <div className="approvalControls">
      <label>Approver<input value={decidedBy} onChange={(event) => setDecidedBy(event.target.value)} /></label>
      <label>Role<select value={decidedByRole} onChange={(event) => setDecidedByRole(event.target.value)}><option value="clinical_director">clinical_director</option><option value="ops_manager">ops_manager</option><option value="senior_clinician">senior_clinician</option><option value="hospital_director">hospital_director</option><option value="supervisor">supervisor</option><option value="governance_lead">governance_lead</option><option value="clinician">clinician - should fail</option></select></label>
      <label>Decision note<textarea value={note} onChange={(event) => setNote(event.target.value)} /></label>
    </div>

    <section className="approvalList">
      {approvals.length ? approvals.map((item) => <article key={item.id} className={item.status === "pending" ? "pending" : item.status}>
        <div>
          <b>{item.event?.action || item.evidenceEventRef}</b>
          <p>{item.reason}</p>
          <small>{item.riskLevel} · {item.requiredRole} · requested by {item.requestedBy || "system"}</small>
          {item.event?.aiSystem || item.event?.aiModel ? <small>AI: {item.event.aiSystem || "AI"} {item.event.aiModel || ""} · human review {item.event.humanReviewStatus || "not recorded"}</small> : null}
          {item.event?.overrideReason ? <small>Override: {item.event.overrideReason}</small> : null}
          {item.status !== "pending" ? <small>Decision: {item.status} by {item.decidedBy || "unknown"} · {item.decisionNote || "no note"}</small> : null}
        </div>
        {item.status === "pending" ? <div className="approvalActions"><button type="button" onClick={() => void decide(item, "approved")}>Approve</button><button type="button" onClick={() => void decide(item, "rejected")}>Reject</button></div> : null}
      </article>) : <p className="empty">No approval tasks for this episode. Red-risk, override, supervisor-required and unreviewed AI evidence will appear here.</p>}
    </section>
  </section>;
}

const css = `.approvalPanel{margin-top:12px;background:white;border:1px solid #d8e0ec;border-radius:18px;padding:14px}.approvalHead{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;border-bottom:1px solid #e5e7eb;padding-bottom:10px}.approvalHead span{display:block;text-transform:uppercase;letter-spacing:.14em;color:#7c3aed;font-size:11px;font-weight:900}.approvalHead h3{font-size:24px;margin:3px 0}.approvalHead p{color:#475569;margin:6px 0 0}.approvalHead button,.approvalActions button{border:1px solid #cbd5e1;background:white;color:#0f172a;border-radius:999px;padding:9px 12px;text-decoration:none;font-weight:800;cursor:pointer}.approvalActions button:first-child{background:#0f172a;color:white;border-color:#0f172a}.approvalControls{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:9px;margin:12px 0}.approvalControls label{display:grid;gap:4px;color:#475569;font-size:12px;font-weight:800}.approvalControls input,.approvalControls select,.approvalControls textarea{width:100%;border:1px solid #cbd5e1;border-radius:10px;padding:9px;background:white;color:#0f172a;font:inherit}.approvalControls textarea{min-height:64px}.approvalList{display:grid;gap:8px}.approvalList article{display:grid;grid-template-columns:1fr auto;gap:10px;border:1px solid #d8e0ec;border-left:6px solid #f59e0b;border-radius:14px;padding:10px;background:#fff}.approvalList article.approved{border-left-color:#16a34a}.approvalList article.rejected{border-left-color:#dc2626}.approvalList b{display:block}.approvalList p{margin:4px 0;color:#475569}.approvalList small{display:block;color:#475569;margin-top:3px}.approvalActions{display:flex;gap:8px;align-items:start}.empty{color:#64748b}@media(max-width:760px){.approvalHead{display:grid}.approvalHead button,.approvalActions button{width:100%}.approvalList article{grid-template-columns:1fr}.approvalActions{display:grid}}`;
