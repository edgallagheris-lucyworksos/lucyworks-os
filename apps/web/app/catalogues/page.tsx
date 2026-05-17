"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Catalogues = {
  summary: Record<string, number>;
  procedures: any[];
  formulary: any[];
  diagnostics: any[];
  assignments: any[];
};

function CountCard({ label, value }: { label: string; value: number | string }) {
  return <div className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>{label}</div><div style={{ fontSize: 30, fontWeight: 950 }}>{value}</div></div>;
}

function Badge({ children, warn }: { children: React.ReactNode; warn?: boolean }) {
  return <span className="lw-pill" style={{ borderColor: warn ? "#78350f" : "#1f2937", color: warn ? "#fbbf24" : "#cbd5e1" }}>{children}</span>;
}

function Section({ title, children, count }: { title: string; children: React.ReactNode; count: number }) {
  return <section className="lw-card" style={{ padding: 16 }}>
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
      <h2 style={{ margin: 0 }}>{title}</h2>
      <span style={{ color: "#94a3b8" }}>{count} rows</span>
    </div>
    {children}
  </section>;
}

function CataloguesInner() {
  const [data, setData] = useState<Catalogues | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/catalogues`, { cache: "no-store" });
      if (!res.ok) throw new Error(`catalogues ${res.status}`);
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Catalogues failed to load");
    }
  }

  useEffect(() => { load(); }, []);

  return <HospitalShell title="Hospital Catalogues" subtitle="BVS/CVS-style procedure, diagnostics and formulary operating depth">
    <div style={{ display: "grid", gap: 16 }}>
      <section className="lw-card" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Operating catalogue layer</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.04em" }}>Specialist procedures, diagnostics and formulary controls</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>These catalogues feed theatre duration, staffing requirements, diagnostics review, pharmacy/stock visibility and compliance gates.</p>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="lw-pill lw-btn-primary" onClick={load}>Refresh</button>
            <Link href="/workspace" className="lw-pill">Workspace</Link>
            <Link href="/flow-state" className="lw-pill">Flow State</Link>
          </div>
        </div>
        {error ? <p style={{ color: "#fca5a5" }}>{error}</p> : null}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
        {Object.entries(data?.summary || {}).map(([key, value]) => <CountCard key={key} label={key.replaceAll("_", " ")} value={value} />)}
      </section>

      <Section title="Specialist procedures" count={data?.procedures?.length || 0}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 10 }}>
          {(data?.procedures || []).map((p) => <article key={p.id || p.code} style={{ border: "1px solid #1f2937", borderRadius: 14, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}><strong>{p.name}</strong><Badge>{p.code}</Badge></div>
            <div style={{ color: "#94a3b8", marginTop: 6 }}>{p.specialty} • {p.duration_est_minutes} min</div>
            <div style={{ marginTop: 8 }}><strong>Staffing</strong><div style={{ color: "#cbd5e1" }}>{p.staffing_requirements || "-"}</div></div>
            <div style={{ marginTop: 8 }}><strong>Kit</strong><div style={{ color: "#cbd5e1" }}>{p.kit_list || "-"}</div></div>
            {p.risks ? <div style={{ color: "#fbbf24", marginTop: 8 }}>Risks: {p.risks}</div> : null}
          </article>)}
        </div>
      </Section>

      <Section title="Formulary / pharmacy controls" count={data?.formulary?.length || 0}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 10 }}>
          {(data?.formulary || []).map((f) => <article key={f.id || f.drug_id} style={{ border: f.restricted_flag ? "1px solid #78350f" : "1px solid #1f2937", borderRadius: 14, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><strong>{f.name}</strong><Badge warn={f.restricted_flag}>{f.drug_id}</Badge></div>
            <div style={{ color: "#94a3b8", marginTop: 6 }}>Species: {f.species_allowed || "-"} • routes {f.routes || "-"}</div>
            <div style={{ marginTop: 8 }}>Storage: {f.storage || "-"}</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
              {f.restricted_flag ? <Badge warn>restricted / controlled</Badge> : <Badge>standard</Badge>}
              {f.cold_chain_flag ? <Badge warn>cold chain</Badge> : null}
              {f.locked_storage_flag ? <Badge warn>locked storage</Badge> : null}
            </div>
            {f.interactions ? <div style={{ color: "#fbbf24", marginTop: 8 }}>Interactions: {f.interactions}</div> : null}
          </article>)}
        </div>
      </Section>

      <Section title="Diagnostics / result review" count={data?.diagnostics?.length || 0}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 10 }}>
          {(data?.diagnostics || []).map((d) => <article key={d.id || d.test_code} style={{ border: "1px solid #1f2937", borderRadius: 14, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}><strong>{d.name}</strong><Badge>{d.test_code}</Badge></div>
            <div style={{ color: "#94a3b8", marginTop: 6 }}>{d.method} • {d.species}</div>
            <div style={{ marginTop: 8 }}>Ref range: {d.ref_range_low ?? "-"} to {d.ref_range_high ?? "-"}</div>
            {d.auto_flag_rules ? <div style={{ color: "#fbbf24", marginTop: 8 }}>Auto flags: {d.auto_flag_rules}</div> : null}
          </article>)}
        </div>
      </Section>
    </div>
  </HospitalShell>;
}

export default function CataloguesPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <CataloguesInner />}</AuthGuard>;
}
