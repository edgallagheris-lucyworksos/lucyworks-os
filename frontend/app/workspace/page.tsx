"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { getSession } from "@/lib/session";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const ROLES = ["ops_manager", "clinical_director", "clinician", "nurse", "admin", "theatre_staff", "ward_staff", "imaging_staff", "stock_controller"];

type Workspace = { role: string; staff_member_id?: number | null; staff_name?: string | null; scope: string[]; summary: Record<string, number>; queues: Record<string, any[]> };

function fmt(value?: string | null) {
  if (!value) return "-";
  try { return new Date(value).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch { return value; }
}

function CountCard({ label, value }: { label: string; value: number | string }) {
  return <div className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>{label}</div><div style={{ fontSize: 28, fontWeight: 950 }}>{value}</div></div>;
}

function ItemCard({ item, type }: { item: any; type: string }) {
  const title = item.title || item.gate_name || item.blocker_type || item.result_type || item.task_type || item.space_id || item.from_owner || item.subject || item.role_required || item.block_type || `${type} #${item.id}`;
  const status = item.status ?? (item.acknowledged === false ? "unacknowledged" : "open");
  const border = item.severity === "CRITICAL" || item.severity === "red" || item.rota_risk === "HIGH" ? "1px solid #7f1d1d" : item.severity === "MODERATE" || item.severity === "amber" || item.rota_risk === "MED" ? "1px solid #78350f" : "1px solid #1f2937";
  return <article style={{ border, borderRadius: 14, padding: 12 }}>
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
      <strong>{title}</strong>
      <span style={{ color: "#94a3b8" }}>{status}</span>
    </div>
    <div style={{ color: "#94a3b8", marginTop: 6 }}>Episode #{item.episode_id || item.linked_episode_ref || "-"} • owner {item.owner_role || item.review_owner || item.to_owner || item.role_required || "-"}</div>
    {item.detail || item.note || item.description || item.reasons ? <div style={{ marginTop: 8 }}>{item.detail || item.note || item.description || item.reasons}</div> : null}
    {item.starts_at || item.due_at || item.created_at ? <div style={{ color: "#94a3b8", marginTop: 6 }}>{fmt(item.starts_at || item.due_at || item.created_at)}</div> : null}
  </article>;
}

function QueueSection({ name, items }: { name: string; items: any[] }) {
  if (!items?.length) return null;
  return <section className="lw-card" style={{ padding: 16 }}>
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
      <h2 style={{ margin: 0 }}>{name.replaceAll("_", " ")}</h2>
      <span style={{ color: "#94a3b8" }}>{items.length}</span>
    </div>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 10 }}>
      {items.slice(0, 12).map((item, idx) => <ItemCard key={`${name}-${item.id || idx}`} item={item} type={name} />)}
    </div>
  </section>;
}

function WorkspaceInner() {
  const [role, setRole] = useState("ops_manager");
  const [staffId, setStaffId] = useState("");
  const [data, setData] = useState<Workspace | null>(null);
  const [error, setError] = useState("");

  async function load(nextRole = role, nextStaffId = staffId) {
    setError("");
    try {
      const qs = new URLSearchParams({ role: nextRole });
      if (nextStaffId.trim()) qs.set("staff_member_id", nextStaffId.trim());
      const res = await fetch(`${API_BASE}/api/workspace?${qs.toString()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`workspace ${res.status}`);
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Workspace failed to load");
    }
  }

  useEffect(() => {
    const session = getSession();
    const initialRole = session?.user?.role || "ops_manager";
    setRole(initialRole);
    load(initialRole, "");
  }, []);

  return <HospitalShell title="My Workspace" subtitle="BVS/CVS-style role-filtered action queue for command and every staff group">
    <div style={{ display: "grid", gap: 16 }}>
      <section className="lw-card" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Role-filtered operating view</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.04em" }}>Every staff member gets their own queue</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>Command, clinicians, nurses, admin, theatre, ward, imaging and stock see their own work, blockers, handovers, results, gates, occupancy, schedule blocks and shifts.</p>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <select value={role} onChange={(e) => { setRole(e.target.value); load(e.target.value, staffId); }} className="lw-pill" style={{ background: "#020617", color: "#f8fafc" }}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <input value={staffId} onChange={(e) => setStaffId(e.target.value)} placeholder="staff id optional" className="lw-pill" style={{ background: "#020617", color: "#f8fafc", width: 140 }} />
            <button className="lw-pill lw-btn-primary" onClick={() => load()}>Refresh</button>
            <Link href="/flow-state" className="lw-pill">Flow State</Link>
          </div>
        </div>
        {data ? <p style={{ color: "#94a3b8" }}>Scope: {data.scope.join(" • ")}</p> : null}
        {error ? <p style={{ color: "#fca5a5" }}>{error}</p> : null}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
        {Object.entries(data?.summary || {}).map(([key, value]) => <CountCard key={key} label={key.replaceAll("_", " ")} value={value} />)}
      </section>

      {Object.entries(data?.queues || {}).map(([name, items]) => <QueueSection key={name} name={name} items={items || []} />)}
    </div>
  </HospitalShell>;
}

export default function WorkspacePage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <WorkspaceInner />}</AuthGuard>;
}
