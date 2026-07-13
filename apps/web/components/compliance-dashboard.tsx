"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Episode = {
  id: string;
  episodeRef: string;
  stage?: string | null;
  ownerRole?: string | null;
  ownerName?: string | null;
  currentLocation?: string | null;
  nextAction?: string | null;
  blocker?: string | null;
  status?: string | null;
  consentStatus?: string | null;
  estimateStatus?: string | null;
  insuranceStatus?: string | null;
  pharmacyReady?: boolean | null;
  ownerUpdated?: boolean | null;
  referringVetReportSent?: boolean | null;
  dischargeClear?: boolean | null;
  events?: unknown[];
};

type PatientCase = {
  id: string;
  patientName: string;
  riskLevel?: string | null;
  status?: string | null;
  episodes?: Episode[];
};

type EvidenceEvent = {
  id?: number;
  eventType?: string;
  action?: string;
  patientCaseId?: string | null;
  referralEpisodeId?: string | null;
  actorName?: string | null;
  professionalRole?: string | null;
  complianceDomain?: string | null;
  riskLevel?: string | null;
  humanReviewStatus?: string | null;
  supervisorApprovalStatus?: string | null;
  createdAt?: string | null;
};

type ComplianceGap = {
  severity: "red" | "amber";
  patient: string;
  episodeId: string;
  episodeRef: string;
  type: string;
  detail: string;
};

function isClear(value: string | null | undefined) {
  const normal = String(value || "").toLowerCase();
  return ["clear", "cleared", "approved", "authorised", "authorized", "complete", "completed", "done", "ready"].includes(normal);
}

function gap(severity: "red" | "amber", patient: string, episode: Episode, type: string, detail: string): ComplianceGap {
  return { severity, patient, episodeId: episode.id, episodeRef: episode.episodeRef, type, detail };
}

function gapsFor(cases: PatientCase[], events: EvidenceEvent[]): ComplianceGap[] {
  const eventsByEpisode = new Map<string, EvidenceEvent[]>();
  for (const event of events) {
    if (!event.referralEpisodeId) continue;
    eventsByEpisode.set(event.referralEpisodeId, [...(eventsByEpisode.get(event.referralEpisodeId) || []), event]);
  }

  const out: ComplianceGap[] = [];
  for (const item of cases) {
    for (const episode of item.episodes || []) {
      const blocker = String(episode.blocker || "none").toLowerCase();
      const hasProcedure = [episode.stage, episode.nextAction, episode.episodeRef].join(" ").toLowerCase().match(/procedure|mri|ct|theatre|surgery|anaesthesia|imaging/);
      const hasClosure = [episode.stage, episode.nextAction, episode.episodeRef].join(" ").toLowerCase().match(/closure|owner|client|report|discharge/);
      const episodeEvents = eventsByEpisode.get(episode.id) || [];

      if (blocker !== "none" || episode.status === "blocked" || item.riskLevel === "red") out.push(gap("red", item.patientName, episode, "blocked_episode", episode.blocker || "case is blocked or red"));
      if (hasProcedure && !isClear(episode.consentStatus)) out.push(gap("red", item.patientName, episode, "consent_not_clear", "procedure pathway has no clear consent state"));
      if (hasProcedure && !isClear(episode.estimateStatus)) out.push(gap("red", item.patientName, episode, "estimate_not_clear", "procedure pathway has no clear estimate state"));
      if (hasProcedure && episode.pharmacyReady === false) out.push(gap("red", item.patientName, episode, "pharmacy_not_ready", "procedure pathway has medication/pharmacy dependency not ready"));
      if (hasClosure && episode.ownerUpdated === false) out.push(gap("red", item.patientName, episode, "owner_not_updated", "owner/client update has not been recorded"));
      if (hasClosure && episode.referringVetReportSent === false) out.push(gap("amber", item.patientName, episode, "referring_vet_report_missing", "referring-vet report has not been recorded"));
      if (!episode.ownerName && !episode.ownerRole) out.push(gap("amber", item.patientName, episode, "ownership_gap", "episode has no named owner or owning role"));
      if (!episodeEvents.length) out.push(gap("amber", item.patientName, episode, "no_evidence_events", "episode has no platform evidence events"));
      if (episodeEvents.some((event) => event.riskLevel === "red" && event.supervisorApprovalStatus !== "accepted" && event.supervisorApprovalStatus !== "approved")) out.push(gap("red", item.patientName, episode, "approval_gap", "red-risk evidence event lacks supervisor approval"));
      if (episodeEvents.some((event) => event.eventType?.includes("ai") || event.action?.toLowerCase().includes("ai")) && episodeEvents.some((event) => !event.humanReviewStatus || event.humanReviewStatus === "not_required")) out.push(gap("amber", item.patientName, episode, "ai_review_gap", "AI-linked evidence lacks explicit human review state"));
    }
  }
  return out.sort((a, b) => Number(a.severity !== "red") - Number(b.severity !== "red") || a.patient.localeCompare(b.patient));
}

async function loadCases(): Promise<PatientCase[]> {
  const response = await fetch(`${API_BASE}/api/patient-care/cases`, { cache: "no-store" });
  if (!response.ok) throw new Error("patient-care unavailable");
  const data = await response.json();
  return Array.isArray(data.cases) ? data.cases : [];
}

