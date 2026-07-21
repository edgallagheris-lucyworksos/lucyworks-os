"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";

type Source = { sourceRef: string; hospitalRef: string; title: string; url: string; evidenceType: string };
type Hospital = {
  hospitalRef: string;
  name: string;
  hospitalType: string;
  publicOperatingModel: string[];
  observedRoleTitles: string[];
  departments: string[];
  facilities: string[];
  sourceRefs: string[];
};
type RoleTemplate = {
  roleRef: string;
  title: string;
  family: string;
  explanation: string;
  typicalResponsibilities: string[];
  lucyWorksCapabilities: string[];
  decisionAuthority: string;
  sourceRefs: string[];
};
type DepartmentTemplate = { departmentRef: string; name: string; purpose: string; sourceRefs: string[] };
type WorkflowPattern = {
  workflowRef: string;
  name: string;
  explanation: string;
  lucyWorksImplication: string;
  evidenceLevel: string;
  sourceRefs: string[];
};
type Catalogue = {
  catalogueVersion: number;
  researchedAt: string;
  scope: string;
  governance: Record<string, unknown>;
  hospitals: Hospital[];
  roleTemplates: RoleTemplate[];
  departmentTemplates: DepartmentTemplate[];
  workflowPatterns: WorkflowPattern[];
  sources: Source[];
  counts: { hospitals: number; roles: number; departments: number; workflows: number; sources: number };
};

type View = "roles" | "hospitals" | "departments" | "workflows" | "sources";

const card: React.CSSProperties = {
  background: "white",
  border: "1px solid #cbd5e1",
  borderRadius: 14,
  padding: 15,
  boxShadow: "0 5px 16px rgba(15,23,42,.05)",
};

const pill: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 8px",
  borderRadius: 999,
  background: "#e2e8f0",
  color: "#334155",
  fontSize: 12,
  fontWeight: 750,
};

function SourceLinks({ refs, sourceMap }: { refs: string[]; sourceMap: Map<string, Source> }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
      {refs.map((ref) => {
        const source = sourceMap.get(ref);
        if (!source) return null;
        return (
          <a key={ref} href={source.url} target="_blank" rel="noreferrer" style={{ ...pill, color: "#1d4ed8", textDecoration: "none", background: "#dbeafe" }}>
            {source.hospitalRef.toUpperCase()} source ↗
          </a>
        );
      })}
    </div>
  );
}

