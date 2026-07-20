"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, apiGet, apiJson, apiPost } from "@/lib/api";
import { getSession } from "@/lib/session";

type Area = { areaRef: string; name: string; areaType: string; department: string; capacity: number; turnoverMinutes: number };
type Episode = { episodeRef: string; patientName: string; phase: string; urgency: string; ownerRole: string; nextAction?: string; version: number; gates: Record<string, unknown> };
type Block = {
  blockRef: string;
  episodeRef?: string;
  patientName?: string;
  procedureName: string;
  blockType: string;
  areaRef: string;
  areaName: string;
  startsAt: string;
  endsAt: string;
  status: string;
  riskLevel: string;
  priority: number;
  leadStaffRef?: string;
  leadStaffName?: string;
  leadStaffRole?: string;
  assistantRefs: unknown[];
  equipmentRefs: unknown[];
  requiredSkills: string[];
  blockers: unknown[];
  gates: Record<string, unknown>;
  pharmacyRefs: unknown[];
  version: number;
};
type Conflict = { conflictRef?: string; conflictType: string; severity: string; primaryBlockRef?: string; relatedRefs: string[]; explanation: string; options: Array<{ type: string; label: string; description: string; score: number; payload?: Record<string, unknown> }> };
type Board = { generatedAt: string; operationalDate: string; premises: { premisesRef: string; name: string }; areas: Area[]; blocks: Block[]; episodes: Episode[]; conflicts: Conflict[]; summary: { blocks: number; episodes: number; redConflicts: number; amberConflicts: number; unassignedBlocks: number; blockedBlocks: number; lastChangeId: number } };
type DelayPreview = { sourceBlockRef: string; minutes: number; affected: Array<{ blockRef: string; patientName?: string; procedureName: string; areaName: string; currentStartsAt: string; proposedStartsAt: string; expectedVersion: number }>; alternatives: Array<{ type: string; label: string; description: string; score: number }> };
type ImportPreview = { batchRef: string; status: string; rowCount: number; acceptedCount: number; rejectedCount: number; summary: Record<string, unknown> };

const PREMISES = "default-premises";
const DAY_START = 7 * 60;
const DAY_END = 22 * 60;
const CELL_HEIGHT = 46;

function isoDate(value = new Date()) {
  return value.toISOString().slice(0, 10);
}

function parseMinute(value: string) {
  const date = new Date(value);
  return date.getHours() * 60 + date.getMinutes();
}

