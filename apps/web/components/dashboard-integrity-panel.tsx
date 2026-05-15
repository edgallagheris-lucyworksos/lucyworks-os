"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Integrity = {
  trust_state: "pass" | "warning" | "fail";
  data_mode: string;
  safe_to_operate: boolean;
  hard_failures: string[];
  warnings: string[];
  counts: Record<string, number>;
  invariant: string;
};

function border(state?: string) {
  if (state === "fail") return "1px solid #7f1d1d";
  if (state === "warning") return "1px solid #78350f";
  return "1px solid #14532d";
}

export function DashboardIntegrityPanel() {
  const [data, setData] = useState<Integrity | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    const res = await fetch(`${API_BASE}/api/dashboard/integrity`, { cache: "no-store" });
    if (!res.ok) {
      setError("Dashboard integrity report failed to load.");
      return;
    }
    setData(await res.json());
  }

  useEffect(() => { load(); }, []);

  if (error) return <section className="lw-card" style={{ padding: 14, border: "1px solid #7f1d1d" }}>{error}</section>;
  if (!data) return <section className="lw-card" style={{ padding: 14 }}>Loading dashboard integrity truth state...</section>;

  return (
    <section className="lw-card" style={{ padding: 16, border: border(data.trust_state) }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Dashboard integrity truth state</div>
          <h2 style={{ margin: "6px 0 0" }}>{data.safe_to_operate ? "SAFE TO OPERATE FROM" : "NOT SAFE TO OPERATE FROM"}</h2>
          <p style={{ color: "#94a3b8", marginBottom: 0 }}>Trust {data.trust_state} • Data mode {data.data_mode}</p>
        </div>
        <button onClick={load} className="lw-pill">Refresh integrity</button>
      </div>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 8, marginTop: 12 }}>
        {[
          ["Seed evidence", data.counts?.seeded_evidence ?? 0],
          ["Missing dependency", data.counts?.missing_dependency ?? 0],
          ["Fake green", data.counts?.fake_green ?? 0],
          ["Missing staff", data.counts?.missing_staff ?? 0],
          ["Missing room state", data.counts?.missing_room_state ?? 0],
        ].map(([label, value]) => <div key={String(label)} style={{ border: "1px solid #1f2937", borderRadius: 10, padding: 8 }}><div style={{ color: "#94a3b8", fontSize: 12 }}>{label}</div><strong>{value}</strong></div>)}
      </section>

      {data.hard_failures?.length ? <div style={{ marginTop: 10 }}><strong>Hard integrity failures</strong>{data.hard_failures.map((x, i) => <div key={i} style={{ color: "#fca5a5", marginTop: 4 }}>{x}</div>)}</div> : null}
      {data.warnings?.length ? <div style={{ marginTop: 10 }}><strong>Integrity warnings</strong>{data.warnings.map((x, i) => <div key={i} style={{ color: "#fbbf24", marginTop: 4 }}>{x}</div>)}</div> : null}
      <p style={{ color: "#64748b", marginBottom: 0, marginTop: 10 }}>{data.invariant}</p>
    </section>
  );
}
