"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type DeptPayload = {
  department: any;
  roles: any[];
  entities: any[];
  states: any[];
  conflicts: any[];
  dashboard_needs: any[];
};

type DepartmentResponse = {
  summary: { departments: number };
  departments: DeptPayload[];
};

function Pill({ children, warn }: { children: React.ReactNode; warn?: boolean }) {
  return <span className="lw-pill" style={{ borderColor: warn ? "#78350f" : "#1f2937", color: warn ? "#fbbf24" : "#cbd5e1" }}>{children}</span>;
}

function SectionList({ title, items, field, warnField }: { title: string; items: any[]; field: string; warnField?: string }) {
  return <div>
    <strong>{title}</strong>
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
      {items.map((item, idx) => <Pill key={`${title}-${idx}`} warn={warnField ? item[warnField] === "red" : false}>{item[field]}</Pill>)}
    </div>
  </div>;
}

function DepartmentOpsInner() {
  const [data, setData] = useState<DepartmentResponse | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/departments`, { cache: "no-store" });
      if (!res.ok) throw new Error(`departments ${res.status}`);
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Department Ops failed to load");
    }
  }

  async function seed() {
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const res = await fetch(`${API_BASE}/api/departments/seed?actor_name=Department%20Ops`, { method: "POST" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(JSON.stringify(body));
      setNotice(`Seeded ${body.seeded_departments} departments`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Seed failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const departments = data?.departments || [];

  return <HospitalShell title="Department Ops" subtitle="Reception, triage, imaging, theatre and ICU operational detail pack">
    <div style={{ display: "grid", gap: 16 }}>
      <section className="lw-card" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>LucyVet department layer</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 36, letterSpacing: "-0.05em" }}>Departments, states, conflicts and dashboard needs</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>This turns the department pack into structured operating data for Lucy Command, Pulse, Flow, Theatre, Ward, Diagnostics and Care.</p>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="lw-pill lw-btn-primary" onClick={seed} disabled={loading}>{loading ? "Seeding..." : "Seed department pack"}</button>
            <button className="lw-pill" onClick={load}>Refresh</button>
            <Link href="/system-control" className="lw-pill">System Control</Link>
            <Link href="/readiness" className="lw-pill">Readiness</Link>
          </div>
        </div>
        {notice ? <p style={{ color: "#86efac" }}>{notice}</p> : null}
        {error ? <p style={{ color: "#fca5a5" }}>{error}</p> : null}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
        <div className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>Departments</div><div style={{ fontSize: 30, fontWeight: 950 }}>{departments.length}</div></div>
        <div className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>Roles</div><div style={{ fontSize: 30, fontWeight: 950 }}>{departments.reduce((a, d) => a + d.roles.length, 0)}</div></div>
        <div className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>Workflow states</div><div style={{ fontSize: 30, fontWeight: 950 }}>{departments.reduce((a, d) => a + d.states.length, 0)}</div></div>
        <div className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>Conflicts</div><div style={{ fontSize: 30, fontWeight: 950 }}>{departments.reduce((a, d) => a + d.conflicts.length, 0)}</div></div>
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 12 }}>
        {departments.map((dept) => <article key={dept.department.code} className="lw-card" style={{ padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>{dept.department.name}</h2>
            <Pill>{dept.department.lucy_module}</Pill>
          </div>
          <p style={{ color: "#cbd5e1" }}>{dept.department.purpose}</p>
          <div style={{ display: "grid", gap: 14 }}>
            <SectionList title="Staff involved" items={dept.roles} field="role_name" />
            <SectionList title="Key entities" items={dept.entities} field="entity_name" />
            <SectionList title="Workflow states" items={dept.states} field="state_name" />
            <SectionList title="Conflict patterns" items={dept.conflicts} field="conflict_name" warnField="severity_default" />
            <SectionList title="Dashboard needs" items={dept.dashboard_needs} field="need_name" />
          </div>
        </article>)}
      </section>
    </div>
  </HospitalShell>;
}

export default function DepartmentOpsPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <DepartmentOpsInner />}</AuthGuard>;
}
