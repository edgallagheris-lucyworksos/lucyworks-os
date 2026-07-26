"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 14, boxShadow: "0 5px 16px rgba(15,23,42,.05)" };
const field: React.CSSProperties = { width: "100%", minHeight: 46, border: "1px solid #94a3b8", borderRadius: 9, padding: "9px 10px", fontSize: 16, background: "white", color: "#0f172a", boxSizing: "border-box" };
const button: React.CSSProperties = { border: 0, borderRadius: 9, padding: "10px 13px", minHeight: 44, background: "#0f766e", color: "white", fontWeight: 850, cursor: "pointer" };

export const accessReviewRoles = ["admin", "governance_lead", "hospital_director", "clinical_director"];

export function AccessReviewWorkspaceV12() {
  const [items, setItems] = useState<any[]>([]);
  const [form, setForm] = useState({ subjectRef: "", subjectName: "", platformRole: "clinician", identityGroup: "referral_clinician", capabilities: "clinical.record, referral.accept, board.view", restrictions: "deployment.approve", dueDays: 30, reason: "Initial role and capability review" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const result = await apiGet<{ items: any[] }>("/api/v12/access-reviews");
      setItems(result.items); setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load access reviews"); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function createReview() {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson("/api/v12/access-reviews", { method: "POST", body: JSON.stringify({
        subjectRef: form.subjectRef,
        subjectName: form.subjectName,
        platformRole: form.platformRole,
        identityGroup: form.identityGroup,
        requestedCapabilities: form.capabilities.split(",").map(item => item.trim()).filter(Boolean),
        restrictedCapabilities: form.restrictions.split(",").map(item => item.trim()).filter(Boolean),
        dueDays: form.dueDays,
        reason: form.reason,
      }) });
      setMessage("Access review opened with an evidence record.");
      setForm({ ...form, subjectRef: "", subjectName: "" });
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create access review"); }
    finally { setBusy(false); }
  }

  async function decide(row: any, decision: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson(`/api/v12/access-reviews/${row.review_ref}`, { method: "PATCH", body: JSON.stringify({
        expectedVersion: row.version,
        decision,
        restrictedCapabilities: row.restricted_capabilities,
        reason: `${decision} after reviewing identity group, role and requested capabilities`,
      }) });
      setMessage(`Access review ${decision}.`);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Access review decision failed"); }
    finally { setBusy(false); }
  }

  return <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter,system-ui,sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}><div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}><div><span style={{ color: "#2dd4bf", fontWeight: 900, fontSize: 11, letterSpacing: ".13em" }}>IDENTITY GOVERNANCE V12</span><h1 style={{ fontSize: "clamp(38px,8vw,70px)", lineHeight: .93, margin: "6px 0" }}>Access review</h1></div><Link href="/system-control" style={{ color: "white" }}>← System control</Link></div><p style={{ color: "#94a3b8", maxWidth: 900 }}>A job title never grants access by itself. Record the verified subject, platform role, identity group, allowed capabilities and explicit restrictions, then make an accountable decision.</p></header>
    {error && <div style={{ ...panel, borderColor: "#ef4444", color: "#991b1b", marginTop: 10 }}>{error}</div>}
    {message && <div style={{ ...panel, borderColor: "#22c55e", color: "#166534", marginTop: 10 }}>{message}</div>}
    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,360px),1fr))", gap: 10, marginTop: 10 }}>
      <article style={{ ...panel, display: "grid", gap: 8, alignContent: "start" }}><h2 style={{ margin: 0 }}>Open review</h2><input style={field} placeholder="Verified subject reference" value={form.subjectRef} onChange={e => setForm({ ...form, subjectRef: e.target.value })}/><input style={field} placeholder="Subject name" value={form.subjectName} onChange={e => setForm({ ...form, subjectName: e.target.value })}/><input style={field} placeholder="Platform role" value={form.platformRole} onChange={e => setForm({ ...form, platformRole: e.target.value })}/><input style={field} placeholder="Identity group" value={form.identityGroup} onChange={e => setForm({ ...form, identityGroup: e.target.value })}/><textarea style={{ ...field, minHeight: 90 }} placeholder="Requested capabilities, comma separated" value={form.capabilities} onChange={e => setForm({ ...form, capabilities: e.target.value })}/><textarea style={{ ...field, minHeight: 80 }} placeholder="Restricted capabilities" value={form.restrictions} onChange={e => setForm({ ...form, restrictions: e.target.value })}/><input style={field} type="number" value={form.dueDays} onChange={e => setForm({ ...form, dueDays: Number(e.target.value) })}/><textarea style={{ ...field, minHeight: 80 }} value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })}/><button style={button} disabled={busy || !form.subjectRef || !form.subjectName} onClick={() => void createReview()}>Open evidence-backed review</button></article>
      <section style={{ display: "grid", gap: 9, alignContent: "start" }}><h2 style={{ margin: 0 }}>{items.length} reviews</h2>{items.map(row => <article key={row.review_ref} style={{ ...panel, borderColor: row.overdue ? "#ef4444" : row.status === "completed" ? "#86efac" : "#f59e0b" }}><div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><strong style={{ fontSize: 20 }}>{row.subject_name}</strong><b>{row.status}</b></div><p>{row.platform_role} · {row.identity_group}</p><p><strong>Capabilities:</strong> {row.requested_capabilities.join(" · ") || "none"}</p><p><strong>Restrictions:</strong> {row.restricted_capabilities.join(" · ") || "none"}</p><small>Due {new Date(row.due_at).toLocaleString()} · version {row.version}</small>{row.status !== "completed" && <div style={{ display: "flex", gap: 7, flexWrap: "wrap", marginTop: 8 }}><button disabled={busy} style={button} onClick={() => void decide(row, "approved")}>Approve</button><button disabled={busy} style={{ ...button, background: "#b45309" }} onClick={() => void decide(row, "restricted")}>Approve restricted</button><button disabled={busy} style={{ ...button, background: "#991b1b" }} onClick={() => void decide(row, "revoked")}>Revoke</button></div>}</article>)}</section>
    </section>
  </main>;
}
