"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 14, boxShadow: "0 5px 16px rgba(15,23,42,.05)" };
const field: React.CSSProperties = { width: "100%", minHeight: 44, border: "1px solid #94a3b8", borderRadius: 9, padding: "9px 10px", fontSize: 16, background: "white", color: "#0f172a", boxSizing: "border-box" };
const button: React.CSSProperties = { border: 0, borderRadius: 9, padding: "10px 13px", minHeight: 44, background: "#0f766e", color: "white", fontWeight: 850, cursor: "pointer" };

export const assuranceControlRoles = ["clinical_director", "governance_lead", "hospital_director"];

export function AssuranceControlWorkspaceV12() {
  const [readiness, setReadiness] = useState<any | null>(null);
  const [summary, setSummary] = useState<any | null>(null);
  const [controlRef, setControlRef] = useState("");
  const [evidenceSummary, setEvidenceSummary] = useState("");
  const [evidenceSource, setEvidenceSource] = useState("");
  const [organisation, setOrganisation] = useState("");
  const [target, setTarget] = useState("shadow");
  const [refs, setRefs] = useState({ identityEvidenceRef: "", dataGovernanceEvidenceRef: "", vendorEvidenceRef: "", clinicalSafetyOfficerEvidenceRef: "", dpiaEvidenceRef: "", penetrationTestEvidenceRef: "", staffUatEvidenceRef: "" });
  const [reviewOutcome, setReviewOutcome] = useState("approved");
  const [reviewReason, setReviewReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [ready, assurance] = await Promise.all([
        apiGet<any>("/api/production-readiness/dashboard"),
        apiGet<any>("/api/v10/compliance-safety/summary"),
      ]);
      setReadiness(ready); setSummary(assurance);
      if (!controlRef && ready.controls?.length) setControlRef(ready.controls[0].controlRef);
      if (assurance.deploymentProfile) {
        const profile = assurance.deploymentProfile;
        setOrganisation(current => current || profile.organisationName || "");
        setTarget(profile.target || "shadow");
        setRefs(current => ({
          identityEvidenceRef: current.identityEvidenceRef || profile.identityEvidenceRef || "",
          dataGovernanceEvidenceRef: current.dataGovernanceEvidenceRef || profile.dataGovernanceEvidenceRef || "",
          vendorEvidenceRef: current.vendorEvidenceRef || profile.vendorEvidenceRef || "",
          clinicalSafetyOfficerEvidenceRef: current.clinicalSafetyOfficerEvidenceRef || profile.clinicalSafetyOfficerEvidenceRef || "",
          dpiaEvidenceRef: current.dpiaEvidenceRef || profile.dpiaEvidenceRef || "",
          penetrationTestEvidenceRef: current.penetrationTestEvidenceRef || profile.penetrationTestEvidenceRef || "",
          staffUatEvidenceRef: current.staffUatEvidenceRef || profile.staffUatEvidenceRef || "",
        }));
      }
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load assurance controls"); }
  }, [controlRef]);

  useEffect(() => { void load(); }, [load]);

  async function bootstrap() {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson("/api/production-readiness/bootstrap", { method: "POST" });
      await apiJson("/api/v10/compliance-safety/bootstrap", { method: "POST" });
      setMessage("Readiness controls, safety case and deployment profile reconciled.");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Assurance bootstrap failed"); }
    finally { setBusy(false); }
  }

  async function recordEvidence() {
    if (!controlRef || !evidenceSummary) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiJson<any>(`/api/production-readiness/controls/${controlRef}/evidence`, { method: "POST", body: JSON.stringify({ evidenceType: "reviewed_record", summary: evidenceSummary, sourceRef: evidenceSource || null }) });
      setMessage(`Evidence ${result.evidence.evidenceRef} recorded. Pass the control after reviewing it.`);
      setEvidenceSummary(""); setEvidenceSource("");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Evidence recording failed"); }
    finally { setBusy(false); }
  }

  async function markControl(control: any, status: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson(`/api/production-readiness/controls/${control.controlRef}`, { method: "PATCH", body: JSON.stringify({ expectedVersion: control.version, status, evidenceSummary: control.evidenceSummary || `Control ${status}`, reason: `Readiness control ${status} after accountable evidence review`, validDays: 180 }) });
      setMessage(`${control.title} marked ${status}.`);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Control update failed"); }
    finally { setBusy(false); }
  }

  async function configureTarget() {
    const profile = summary?.deploymentProfile;
    if (!profile) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson(`/api/v10/compliance-safety/deployment-profile/${profile.profileRef}`, { method: "PATCH", body: JSON.stringify({ expectedVersion: profile.version, target, dataMode: target === "shadow" ? "shadow_copy" : "live", identityMode: "hospital_oidc", vendorMode: "governed_adapters", realIdentityConfirmed: false, realDataGovernanceConfirmed: false, realVendorConnectionsConfirmed: false, clinicalSafetyOfficerConfirmed: false, dpiaApproved: false, penetrationTestConfirmed: false, staffUatConfirmed: false, reason: `Deployment target configured as ${target}; evidence confirmations remain false until bound` }) });
      setMessage(`Deployment target set to ${target}.`);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Target configuration failed"); }
    finally { setBusy(false); }
  }

  async function bindEvidence() {
    const profile = summary?.deploymentProfile;
    if (!profile) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson(`/api/v10/compliance-safety/deployment-profile/${profile.profileRef}/evidence`, { method: "PATCH", body: JSON.stringify({ expectedVersion: profile.version, organisationName: organisation, ...Object.fromEntries(Object.entries(refs).map(([key, value]) => [key, value || null])), reason: "Bind current passed-control evidence to the named deploying organisation" }) });
      setMessage("Deployment evidence bound to the named organisation.");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Deployment evidence binding failed"); }
    finally { setBusy(false); }
  }

  async function recordSafetyReview() {
    const safetyCase = summary?.safetyCase;
    if (!safetyCase) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson("/api/v10/compliance-safety/reviews", { method: "POST", body: JSON.stringify({ safetyCaseRef: safetyCase.safetyCaseRef, reviewType: "target_release_review", target, outcome: reviewOutcome, findings: [{ code: "target", status: reviewOutcome, detail: reviewReason }], reason: reviewReason }) });
      setMessage(`${target} safety review recorded as ${reviewOutcome}.`);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Safety review failed"); }
    finally { setBusy(false); }
  }

  const controls = readiness?.controls || [];
  const selected = controls.find((row: any) => row.controlRef === controlRef);
  const profile = summary?.deploymentProfile;
  const gate = summary?.gates?.[target];

  return <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter,system-ui,sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}><div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}><div><span style={{ color: "#2dd4bf", fontWeight: 900, fontSize: 11, letterSpacing: ".13em" }}>DEPLOYMENT ASSURANCE CONTROL</span><h1 style={{ fontSize: "clamp(38px,8vw,70px)", lineHeight: .93, margin: "6px 0" }}>Evidence to release</h1></div><div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}><Link href="/compliance-safety" style={{ color: "white" }}>Compliance</Link><Link href="/system-control" style={{ color: "white" }}>System control</Link></div></div><p style={{ color: "#94a3b8", maxWidth: 980 }}>Record evidence, formally pass the matching readiness control, bind only current passed-control evidence to a named organisation, then make a separate target safety decision.</p><button disabled={busy} style={button} onClick={() => void bootstrap()}>Reconcile assurance records</button></header>
    {error && <div style={{ ...panel, borderColor: "#ef4444", color: "#991b1b", marginTop: 10 }}>{error}</div>}
    {message && <div style={{ ...panel, borderColor: "#22c55e", color: "#166534", marginTop: 10 }}>{message}</div>}
    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,360px),1fr))", gap: 10, marginTop: 10 }}>
      <article style={{ ...panel, display: "grid", gap: 8, alignContent: "start" }}><h2 style={{ margin: 0 }}>1. Readiness evidence</h2><select style={field} value={controlRef} onChange={e => setControlRef(e.target.value)}>{controls.map((row: any) => <option key={row.controlRef} value={row.controlRef}>{row.controlRef} · {row.status}</option>)}</select>{selected && <><p><strong>{selected.title}</strong><br/>{selected.description}</p><small>Owner {selected.ownerRole} · version {selected.version} · evidence {selected.evidenceRef || "none"}</small></>}<textarea style={{ ...field, minHeight: 90 }} placeholder="Evidence summary" value={evidenceSummary} onChange={e => setEvidenceSummary(e.target.value)}/><input style={field} placeholder="Source reference" value={evidenceSource} onChange={e => setEvidenceSource(e.target.value)}/><button disabled={busy || !selected || !evidenceSummary} style={button} onClick={() => void recordEvidence()}>Record durable evidence</button>{selected && <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}><button disabled={busy || !selected.evidenceRef} style={button} onClick={() => void markControl(selected, "passed")}>Pass control</button><button disabled={busy} style={{ ...button, background: "#991b1b" }} onClick={() => void markControl(selected, "failed")}>Fail control</button></div>}</article>
      <article style={{ ...panel, display: "grid", gap: 8, alignContent: "start" }}><h2 style={{ margin: 0 }}>2. Deployment profile</h2><select style={field} value={target} onChange={e => setTarget(e.target.value)}><option value="synthetic">Synthetic</option><option value="historical_replay">Historical replay</option><option value="shadow">Shadow</option><option value="bounded_pilot">Bounded pilot</option><option value="live">Live</option></select><button disabled={busy || !profile} style={{ ...button, background: "#334155" }} onClick={() => void configureTarget()}>Set target without false confirmations</button><input style={field} placeholder="Deploying legal organisation" value={organisation} onChange={e => setOrganisation(e.target.value)}/>{Object.keys(refs).map(key => <input key={key} style={field} placeholder={key} value={(refs as any)[key]} onChange={e => setRefs({ ...refs, [key]: e.target.value })}/>) }<button disabled={busy || !profile || !organisation} style={button} onClick={() => void bindEvidence()}>Bind passed-control evidence</button><small>Profile {profile?.profileRef || "not bootstrapped"} · version {profile?.version ?? "—"}</small></article>
      <article style={{ ...panel, display: "grid", gap: 8, alignContent: "start", borderColor: gate?.canRelease ? "#86efac" : "#ef4444" }}><h2 style={{ margin: 0 }}>3. Target safety decision</h2><p><strong>{target.replaceAll("_", " ")}</strong> · {gate?.canRelease ? "control gate clear" : `${gate?.blockers?.length || 0} blockers`}</p>{gate?.blockers?.map((row: any) => <small key={row.code}><strong>{row.code}</strong> — {row.detail}</small>)}<select style={field} value={reviewOutcome} onChange={e => setReviewOutcome(e.target.value)}><option value="approved">Approved</option><option value="approved_with_conditions">Approved with conditions</option><option value="changes_required">Changes required</option><option value="rejected">Rejected</option></select><textarea style={{ ...field, minHeight: 100 }} placeholder="Accountable findings and decision reason" value={reviewReason} onChange={e => setReviewReason(e.target.value)}/><button disabled={busy || !summary?.safetyCase || !reviewReason} style={button} onClick={() => void recordSafetyReview()}>Record target safety review</button><small>Approval is rejected by the API while control evidence remains blocked.</small></article>
    </section>
  </main>;
}
