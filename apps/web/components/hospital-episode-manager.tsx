"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiJson, apiPost } from "@/lib/api";

type Episode = {
  episodeRef: string;
  patientRef?: string;
  patientName: string;
  serviceLine: string;
  urgency: string;
  phase: string;
  status: string;
  ownerRole: string;
  ownerSubject?: string;
  currentAreaRef?: string;
  nextAction?: string;
  gates: Record<string, unknown>;
  flags: unknown[];
  version: number;
};

type EpisodeList = { episodes: Episode[]; count: number };

const PHASES = [
  "referral_received", "intake_validation", "accepted", "arrived", "consultation",
  "diagnostic_plan", "estimate_and_consent", "preparation", "procedure", "recovery",
  "ward_or_icu", "discharge_readiness", "discharged", "referring_vet_report", "closed",
];

const NEXT: Record<string, string[]> = {
  referral_received: ["intake_validation"],
  intake_validation: ["accepted", "closed"],
  accepted: ["arrived", "closed"],
  arrived: ["consultation"],
  consultation: ["diagnostic_plan", "discharge_readiness"],
  diagnostic_plan: ["estimate_and_consent"],
  estimate_and_consent: ["preparation", "diagnostic_plan"],
  preparation: ["procedure", "estimate_and_consent"],
  procedure: ["recovery"],
  recovery: ["ward_or_icu", "discharge_readiness"],
  ward_or_icu: ["discharge_readiness", "procedure"],
  discharge_readiness: ["discharged", "ward_or_icu"],
  discharged: ["referring_vet_report"],
  referring_vet_report: ["closed"],
  closed: [],
};

function label(value: string) {
  return value.replaceAll("_", " ");
}

function gateValue(value: unknown) {
  if (typeof value === "boolean") return value ? "complete" : "pending";
  return String(value || "not recorded");
}