export function HospitalIntelligencePanel() {
  const [data, setData] = useState<Catalogue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("roles");
  const [query, setQuery] = useState("");
  const [hospital, setHospital] = useState("all");
  const [family, setFamily] = useState("all");

  useEffect(() => {
    apiGet<Catalogue>("/api/hospital-intelligence/catalogue")
      .then(setData)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load catalogue"));
  }, []);

  const sourceMap = useMemo(() => new Map((data?.sources || []).map((source) => [source.sourceRef, source])), [data]);
  const selectedSourceRefs = useMemo(() => {
    if (!data || hospital === "all") return null;
    return new Set(data.hospitals.find((item) => item.hospitalRef === hospital)?.sourceRefs || []);
  }, [data, hospital]);
  const families = useMemo(() => Array.from(new Set((data?.roleTemplates || []).map((item) => item.family))).sort(), [data]);
  const matches = (value: unknown) => !query.trim() || JSON.stringify(value).toLowerCase().includes(query.trim().toLowerCase());

  const roles = useMemo(
    () =>
      (data?.roleTemplates || []).filter(
        (item) =>
          (family === "all" || item.family === family) &&
          (!selectedSourceRefs || item.sourceRefs.some((ref) => selectedSourceRefs.has(ref))) &&
          matches(item),
      ),
    [data, family, selectedSourceRefs, query],
  );
  const hospitals = useMemo(() => (data?.hospitals || []).filter((item) => (hospital === "all" || item.hospitalRef === hospital) && matches(item)), [data, hospital, query]);
  const departments = useMemo(
    () => (data?.departmentTemplates || []).filter((item) => (!selectedSourceRefs || item.sourceRefs.some((ref) => selectedSourceRefs.has(ref))) && matches(item)),
    [data, selectedSourceRefs, query],
  );
  const workflows = useMemo(
    () => (data?.workflowPatterns || []).filter((item) => (!selectedSourceRefs || item.sourceRefs.some((ref) => selectedSourceRefs.has(ref))) && matches(item)),
    [data, selectedSourceRefs, query],
  );
  const sources = useMemo(() => (data?.sources || []).filter((item) => (hospital === "all" || item.hospitalRef === hospital) && matches(item)), [data, hospital, query]);

  if (error) return <main style={{ padding: 24 }}><h1>Hospital intelligence unavailable</h1><p>{error}</p></main>;
  if (!data) return <main style={{ padding: 24 }}>Loading public hospital intelligence…</main>;

  const tabs: Array<[View, string, number]> = [
    ["roles", "Roles", roles.length],
    ["hospitals", "Hospitals", hospitals.length],
    ["departments", "Departments", departments.length],
    ["workflows", "Workflows", workflows.length],
    ["sources", "Sources", sources.length],
  ];

  return (
    <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
        <span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em", textTransform: "uppercase" }}>LucyWorks OS · Public evidence</span>
        <h1 style={{ fontSize: "clamp(38px, 8vw, 70px)", lineHeight: .94, margin: "7px 0" }}>Hospital intelligence</h1>
        <p style={{ color: "#cbd5e1", maxWidth: 920, marginBottom: 8 }}>{data.scope}</p>
        <p style={{ color: "#94a3b8", maxWidth: 920, margin: 0 }}>
          Public titles explain work; they do not grant permissions. Local identity, registration, competence and delegation remain mandatory.
        </p>
      </header>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 8, marginTop: 10 }}>
        {[
          ["Hospitals", data.counts.hospitals],
          ["Role templates", data.counts.roles],
          ["Departments", data.counts.departments],
          ["Workflows", data.counts.workflows],
          ["Official sources", data.counts.sources],
        ].map(([label, value]) => <div key={String(label)} style={card}><strong style={{ fontSize: 30 }}>{value}</strong><div style={{ color: "#64748b" }}>{label}</div></div>)}
      </section>

      <section style={{ ...card, marginTop: 10, display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 8 }}>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search roles, facilities, services or workflows" style={{ padding: 11, border: "1px solid #94a3b8", borderRadius: 10, minWidth: 0 }} />
        <select value={hospital} onChange={(event) => setHospital(event.target.value)} style={{ padding: 11, border: "1px solid #94a3b8", borderRadius: 10, minWidth: 0 }}>
          <option value="all">All hospitals</option>
          {data.hospitals.map((item) => <option key={item.hospitalRef} value={item.hospitalRef}>{item.name}</option>)}
        </select>
        <select value={family} onChange={(event) => setFamily(event.target.value)} disabled={view !== "roles"} style={{ padding: 11, border: "1px solid #94a3b8", borderRadius: 10, minWidth: 0 }}>
          <option value="all">All role families</option>
          {families.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
        </select>
      </section>

      <nav style={{ display: "flex", flexWrap: "wrap", gap: 7, marginTop: 10 }}>
        {tabs.map(([key, label, count]) => (
          <button key={key} onClick={() => setView(key)} style={{ border: 0, borderRadius: 999, padding: "9px 13px", fontWeight: 850, cursor: "pointer", background: view === key ? "#0f172a" : "white", color: view === key ? "white" : "#334155" }}>
            {label} {count}
          </button>
        ))}
      </nav>

      {view === "roles" && <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(310px, 1fr))", gap: 10, marginTop: 10 }}>
        {roles.map((item) => <article key={item.roleRef} style={card}>
          <span style={pill}>{item.family.replaceAll("_", " ")}</span>
          <h2 style={{ margin: "9px 0 6px", fontSize: 23 }}>{item.title}</h2>
          <p style={{ color: "#334155" }}>{item.explanation}</p>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>Typical work</h3>
          <p style={{ color: "#475569", marginTop: 0 }}>{item.typicalResponsibilities.join(" · ")}</p>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>LucyWorks should support</h3>
          <p style={{ color: "#475569", marginTop: 0 }}>{item.lucyWorksCapabilities.join(" · ")}</p>
          <p style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 9, padding: 9, fontSize: 13 }}><strong>Authority:</strong> {item.decisionAuthority}</p>
          <SourceLinks refs={item.sourceRefs} sourceMap={sourceMap} />
        </article>)}
      </section>}

      {view === "hospitals" && <section style={{ display: "grid", gap: 10, marginTop: 10 }}>
        {hospitals.map((item) => <article key={item.hospitalRef} style={card}>
          <h2 style={{ marginTop: 0 }}>{item.name}</h2>
          <p style={{ color: "#64748b" }}>{item.hospitalType}</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
            <div><h3>Operating model</h3><ul>{item.publicOperatingModel.map((value) => <li key={value}>{value}</li>)}</ul></div>
            <div><h3>Observed roles</h3><p>{item.observedRoleTitles.join(" · ")}</p></div>
            <div><h3>Departments</h3><p>{item.departments.join(" · ")}</p></div>
            <div><h3>Facilities</h3><ul>{item.facilities.map((value) => <li key={value}>{value}</li>)}</ul></div>
          </div>
          <SourceLinks refs={item.sourceRefs} sourceMap={sourceMap} />
        </article>)}
      </section>}

      {view === "departments" && <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 10, marginTop: 10 }}>
        {departments.map((item) => <article key={item.departmentRef} style={card}><h2 style={{ marginTop: 0 }}>{item.name}</h2><p>{item.purpose}</p><SourceLinks refs={item.sourceRefs} sourceMap={sourceMap} /></article>)}
      </section>}

      {view === "workflows" && <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(310px, 1fr))", gap: 10, marginTop: 10 }}>
        {workflows.map((item) => <article key={item.workflowRef} style={card}>
          <span style={pill}>{item.evidenceLevel.replaceAll("_", " ")}</span>
          <h2>{item.name}</h2>
          <p>{item.explanation}</p>
          <p style={{ background: "#ecfeff", border: "1px solid #a5f3fc", borderRadius: 9, padding: 10 }}><strong>LucyWorks implication:</strong> {item.lucyWorksImplication}</p>
          <SourceLinks refs={item.sourceRefs} sourceMap={sourceMap} />
        </article>)}
      </section>}

      {view === "sources" && <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 10, marginTop: 10 }}>
        {sources.map((item) => <a key={item.sourceRef} href={item.url} target="_blank" rel="noreferrer" style={{ ...card, display: "block", color: "#0f172a", textDecoration: "none" }}>
          <span style={pill}>{item.hospitalRef.toUpperCase()}</span>
          <h2 style={{ fontSize: 19 }}>{item.title}</h2>
          <p style={{ color: "#64748b" }}>{item.evidenceType.replaceAll("_", " ")}</p>
          <strong style={{ color: "#2563eb" }}>Open official source ↗</strong>
        </a>)}
      </section>}

      <footer style={{ color: "#64748b", padding: "18px 4px" }}>Catalogue v{data.catalogueVersion} · researched {data.researchedAt} · revalidate before hospital adoption.</footer>
    </main>
  );
}
