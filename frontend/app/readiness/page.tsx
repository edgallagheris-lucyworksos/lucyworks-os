"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type ReadinessLayer = {
  layer: string;
  status: "ready" | "partial" | "missing" | string;
  evidence: Record<string, number>;
  missing_depth: string;
};

type Readiness = {
  target: string;
  overall_status: string;
  summary: Record<string, number>;
  layers: ReadinessLayer[];
  metrics: Record<string, number>;
  next_required_build_slices: string[];
};

function statusColour(status: string) {
  if (status === "ready") return { border: "#14532d", text: "#86efac" };
  if (status === "partial") return { border: "#78350f", text: "#fbbf24" };
  return { border: "#7f1d1d", text: "#fca5a5" };
}

function Card({ label, value }: { label: string; value: number | string }) {
  return <div className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>{label}</div><div style={{ fontSize: 30, fontWeight: 950 }}>{value}</div></div>;
}

function ReadinessInner() {
  const [data, setData] = useState<Readiness | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/readiness/bvs`, { cache: "no-store" });
      if (!res.ok) throw new Error(`readiness ${res.status}`);
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Readiness report failed to load");
    }
  }

  useEffect(() => { load(); }, []);

  return <HospitalShell title="BVS / CVS Readiness" subtitle="Live system readiness report for specialist hospital operations">
    <div style={{ display: "grid", gap: 16 }}>
      <section className="lw-card" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Readiness checker</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.04em" }}>BVS/CVS-grade system gap report</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>{data?.target || "Checks live data across command, HR, scheduling, inpatients, gates, pharmacy, catalogues, comms and audit."}</p>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="lw-pill lw-btn-primary" onClick={load}>Refresh</button>
            <Link href="/workspace" className="lw-pill">Workspace</Link>
            <Link href="/command" className="lw-pill">Command</Link>
            <Link href="/hr" className="lw-pill">HR</Link>
          </div>
        </div>
        {error ? <p style={{ color: "#fca5a5" }}>{error}</p> : null}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
        <Card label="Overall" value={data?.overall_status || "-"} />
        <Card label="Ready layers" value={data?.summary?.ready_layers ?? 0} />
        <Card label="Partial layers" value={data?.summary?.partial_layers ?? 0} />
        <Card label="Missing layers" value={data?.summary?.missing_layers ?? 0} />
        <Card label="Total layers" value={data?.summary?.total_layers ?? 0} />
      </section>

      <section className="lw-card" style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Layer readiness</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 12 }}>
          {(data?.layers || []).map((layer) => {
            const colour = statusColour(layer.status);
            return <article key={layer.layer} style={{ border: `1px solid ${colour.border}`, borderRadius: 14, padding: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                <strong>{layer.layer}</strong>
                <span className="lw-pill" style={{ borderColor: colour.border, color: colour.text }}>{layer.status}</span>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
                {Object.entries(layer.evidence || {}).map(([k, v]) => <span className="lw-pill" key={k}>{k}: {v}</span>)}
              </div>
              <p style={{ color: "#cbd5e1", marginBottom: 0 }}>{layer.missing_depth}</p>
            </article>;
          })}
        </div>
      </section>

      <section className="lw-card" style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Next required build slices</h2>
        <div style={{ display: "grid", gap: 8 }}>
          {(data?.next_required_build_slices || []).map((item) => <div key={item} style={{ border: "1px solid #1f2937", borderRadius: 12, padding: 10 }}>{item}</div>)}
        </div>
      </section>

      <section className="lw-card" style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Raw live metrics</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
          {Object.entries(data?.metrics || {}).map(([key, value]) => <Card key={key} label={key.replaceAll("_", " ")} value={value} />)}
        </div>
      </section>
    </div>
  </HospitalShell>;
}

export default function ReadinessPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "admin"]}>{() => <ReadinessInner />}</AuthGuard>;
}
