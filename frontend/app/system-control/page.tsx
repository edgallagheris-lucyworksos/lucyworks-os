"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Check = { key: string; label: string; url: string; ok: boolean; status: string; detail: string; data?: any };

const checks = [
  { key: "health", label: "Backend health", url: "/api/health" },
  { key: "readiness", label: "BVS readiness", url: "/api/readiness/bvs" },
  { key: "departments", label: "Department Ops", url: "/api/departments" },
  { key: "workspace", label: "Workspace queue", url: "/api/workspace?role=ops_manager" },
  { key: "flow", label: "Flow state", url: "/api/flow-state" },
  { key: "catalogues", label: "Catalogues", url: "/api/catalogues" },
  { key: "hr", label: "HR / LucyRota", url: "/api/hr" },
  { key: "forecast", label: "Forecast / Lucy Pulse", url: "/api/forecast/hospital?hours=12&slot_minutes=60" },
];

function statusTone(ok: boolean) {
  return ok ? { border: "#14532d", text: "#86efac", label: "OK" } : { border: "#7f1d1d", text: "#fca5a5", label: "FAIL" };
}

function CountCard({ label, value }: { label: string; value: number | string }) {
  return <div className="lw-kpi"><div className="lw-kpi-label">{label}</div><div className="lw-kpi-value">{value}</div></div>;
}

function SystemControlInner() {
  const [results, setResults] = useState<Check[]>([]);
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [lastRun, setLastRun] = useState<string>("");
  const [notice, setNotice] = useState("");
  const [seedError, setSeedError] = useState("");

  async function runChecks() {
    setLoading(true);
    const next: Check[] = [];
    for (const check of checks) {
      try {
        const res = await fetch(`${API_BASE}${check.url}`, { cache: "no-store" });
        const data = await res.json().catch(() => null);
        next.push({ ...check, ok: res.ok, status: String(res.status), detail: res.ok ? "Connected" : JSON.stringify(data || {}).slice(0, 180), data });
      } catch (err) {
        next.push({ ...check, ok: false, status: "offline", detail: err instanceof Error ? err.message : "Connection failed" });
      }
    }
    setResults(next);
    setLastRun(new Date().toLocaleString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    setLoading(false);
  }

  async function firstRun() {
    setSeeding(true);
    setNotice("");
    setSeedError("");
    try {
      const res = await fetch(`${API_BASE}/api/admin/first-run`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(JSON.stringify(data));
      setNotice("First Run complete: hospital scale + department ops seeded.");
      await runChecks();
    } catch (err) {
      setSeedError(err instanceof Error ? err.message : "First Run failed");
    } finally {
      setSeeding(false);
    }
  }

  useEffect(() => { runChecks(); }, []);

  const okCount = results.filter((r) => r.ok).length;
  const failCount = results.filter((r) => !r.ok).length;
  const readiness = results.find((r) => r.key === "readiness")?.data;
  const flow = results.find((r) => r.key === "flow")?.data;
  const workspace = results.find((r) => r.key === "workspace")?.data;
  const forecast = results.find((r) => r.key === "forecast")?.data;
  const departments = results.find((r) => r.key === "departments")?.data;
  const workspaceTotal = Object.values(workspace?.summary || {}).reduce((a: any, b: any) => Number(a) + Number(b), 0);

  return <HospitalShell title="System Control" subtitle="One mobile control surface for running LucyWorks OS as one system">
    <div style={{ display: "grid", gap: 12 }}>
      <section className="lw-command-panel">
        <div className="lw-command-header">
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Phone control surface</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.05em" }}>Start here. Seed, check, then operate.</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>One button seeds the hospital operating data. One check confirms backend, departments, readiness, workspace, flow-state, catalogues, HR and forecast.</p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="lw-pill lw-btn-primary" onClick={firstRun} disabled={seeding}>{seeding ? "Seeding..." : "First Run / Seed System"}</button>
            <button className="lw-pill" onClick={runChecks} disabled={loading}>{loading ? "Checking..." : "Check system"}</button>
            <Link href="/departments" className="lw-pill">Department Ops</Link>
            <Link href="/actions" className="lw-pill">Actions</Link>
          </div>
        </div>
        <div style={{ padding: 12 }}>
          {notice ? <p style={{ color: "#86efac", marginTop: 0 }}>{notice}</p> : null}
          {seedError ? <p style={{ color: "#fca5a5", marginTop: 0 }}>{seedError}</p> : null}
          {lastRun ? <p style={{ color: "#94a3b8", margin: 0 }}>Last check: {lastRun}</p> : null}
        </div>
      </section>

      <section className="lw-kpi-strip">
        <CountCard label="Checks OK" value={okCount} />
        <CountCard label="Checks failing" value={failCount} />
        <CountCard label="Readiness" value={readiness?.overall_status || "-"} />
        <CountCard label="Departments" value={departments?.summary?.departments ?? "-"} />
        <CountCard label="Blocked gates" value={flow?.summary?.blocked_live_gates ?? "-"} />
        <CountCard label="Workspace items" value={workspaceTotal || "-"} />
        <CountCard label="Forecast red slots" value={forecast?.summary?.red_slots ?? "-"} />
      </section>

      <section className="lw-command-panel">
        <div className="lw-command-header"><h2 className="lw-section-title">System checks</h2><span className="lw-status-meta">Live API checks</span></div>
        <div>
          {results.map((r) => {
            const tone = statusTone(r.ok);
            return <div key={r.key} className="lw-status-row">
              <div className="lw-status-title">{r.label}</div>
              <span className="lw-pill" style={{ borderColor: tone.border, color: tone.text }}>{tone.label} {r.status}</span>
              <div className="lw-status-detail">{r.detail}</div>
              <div className="lw-status-meta">{r.url}</div>
            </div>;
          })}
        </div>
      </section>

      <section className="lw-mobile-actionbar">
        <Link href="/readiness" className="lw-pill">Readiness</Link>
        <Link href="/command" className="lw-pill">Command</Link>
        <Link href="/workspace" className="lw-pill">Workspace</Link>
        <Link href="/actions" className="lw-pill">Actions</Link>
        <Link href="/flow-state" className="lw-pill">Flow State</Link>
        <Link href="/overnight" className="lw-pill">Lucy Care</Link>
        <Link href="/departments" className="lw-pill">Departments</Link>
      </section>
    </div>
  </HospitalShell>;
}

export default function SystemControlPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <SystemControlInner />}</AuthGuard>;
}
