"use client";

import { requestEvidence } from "@/lib/evidence-dialog";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { apiGet, apiJson } from "@/lib/api-client";

type Comparison = {
  comparisonRef: string;
  sourceSystem: string;
  sourceRecordRef: string;
  episodeRef?: string | null;
  blockRef?: string | null;
  sourceSnapshot: Record<string, unknown>;
  canonicalSnapshot: Record<string, unknown>;
  mismatchCodes: string[];
  validationState: string;
  status: string;
  version: number;
  reviewedBy?: string | null;
  reviewNote?: string | null;
};

type Summary = { count: number; open: number; matched: number; mismatch: number; investigation: number; readyForPilotReview: boolean };

const panel: React.CSSProperties = { background: "#0f172a", border: "1px solid #334155", borderRadius: 15, padding: 14 };
const button: React.CSSProperties = { border: 0, borderRadius: 9, padding: "9px 12px", background: "#0f766e", color: "white", fontWeight: 800, cursor: "pointer", minHeight: 42 };

export default function ShadowModePage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "hospital_director", "governance_lead", "senior_clinician", "supervisor", "admin"]}>
    <CanonicalShadowWorkspace />
  </AuthGuard>;
}

function CanonicalShadowWorkspace() {
  const [rows, setRows] = useState<Comparison[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [sourceSystem, setSourceSystem] = useState("historical-export");
  const [jsonText, setJsonText] = useState('[{"source_record_ref":"row-1","episode_ref":"EP-001","phase":"consultation"}]');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [list, state] = await Promise.all([
        apiGet<{ comparisons: Comparison[] }>("/api/v7/shadow/comparisons"),
        apiGet<Summary>("/api/v7/shadow/summary"),
      ]);
      setRows(list.comparisons || []);
      setSummary(state);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load canonical shadow mode");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function importRows() {
    setBusy(true); setError(""); setMessage("");
    try {
      const parsed = JSON.parse(jsonText);
      if (!Array.isArray(parsed)) throw new Error("Import must be a JSON array");
      await apiJson("/api/v7/shadow/comparisons", { method: "POST", body: JSON.stringify({ source_system: sourceSystem, premises_ref: "bvs-bristol", rows: parsed }) });
      setMessage("Source rows compared against canonical episode and operational-block state.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Shadow import failed");
    } finally { setBusy(false); }
  }

  async function decide(row: Comparison, decision: string) {
    const note = await requestEvidence("Record the reason and evidence for this decision:");
    if (!note) return;
    setBusy(true); setError("");
    try {
      await apiJson(`/api/v7/shadow/comparisons/${row.comparisonRef}`, { method: "PATCH", body: JSON.stringify({ expected_version: row.version, decision, note }) });
      setMessage(`Comparison ${row.sourceRecordRef} reviewed.`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Review failed");
    } finally { setBusy(false); }
  }

  return <main style={{ minHeight: "100vh", background: "#020617", color: "white", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
    <header style={{ ...panel, background: "#071019" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div><span style={{ color: "#2dd4bf", fontWeight: 900, fontSize: 11, letterSpacing: ".12em" }}>CANONICAL VALIDATION</span><h1 style={{ margin: "5px 0", fontSize: "clamp(34px,7vw,66px)", lineHeight: .95 }}>Shadow Mode</h1></div>
        <Link href="/system-control" style={{ color: "white" }}>← System control</Link>
      </div>
      <p style={{ color: "#94a3b8", maxWidth: 900 }}>Imported hospital state is compared with canonical episodes and operational blocks. Reviews are versioned, attributed to the verified session and written to the evidence chain.</p>
    </header>

    {error && <section style={{ ...panel, borderColor: "#ef4444", marginTop: 10, color: "#fecaca" }}>{error}</section>}
    {message && <section style={{ ...panel, borderColor: "#22c55e", marginTop: 10, color: "#bbf7d0" }}>{message}</section>}

    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 8, marginTop: 10 }}>
      {[['Total', summary?.count || 0], ['Open', summary?.open || 0], ['Matched', summary?.matched || 0], ['Mismatch', summary?.mismatch || 0], ['Investigation', summary?.investigation || 0]].map(([label, value]) => <div key={String(label)} style={panel}><small style={{ color: "#94a3b8" }}>{label}</small><div style={{ fontSize: 30, fontWeight: 900 }}>{value}</div></div>)}
      <div style={{ ...panel, borderColor: summary?.readyForPilotReview ? "#22c55e" : "#ef4444" }}><small style={{ color: "#94a3b8" }}>Pilot review</small><div style={{ fontSize: 24, fontWeight: 900 }}>{summary?.readyForPilotReview ? "READY" : "BLOCKED"}</div></div>
    </section>

    <section style={{ ...panel, marginTop: 10, display: "grid", gap: 8 }}>
      <h2 style={{ margin: 0 }}>Import anonymised source state</h2>
      <input aria-label="Source system" value={sourceSystem} onChange={event => setSourceSystem(event.target.value)} style={{ padding: 10, borderRadius: 8, border: "1px solid #475569", fontSize: 16 }} />
      <textarea aria-label="Source rows JSON" value={jsonText} onChange={event => setJsonText(event.target.value)} style={{ minHeight: 130, padding: 10, borderRadius: 8, border: "1px solid #475569", fontSize: 16, fontFamily: "monospace" }} />
      <button disabled={busy} onClick={() => void importRows()} style={button}>{busy ? "Working…" : "Compare source rows"}</button>
    </section>

    <section style={{ display: "grid", gap: 9, marginTop: 10 }}>
      {rows.map(row => <article key={row.comparisonRef} style={{ ...panel, borderColor: row.mismatchCodes.length ? "#ef4444" : "#22c55e" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><strong>{row.sourceSystem} · {row.sourceRecordRef}</strong><span>{row.validationState.toUpperCase()} · v{row.version}</span></div>
        <p style={{ color: row.mismatchCodes.length ? "#fecaca" : "#bbf7d0" }}>{row.mismatchCodes.length ? row.mismatchCodes.join(", ") : "Canonical match"}</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: 8 }}>
          <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", background: "#020617", padding: 10, borderRadius: 8 }}>SOURCE\n{JSON.stringify(row.sourceSnapshot, null, 2)}</pre>
          <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", background: "#020617", padding: 10, borderRadius: 8 }}>CANONICAL\n{JSON.stringify(row.canonicalSnapshot, null, 2)}</pre>
        </div>
        <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
          <button disabled={busy} style={button} onClick={() => void decide(row, "accept_canonical")}>Accept canonical</button>
          <button disabled={busy} style={{ ...button, background: "#2563eb" }} onClick={() => void decide(row, "approve_source")}>Approve source</button>
          <button disabled={busy} style={{ ...button, background: "#b91c1c" }} onClick={() => void decide(row, "reject_source")}>Reject source</button>
          <button disabled={busy} style={{ ...button, background: "#a16207" }} onClick={() => void decide(row, "needs_investigation")}>Investigate</button>
        </div>
        {row.reviewedBy && <small style={{ color: "#94a3b8" }}>Reviewed by {row.reviewedBy}: {row.reviewNote}</small>}
      </article>)}
    </section>
  </main>;
}