async function loadEvents(): Promise<EvidenceEvent[]> {
  const response = await fetch(`${API_BASE}/api/evidence/events`, { cache: "no-store" });
  if (!response.ok) throw new Error("evidence unavailable");
  const data = await response.json();
  return Array.isArray(data.events) ? data.events : [];
}

export function ComplianceDashboard() {
  const [cases, setCases] = useState<PatientCase[]>([]);
  const [events, setEvents] = useState<EvidenceEvent[]>([]);
  const [status, setStatus] = useState("loading");

  async function refresh() {
    try {
      const [nextCases, nextEvents] = await Promise.all([loadCases(), loadEvents()]);
      setCases(nextCases);
      setEvents(nextEvents);
      setStatus("live database");
    } catch {
      setStatus("offline");
    }
  }

  useEffect(() => { void refresh(); }, []);

  const gaps = useMemo(() => gapsFor(cases, events), [cases, events]);
  const red = gaps.filter((item) => item.severity === "red").length;
  const amber = gaps.filter((item) => item.severity === "amber").length;
  const episodeCount = cases.reduce((total, item) => total + (item.episodes?.length || 0), 0);

  return <main className="compliance"><style>{css}</style>
    <header>
      <div>
        <span>LucyWorks OS</span>
        <h1>Compliance control</h1>
        <p>Premises and patient-flow evidence view: consent, estimates, pharmacy, ownership, reports, AI review and red-risk approvals.</p>
      </div>
      <nav><a href="/patient-care">Patient care</a><a href="/hospital-board">Board</a><button onClick={() => void refresh()}>Refresh</button></nav>
    </header>

    <section className="kpis">
      <article><b>{red}</b><small>red gaps</small></article>
      <article><b>{amber}</b><small>amber gaps</small></article>
      <article><b>{episodeCount}</b><small>episodes</small></article>
      <article><b>{events.length}</b><small>evidence events</small></article>
      <article><b>{status}</b><small>source</small></article>
    </section>

    <section className="board">
      <article>
        <h2>Open compliance gaps</h2>
        {gaps.length ? gaps.map((item) => <div className={`gap ${item.severity}`} key={`${item.episodeId}-${item.type}`}>
          <strong>{item.type.replace(/_/g, " ")}</strong>
          <span>{item.patient} · {item.episodeRef}</span>
          <p>{item.detail}</p>
        </div>) : <p className="empty">No compliance gaps found from current case/evidence data.</p>}
      </article>
      <article>
        <h2>Recent evidence</h2>
        {events.length ? events.slice(0, 12).map((event) => <div className="event" key={event.id}>
          <strong>{event.action || event.eventType}</strong>
          <span>{event.actorName || "system"} · {event.professionalRole || "role not set"}</span>
          <p>{event.complianceDomain || "domain not set"} · {event.riskLevel || "risk not set"} · review {event.humanReviewStatus || "not recorded"}</p>
        </div>) : <p className="empty">No evidence events recorded yet.</p>}
      </article>
    </section>
  </main>;
}

const css = `.compliance{min-height:100vh;background:#f5f7fb;color:#111827;padding:14px;font-family:Inter,system-ui,sans-serif}.compliance *{box-sizing:border-box}.compliance header{display:flex;justify-content:space-between;gap:14px;background:#fff;border:1px solid #d8e0ec;border-radius:18px;padding:16px;box-shadow:0 10px 28px rgba(15,23,42,.06)}.compliance header span{display:block;text-transform:uppercase;letter-spacing:.14em;color:#2563eb;font-size:11px;font-weight:900}.compliance h1{font-size:clamp(34px,7vw,64px);line-height:.95;margin:6px 0}.compliance p{color:#475569;margin:6px 0 0}.compliance nav{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-start}.compliance a,.compliance button{border:1px solid #cbd5e1;background:#fff;color:#0f172a;border-radius:999px;padding:9px 12px;text-decoration:none;font-weight:800;cursor:pointer}.compliance a:first-child,.compliance button{background:#0f172a;color:#fff}.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:12px 0}.kpis article,.board article{background:#fff;border:1px solid #d8e0ec;border-radius:18px;padding:14px}.kpis b{display:block;font-size:32px;line-height:1}.kpis small{display:block;color:#64748b;margin-top:4px}.board{display:grid;grid-template-columns:1.2fr .8fr;gap:12px}.board h2{margin:0 0 10px}.gap,.event{border:1px solid #e2e8f0;border-left-width:6px;border-radius:14px;padding:10px;margin-bottom:8px;background:#fff}.gap.red{border-left-color:#dc2626;background:#fff7f7}.gap.amber{border-left-color:#f59e0b;background:#fffbeb}.event{border-left-color:#2563eb;background:#eff6ff}.gap strong,.event strong{display:block;text-transform:capitalize}.gap span,.event span{display:block;color:#475569;font-size:13px;margin-top:3px}.empty{color:#64748b}@media(max-width:760px){.compliance{padding:10px}.compliance header{display:grid}.compliance nav a,.compliance nav button{flex:1;text-align:center}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.board{grid-template-columns:1fr}}`;
