"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type ShadowSummary = {
  count?: number;
  pending?: number;
  matched?: number;
  mismatch?: number;
  approved?: number;
  rejected?: number;
  records?: any[];
};

export default function ShadowModePage() {
  const [summary, setSummary] = useState<ShadowSummary>({});
  const [records, setRecords] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [summaryRes, recordsRes] = await Promise.all([
        fetch(`${API_BASE}/api/shadow-mode/summary`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/shadow-mode/records`, { cache: "no-store" }),
      ]);
      const summaryData = await summaryRes.json().catch(() => ({}));
      const recordsData = await recordsRes.json().catch(() => ({}));
      if (!summaryRes.ok) throw new Error(JSON.stringify(summaryData));
      if (!recordsRes.ok) throw new Error(JSON.stringify(recordsData));
      setSummary(summaryData);
      setRecords(recordsData.records || summaryData.records || []);
    } catch {
      setError("Shadow Mode API unavailable. Backend or API base needs checking.");
      setSummary({ count: 0, pending: 0, matched: 0, mismatch: 0, approved: 0, rejected: 0, records: [] });
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }

  async function validate() {
    await fetch(`${API_BASE}/api/shadow-mode/validate`, { method: "POST" });
    await load();
  }

  async function approve(id: number) {
    await fetch(`${API_BASE}/api/shadow-mode/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [id], actor_name: "LucyWorks UI", note: "Approved from Shadow Mode screen" }),
    });
    await load();
  }

  async function reject(id: number) {
    await fetch(`${API_BASE}/api/shadow-mode/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [id], actor_name: "LucyWorks UI", note: "Rejected from Shadow Mode screen" }),
    });
    await load();
  }

  useEffect(() => { load(); }, []);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "admin"]}>
      {() => (
        <HospitalShell title="Shadow Mode" subtitle="side-by-side validation before workflow replacement">
          <div className="lw-neo-page">
            <section className="lw-hero-panel">
              <div className="lw-hero-content">
                <span className="lw-eyebrow">LucyWorks / validation layer</span>
                <h1>Shadow Mode</h1>
                <p>Compare imported hospital state against LucyWorks detected truth before approving operational change.</p>
                {error ? <div className="lw-banner warn">{error}</div> : null}
              </div>
              <div className="lw-hero-actions">
                <button className="lw-glow-button" onClick={load}>{loading ? "Refreshing" : "Refresh"}</button>
                <button className="lw-glow-button" onClick={validate}>Validate records</button>
              </div>
            </section>

            <section className="lw-neo-kpis">
              <div className="lw-neo-kpi"><span>Total</span><strong>{summary.count ?? 0}</strong></div>
              <div className="lw-neo-kpi warn"><span>Pending</span><strong>{summary.pending ?? 0}</strong></div>
              <div className="lw-neo-kpi safe"><span>Matched</span><strong>{summary.matched ?? 0}</strong></div>
              <div className="lw-neo-kpi danger"><span>Mismatch</span><strong>{summary.mismatch ?? 0}</strong></div>
              <div className="lw-neo-kpi safe"><span>Approved</span><strong>{summary.approved ?? 0}</strong></div>
              <div className="lw-neo-kpi danger"><span>Rejected</span><strong>{summary.rejected ?? 0}</strong></div>
            </section>

            <section className="lw-command-grid">
              <main className="lw-command-main">
                <div className="lw-section-title"><div><span>side-by-side queue</span><h2>Imported records</h2></div><small>{records.length} records</small></div>
                <div className="lw-case-stack">
                  {records.slice(0, 20).map((record) => (
                    <div className={`lw-case-card ${record.validation_state === "mismatch" ? "danger" : record.validation_state === "approved" ? "safe" : "info"}`} key={record.id || record.external_ref}>
                      <div className="lw-case-top"><span>{record.validation_state || "pending"}</span><small>{record.source || "import"}</small></div>
                      <h3>{record.patient_name || record.episode_ref || record.external_ref}</h3>
                      <p>{record.mismatch_summary || "No mismatch summary yet."}</p>
                      <div className="lw-case-meta"><span>{record.episode_ref || "No episode"}</span><span>{record.imported_stage || "No stage"}</span><span>{record.imported_room || "No room"}</span></div>
                      <div className="lw-hero-actions"><button className="lw-pill" onClick={() => approve(record.id)}>Approve</button><button className="lw-pill" onClick={() => reject(record.id)}>Reject</button></div>
                    </div>
                  ))}
                </div>
              </main>
            </section>
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