export function HospitalEpisodeManager() {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [selectedRef, setSelectedRef] = useState("");
  const [status, setStatus] = useState("loading referral episodes");
  const [patientName, setPatientName] = useState("");
  const [patientRef, setPatientRef] = useState("");
  const [urgency, setUrgency] = useState("routine");
  const [nextPhase, setNextPhase] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [gateDraft, setGateDraft] = useState<Record<string, string>>({
    consent: "not_recorded",
    estimate: "not_recorded",
    insurance: "not_recorded",
    pharmacy: "not_ready",
    preparation: "not_ready",
    discharge: "not_ready",
    medication: "not_ready",
    owner_update: "not_ready",
  });

  const selected = useMemo(() => episodes.find((item) => item.episodeRef === selectedRef) || episodes[0] || null, [episodes, selectedRef]);

  async function refresh(preferRef?: string) {
    try {
      const data = await apiGet<EpisodeList>("/api/hospital-ops/episodes?premises_ref=default-premises");
      setEpisodes(data.episodes);
      const ref = preferRef || selectedRef || data.episodes[0]?.episodeRef || "";
      setSelectedRef(ref);
      const current = data.episodes.find((item) => item.episodeRef === ref) || data.episodes[0];
      if (current) {
        setGateDraft((draft) => ({ ...draft, ...Object.fromEntries(Object.entries(current.gates || {}).map(([key, value]) => [key, String(value)])) }));
        setNextPhase(NEXT[current.phase]?.[0] || "");
      }
      setStatus(`${data.count} referral episodes loaded from canonical state`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "episode service unavailable");
    }
  }

  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    if (!selected) return;
    setGateDraft((draft) => ({ ...draft, ...Object.fromEntries(Object.entries(selected.gates || {}).map(([key, value]) => [key, String(value)])) }));
    setNextPhase(NEXT[selected.phase]?.[0] || "");
    setOverrideReason("");
  }, [selected?.episodeRef, selected?.version]);

  async function createEpisode() {
    if (!patientName.trim()) return;
    setStatus("creating versioned referral episode");
    try {
      const result = await apiPost<{ episode: Episode }>("/api/hospital-ops/episodes", {
        patientName: patientName.trim(),
        patientRef: patientRef.trim() || undefined,
        premisesRef: "default-premises",
        urgency,
        serviceLine: "referral",
        gates: {},
        flags: [],
        idempotencyKey: `intake:${Date.now()}:${patientName.trim().toLowerCase()}`,
      });
      setPatientName("");
      setPatientRef("");
      await refresh(result.episode.episodeRef);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "episode creation failed");
    }
  }

  async function saveGates() {
    if (!selected) return;
    setStatus("recording governance gates");
    try {
      const result = await apiJson<{ episode: Episode }>(`/api/hospital-ops/episodes/${selected.episodeRef}/gates`, {
        method: "PATCH",
        body: JSON.stringify({
          expectedVersion: selected.version,
          gates: gateDraft,
          reason: "referral episode governance reviewed",
          nextAction: selected.nextAction,
        }),
      });
      await refresh(result.episode.episodeRef);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "gate update failed");
      await refresh(selected.episodeRef);
    }
  }

  async function transition() {
    if (!selected || !nextPhase) return;
    setStatus(`transitioning to ${label(nextPhase)}`);
    try {
      const result = await apiJson<{ episode: Episode }>(`/api/hospital-ops/episodes/${selected.episodeRef}/transition`, {
        method: "PATCH",
        body: JSON.stringify({
          expectedVersion: selected.version,
          phase: nextPhase,
          reason: "phase completed by episode owner",
          overrideReason: overrideReason.trim() || undefined,
        }),
      });
      await refresh(result.episode.episodeRef);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "transition failed");
      await refresh(selected.episodeRef);
    }
  }

  return <main className="hem"><style>{css}</style>
    <header>
      <div><span>LucyWorks OS · referral continuity</span><h1>Canonical episodes</h1><p>One pathway from referral receipt to closure. Ownership, gates and phase changes are version checked and written to the evidence chain.</p></div>
      <nav><a href="/hospital-board">Master board</a><a href="/patient-care">Patient care</a><a href="/system-control">System control</a></nav>
    </header>
    <section className="status">{status}</section>

    <section className="create panel">
      <h2>New referral intake</h2>
      <label>Patient name<input value={patientName} onChange={(event) => setPatientName(event.target.value)} /></label>
      <label>Patient / PIMS reference<input value={patientRef} onChange={(event) => setPatientRef(event.target.value)} /></label>
      <label>Urgency<select value={urgency} onChange={(event) => setUrgency(event.target.value)}><option>routine</option><option>urgent</option><option>emergency</option></select></label>
      <button onClick={() => void createEpisode()}>Create referral episode</button>
    </section>

    <section className="layout">
      <aside className="panel list"><h2>Episodes</h2>{episodes.map((episode) => <button key={episode.episodeRef} className={selected?.episodeRef === episode.episodeRef ? "active" : ""} onClick={() => setSelectedRef(episode.episodeRef)}><b>{episode.patientName}</b><span>{label(episode.phase)} · {episode.ownerRole}</span><small>{episode.urgency} · version {episode.version}</small></button>)}</aside>

      {selected ? <section className="panel detail">
        <div className="episodeHead"><div><span>{selected.episodeRef}</span><h2>{selected.patientName}</h2><p>{label(selected.phase)} · owner {selected.ownerRole} · version {selected.version}</p></div><b className={`risk ${selected.urgency}`}>{selected.urgency}</b></div>
        <section className="path">{PHASES.map((phase) => <div key={phase} className={phase === selected.phase ? "current" : PHASES.indexOf(phase) < PHASES.indexOf(selected.phase) ? "done" : "future"}>{label(phase)}</div>)}</section>

        <h3>Governance gates</h3>
        <div className="gates">{Object.entries(gateDraft).map(([key, value]) => <label key={key}>{label(key)}<select value={value} onChange={(event) => setGateDraft({ ...gateDraft, [key]: event.target.value })}><option value="not_recorded">not recorded</option><option value="pending">pending</option><option value="approved">approved</option><option value="authorised">authorised</option><option value="accepted">accepted</option><option value="ready">ready</option><option value="complete">complete</option><option value="sent">sent</option><option value="declined">declined</option><option value="emergency_authority">emergency authority</option></select><small>Current: {gateValue(selected.gates?.[key])}</small></label>)}</div>
        <button onClick={() => void saveGates()}>Record gates</button>

        <h3>Phase transition</h3>
        {NEXT[selected.phase]?.length ? <div className="transition"><label>Next phase<select value={nextPhase} onChange={(event) => setNextPhase(event.target.value)}>{NEXT[selected.phase].map((phase) => <option key={phase} value={phase}>{label(phase)}</option>)}</select></label><label>Emergency override reason<textarea value={overrideReason} onChange={(event) => setOverrideReason(event.target.value)} placeholder="Leave blank for the normal controlled transition" /></label><button onClick={() => void transition()}>Complete phase and transfer ownership</button></div> : <p>This episode is closed.</p>}
      </section> : <section className="panel"><p>No referral episode selected.</p></section>}
    </section>
  </main>;
}

