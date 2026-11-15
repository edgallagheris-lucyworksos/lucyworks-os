"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import type { SessionUser } from "@/lib/session";

type Workspace = {
  generatedAt: string;
  summary: {
    activePatients: number;
    scheduledPatients: number;
    unscheduledPatients: number;
    unlinkedTasks: number;
  };
  tasks: Array<{ id: number; urgency: string; status: string; overdue: boolean }>;
  conflicts: Array<{ severity: string }>;
};

type ContextPayload = {
  context: {
    organisationRef: string;
    siteRef: string;
    premisesRef: string;
    version: number;
  };
  sites: Array<{
    siteRef: string;
    premisesRef: string;
    name: string;
    configurationState: string;
  }>;
};

type OperationalView = {
  summary: {
    activeImpacts: number;
    openCommands: number;
    affectedPatients: number;
    severityCounts: Record<string, number>;
  };
};

type LoadState = {
  workspace: Workspace | null;
  context: ContextPayload | null;
  operational: OperationalView | null;
  error: string;
};

const clinical = [
  { href: "/workspace", eyebrow: "Patients", title: "Patient command", text: "Active patients, next safe action, owner, place, timing and blockers." },
  { href: "/care", eyebrow: "At a glance", title: "Care brief", text: "The concise patient view for handover and bedside decisions." },
  { href: "/patient-record", eyebrow: "Record", title: "Patient record", text: "Longitudinal clinical history, observations, consent and communications." },
  { href: "/medications", eyebrow: "Medication", title: "Medication safety", text: "Product, protocol, calculation, warnings, prescriber review and administration." },
  { href: "/clinical-execution", eyebrow: "Work", title: "Clinical work", text: "Treatment tasks, diagnostics, anaesthesia, inpatient work and discharge." },
];

const operations = [
  { href: "/hospital-board", title: "Hospital operations", text: "Rooms, theatres, imaging, wards, staffing, cases and conflicts." },
  { href: "/referral-intake", title: "Referral intake", text: "Create or match the patient, confirm authority, triage and start the episode." },
  { href: "/workforce-rota", title: "Workforce & rota", text: "Staff availability, competence and safe coverage." },
  { href: "/input", title: "Quick input", text: "Capture an issue, task or operational change without losing it." },
];

const goLive = [
  { href: "/onboarding", title: "Hospital setup", text: "Organisation, site and premises configuration." },
  { href: "/integrations", title: "Vendor connections", text: "PIMS, labs, imaging, HR and other hospital systems." },
  { href: "/compliance-safety", title: "Compliance & safety", text: "UK veterinary, privacy, clinical-safety and governance evidence." },
  { href: "/production-readiness", title: "Production readiness", text: "Identity, recovery, security, validation and deployment gates." },
];

