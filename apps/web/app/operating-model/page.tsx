"use client";

import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Department = {
  name: string;
  short_name: string;
  purpose: string;
  rooms: string[];
  roles: string[];
  specialisms: string[];
  common_blockers: string[];
};

type ProcedureTemplate = {
  name: string;
  department: string;
  prep_min: number;
  anaesthesia_min: number;
  procedure_min: number;
  recovery_min: number;
  cleaning_min: number;
  risk: string;
};

type PharmacyRule = {
  area: string;
  rule: string;
  system_guardrail: string;
};

type Catalogue = {
  departments: Department[];
  procedure_templates: ProcedureTemplate[];
  pharmacy_governance: PharmacyRule[];
  legal_and_compliance_guardrails: string[];
  operating_rules: string[];
};

function totalMinutes(p: ProcedureTemplate) {
  return p.prep_min + p.anaesthesia_min + p.procedure_min + p.recovery_min + p.cleaning_min;
}

export default function OperatingModelPage() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [selectedDepartment, setSelectedDepartment] = useState<string>("All");

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/operating-catalogue`, { cache: "no-store" });
      setCatalogue(await res.json());
    }
    load();
  }, []);

  const procedures = useMemo(() => {
    if (!catalogue) return [];
    if (selectedDepartment === "All") return catalogue.procedure_templates;
    return catalogue.procedure_templates.filter((p) => p.department === selectedDepartment || p.department === catalogue.departments.find((d) => d.name === selectedDepartment)?.short_name);
  }, [catalogue, selectedDepartment]);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>{() => (
      <HospitalShell title="Operating Model" subtitle="Departments, rooms, specialisms, timings, pharmacy and compliance guardrails">
        {!catalogue ? <p>Loading operating model...</p> : null}
        {catalogue ? <div style={{ display: "grid", gap: 20 }}>
          <section className="lw-card" style={{ padding: 22 }}>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Operating depth</div>
            <h1 style={{ margin: "10px 0 0", fontSize: 40, letterSpacing: "-0.04em" }}>The hospital map behind the work.</h1>
            <p style={{ color: "#94a3b8", maxWidth: 980, fontSize: 17, lineHeight: 1.5 }}>This catalogue is the current structured operating layer: departments, rooms, roles, specialisms, common blockers, procedure timing templates, pharmacy governance and compliance guardrails. These definitions should drive scheduling, flow-readiness, triage routing, pharmacy work, stock blockers and audit prompts.</p>
          </section>

          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
            {catalogue.departments.map((department) => (
              <article key={department.name} className="lw-card" style={{ padding: 18 }}>
                <div style={{ color: "#14b8a6", fontWeight: 900 }}>{department.short_name}</div>
                <h2 style={{ margin: "6px 0" }}>{department.name}</h2>
                <p style={{ color: "#94a3b8" }}>{department.purpose}</p>
                <strong>Rooms</strong>
                <p style={{ color: "#94a3b8" }}>{department.rooms.join(" • ")}</p>
                <strong>Specialisms</strong>
                <p style={{ color: "#94a3b8" }}>{department.specialisms.join(" • ")}</p>
                <strong>Common blockers</strong>
                <ul style={{ color: "#94a3b8", paddingLeft: 18 }}>
                  {department.common_blockers.slice(0, 5).map((blocker) => <li key={blocker}>{blocker}</li>)}
                </ul>
              </article>
            ))}
          </section>

          <section className="lw-card" style={{ padding: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
              <div>
                <h2 style={{ margin: 0 }}>Procedure timing templates</h2>
                <p style={{ color: "#94a3b8", marginBottom: 0 }}>Operational planning timings, not clinical guarantees.</p>
              </div>
              <select value={selectedDepartment} onChange={(e) => setSelectedDepartment(e.target.value)} style={{ borderRadius: 12, padding: "10px 12px" }}>
                <option value="All">All departments</option>
                {catalogue.departments.map((department) => <option key={department.name} value={department.name}>{department.name}</option>)}
                <option value="ECC">ECC</option>
                <option value="Discharge">Discharge</option>
              </select>
            </div>
            <div style={{ display: "grid", gap: 10, marginTop: 14 }}>
              {procedures.map((procedure) => (
                <div key={`${procedure.department}-${procedure.name}`} style={{ border: "1px solid #1f2937", borderRadius: 14, padding: 14, background: "rgba(15,23,42,0.72)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <strong>{procedure.name}</strong>
                    <span>{procedure.department} • total {totalMinutes(procedure)} min</span>
                  </div>
                  <div style={{ color: "#94a3b8", marginTop: 8 }}>prep {procedure.prep_min} • anaesthesia {procedure.anaesthesia_min} • procedure {procedure.procedure_min} • recovery {procedure.recovery_min} • cleaning {procedure.cleaning_min}</div>
                  <div style={{ color: "#94a3b8", marginTop: 8 }}>Risk/guardrail: {procedure.risk}</div>
                </div>
              ))}
            </div>
          </section>

          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 14 }}>
            <div className="lw-card" style={{ padding: 18 }}>
              <h2 style={{ marginTop: 0 }}>Pharmacy governance</h2>
              {catalogue.pharmacy_governance.map((rule) => (
                <div key={rule.area} style={{ borderTop: "1px solid #1f2937", paddingTop: 12, marginTop: 12 }}>
                  <strong>{rule.area}</strong>
                  <p style={{ color: "#94a3b8", marginBottom: 6 }}>{rule.rule}</p>
                  <p style={{ color: "#cbd5e1", margin: 0 }}>System guardrail: {rule.system_guardrail}</p>
                </div>
              ))}
            </div>
            <div className="lw-card" style={{ padding: 18 }}>
              <h2 style={{ marginTop: 0 }}>Compliance and operating rules</h2>
              <strong>Compliance guardrails</strong>
              <ul style={{ color: "#94a3b8", paddingLeft: 18 }}>
                {catalogue.legal_and_compliance_guardrails.map((rule) => <li key={rule}>{rule}</li>)}
              </ul>
              <strong>Operating rules</strong>
              <ul style={{ color: "#94a3b8", paddingLeft: 18 }}>
                {catalogue.operating_rules.map((rule) => <li key={rule}>{rule}</li>)}
              </ul>
            </div>
          </section>
        </div> : null}
      </HospitalShell>
    )}</AuthGuard>
  );
}
