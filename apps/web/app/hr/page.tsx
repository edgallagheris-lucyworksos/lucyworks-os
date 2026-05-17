"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type HROverview = {
  profiles: any[];
  competencies: any[];
  leave_requests: any[];
  absence_records: any[];
  overtime_requests: any[];
  on_call: any[];
  fatigue_risks: any[];
  approval_gates: any[];
};

function fmt(value?: string | null) {
  if (!value) return "-";
  try { return new Date(value).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch { return value; }
}

function Card({ label, value }: { label: string; value: number | string }) {
  return <div className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>{label}</div><div style={{ fontSize: 30, fontWeight: 950 }}>{value}</div></div>;
}

function Badge({ value }: { value?: string }) {
  const red = ["HIGH", "red", "open", "declined"].includes(value || "");
  const amber = ["MED", "amber", "requested", "pending"].includes(value || "");
  return <span className="lw-pill" style={{ borderColor: red ? "#7f1d1d" : amber ? "#78350f" : "#14532d", color: red ? "#fca5a5" : amber ? "#fbbf24" : "#86efac" }}>{value || "-"}</span>;
}

function Section({ title, items, render, empty }: { title: string; items: any[]; render: (item: any, idx: number) => React.ReactNode; empty: string }) {
  return <section className="lw-card" style={{ padding: 16 }}>
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
      <h2 style={{ margin: 0 }}>{title}</h2><span style={{ color: "#94a3b8" }}>{items.length}</span>
    </div>
    {items.length ? <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 10 }}>{items.slice(0, 18).map(render)}</div> : <p style={{ color: "#94a3b8" }}>{empty}</p>}
  </section>;
}

function HRInner() {
  const [data, setData] = useState<HROverview | null>(null);
  const [error, setError] = useState("");
  async function load() {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/hr`, { cache: "no-store" });
      if (!res.ok) throw new Error(`hr ${res.status}`);
      setData(await res.json());
    } catch (err) { setError(err instanceof Error ? err.message : "HR overview failed to load"); }
  }
  useEffect(() => { load(); }, []);

  const profiles = data?.profiles || [];
  const competencies = data?.competencies || [];
  const leave = data?.leave_requests || [];
  const absence = data?.absence_records || [];
  const overtime = data?.overtime_requests || [];
  const onCall = data?.on_call || [];
  const fatigue = data?.fatigue_risks || [];
  const gates = data?.approval_gates || [];

  return <HospitalShell title="Staff / HR Command" subtitle="LucyRota depth: skills, leave, overtime, on-call and fatigue risk">
    <div style={{ display: "grid", gap: 16 }}>
      <section className="lw-card" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>LucyRota / HR depth</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.04em" }}>Safe staffing is part of clinical operations</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>Profiles, competencies, leave, absence, overtime, on-call load, fatigue/rest risk and manager approval audit.</p>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="lw-pill lw-btn-primary" onClick={load}>Refresh</button>
            <Link href="/workspace" className="lw-pill">Workspace</Link>
            <Link href="/staff" className="lw-pill">Staff</Link>
            <Link href="/schedule" className="lw-pill">Schedule</Link>
          </div>
        </div>
        {error ? <p style={{ color: "#fca5a5" }}>{error}</p> : null}
      </section>
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(165px, 1fr))", gap: 12 }}>
        <Card label="Profiles" value={profiles.length} /><Card label="Competencies" value={competencies.length} /><Card label="Leave" value={leave.length} /><Card label="Absence" value={absence.length} /><Card label="Overtime" value={overtime.length} /><Card label="On-call" value={onCall.length} /><Card label="Fatigue" value={fatigue.length} /><Card label="HR gates" value={gates.length} />
      </section>
      <Section title="Fatigue / rest risk" items={fatigue} empty="No fatigue risks recorded." render={(x, i) => <article key={x.id || i} className="lw-card" style={{ padding: 12 }}><div style={{ display: "flex", justifyContent: "space-between" }}><strong>Staff #{x.staff_member_id}</strong><Badge value={x.risk_level} /></div><div style={{ color: "#94a3b8", marginTop: 6 }}>Window {x.measured_window_hours}h • open {String(x.open)}</div><div style={{ marginTop: 8 }}>{x.reasons}</div></article>} />
      <Section title="Competencies / skill signoff" items={competencies} empty="No competency records." render={(x, i) => <article key={x.id || i} className="lw-card" style={{ padding: 12 }}><div style={{ display: "flex", justifyContent: "space-between" }}><strong>{x.competency}</strong><Badge value={x.status} /></div><div style={{ color: "#94a3b8", marginTop: 6 }}>Staff #{x.staff_member_id} • {x.department}</div><div style={{ marginTop: 8 }}>Signed off by {x.signed_off_by || "-"} • expires {fmt(x.expires_at)}</div>{x.evidence_note ? <div style={{ color: "#cbd5e1", marginTop: 8 }}>{x.evidence_note}</div> : null}</article>} />
      <Section title="Overtime requests" items={overtime} empty="No overtime requests." render={(x, i) => <article key={x.id || i} className="lw-card" style={{ padding: 12 }}><div style={{ display: "flex", justifyContent: "space-between" }}><strong>{x.hours} hours</strong><Badge value={x.status} /></div><div style={{ color: "#94a3b8", marginTop: 6 }}>Staff #{x.staff_member_id} • {fmt(x.requested_at)}</div><div style={{ marginTop: 8 }}>{x.reason}</div>{x.reviewer_name ? <div style={{ color: "#cbd5e1", marginTop: 8 }}>Reviewed by {x.reviewer_name}: {x.decision_note}</div> : null}</article>} />
      <Section title="Leave / absence" items={[...leave, ...absence]} empty="No leave or absence records." render={(x, i) => <article key={`${x.leave_type || x.absence_type}-${x.id || i}`} className="lw-card" style={{ padding: 12 }}><div style={{ display: "flex", justifyContent: "space-between" }}><strong>{x.leave_type || x.absence_type}</strong><Badge value={x.status} /></div><div style={{ color: "#94a3b8", marginTop: 6 }}>Staff #{x.staff_member_id} • {fmt(x.starts_at)} → {fmt(x.ends_at)}</div><div style={{ marginTop: 8 }}>{x.reason || x.notes || "-"}</div></article>} />
      <Section title="On-call assignments" items={onCall} empty="No on-call records." render={(x, i) => <article key={x.id || i} className="lw-card" style={{ padding: 12 }}><div style={{ display: "flex", justifyContent: "space-between" }}><strong>{x.department}</strong><Badge value={x.status} /></div><div style={{ color: "#94a3b8", marginTop: 6 }}>Staff #{x.staff_member_id} • {x.escalation_role}</div><div style={{ marginTop: 8 }}>{fmt(x.starts_at)} → {fmt(x.ends_at)}</div></article>} />
      <Section title="HR approval gates" items={gates} empty="No HR approval gates." render={(x, i) => <article key={x.id || i} className="lw-card" style={{ padding: 12 }}><div style={{ display: "flex", justifyContent: "space-between" }}><strong>{x.gate_name}</strong><Badge value={x.severity} /></div><div style={{ color: "#94a3b8", marginTop: 6 }}>Staff #{x.staff_member_id || "-"} • {x.status}</div><div style={{ marginTop: 8 }}>{x.reasons}</div></article>} />
    </div>
  </HospitalShell>;
}

export default function HRPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "admin"]}>{() => <HRInner />}</AuthGuard>;
}