function localDate() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function roleLabel(role: string) {
  return role.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

export function HospitalOsHomeV32({ user }: { user: SessionUser }) {
  const [state, setState] = useState<LoadState>({ workspace: null, context: null, operational: null, error: "" });
  const [updatedAt, setUpdatedAt] = useState("");

  const refresh = useCallback(async () => {
    const date = localDate();
    const [workspaceResult, contextResult, operationalResult] = await Promise.allSettled([
      apiGet<Workspace>(`/api/v14/operational-workspace?operational_date=${date}`),
      apiGet<ContextPayload>("/api/v26/context"),
      apiGet<OperationalView>("/api/v26/operational-view"),
    ]);

    const workspace = workspaceResult.status === "fulfilled" ? workspaceResult.value : null;
    const context = contextResult.status === "fulfilled" ? contextResult.value : null;
    const operational = operationalResult.status === "fulfilled" ? operationalResult.value : null;
    const failed = [workspaceResult, contextResult, operationalResult].filter(item => item.status === "rejected").length;

    setState({
      workspace,
      context,
      operational,
      error: failed === 3 ? "Live hospital data is unavailable. Navigation remains available." : "",
    });
    setUpdatedAt(new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }));
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const site = useMemo(() => {
    const current = state.context?.context.siteRef;
    return state.context?.sites.find(item => item.siteRef === current) || state.context?.sites[0] || null;
  }, [state.context]);

  const critical = useMemo(() => {
    const tasks = state.workspace?.tasks || [];
    const criticalTasks = tasks.filter(item => item.overdue || item.status === "blocked" || item.urgency === "red").length;
    const redConflicts = (state.workspace?.conflicts || []).filter(item => ["red", "critical"].includes(item.severity)).length;
    return criticalTasks + redConflicts;
  }, [state.workspace]);

  const impact = state.operational?.summary;
  const active = state.workspace?.summary.activePatients ?? null;
  const unscheduled = state.workspace?.summary.unscheduledPatients ?? null;
  const unlinked = state.workspace?.summary.unlinkedTasks ?? null;
  const liveAvailable = Boolean(state.workspace || state.operational);

  return (
    <main className="os-home">
      <style>{css}</style>

      <header className="os-top">
        <div className="os-brand">
          <div className="os-mark" aria-hidden="true">LW</div>
          <div>
            <span>LucyWorks OS</span>
            <h1>Hospital home</h1>
            <p>{site?.name || "Active hospital"} · {roleLabel(user.role)}</p>
          </div>
        </div>
        <nav className="os-top-actions" aria-label="Primary hospital actions">
          <Link href="/referral-intake" className="primary">New referral</Link>
          <Link href="/workspace">Find patient</Link>
          <button type="button" onClick={() => void refresh()}>Refresh</button>
          <Link href="/system-control">All tools</Link>
        </nav>
      </header>

      {state.error ? <div className="os-alert" role="alert">{state.error}</div> : null}

      <section className="os-hero">
        <div className="os-hero-copy">
          <span className="os-eyebrow">START HERE</span>
          <h2>Run the hospital from the work, not from the software.</h2>
          <p>Patients first. Then hospital flow. Governance and technical controls stay underneath, where authorised staff can reach them without getting in the way of care.</p>
          <div className="os-hero-actions">
            <Link href="/workspace" className="primary">Open patient command</Link>
            <Link href="/hospital-board">Open hospital operations</Link>
          </div>
        </div>

        <aside className={`os-attention ${critical ? "danger" : ""}`}>
          <div className="os-attention-head">
            <span>{liveAvailable ? "LIVE HOSPITAL" : "HOSPITAL STATUS"}</span>
            <small>{updatedAt ? `updated ${updatedAt}` : "loading"}</small>
          </div>
          <strong>{critical ?? "—"}</strong>
          <h3>{critical === 1 ? "item needs immediate attention" : "items need immediate attention"}</h3>
          <p>
            {critical
              ? "Open Patient Command to work through overdue, blocked or red items and operational conflicts."
              : liveAvailable
                ? "No red or blocked work is visible in the connected patient workspace."
                : "Live hospital feeds have not loaded yet."}
          </p>
          <Link href="/workspace">Review attention queue →</Link>
        </aside>
      </section>

      <section className="os-kpis" aria-label="Hospital summary">
        <article><span>Active patients</span><strong>{active ?? "—"}</strong><small>current episodes</small></article>
        <article className={unscheduled ? "warn" : ""}><span>Need time / place</span><strong>{unscheduled ?? "—"}</strong><small>unscheduled patients</small></article>
        <article className={unlinked ? "warn" : ""}><span>Unlinked work</span><strong>{unlinked ?? "—"}</strong><small>must be linked before care use</small></article>
        <article className={(impact?.activeImpacts || 0) ? "warn" : ""}><span>Operational impacts</span><strong>{impact?.activeImpacts ?? "—"}</strong><small>{impact?.affectedPatients ?? "—"} patients affected</small></article>
        <article><span>Open commands</span><strong>{impact?.openCommands ?? "—"}</strong><small>governed changes</small></article>
      </section>

      <section className="os-section">
        <header className="os-section-head">
          <div><span>01 · PATIENT CARE</span><h2>One patient, one connected journey</h2><p>These screens should share the same patient and episode context. Staff should not need to re-key identifiers.</p></div>
          <Link href="/workspace">Open patient command →</Link>
        </header>
        <div className="os-clinical-grid">
          {clinical.map((item, index) => (
            <Link href={item.href} className={index === 0 ? "featured" : ""} key={item.href}>
              <span>{item.eyebrow}</span>
              <strong>{item.title}</strong>
              <p>{item.text}</p>
              <b>Open →</b>
            </Link>
          ))}
        </div>
      </section>

      <section className="os-section">
        <header className="os-section-head">
          <div><span>02 · HOSPITAL FLOW</span><h2>Operate the whole day</h2><p>Who is doing what, where, when and what is stopping safe flow.</p></div>
          <Link href="/hospital-board">Open hospital operations →</Link>
        </header>
        <div className="os-ops-grid">
          {operations.map(item => <Link href={item.href} key={item.href}><strong>{item.title}</strong><p>{item.text}</p><b>Open →</b></Link>)}
        </div>
      </section>

      <section className="os-completion">
        <div className="os-completion-copy">
          <span>03 · COMPLETE THE SYSTEM</span>
          <h2>Software built and hospital-connected are different things.</h2>
          <p>The core operating, patient, safety, medication and governance software exists. The remaining work is to connect it to a real hospital, finish speech capture, validate real workflows and prove it safely in use.</p>

          <div className="os-roadmap">
            <article className="done"><i>1</i><div><strong>Core hospital operating spine</strong><span>Built: referrals, patient record, patient command, rooms, staffing, tasks, clinical work, compliance and evidence.</span></div><b>BUILT</b></article>
            <article className="done"><i>2</i><div><strong>Medication safety foundation</strong><span>Built: versioned products, governed protocols, deterministic calculation, prescriber review and administration link.</span></div><b>BUILT</b></article>
            <article className="next"><i>3</i><div><strong>Veterinary speech & structured capture</strong><span>Next build: dictate, transcribe, extract proposals, review, confirm and write into the governed patient record.</span></div><b>NEXT</b></article>
            <article><i>4</i><div><strong>Real hospital configuration</strong><span>Verify rooms, services, staffing, competencies, roles, local SOPs and operating rules with authorised hospital evidence.</span></div><b>CONNECT</b></article>
            <article><i>5</i><div><strong>Real integrations & identity</strong><span>Connect hospital OIDC, PIMS, imaging, lab, HR and pharmacy interfaces using the existing integration layer.</span></div><b>CONNECT</b></article>
            <article><i>6</i><div><strong>Clinical UAT and shadow pilot</strong><span>Run named users through realistic cases, capture defects, complete DPIA/IG/security evidence and only then approve go-live.</span></div><b>PROVE</b></article>
          </div>
        </div>

        <aside className="os-go-live">
          <span>GO-LIVE CONTROLS</span>
          <h3>Finish configuration without cluttering daily care</h3>
          <div>
            {goLive.map(item => <Link href={item.href} key={item.href}><strong>{item.title}</strong><small>{item.text}</small><b>›</b></Link>)}
          </div>
          <Link href="/system-control" className="all">Open full system directory</Link>
        </aside>
      </section>

      <footer className="os-footer">
        <div><strong>LucyWorks OS</strong><span>Patient-centred referral-hospital operating system</span></div>
        <div><span>Signed in as {user.name}</span><span>{site ? `${site.name} · ${site.premisesRef}` : "Hospital context loading"}</span></div>
      </footer>
    </main>
  );
}

const css = `
.os-home{min-height:100vh;padding:14px 18px 34px;background:#eef2f7;color:#172033;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.os-home *{box-sizing:border-box}.os-top{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:10px;padding:12px 14px;background:#fff;border:1px solid #d7e0e9;border-radius:12px}.os-brand{display:flex;align-items:center;gap:11px}.os-mark{display:grid;place-items:center;width:38px;height:38px;border-radius:10px;background:linear-gradient(145deg,#153a58,#10283f);color:#fff;font-size:11px;font-weight:950;letter-spacing:.03em}.os-brand>div:last-child>span{display:block;color:#6e7e90;font-size:8px;font-weight:900;letter-spacing:.12em;text-transform:uppercase}.os-brand h1{margin:1px 0 0;color:#142d44;font-size:18px;line-height:1.05;letter-spacing:-.02em}.os-brand p{margin:3px 0 0;color:#748296;font-size:9px;font-weight:700}.os-top-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}.os-top-actions a,.os-top-actions button{min-height:36px;padding:0 10px;border:1px solid #cbd5df;border-radius:8px;background:#fff;color:#294861;text-decoration:none;font-size:10px;font-weight:850;display:inline-flex;align-items:center;justify-content:center}.os-top-actions .primary{border-color:#173f5f;background:#173f5f;color:#fff}.os-alert{margin-bottom:10px;padding:9px 11px;border:1px solid #e2b1ad;border-radius:9px;background:#fff5f4;color:#8e3730;font-size:10px;font-weight:800}.os-hero{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(280px,.65fr);gap:10px;margin-bottom:10px}.os-hero-copy,.os-attention{background:#fff;border:1px solid #d7e0e9;border-radius:12px}.os-hero-copy{padding:28px 28px 25px;background:linear-gradient(135deg,#ffffff 0%,#f8fafc 62%,#edf4f7 100%)}.os-eyebrow,.os-section-head span,.os-completion-copy>span,.os-go-live>span{display:block;color:#5d7488;font-size:8px;font-weight:950;letter-spacing:.14em;text-transform:uppercase}.os-hero-copy h2{max-width:820px;margin:7px 0 0;color:#132c42;font-size:34px;line-height:1.01;letter-spacing:-.045em}.os-hero-copy p{max-width:760px;margin:11px 0 0;color:#637589;font-size:12px;line-height:1.55}.os-hero-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:20px}.os-hero-actions a{display:inline-flex;align-items:center;min-height:39px;padding:0 12px;border:1px solid #cbd5df;border-radius:8px;background:#fff;color:#294861;font-size:10px;font-weight:850}.os-hero-actions .primary{border-color:#173f5f;background:#173f5f;color:#fff}.os-attention{padding:17px;border-left:5px solid #2d8061}.os-attention.danger{border-left-color:#b9403a}.os-attention-head{display:flex;justify-content:space-between;align-items:center;gap:8px}.os-attention-head span{color:#6b7b8d;font-size:8px;font-weight:900;letter-spacing:.1em}.os-attention-head small{color:#8491a0;font-size:8px}.os-attention>strong{display:block;margin-top:20px;color:#17334d;font-size:54px;line-height:.9;letter-spacing:-.07em}.os-attention h3{margin:8px 0 0;color:#22394d;font-size:14px}.os-attention p{margin:7px 0 16px;color:#68798a;font-size:10px;line-height:1.5}.os-attention>a{font-size:10px;font-weight:850;color:#245271}.os-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin-bottom:10px}.os-kpis article{display:grid;gap:3px;padding:10px 11px;background:#fff;border:1px solid #d7e0e9;border-top:3px solid #52738d;border-radius:9px}.os-kpis article.warn{border-top-color:#c27a16;background:#fffdfa}.os-kpis span{color:#6b7b8c;font-size:8px;font-weight:850;text-transform:uppercase;letter-spacing:.05em}.os-kpis strong{color:#17334d;font-size:23px;letter-spacing:-.04em}.os-kpis small{color:#8190a0;font-size:8px}.os-section{margin-bottom:10px;background:#fff;border:1px solid #d7e0e9;border-radius:12px;overflow:hidden}.os-section-head{display:flex;justify-content:space-between;align-items:end;gap:16px;padding:13px 15px;border-bottom:1px solid #e5eaf0;background:#f8fafc}.os-section-head h2{margin:3px 0 0;color:#193249;font-size:17px}.os-section-head p{margin:4px 0 0;color:#748294;font-size:9px;line-height:1.4}.os-section-head>a{color:#2b5877;font-size:9px;font-weight:850;white-space:nowrap}.os-clinical-grid{display:grid;grid-template-columns:1.35fr repeat(4,1fr);gap:1px;background:#e7ecf1}.os-clinical-grid>a{min-height:152px;padding:14px;background:#fff;color:#172033;display:flex;flex-direction:column;text-decoration:none;border-top:3px solid #5d7b93}.os-clinical-grid>a.featured{background:#f7fbf9;border-top-color:#2d8061}.os-clinical-grid span{color:#748397;font-size:8px;font-weight:850;text-transform:uppercase}.os-clinical-grid strong{margin-top:7px;color:#20384d;font-size:13px}.os-clinical-grid p{margin:6px 0 12px;color:#6b7b8e;font-size:9px;line-height:1.45}.os-clinical-grid b,.os-ops-grid b{margin-top:auto;color:#315d7b;font-size:8px;text-transform:uppercase;letter-spacing:.05em}.os-ops-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:#e7ecf1}.os-ops-grid>a{min-height:118px;padding:13px;background:#fff;color:#172033;display:flex;flex-direction:column}.os-ops-grid strong{font-size:12px;color:#20384d}.os-ops-grid p{margin:6px 0 10px;color:#6b7b8e;font-size:9px;line-height:1.45}.os-completion{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(300px,.65fr);gap:10px}.os-completion-copy,.os-go-live{background:#fff;border:1px solid #d7e0e9;border-radius:12px;padding:15px}.os-completion-copy h2{margin:4px 0 0;color:#183148;font-size:20px;letter-spacing:-.025em}.os-completion-copy>p{margin:7px 0 12px;color:#68798b;font-size:10px;line-height:1.5;max-width:900px}.os-roadmap{display:grid;gap:5px}.os-roadmap article{display:grid;grid-template-columns:30px minmax(0,1fr) auto;gap:9px;align-items:center;padding:8px 9px;border:1px solid #e1e7ed;border-radius:8px;background:#fbfcfd}.os-roadmap i{display:grid;place-items:center;width:26px;height:26px;border-radius:99px;background:#e8edf2;color:#526b80;font-style:normal;font-size:9px;font-weight:900}.os-roadmap article.done i{background:#dfeee7;color:#2d684f}.os-roadmap article.next{border-color:#dfc58f;background:#fffaf1}.os-roadmap article.next i{background:#f8e7c4;color:#8b5a13}.os-roadmap article>div{display:grid;gap:2px}.os-roadmap strong{font-size:10px;color:#233b4f}.os-roadmap span{font-size:8px;color:#728294;line-height:1.4}.os-roadmap b{padding:4px 6px;border-radius:99px;background:#edf1f5;color:#657689;font-size:7px;letter-spacing:.06em}.os-roadmap .done b{background:#e4f1ea;color:#356c55}.os-roadmap .next b{background:#faebcc;color:#8c5c18}.os-go-live h3{margin:4px 0 12px;color:#1d354a;font-size:15px}.os-go-live>div{display:grid;border:1px solid #e2e7ed;border-radius:8px;overflow:hidden}.os-go-live>div>a{display:grid;grid-template-columns:minmax(0,1fr) 15px;gap:3px 8px;padding:9px 10px;background:#fff;border-bottom:1px solid #edf0f3;color:#172033}.os-go-live>div>a:last-child{border-bottom:0}.os-go-live strong{font-size:10px;color:#28465f}.os-go-live small{grid-column:1;color:#778697;font-size:8px;line-height:1.35}.os-go-live b{grid-column:2;grid-row:1/3;align-self:center;color:#7b8a9a}.os-go-live .all{display:block;margin-top:10px;padding:9px 10px;border-radius:7px;background:#173f5f;color:#fff;text-align:center;font-size:9px;font-weight:850}.os-footer{display:flex;justify-content:space-between;gap:18px;margin-top:10px;padding:11px 13px;color:#718194;font-size:8px}.os-footer>div{display:grid;gap:2px}.os-footer strong{color:#29455c;font-size:10px}
@media(max-width:1100px){.os-clinical-grid{grid-template-columns:repeat(3,1fr)}.os-ops-grid{grid-template-columns:repeat(2,1fr)}.os-kpis{grid-template-columns:repeat(3,1fr)}}
@media(max-width:760px){.os-home{padding:8px}.os-top{align-items:flex-start}.os-top-actions a:not(.primary),.os-top-actions button{display:none}.os-hero{grid-template-columns:1fr}.os-hero-copy{padding:20px 16px}.os-hero-copy h2{font-size:29px}.os-kpis{grid-template-columns:1fr 1fr}.os-kpis article:last-child{grid-column:1/-1}.os-section-head{align-items:flex-start}.os-section-head>a{display:none}.os-clinical-grid{grid-template-columns:1fr 1fr}.os-clinical-grid>a{min-height:128px}.os-clinical-grid>a.featured{grid-column:1/-1}.os-ops-grid{grid-template-columns:1fr 1fr}.os-completion{grid-template-columns:1fr}.os-footer{display:grid}.os-roadmap article{grid-template-columns:28px minmax(0,1fr)}.os-roadmap article>b{display:none}}
@media(max-width:480px){.os-kpis{grid-template-columns:1fr 1fr}.os-clinical-grid,.os-ops-grid{grid-template-columns:1fr}.os-clinical-grid>a.featured{grid-column:auto}.os-top-actions{justify-content:flex-end}.os-brand p{max-width:170px}.os-hero-copy h2{font-size:26px}}
`;
