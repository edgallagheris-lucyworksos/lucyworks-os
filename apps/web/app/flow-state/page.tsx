"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type FlowState = {
  summary: Record<string, number>;
  unacknowledged_handovers: any[];
  pending_results: any[];
  open_discharge_blockers: any[];
  active_occupancy: any[];
  blocked_live_gates: any[];
  staff_assignments_requiring_review: any[];
};

function riskBorder(kind: string) {
  if (kind === "red" || kind === "CRITICAL" || kind === "HIGH") return "1px solid #7f1d1d";
  if (kind === "amber" || kind === "MODERATE" || kind === "MED") return "1px solid #78350f";
  return "1px solid #14532d";
}

function fmt(value?: string | null) {
  if (!value) return "-";
  try { return new Date(value).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch { return value; }
}

function CountCard({ label, value }: { label: string; value: number | string }) {
  return <div className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>{label}</div><div style={{ fontSize: 30, fontWeight: 950 }}>{value}</div></div>;
}

function SectionList({ title, items, render, empty }: { title: string; items: any[]; render: (item: any) => React.ReactNode; empty: string }) {
  return <section className="lw-card" style={{ padding: 16 }}><div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}><h2 style={{ margin: 0 }}>{title}</h2><span style={{ color: "#94a3b8" }}>{items.length} open</span></div>{items.length ? <div style={{ display: "grid", gap: 10 }}>{items.map(render)}</div> : <p style={{ color: "#94a3b8" }}>{empty}</p>}</section>;
}

function FlowStateInner() {
  const [data, setData] = useState<FlowState | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/flow-state`, { cache: "no-store" });
      if (!res.ok) throw new Error(`flow-state ${res.status}`);
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Flow state failed to load");
    }
  }

  useEffect(() => { load(); }, []);

  return <HospitalShell title="Flow State Command" subtitle="LIVE gates, handovers, results, admissions, occupancy, discharge blockers and rota risk">
    <div style={{ display: "grid", gap: 16 }}>
      <section className="lw-card" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Operational enforcement layer</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.04em" }}>Not just status — blocked work, owners and gates</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>This view shows the missing operating depth: handover ownership, result review, discharge blockers, occupied spaces, LIVE gates and unsafe staff assignment risk.</p>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="lw-pill lw-btn-primary" onClick={load}>Refresh flow state</button>
            <Link href="/dashboard" className="lw-pill">Dashboard</Link>
            <Link href="/overnight" className="lw-pill">Overnight</Link>
          </div>
        </div>
        {error ? <p style={{ color: "#fca5a5" }}>{error}</p> : null}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 12 }}>
        <CountCard label="Unack handovers" value={data?.summary?.unacknowledged_handovers ?? 0} />
        <CountCard label="Pending results" value={data?.summary?.pending_results ?? 0} />
        <CountCard label="Discharge blockers" value={data?.summary?.open_discharge_blockers ?? 0} />
        <CountCard label="Active occupancy" value={data?.summary?.active_occupancy ?? 0} />
        <CountCard label="Blocked LIVE gates" value={data?.summary?.blocked_live_gates ?? 0} />
        <CountCard label="Staff risk reviews" value={data?.summary?.staff_assignments_requiring_review ?? 0} />
      </section>

      <SectionList title="Blocked LIVE gates" items={data?.blocked_live_gates || []} empty="No blocked live gates."
        render={(g) => <article key={g.id} style={{ border: riskBorder(g.severity), borderRadius: 14, padding: 12 }}><strong>{g.gate_name} • {g.severity}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{g.target_entity_type} #{g.target_entity_id || "-"} • {g.status}</div><div style={{ marginTop: 6 }}>{g.system_action}</div><div style={{ color: "#fca5a5", marginTop: 6 }}>{g.reasons}</div></article>} />

      <SectionList title="Unacknowledged handovers" items={data?.unacknowledged_handovers || []} empty="No unacknowledged handovers."
        render={(h) => <article key={h.id} style={{ border: "1px solid #78350f", borderRadius: 14, padding: 12 }}><strong>{h.from_owner} → {h.to_owner}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>Episode #{h.episode_id} • created {fmt(h.created_at)}</div><div style={{ marginTop: 6 }}>{h.note}</div></article>} />

      <SectionList title="Pending results" items={data?.pending_results || []} empty="No pending result reviews."
        render={(r) => <article key={r.id} style={{ border: "1px solid #78350f", borderRadius: 14, padding: 12 }}><strong>{r.result_type} • {r.status}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>Episode #{r.episode_id} • review owner {r.review_owner}</div>{r.required_action ? <div style={{ marginTop: 6 }}>{r.required_action}</div> : null}</article>} />

      <SectionList title="Discharge blockers" items={data?.open_discharge_blockers || []} empty="No open discharge blockers."
        render={(b) => <article key={b.id} style={{ border: riskBorder(b.severity), borderRadius: 14, padding: 12 }}><strong>{b.blocker_type} • {b.severity}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>Episode #{b.episode_id} • owner {b.owner_role} • {b.status}</div><div style={{ marginTop: 6 }}>{b.detail}</div></article>} />

      <SectionList title="Active occupancy" items={data?.active_occupancy || []} empty="No active occupancy records."
        render={(o) => <article key={o.id} style={{ border: "1px solid #1f2937", borderRadius: 14, padding: 12 }}><strong>{o.space_id} • {o.space_type}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>Episode #{o.episode_id || "-"} • {o.status}</div><div style={{ color: "#94a3b8", marginTop: 6 }}>Occupied {fmt(o.occupied_from)} • release {fmt(o.expected_release)}</div></article>} />

      <SectionList title="Staff assignments requiring review" items={data?.staff_assignments_requiring_review || []} empty="No risky staff assignment records."
        render={(s) => <article key={s.id} style={{ border: riskBorder(s.rota_risk), borderRadius: 14, padding: 12 }}><strong>{s.role_required} • {s.rota_risk}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>Episode #{s.episode_id || "-"} • staff #{s.staff_member_id || "unassigned"} • {s.status}</div><div style={{ marginTop: 6 }}>Skills {s.matched_skills || "none"} / required {s.required_skills || "-"}</div><div style={{ color: "#94a3b8", marginTop: 6 }}>Load ratio {Number(s.load_ratio || 0).toFixed(2)}</div></article>} />
    </div>
  </HospitalShell>;
}

export default function FlowStatePage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>{() => <FlowStateInner />}</AuthGuard>;
}
