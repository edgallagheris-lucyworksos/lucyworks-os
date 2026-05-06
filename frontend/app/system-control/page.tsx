"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Check = {
  key: string;
  label: string;
  url: string;
  ok: boolean;
  status: string;
  detail: string;
  data?: any;
};

const checks = [
  { key: "health", label: "Backend health", url: "/api/health" },
  { key: "readiness", label: "BVS readiness", url: "/api/readiness/bvs" },
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
  return <div className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>{label}</div><div style={{ fontSize: 28, fontWeight: 950 }}>{value}</div></div>;
}

function SystemControlInner() {
  const [results, setResults] = useState<Check[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastRun, setLastRun] = useState<string>("");

  async function runChecks() {
    setLoading(true);
    const next: Check[] = [];
    for (const check of checks) {
      try {
        const res = await fetch(`${API_BASE}${check.url}`, { cache: "no-store" });
        const data = await res.json().catch(() => null);
        next.push({
          ...check,
          ok: res.ok,
          status: String(res.status),
          detail: res.ok ? "Connected" : JSON.stringify(data || {}).slice(0, 180),
          data,
        });
      } catch (err) {
        next.push({
          ...check,
          ok: false,
          status: "offline",
          detail: err instanceof Error ? err.message : "Connection failed",
        });
      }
    }
    setResults(next);
    setLastRun(new Date().toLocaleString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    setLoading(false);
  }

  useEffect(() => { runChecks(); }, []);

  const okCount = results.filter((r) => r.ok).length;
  const failCount = results.filter((r) => !r.ok).length;
  const readiness = results.find((r) => r.key === "readiness")?.data;
  const flow = results.find((r) => r.key === "flow")?.data;
  const workspace = results.find((r) => r.key === "workspace")?.data;
  const forecast = results.find((r) => r.key === "forecast")?.data;

  return <HospitalShell title="System Control" subtitle="One mobile control surface for running LucyWorks OS as one system">
    <div style={{ display: "grid", gap: 16 }}>
      <section className="lw-card" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Phone control surface</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 36, letterSpacing: "-0.05em" }}>Start here. Check the whole app. Open the right board.</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>This page checks whether the backend, readiness layer, workspace, flow state, catalogues, HR and forecast are responding as one LucyWorks system.</p>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="lw-pill lw-btn-primary" onClick={runChecks} disabled={loading}>{loading ? "Checking..." : "Check system"}</button>
            <Link href="/readiness" className="lw-pill">Readiness</Link>
            <Link href="/command" className="lw-pill">Command</Link>
            <Link href="/actions" className="lw-pill">Actions</Link>
          </div>
        </div>
        {lastRun ? <p style={{ color: "#94a3b8" }}>Last check: {lastRun}</p> : null}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(165px, 1fr))", gap: 12 }}>
        <CountCard label="Checks OK" value={okCount} />
        <CountCard label="Checks failing" value={failCount} />
        <CountCard label="Readiness" value={readiness?.overall_status || "-"} />
        <CountCard label="Blocked gates" value={flow?.summary?.blocked_live_gates ?? "-"} />
        <CountCard label="Workspace items" value={Object.values(workspace?.summary || {}).reduce((a: any, b: any) => Number(a) + Number(b), 0) || "-"} />
        <CountCard label="Forecast red slots" value={forecast?.summary?.red_slots ?? "-"} />
      </section>

      <section className="lw-card" style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>System checks</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 10 }}>
          {results.map((r) => {
            const tone = statusTone(r.ok);
            return <article key={r.key} style={{ border: `1px solid ${tone.border}`, borderRadius: 14, padding: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                <strong>{r.label}</strong>
                <span className="lw-pill" style={{ borderColor: tone.border, color: tone.text }}>{tone.label} {r.status}</span>
              </div>
              <div style={{ color: "#94a3b8", marginTop: 6 }}>{r.url}</div>
              <div style={{ marginTop: 8 }}>{r.detail}</div>
            </article>;
          })}
        </div>
      </section>

      <section className="lw-card" style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Operate from phone</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
          <Link href="/readiness" className="lw-card" style={{ padding: 14 }}>1. Readiness<br /><span style={{ color: "#94a3b8" }}>Find what is missing.</span></Link>
          <Link href="/command" className="lw-card" style={{ padding: 14 }}>2. Lucy Command<br /><span style={{ color: "#94a3b8" }}>Run the hospital board.</span></Link>
          <Link href="/workspace" className="lw-card" style={{ padding: 14 }}>3. My Workspace<br /><span style={{ color: "#94a3b8" }}>See owned work.</span></Link>
          <Link href="/actions" className="lw-card" style={{ padding: 14 }}>4. Actions<br /><span style={{ color: "#94a3b8" }}>Change state through gates.</span></Link>
          <Link href="/flow-state" className="lw-card" style={{ padding: 14 }}>5. Flow State<br /><span style={{ color: "#94a3b8" }}>See blockers and gates.</span></Link>
          <Link href="/overnight" className="lw-card" style={{ padding: 14 }}>6. Lucy Care<br /><span style={{ color: "#94a3b8" }}>Inpatients and overnight.</span></Link>
        </div>
      </section>
    </div>
  </HospitalShell>;
}

export default function SystemControlPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <SystemControlInner />}</AuthGuard>;
}