const css = `.hem{min-height:100vh;background:#e9eef5;color:#0f172a;padding:12px;font-family:Inter,system-ui,sans-serif}.hem *{box-sizing:border-box}.hem header{display:flex;justify-content:space-between;gap:14px;background:#071019;color:#fff;border-radius:18px;padding:17px}.hem header span{color:#2dd4bf;font-size:11px;font-weight:900;letter-spacing:.13em;text-transform:uppercase}.hem h1{font-size:clamp(36px,7vw,68px);line-height:.94;margin:6px 0}.hem header p{color:#94a3b8}.hem nav{display:flex;gap:7px;flex-wrap:wrap;align-content:flex-start}.hem a,.hem button{border:1px solid #334155;border-radius:999px;background:#0f172a;color:#fff;padding:9px 12px;text-decoration:none;font-weight:800;cursor:pointer}.status,.panel{background:#fff;border:1px solid #cbd5e1;border-radius:14px;padding:12px}.status{margin:10px 0;color:#475569;font-weight:800}.create{display:grid;grid-template-columns:1fr 1fr .55fr auto;gap:8px;align-items:end;margin-bottom:10px}.panel label{display:grid;gap:4px;font-size:12px;color:#475569;font-weight:800}.panel input,.panel select,.panel textarea{width:100%;border:1px solid #cbd5e1;border-radius:9px;padding:9px;background:#fff;font:inherit}.create h2{grid-column:1/-1;margin:0}.layout{display:grid;grid-template-columns:minmax(250px,.32fr) 1fr;gap:10px}.list{align-content:start}.list h2{margin-top:0}.list button{display:grid;width:100%;text-align:left;border:1px solid #e2e8f0;background:#f8fafc;color:#0f172a;border-radius:11px;padding:10px;margin-bottom:7px}.list button.active{border-color:#2563eb;background:#eff6ff}.list span,.list small{color:#64748b}.episodeHead{display:flex;justify-content:space-between;gap:10px}.episodeHead h2{font-size:38px;margin:5px 0}.episodeHead p{color:#475569}.risk{height:max-content;border-radius:999px;padding:7px 10px}.risk.emergency{background:#fee2e2;color:#991b1b}.risk.urgent{background:#fef3c7;color:#92400e}.risk.routine{background:#dcfce7;color:#166534}.path{display:flex;overflow:auto;gap:4px;padding:8px 0}.path div{min-width:125px;border:1px solid #cbd5e1;border-radius:9px;padding:7px;font-size:11px;text-transform:capitalize}.path .done{background:#dcfce7;border-color:#86efac}.path .current{background:#dbeafe;border-color:#60a5fa;font-weight:900}.path .future{color:#64748b}.gates{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:8px;margin-bottom:9px}.gates label{border:1px solid #e2e8f0;border-radius:10px;padding:8px}.gates small{color:#64748b}.detail h3{margin:18px 0 8px}.transition{display:grid;gap:9px;max-width:760px}.transition textarea{min-height:90px}@media(max-width:800px){.hem header{display:grid}.create{grid-template-columns:1fr}.create h2{grid-column:auto}.layout{grid-template-columns:1fr}.list{max-height:40vh;overflow:auto}.episodeHead{display:grid}}`;