function timeLabel(minutes: number) {
  const hour = Math.floor(minutes / 60);
  const minute = minutes % 60;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function shiftIso(value: string, minutes: number) {
  return new Date(new Date(value).getTime() + minutes * 60_000).toISOString();
}

function tone(value: string) {
  const normal = value.toLowerCase();
  if (["red", "blocked", "failed", "unavailable"].includes(normal)) return "red";
  if (["amber", "planned", "pending", "reduced"].includes(normal)) return "amber";
  return "green";
}

function nextPhase(current: string) {
  const phases = ["referral_received", "intake_validation", "accepted", "arrived", "consultation", "diagnostic_plan", "estimate_and_consent", "preparation", "procedure", "recovery", "ward_or_icu", "discharge_readiness", "discharged", "referring_vet_report", "closed"];
  const index = phases.indexOf(current);
  return index >= 0 && index < phases.length - 1 ? phases[index + 1] : null;
}

export function HospitalOperatingBoard() {
  const [operationalDate, setOperationalDate] = useState(isoDate());
  const [board, setBoard] = useState<Board | null>(null);
  const [status, setStatus] = useState("loading canonical board");
  const [selected, setSelected] = useState<Block | null>(null);
  const [selectedEpisode, setSelectedEpisode] = useState<Episode | null>(null);
  const [areaFilter, setAreaFilter] = useState("all");
  const [delayMinutes, setDelayMinutes] = useState(30);
  const [delayPreview, setDelayPreview] = useState<DelayPreview | null>(null);
  const [leadStaffRef, setLeadStaffRef] = useState("");
  const [leadStaffName, setLeadStaffName] = useState("");
  const [importText, setImportText] = useState("patientName,procedureName,areaRef,startsAt,endsAt\nExample dog,MRI,mri,2026-07-20T09:00:00Z,2026-07-20T10:00:00Z");
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
  const refreshTimer = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<Board>(`/api/hospital-ops/board?premises_ref=${PREMISES}&operational_date=${operationalDate}`);
      setBoard(data);
      setSelected((current) => current ? data.blocks.find((item) => item.blockRef === current.blockRef) || null : null);
      setSelectedEpisode((current) => current ? data.episodes.find((item) => item.episodeRef === current.episodeRef) || null : null);
      setStatus("live server state");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "board unavailable");
    }
  }, [operationalDate]);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    const controller = new AbortController();
    let stopped = false;
    async function connect() {
      const session = getSession();
      if (!session?.token) return;
      try {
        const response = await fetch(`${API_BASE}/api/hospital-ops/stream?premises_ref=${PREMISES}&operational_date=${operationalDate}&after_id=${board?.summary.lastChangeId || 0}`, {
          headers: { Authorization: `Bearer ${session.token}` },
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok || !response.body) throw new Error(`live stream ${response.status}`);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!stopped) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const messages = buffer.split("\n\n");
          buffer = messages.pop() || "";
          if (messages.some((message) => message.includes("event: board-change"))) {
            window.clearTimeout(refreshTimer.current || undefined);
            refreshTimer.current = window.setTimeout(() => void refresh(), 100);
          }
        }
      } catch {
        if (!stopped) {
          setStatus("live stream interrupted; reconnection polling active");
          refreshTimer.current = window.setTimeout(() => void refresh(), 3000);
        }
      }
    }
    void connect();
    return () => { stopped = true; controller.abort(); if (refreshTimer.current) window.clearTimeout(refreshTimer.current); };
  }, [operationalDate, board?.summary.lastChangeId, refresh]);

  const timeRows = useMemo(() => {
    const rows: number[] = [];
    for (let minute = DAY_START; minute <= DAY_END; minute += 15) rows.push(minute);
    return rows;
  }, []);

  const areas = useMemo(() => {
    if (!board) return [];
    const important = board.areas.filter((area) => ["theatre", "imaging", "prep", "recovery", "ward", "consult"].includes(area.areaType));
    return areaFilter === "all" ? important : important.filter((area) => area.areaType === areaFilter || area.department === areaFilter);
  }, [board, areaFilter]);

  const conflictsByBlock = useMemo(() => {
    const map = new Map<string, Conflict[]>();
    for (const conflict of board?.conflicts || []) {
      const refs = [conflict.primaryBlockRef, ...conflict.relatedRefs].filter(Boolean) as string[];
      for (const ref of refs) map.set(ref, [...(map.get(ref) || []), conflict]);
    }
    return map;
  }, [board]);

  async function patchSelected(patch: Record<string, unknown>) {
    if (!selected) return;
    setStatus("saving versioned command");
    try {
      const result = await apiJson<{ block: Block }>(`/api/hospital-ops/blocks/${selected.blockRef}`, {
        method: "PATCH",
        body: JSON.stringify({ expectedVersion: selected.version, ...patch }),
      });
      setSelected(result.block);
      setDelayPreview(null);
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "command failed");
      await refresh();
    }
  }

  async function previewDelay() {
    if (!selected) return;
    try {
      setDelayPreview(await apiPost<DelayPreview>(`/api/hospital-ops/blocks/${selected.blockRef}/delay-preview`, { minutes: delayMinutes }));
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "delay preview failed");
    }
  }

  async function applyDelay() {
    if (!selected || !delayPreview) return;
    const expectedVersions = Object.fromEntries(delayPreview.affected.map((item) => [item.blockRef, item.expectedVersion]));
    try {
      await apiPost(`/api/hospital-ops/blocks/${selected.blockRef}/delay`, { minutes: delayMinutes, expectedVersions, reason: "live operational delay" });
      setDelayPreview(null);
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "delay command failed");
      await refresh();
    }
  }

  async function advanceEpisode() {
    if (!selectedEpisode) return;
    const phase = nextPhase(selectedEpisode.phase);
    if (!phase) return;
    try {
      const result = await apiJson<{ episode: Episode }>(`/api/hospital-ops/episodes/${selectedEpisode.episodeRef}/transition`, {
        method: "PATCH",
        body: JSON.stringify({ expectedVersion: selectedEpisode.version, phase, reason: "phase completed from master board" }),
      });
      setSelectedEpisode(result.episode);
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "transition blocked");
      await refresh();
    }
  }

  async function runSimulation(commit: boolean) {
    try {
      const data = await apiPost<{ runRef: string; metrics: Record<string, unknown> }>("/api/hospital-ops/simulation/run", { scenarioName: "eleven-theatre-referral-day", premisesRef: commit ? PREMISES : "simulation-premises", operationalDate, seed: 42, caseCount: 40, commit });
      setStatus(`simulation ${data.runRef}: ${JSON.stringify(data.metrics)}`);
      if (commit) await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "simulation failed");
    }
  }

  async function previewImport() {
    try {
      const data = await apiPost<ImportPreview>("/api/hospital-ops/imports/preview", { sourceType: "csv", sourceName: "board CSV", premisesRef: PREMISES, content: importText, mapping: {} });
      setImportPreview(data);
      setStatus(`import preview: ${data.acceptedCount} accepted, ${data.rejectedCount} reconciliation items`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "import preview failed");
    }
  }

  async function commitImport() {
    if (!importPreview) return;
    try {
      await apiPost(`/api/hospital-ops/imports/${importPreview.batchRef}/commit`, {});
      setImportPreview(null);
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "import commit failed");
    }
  }

  if (!board) return <main className="hosLoading">{status}</main>;

  return <main className="hos"><style>{css}</style>
    <header className="hero">
      <div><span>LucyWorks OS · canonical operations v3</span><h1>Referral hospital master grid</h1><p>One server-authoritative plan. Every change is version checked, attributed, evidenced and streamed to every screen.</p></div>
      <nav><a href="/control-plane">Control plane</a><a href="/patient-care">Patient care</a><a href="/integrations">Integrations</a><button onClick={() => void refresh()}>Refresh</button></nav>
    </header>

    <section className="toolbar">
      <label>Date<input type="date" value={operationalDate} onChange={(event) => setOperationalDate(event.target.value)} /></label>
      <label>Areas<select value={areaFilter} onChange={(event) => setAreaFilter(event.target.value)}><option value="all">All clinical areas</option><option value="theatre">Theatres</option><option value="imaging">Imaging</option><option value="ward">Wards</option><option value="recovery">Recovery</option><option value="consult">Consults</option></select></label>
      <strong>{status}</strong>
    </section>

    <section className="kpis">
      <article><b>{board.summary.blocks}</b><small>operational blocks</small></article>
      <article><b>{board.summary.episodes}</b><small>active episodes</small></article>
      <article className={board.summary.redConflicts ? "red" : "green"}><b>{board.summary.redConflicts}</b><small>red conflicts</small></article>
      <article className={board.summary.amberConflicts ? "amber" : "green"}><b>{board.summary.amberConflicts}</b><small>amber conflicts</small></article>
      <article className={board.summary.unassignedBlocks ? "amber" : "green"}><b>{board.summary.unassignedBlocks}</b><small>unassigned</small></article>
      <article><b>v3</b><small>canonical state</small></article>
    </section>

    <section className="mobileCases">
      {board.blocks.sort((a, b) => a.startsAt.localeCompare(b.startsAt)).map((block) => <button key={block.blockRef} className={tone(conflictsByBlock.get(block.blockRef)?.some((item) => item.severity === "red") ? "red" : block.riskLevel)} onClick={() => { setSelected(block); setSelectedEpisode(board.episodes.find((item) => item.episodeRef === block.episodeRef) || null); setLeadStaffRef(block.leadStaffRef || ""); setLeadStaffName(block.leadStaffName || ""); }}><time>{new Date(block.startsAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time><div><b>{block.patientName || "Operational work"}</b><strong>{block.procedureName}</strong><small>{block.areaName} · {block.leadStaffName || "UNASSIGNED"} · v{block.version}</small></div></button>)}
    </section>

    <section className="gridShell">
      <div className="grid" style={{ gridTemplateColumns: `74px repeat(${areas.length}, minmax(180px, 1fr))`, minWidth: `${74 + areas.length * 180}px` }}>
        <div className="corner">Time</div>
        {areas.map((area) => <div className="areaHead" key={area.areaRef}><b>{area.name}</b><small>{area.department} · cap {area.capacity} · turn {area.turnoverMinutes}m</small></div>)}
        {timeRows.map((minute) => <div className="timeRow" key={`time-${minute}`} style={{ gridColumn: "1", gridRow: `${2 + (minute - DAY_START) / 15}` }}>{timeLabel(minute)}</div>)}
        {areas.flatMap((area, areaIndex) => timeRows.map((minute) => <div key={`${area.areaRef}-${minute}`} className="cell" style={{ gridColumn: `${2 + areaIndex}`, gridRow: `${2 + (minute - DAY_START) / 15}` }} />))}
        {board.blocks.filter((block) => areas.some((area) => area.areaRef === block.areaRef)).map((block) => {
          const areaIndex = areas.findIndex((area) => area.areaRef === block.areaRef);
          const start = Math.max(DAY_START, parseMinute(block.startsAt));
          const end = Math.min(DAY_END + 15, parseMinute(block.endsAt));
          const rowStart = 2 + Math.floor((start - DAY_START) / 15);
          const span = Math.max(1, Math.ceil((end - start) / 15));
          const conflicts = conflictsByBlock.get(block.blockRef) || [];
          const severity = conflicts.some((item) => item.severity === "red") ? "red" : conflicts.some((item) => item.severity === "amber") ? "amber" : block.riskLevel;
          return <button key={block.blockRef} className={`gridBlock ${tone(severity)}`} style={{ gridColumn: `${2 + areaIndex}`, gridRow: `${rowStart} / span ${span}` }} onClick={() => { setSelected(block); setSelectedEpisode(board.episodes.find((item) => item.episodeRef === block.episodeRef) || null); setLeadStaffRef(block.leadStaffRef || ""); setLeadStaffName(block.leadStaffName || ""); }}><span>{new Date(block.startsAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}–{new Date(block.endsAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span><b>{block.patientName || "Operational work"}</b><strong>{block.procedureName}</strong><small>{block.leadStaffName || "NO LEAD"} · v{block.version}</small>{conflicts.length ? <em>{conflicts.length} conflict{conflicts.length === 1 ? "" : "s"}</em> : null}</button>;
        })}
      </div>
    </section>

    <section className="lower">
      <article className="panel conflicts"><h2>Explained constraints</h2>{board.conflicts.length ? board.conflicts.map((conflict, index) => <div className={`conflict ${tone(conflict.severity)}`} key={conflict.conflictRef || `${conflict.conflictType}-${index}`}><b>{conflict.conflictType.replaceAll("_", " ")}</b><p>{conflict.explanation}</p>{conflict.options.slice(0, 3).map((option) => <small key={option.label}><strong>{option.label}</strong> — {option.description}</small>)}</div>) : <p>No conflicts detected for this operating date.</p>}</article>

      <article className="panel episodes"><h2>Referral episode state machine</h2>{board.episodes.slice(0, 30).map((episode) => <button key={episode.episodeRef} className={selectedEpisode?.episodeRef === episode.episodeRef ? "active" : ""} onClick={() => setSelectedEpisode(episode)}><b>{episode.patientName}</b><span>{episode.phase.replaceAll("_", " ")} · {episode.ownerRole} · v{episode.version}</span><small>{episode.nextAction || "no next action"}</small></button>)}</article>
    </section>

    <details className="tools"><summary>Simulation, shadow mode and import reconciliation</summary><div className="toolGrid"><section><h3>40-case hospital simulation</h3><p>Runs an eleven-theatre referral day with imaging pressure, gate failures and collisions.</p><button onClick={() => void runSimulation(false)}>Dry-run simulation</button><button onClick={() => void runSimulation(true)}>Commit to selected date</button></section><section><h3>CSV / export preview</h3><textarea value={importText} onChange={(event) => setImportText(event.target.value)} /><button onClick={() => void previewImport()}>Preview and reconcile</button>{importPreview ? <button disabled={importPreview.rejectedCount > 0} onClick={() => void commitImport()}>Commit {importPreview.acceptedCount} accepted rows</button> : null}{importPreview?.rejectedCount ? <p>{importPreview.rejectedCount} rows must be reconciled before commit.</p> : null}</section></div></details>

    {selected ? <aside className="drawer"><button className="close" onClick={() => setSelected(null)}>×</button><span>{selected.blockRef}</span><h2>{selected.patientName || "Operational work"}</h2><h3>{selected.procedureName}</h3><p>{selected.areaName} · version {selected.version}</p><div className="drawerActions"><button onClick={() => void patchSelected({ commandType: "MoveOperationalBlock", action: "moved block earlier", startsAt: shiftIso(selected.startsAt, -15), endsAt: shiftIso(selected.endsAt, -15), reason: "manual board move" })}>−15 min</button><button onClick={() => void patchSelected({ commandType: "MoveOperationalBlock", action: "moved block later", startsAt: shiftIso(selected.startsAt, 15), endsAt: shiftIso(selected.endsAt, 15), reason: "manual board move" })}>+15 min</button></div><label>Lead staff reference<input value={leadStaffRef} onChange={(event) => setLeadStaffRef(event.target.value)} /></label><label>Lead staff name<input value={leadStaffName} onChange={(event) => setLeadStaffName(event.target.value)} /></label><button onClick={() => void patchSelected({ commandType: "AssignStaff", action: "assigned verified staff reference", leadStaffRef, leadStaffName, reason: "master-board assignment" })}>Save assignment</button><h3>Governance gates</h3><div className="drawerActions"><button onClick={() => void patchSelected({ commandType: "RecordGate", action: "consent gate recorded", gates: { ...selected.gates, consent: "approved" }, reason: "consent evidence confirmed" })}>Consent approved</button><button onClick={() => void patchSelected({ commandType: "RecordGate", action: "estimate gate recorded", gates: { ...selected.gates, estimate: "approved" }, reason: "estimate authority confirmed" })}>Estimate approved</button><button onClick={() => void patchSelected({ commandType: "RecordGate", action: "pharmacy gate recorded", gates: { ...selected.gates, pharmacy: "ready" }, reason: "pharmacy readiness confirmed" })}>Pharmacy ready</button></div><h3>Delay propagation</h3><label>Minutes<input type="number" value={delayMinutes} onChange={(event) => setDelayMinutes(Number(event.target.value))} /></label><button onClick={() => void previewDelay()}>Preview consequences</button>{delayPreview ? <div className="preview"><b>{delayPreview.affected.length} connected blocks affected</b>{delayPreview.affected.map((item) => <small key={item.blockRef}>{item.patientName} · {item.procedureName} → {new Date(item.proposedStartsAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</small>)}<button onClick={() => void applyDelay()}>Apply propagated delay</button></div> : null}{selectedEpisode ? <><h3>Episode</h3><p>{selectedEpisode.phase.replaceAll("_", " ")} · v{selectedEpisode.version}</p>{nextPhase(selectedEpisode.phase) ? <button onClick={() => void advanceEpisode()}>Advance to {nextPhase(selectedEpisode.phase)?.replaceAll("_", " ")}</button> : null}</> : null}</aside> : null}
  </main>;
}

const css = `.hosLoading{min-height:100vh;display:grid;place-items:center;background:#071019;color:#e2e8f0;font:700 18px system-ui}.hos{min-height:100vh;background:#e9eef5;color:#101827;padding:10px;font-family:Inter,system-ui,sans-serif}.hos *{box-sizing:border-box}.hero{display:flex;justify-content:space-between;gap:16px;background:#071019;color:#f8fafc;border-radius:18px;padding:16px}.hero span{color:#2dd4bf;font-size:11px;font-weight:900;letter-spacing:.13em;text-transform:uppercase}.hero h1{font-size:clamp(34px,6vw,64px);line-height:.95;margin:6px 0}.hero p{color:#94a3b8;margin:5px 0}.hero nav{display:flex;gap:7px;flex-wrap:wrap;align-content:flex-start}.hero a,.hero button,.tools button,.drawer button{border:1px solid #334155;border-radius:999px;background:#0f172a;color:#fff;padding:9px 12px;text-decoration:none;font-weight:800;cursor:pointer}.toolbar{display:flex;gap:10px;align-items:end;flex-wrap:wrap;background:#fff;border:1px solid #cbd5e1;border-radius:14px;padding:10px;margin:10px 0}.toolbar label,.drawer label{display:grid;gap:4px;color:#475569;font-size:12px;font-weight:800}.toolbar input,.toolbar select,.drawer input,.tools textarea{border:1px solid #cbd5e1;border-radius:9px;padding:8px;background:#fff}.toolbar strong{margin-left:auto;color:#475569}.kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-bottom:10px}.kpis article{background:#fff;border:1px solid #cbd5e1;border-top:5px solid #64748b;border-radius:13px;padding:10px}.kpis article.red{border-top-color:#dc2626}.kpis article.amber{border-top-color:#f59e0b}.kpis article.green{border-top-color:#16a34a}.kpis b{font-size:28px;display:block}.kpis small{color:#64748b}.gridShell{background:#fff;border:1px solid #cbd5e1;border-radius:15px;overflow:auto;max-height:72vh}.grid{display:grid;position:relative}.corner,.areaHead{position:sticky;top:0;z-index:6;background:#0f172a;color:#fff;padding:9px;border-right:1px solid #334155;height:58px}.corner{left:0;z-index:8}.areaHead small{display:block;color:#94a3b8;margin-top:3px}.timeRow{position:sticky;left:0;z-index:4;background:#f8fafc;border-right:1px solid #cbd5e1;border-bottom:1px solid #e2e8f0;padding:6px;font-size:12px;font-weight:900;height:${CELL_HEIGHT}px}.cell{height:${CELL_HEIGHT}px;border-right:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;background:linear-gradient(180deg,#fff,#fbfdff)}.gridBlock{z-index:3;margin:2px;border:1px solid #64748b;border-left:6px solid #64748b;border-radius:9px;padding:6px;text-align:left;overflow:hidden;box-shadow:0 3px 8px rgba(15,23,42,.12);cursor:pointer}.gridBlock.red,.mobileCases button.red{border-left-color:#dc2626;background:#fff1f2}.gridBlock.amber,.mobileCases button.amber{border-left-color:#f59e0b;background:#fffbeb}.gridBlock.green,.mobileCases button.green{border-left-color:#16a34a;background:#f0fdf4}.gridBlock span,.gridBlock b,.gridBlock strong,.gridBlock small,.gridBlock em{display:block}.gridBlock span{font-size:11px;color:#475569}.gridBlock b{font-size:13px}.gridBlock strong{font-size:11px}.gridBlock small,.gridBlock em{font-size:10px;color:#475569}.gridBlock em{color:#991b1b;font-style:normal;font-weight:900}.mobileCases{display:none}.lower{display:grid;grid-template-columns:1.2fr .8fr;gap:10px;margin-top:10px}.panel,.tools{background:#fff;border:1px solid #cbd5e1;border-radius:15px;padding:12px}.panel h2{margin-top:0}.conflict{border-left:6px solid #64748b;border-radius:10px;padding:9px;margin-bottom:8px;background:#f8fafc}.conflict.red{border-left-color:#dc2626;background:#fff1f2}.conflict.amber{border-left-color:#f59e0b;background:#fffbeb}.conflict p{margin:4px 0;color:#334155}.conflict small{display:block;margin-top:4px}.episodes button{display:grid;width:100%;text-align:left;border:1px solid #e2e8f0;background:#f8fafc;border-radius:10px;padding:9px;margin-bottom:7px}.episodes button.active{border-color:#2563eb;background:#eff6ff}.episodes span,.episodes small{color:#64748b}.tools{margin-top:10px}.tools summary{font-weight:900;cursor:pointer}.toolGrid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px}.toolGrid section{border:1px solid #e2e8f0;border-radius:12px;padding:10px}.toolGrid textarea{width:100%;min-height:130px;display:block;margin-bottom:8px;font-family:monospace}.drawer{position:fixed;right:0;top:0;bottom:0;width:min(440px,100vw);overflow:auto;background:#fff;border-left:1px solid #cbd5e1;box-shadow:-18px 0 40px rgba(15,23,42,.2);z-index:30;padding:18px}.drawer .close{position:absolute;right:12px;top:10px;font-size:24px;background:#fff;color:#0f172a}.drawer span{font-size:11px;color:#64748b}.drawer h2{font-size:34px;margin:10px 0 0}.drawer h3{margin:18px 0 6px}.drawer label{margin:8px 0}.drawerActions{display:flex;gap:7px;flex-wrap:wrap}.preview{border:1px solid #f59e0b;background:#fffbeb;border-radius:10px;padding:9px;margin-top:8px}.preview small{display:block;margin:5px 0}@media(max-width:900px){.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.lower{grid-template-columns:1fr}.toolGrid{grid-template-columns:1fr}.gridShell{display:none}.mobileCases{display:grid;gap:7px}.mobileCases button{display:grid;grid-template-columns:60px 1fr;gap:8px;text-align:left;border:1px solid #cbd5e1;border-left:6px solid #64748b;border-radius:12px;padding:10px}.mobileCases time{font-weight:900}.mobileCases b,.mobileCases strong,.mobileCases small{display:block}.mobileCases small{color:#64748b}.hero{display:grid}.toolbar strong{margin-left:0;width:100%}}`;
