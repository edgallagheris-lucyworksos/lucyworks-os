"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson, apiPost } from "@/lib/api";

type Area = {
  areaRef: string;
  name: string;
  areaType: string;
  department: string;
  capacity: number;
  turnoverMinutes: number;
};

type Block = {
  blockRef: string;
  episodeRef?: string;
  patientRef?: string;
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
  version: number;
};

type Episode = {
  episodeRef: string;
  patientRef?: string;
  patientName: string;
  phase: string;
  urgency: string;
  ownerRole: string;
  currentAreaRef?: string;
  nextAction?: string;
  version: number;
};

type Conflict = {
  conflictRef?: string;
  conflictType: string;
  severity: string;
  primaryBlockRef?: string;
  relatedRefs: string[];
  explanation: string;
  options: Array<{ label: string; description: string; score: number }>;
};

type Board = {
  boardVersion: string;
  generatedAt: string;
  operationalDate: string;
  premises: { premisesRef: string; name: string };
  areas: Area[];
  blocks: Block[];
  episodes: Episode[];
  conflicts: Conflict[];
  summary: {
    blocks: number;
    episodes: number;
    redConflicts: number;
    amberConflicts: number;
    unassignedBlocks: number;
    blockedBlocks: number;
    lastChangeId: number;
  };
  liveWindow: { from: string; to: string; blocks: Block[] };
};

type DelayPreview = {
  sourceBlockRef: string;
  minutes: number;
  affected: Array<{
    blockRef: string;
    patientName?: string;
    procedureName: string;
    proposedStartsAt: string;
    expectedVersion: number;
  }>;
};

type Guard = {
  canTransition: boolean;
  blockers: Array<{ code: string; detail: string; ownerRole: string }>;
  warnings: Array<{ code: string; detail: string; ownerRole: string }>;
};

type CommandView = {
  episode: Episode;
  nextTransitions: Record<string, Guard>;
};

type EmergencyOption = {
  optionRef: string;
  areaRef: string;
  areaName: string;
  startsAt: string;
  endsAt: string;
  displacedCount: number;
  totalDisplacementMinutes: number;
  affected: Array<{
    blockRef: string;
    patientName?: string;
    procedureName: string;
    proposedStartsAt: string;
    expectedVersion: number;
  }>;
  warnings: string[];
  score: number;
};

type EmergencyPreview = {
  canInsert: boolean;
  options: EmergencyOption[];
  explanation: string;
};

const PREMISES = "default-premises";
const DAY_START = 7 * 60;
const DAY_END = 22 * 60;
const CELL_HEIGHT = 44;

function today() {
  return new Date().toISOString().slice(0, 10);
}

function localDateTime(offsetMinutes = 0) {
  const value = new Date(Date.now() + offsetMinutes * 60_000);
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function minuteOfDay(value: string) {
  const date = new Date(value);
  return date.getHours() * 60 + date.getMinutes();
}

function timeLabel(minutes: number) {
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
}

function displayTime(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function shiftIso(value: string, minutes: number) {
  return new Date(new Date(value).getTime() + minutes * 60_000).toISOString();
}

function tone(value: string) {
  const normal = value.toLowerCase();
  if (["red", "blocked", "failed", "unavailable", "emergency"].includes(normal)) return "red";
  if (["amber", "planned", "pending", "reduced"].includes(normal)) return "amber";
  return "green";
}

export const masterBoardRoles = [
  "admin",
  "clinician",
  "clinical_director",
  "hospital_director",
  "nurse",
  "ops_manager",
  "senior_clinician",
  "supervisor",
];

export function HospitalMasterBoardV11() {
  const [operationalDate, setOperationalDate] = useState(today());
  const [board, setBoard] = useState<Board | null>(null);
  const [status, setStatus] = useState("Loading canonical board");
  const [areaFilter, setAreaFilter] = useState("all");
  const [selected, setSelected] = useState<Block | null>(null);
  const [selectedEpisode, setSelectedEpisode] = useState<Episode | null>(null);
  const [commandView, setCommandView] = useState<CommandView | null>(null);
  const [delayMinutes, setDelayMinutes] = useState(30);
  const [delayPreview, setDelayPreview] = useState<DelayPreview | null>(null);
  const [leadStaffRef, setLeadStaffRef] = useState("");
  const [leadStaffName, setLeadStaffName] = useState("");
  const [emergencyOpen, setEmergencyOpen] = useState(false);
  const [emergencyPatient, setEmergencyPatient] = useState("");
  const [emergencyProcedure, setEmergencyProcedure] = useState("Emergency procedure");
  const [emergencyEpisode, setEmergencyEpisode] = useState("");
  const [emergencyAreaType, setEmergencyAreaType] = useState("theatre");
  const [emergencyEarliest, setEmergencyEarliest] = useState(localDateTime());
  const [emergencyLatest, setEmergencyLatest] = useState(localDateTime(120));
  const [emergencyDuration, setEmergencyDuration] = useState(90);
  const [emergencyLeadRef, setEmergencyLeadRef] = useState("");
  const [emergencyLeadName, setEmergencyLeadName] = useState("");
  const [emergencyPreview, setEmergencyPreview] = useState<EmergencyPreview | null>(null);
  const [emergencyKey, setEmergencyKey] = useState("");

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<Board>(
        `/api/v11/master-board/day?premises_ref=${PREMISES}&operational_date=${operationalDate}`,
      );
      setBoard(data);
      setSelected((current) =>
        current ? data.blocks.find((item) => item.blockRef === current.blockRef) || null : null,
      );
      setSelectedEpisode((current) =>
        current ? data.episodes.find((item) => item.episodeRef === current.episodeRef) || null : null,
      );
      setStatus("Live server state");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Board unavailable");
    }
  }, [operationalDate]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [refresh]);

  useEffect(() => {
    if (!selectedEpisode) {
      setCommandView(null);
      return;
    }
    apiGet<CommandView>(`/api/v9/episodes/${selectedEpisode.episodeRef}/command-view`)
      .then(setCommandView)
      .catch((error) => setStatus(error instanceof Error ? error.message : "Episode command unavailable"));
  }, [selectedEpisode]);

  const timeRows = useMemo(() => {
    const rows: number[] = [];
    for (let minute = DAY_START; minute <= DAY_END; minute += 15) rows.push(minute);
    return rows;
  }, []);

  const areas = useMemo(() => {
    if (!board) return [];
    const visible = board.areas.filter((area) =>
      ["theatre", "imaging", "prep", "recovery", "ward", "consult"].includes(area.areaType),
    );
    return areaFilter === "all"
      ? visible
      : visible.filter((area) => area.areaType === areaFilter || area.department === areaFilter);
  }, [board, areaFilter]);

  const conflictsByBlock = useMemo(() => {
    const map = new Map<string, Conflict[]>();
    for (const conflict of board?.conflicts || []) {
      const refs = [conflict.primaryBlockRef, ...conflict.relatedRefs].filter(Boolean) as string[];
      for (const ref of refs) map.set(ref, [...(map.get(ref) || []), conflict]);
    }
    return map;
  }, [board]);

  function selectBlock(block: Block) {
    setSelected(block);
    const episode = board?.episodes.find((item) => item.episodeRef === block.episodeRef) || null;
    setSelectedEpisode(episode);
    setLeadStaffRef(block.leadStaffRef || "");
    setLeadStaffName(block.leadStaffName || "");
    setDelayPreview(null);
  }

  async function patchSelected(patch: Record<string, unknown>) {
    if (!selected) return;
    try {
      setStatus("Saving versioned command");
      await apiJson(`/api/hospital-ops/blocks/${selected.blockRef}`, {
        method: "PATCH",
        body: JSON.stringify({ expectedVersion: selected.version, ...patch }),
      });
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Command failed");
      await refresh();
    }
  }

  async function previewDelay() {
    if (!selected) return;
    try {
      const preview = await apiPost<DelayPreview>(
        `/api/hospital-ops/blocks/${selected.blockRef}/delay-preview`,
        { minutes: delayMinutes },
      );
      setDelayPreview(preview);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Delay preview failed");
    }
  }

  async function applyDelay() {
    if (!selected || !delayPreview) return;
    const expectedVersions = Object.fromEntries(
      delayPreview.affected.map((item) => [item.blockRef, item.expectedVersion]),
    );
    try {
      await apiPost(`/api/hospital-ops/blocks/${selected.blockRef}/delay`, {
        minutes: delayMinutes,
        expectedVersions,
        reason: "Live operational delay from master board v11",
        idempotencyKey: crypto.randomUUID(),
      });
      setDelayPreview(null);
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Delay command failed");
      await refresh();
    }
  }

  async function transitionEpisode(targetPhase: string, guard: Guard) {
    if (!selectedEpisode || !guard.canTransition) return;
    try {
      const result = await apiPost<{ ok: boolean; episode?: Episode; guard?: Guard }>(
        `/api/v9/episodes/${selectedEpisode.episodeRef}/transition`,
        {
          expected_version: selectedEpisode.version,
          target_phase: targetPhase,
          idempotency_key: crypto.randomUUID(),
          current_area_ref: selected?.areaRef || selectedEpisode.currentAreaRef,
          reason: `Phase advanced from master board v11 to ${targetPhase}`,
        },
      );
      if (!result.ok) {
        setStatus("Episode transition was blocked by current evidence");
      } else {
        setSelectedEpisode(result.episode || null);
        setStatus(`Episode moved to ${targetPhase.replaceAll("_", " ")}`);
      }
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Episode transition failed");
      await refresh();
    }
  }

  function emergencyPayload() {
    return {
      premisesRef: PREMISES,
      operationalDate,
      episodeRef: emergencyEpisode || undefined,
      patientName: emergencyPatient,
      procedureName: emergencyProcedure,
      areaTypes: [emergencyAreaType],
      earliestStart: new Date(emergencyEarliest).toISOString(),
      latestStart: new Date(emergencyLatest).toISOString(),
      durationMinutes: emergencyDuration,
      turnoverMinutes: 20,
      requiredSkills: emergencyAreaType === "theatre" ? ["surgical", "anaesthesia"] : [],
      equipmentRefs: [],
      leadStaffRef: emergencyLeadRef || undefined,
      leadStaffName: emergencyLeadName || undefined,
      leadStaffRole: emergencyLeadRef ? "clinician" : undefined,
      priority: 100,
      maxDisplacedBlocks: 6,
    };
  }

  async function previewEmergency() {
    if (!emergencyPatient.trim() || !emergencyProcedure.trim()) {
      setStatus("Emergency patient and procedure are required");
      return;
    }
    try {
      const preview = await apiPost<EmergencyPreview>(
        "/api/v11/master-board/emergency/preview",
        emergencyPayload(),
      );
      setEmergencyPreview(preview);
      setEmergencyKey(crypto.randomUUID());
      setStatus(preview.canInsert ? `${preview.options.length} safe insertion options` : "No safe insertion option");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Emergency preview failed");
    }
  }

  async function applyEmergency(option: EmergencyOption) {
    try {
      const expectedVersions = Object.fromEntries(
        option.affected.map((item) => [item.blockRef, item.expectedVersion]),
      );
      await apiPost("/api/v11/master-board/emergency/apply", {
        ...emergencyPayload(),
        areaRef: option.areaRef,
        startsAt: option.startsAt,
        optionRef: option.optionRef,
        expectedVersions,
        reason: "Emergency case inserted by accountable hospital controller",
        idempotencyKey: emergencyKey || crypto.randomUUID(),
      });
      setEmergencyOpen(false);
      setEmergencyPreview(null);
      setEmergencyPatient("");
      setStatus("Emergency inserted and displaced cases moved transactionally");
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Emergency insertion failed");
      await refresh();
    }
  }

  if (!board) return <main className="mbLoading">{status}</main>;

  return (
    <main className="mb">
      <style>{css}</style>
      <header className="hero">
        <div>
          <span>LucyWorks OS · master board v11</span>
          <h1>Hospital day control</h1>
          <p>One 15-minute plan for theatres, imaging, preparation, recovery, wards and consults.</p>
        </div>
        <nav>
          <a href="/episode-command">Episode command</a>
          <a href="/patient-record">Patient record</a>
          <a href="/compliance-safety">Safety</a>
          <button onClick={() => setEmergencyOpen(true)}>Insert emergency</button>
          <button onClick={() => void refresh()}>Refresh</button>
        </nav>
      </header>

      <section className="toolbar">
        <label>
          Operating date
          <input type="date" value={operationalDate} onChange={(event) => setOperationalDate(event.target.value)} />
        </label>
        <label>
          Clinical area
          <select value={areaFilter} onChange={(event) => setAreaFilter(event.target.value)}>
            <option value="all">All clinical areas</option>
            <option value="theatre">Theatres</option>
            <option value="imaging">Imaging</option>
            <option value="prep">Preparation</option>
            <option value="recovery">Recovery</option>
            <option value="ward">Wards and ICU</option>
            <option value="consult">Consults</option>
          </select>
        </label>
        <strong>{status}</strong>
      </section>

      <section className="kpis">
        <article><b>{board.summary.blocks}</b><small>blocks</small></article>
        <article><b>{board.summary.episodes}</b><small>episodes</small></article>
        <article className={board.summary.redConflicts ? "red" : "green"}><b>{board.summary.redConflicts}</b><small>red conflicts</small></article>
        <article className={board.summary.amberConflicts ? "amber" : "green"}><b>{board.summary.amberConflicts}</b><small>amber conflicts</small></article>
        <article className={board.summary.unassignedBlocks ? "amber" : "green"}><b>{board.summary.unassignedBlocks}</b><small>unassigned</small></article>
        <article><b>{board.liveWindow.blocks.length}</b><small>next 90 minutes</small></article>
      </section>

      <section className="liveStrip">
        <strong>Live window</strong>
        {board.liveWindow.blocks.length ? board.liveWindow.blocks.map((block) => (
          <button key={block.blockRef} className={tone(block.riskLevel)} onClick={() => selectBlock(block)}>
            <time>{displayTime(block.startsAt)}</time>
            <span>{block.patientName || "Operational work"}</span>
            <small>{block.procedureName} · {block.areaName}</small>
          </button>
        )) : <p>No blocks in the next 90 minutes.</p>}
      </section>

      <section className="gridShell">
        <div
          className="grid"
          style={{
            gridTemplateColumns: `74px repeat(${areas.length}, minmax(180px, 1fr))`,
            minWidth: `${74 + areas.length * 180}px`,
          }}
        >
          <div className="corner">Time</div>
          {areas.map((area) => (
            <div className="areaHead" key={area.areaRef}>
              <b>{area.name}</b>
              <small>{area.department} · capacity {area.capacity} · turnover {area.turnoverMinutes}m</small>
            </div>
          ))}
          {timeRows.map((minute) => (
            <div
              className="timeRow"
              key={`time-${minute}`}
              style={{ gridColumn: "1", gridRow: `${2 + (minute - DAY_START) / 15}` }}
            >
              {timeLabel(minute)}
            </div>
          ))}
          {areas.flatMap((area, areaIndex) => timeRows.map((minute) => (
            <div
              key={`${area.areaRef}-${minute}`}
              className="cell"
              style={{ gridColumn: `${2 + areaIndex}`, gridRow: `${2 + (minute - DAY_START) / 15}` }}
            />
          )))}
          {board.blocks.filter((block) => areas.some((area) => area.areaRef === block.areaRef)).map((block) => {
            const areaIndex = areas.findIndex((area) => area.areaRef === block.areaRef);
            const start = Math.max(DAY_START, minuteOfDay(block.startsAt));
            const end = Math.min(DAY_END + 15, minuteOfDay(block.endsAt));
            const rowStart = 2 + Math.floor((start - DAY_START) / 15);
            const span = Math.max(1, Math.ceil((end - start) / 15));
            const conflicts = conflictsByBlock.get(block.blockRef) || [];
            const severity = conflicts.some((item) => item.severity === "red")
              ? "red"
              : conflicts.some((item) => item.severity === "amber")
                ? "amber"
                : block.blockType === "emergency" ? "red" : block.riskLevel;
            return (
              <button
                key={block.blockRef}
                className={`gridBlock ${tone(severity)}`}
                style={{ gridColumn: `${2 + areaIndex}`, gridRow: `${rowStart} / span ${span}` }}
                onClick={() => selectBlock(block)}
              >
                <span>{displayTime(block.startsAt)}–{displayTime(block.endsAt)}</span>
                <b>{block.patientName || "Operational work"}</b>
                <strong>{block.procedureName}</strong>
                <small>{block.leadStaffName || "NO LEAD"} · v{block.version}</small>
                {conflicts.length ? <em>{conflicts.length} conflict{conflicts.length === 1 ? "" : "s"}</em> : null}
              </button>
            );
          })}
        </div>
      </section>

      <section className="lower">
        <article className="panel">
          <h2>Explained constraints</h2>
          {board.conflicts.length ? board.conflicts.map((conflict, index) => (
            <div className={`conflict ${tone(conflict.severity)}`} key={conflict.conflictRef || `${conflict.conflictType}-${index}`}>
              <b>{conflict.conflictType.replaceAll("_", " ")}</b>
              <p>{conflict.explanation}</p>
              {conflict.options.slice(0, 3).map((option) => (
                <small key={option.label}><strong>{option.label}</strong> — {option.description}</small>
              ))}
            </div>
          )) : <p>No conflicts detected for this operating date.</p>}
        </article>

        <article className="panel episodes">
          <h2>Canonical episode command</h2>
          {board.episodes.slice(0, 40).map((episode) => (
            <button
              key={episode.episodeRef}
              className={selectedEpisode?.episodeRef === episode.episodeRef ? "active" : ""}
              onClick={() => setSelectedEpisode(episode)}
            >
              <b>{episode.patientName}</b>
              <span>{episode.phase.replaceAll("_", " ")} · {episode.ownerRole} · v{episode.version}</span>
              <small>{episode.nextAction || "No next action recorded"}</small>
            </button>
          ))}
        </article>
      </section>

      {selected ? (
        <aside className="drawer">
          <button className="close" onClick={() => setSelected(null)}>×</button>
          <span>{selected.blockRef}</span>
          <h2>{selected.patientName || "Operational work"}</h2>
          <h3>{selected.procedureName}</h3>
          <p>{selected.areaName} · {displayTime(selected.startsAt)}–{displayTime(selected.endsAt)} · v{selected.version}</p>
          <div className="actions">
            <button onClick={() => void patchSelected({ commandType: "MoveOperationalBlock", startsAt: shiftIso(selected.startsAt, -15), endsAt: shiftIso(selected.endsAt, -15), action: "moved block earlier", reason: "master board v11 move" })}>−15 min</button>
            <button onClick={() => void patchSelected({ commandType: "MoveOperationalBlock", startsAt: shiftIso(selected.startsAt, 15), endsAt: shiftIso(selected.endsAt, 15), action: "moved block later", reason: "master board v11 move" })}>+15 min</button>
          </div>
          <label>Lead staff reference<input value={leadStaffRef} onChange={(event) => setLeadStaffRef(event.target.value)} /></label>
          <label>Lead staff name<input value={leadStaffName} onChange={(event) => setLeadStaffName(event.target.value)} /></label>
          <button onClick={() => void patchSelected({ commandType: "AssignStaff", leadStaffRef, leadStaffName, action: "assigned verified staff reference", reason: "master board v11 assignment" })}>Save assignment</button>

          <h3>Delay propagation</h3>
          <label>Delay minutes<input type="number" min={-720} max={1440} value={delayMinutes} onChange={(event) => setDelayMinutes(Number(event.target.value))} /></label>
          <button onClick={() => void previewDelay()}>Preview consequences</button>
          {delayPreview ? (
            <div className="preview">
              <b>{delayPreview.affected.length} connected blocks affected</b>
              {delayPreview.affected.map((item) => (
                <small key={item.blockRef}>{item.patientName || "Operational work"} · {item.procedureName} → {displayTime(item.proposedStartsAt)}</small>
              ))}
              <button onClick={() => void applyDelay()}>Apply propagated delay</button>
            </div>
          ) : null}

          {selectedEpisode && commandView ? (
            <>
              <h3>Episode phase authority</h3>
              <p>{selectedEpisode.phase.replaceAll("_", " ")} · version {selectedEpisode.version}</p>
              {Object.entries(commandView.nextTransitions).map(([target, guard]) => (
                <div className={`guard ${guard.canTransition ? "green" : "red"}`} key={target}>
                  <b>{target.replaceAll("_", " ")}</b>
                  {guard.blockers.slice(0, 3).map((item) => <small key={item.code}>{item.detail}</small>)}
                  <button disabled={!guard.canTransition} onClick={() => void transitionEpisode(target, guard)}>
                    {guard.canTransition ? "Move episode" : `${guard.blockers.length} blocker${guard.blockers.length === 1 ? "" : "s"}`}
                  </button>
                </div>
              ))}
              <a className="deepLink" href={`/episode-command?episode=${selectedEpisode.episodeRef}`}>Open full episode command →</a>
            </>
          ) : null}
        </aside>
      ) : null}

      {emergencyOpen ? (
        <aside className="emergencyModal">
          <div className="emergencyCard">
            <button className="close" onClick={() => setEmergencyOpen(false)}>×</button>
            <span>Governed emergency insertion</span>
            <h2>Insert emergency case</h2>
            <p>The preview ranks safe options and shows every displaced case before anything is changed.</p>
            <div className="formGrid">
              <label>Patient<input value={emergencyPatient} onChange={(event) => setEmergencyPatient(event.target.value)} /></label>
              <label>Procedure<input value={emergencyProcedure} onChange={(event) => setEmergencyProcedure(event.target.value)} /></label>
              <label>Episode reference<input value={emergencyEpisode} onChange={(event) => setEmergencyEpisode(event.target.value)} /></label>
              <label>Area type<select value={emergencyAreaType} onChange={(event) => setEmergencyAreaType(event.target.value)}><option value="theatre">Theatre</option><option value="imaging">Imaging</option><option value="prep">Preparation</option><option value="recovery">Recovery</option><option value="ward">Ward / ICU</option></select></label>
              <label>Earliest start<input type="datetime-local" value={emergencyEarliest} onChange={(event) => setEmergencyEarliest(event.target.value)} /></label>
              <label>Latest start<input type="datetime-local" value={emergencyLatest} onChange={(event) => setEmergencyLatest(event.target.value)} /></label>
              <label>Duration minutes<input type="number" min={15} max={720} step={15} value={emergencyDuration} onChange={(event) => setEmergencyDuration(Number(event.target.value))} /></label>
              <label>Lead reference<input value={emergencyLeadRef} onChange={(event) => setEmergencyLeadRef(event.target.value)} /></label>
              <label>Lead name<input value={emergencyLeadName} onChange={(event) => setEmergencyLeadName(event.target.value)} /></label>
            </div>
            <button className="primary" onClick={() => void previewEmergency()}>Preview safe options</button>
            {emergencyPreview ? (
              <section className="options">
                <p>{emergencyPreview.explanation}</p>
                {emergencyPreview.options.length ? emergencyPreview.options.slice(0, 8).map((option, index) => (
                  <article key={option.optionRef}>
                    <div>
                      <b>Option {index + 1}: {option.areaName}</b>
                      <span>{displayTime(option.startsAt)}–{displayTime(option.endsAt)}</span>
                      <small>{option.displacedCount} displaced · {option.totalDisplacementMinutes} total delay minutes</small>
                      {option.affected.map((item) => <small key={item.blockRef}>{item.patientName || "Operational work"} → {displayTime(item.proposedStartsAt)}</small>)}
                      {option.warnings.map((warning) => <em key={warning}>{warning}</em>)}
                    </div>
                    <button onClick={() => void applyEmergency(option)}>Apply this plan</button>
                  </article>
                )) : <strong>No safe option is available inside the requested window.</strong>}
              </section>
            ) : null}
          </div>
        </aside>
      ) : null}
    </main>
  );
}

const css = `
.mbLoading{min-height:100vh;display:grid;place-items:center;background:#071019;color:#e2e8f0;font:700 18px system-ui}.mb{min-height:100vh;background:#e9eef5;color:#0f172a;padding:10px;font-family:Inter,system-ui,sans-serif}.mb *{box-sizing:border-box}.hero{display:flex;justify-content:space-between;gap:16px;background:#071019;color:#f8fafc;border-radius:18px;padding:17px}.hero span,.emergencyCard>span{color:#2dd4bf;font-size:11px;font-weight:900;letter-spacing:.13em;text-transform:uppercase}.hero h1{font-size:clamp(36px,7vw,70px);line-height:.92;margin:7px 0}.hero p{color:#94a3b8;margin:5px 0}.hero nav{display:flex;gap:7px;flex-wrap:wrap;align-content:flex-start}.hero a,.hero button,.drawer button,.emergencyCard button{border:1px solid #334155;border-radius:999px;background:#0f172a;color:#fff;padding:9px 12px;text-decoration:none;font-weight:800;cursor:pointer}.toolbar{display:flex;gap:10px;align-items:end;flex-wrap:wrap;background:#fff;border:1px solid #cbd5e1;border-radius:14px;padding:10px;margin:10px 0}.toolbar label,.drawer label,.formGrid label{display:grid;gap:4px;color:#475569;font-size:12px;font-weight:800}.toolbar input,.toolbar select,.drawer input,.formGrid input,.formGrid select{border:1px solid #cbd5e1;border-radius:9px;padding:8px;background:#fff}.toolbar strong{margin-left:auto;color:#475569}.kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.kpis article{background:#fff;border:1px solid #cbd5e1;border-top:5px solid #64748b;border-radius:13px;padding:10px}.kpis article.red{border-top-color:#dc2626}.kpis article.amber{border-top-color:#f59e0b}.kpis article.green{border-top-color:#16a34a}.kpis b{font-size:28px;display:block}.kpis small{color:#64748b}.liveStrip{display:flex;gap:8px;align-items:stretch;overflow:auto;padding:9px 0}.liveStrip>strong{display:grid;place-items:center;background:#0f172a;color:#fff;border-radius:10px;padding:10px;min-width:88px}.liveStrip button{display:grid;gap:2px;min-width:180px;text-align:left;border:1px solid #cbd5e1;border-left:6px solid #64748b;border-radius:10px;padding:8px;background:#fff}.liveStrip button.red{border-left-color:#dc2626}.liveStrip button.amber{border-left-color:#f59e0b}.liveStrip button.green{border-left-color:#16a34a}.liveStrip time{font-weight:900}.liveStrip small{color:#64748b}.gridShell{background:#fff;border:1px solid #cbd5e1;border-radius:15px;overflow:auto;max-height:70vh}.grid{display:grid;position:relative}.corner,.areaHead{position:sticky;top:0;z-index:6;background:#0f172a;color:#fff;padding:9px;border-right:1px solid #334155;height:58px}.corner{left:0;z-index:8}.areaHead small{display:block;color:#94a3b8;margin-top:3px}.timeRow{position:sticky;left:0;z-index:4;background:#f8fafc;border-right:1px solid #cbd5e1;border-bottom:1px solid #e2e8f0;padding:6px;font-size:12px;font-weight:900;height:${CELL_HEIGHT}px}.cell{height:${CELL_HEIGHT}px;border-right:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;background:linear-gradient(180deg,#fff,#fbfdff)}.gridBlock{z-index:3;margin:2px;border:1px solid #64748b;border-left:6px solid #64748b;border-radius:9px;padding:6px;text-align:left;overflow:hidden;box-shadow:0 3px 8px rgba(15,23,42,.12);cursor:pointer}.gridBlock.red{border-left-color:#dc2626;background:#fff1f2}.gridBlock.amber{border-left-color:#f59e0b;background:#fffbeb}.gridBlock.green{border-left-color:#16a34a;background:#f0fdf4}.gridBlock span,.gridBlock b,.gridBlock strong,.gridBlock small,.gridBlock em{display:block}.gridBlock span{font-size:11px;color:#475569}.gridBlock b{font-size:13px}.gridBlock strong{font-size:11px}.gridBlock small,.gridBlock em{font-size:10px;color:#475569}.gridBlock em{color:#991b1b;font-style:normal;font-weight:900}.lower{display:grid;grid-template-columns:1.2fr .8fr;gap:10px;margin-top:10px}.panel{background:#fff;border:1px solid #cbd5e1;border-radius:15px;padding:12px}.panel h2{margin-top:0}.conflict{border-left:6px solid #64748b;border-radius:10px;padding:9px;margin-bottom:8px;background:#f8fafc}.conflict.red{border-left-color:#dc2626;background:#fff1f2}.conflict.amber{border-left-color:#f59e0b;background:#fffbeb}.conflict p{margin:4px 0;color:#334155}.conflict small{display:block;margin-top:4px}.episodes button{display:grid;width:100%;text-align:left;border:1px solid #e2e8f0;background:#f8fafc;border-radius:10px;padding:9px;margin-bottom:7px}.episodes button.active{border-color:#2563eb;background:#eff6ff}.episodes span,.episodes small{color:#64748b}.drawer{position:fixed;right:0;top:0;bottom:0;width:min(440px,100vw);z-index:30;background:#fff;border-left:1px solid #cbd5e1;box-shadow:-20px 0 50px rgba(15,23,42,.18);padding:20px;overflow:auto}.close{position:absolute;right:12px;top:12px;width:38px;height:38px;padding:0!important;font-size:24px}.drawer>span{font-size:11px;color:#64748b}.drawer h2{font-size:32px;margin:8px 0}.drawer h3{margin:20px 0 7px}.actions{display:flex;gap:8px}.drawer label{margin:9px 0}.preview,.guard{display:grid;gap:6px;border:1px solid #cbd5e1;border-radius:11px;padding:10px;margin-top:8px}.preview small,.guard small{display:block;color:#475569}.guard.red{border-color:#fecaca;background:#fff1f2}.guard.green{border-color:#bbf7d0;background:#f0fdf4}.guard button:disabled{opacity:.45;cursor:not-allowed}.deepLink{display:block;margin-top:14px;color:#1d4ed8;font-weight:900}.emergencyModal{position:fixed;inset:0;z-index:50;background:rgba(2,6,23,.72);display:grid;place-items:center;padding:12px}.emergencyCard{position:relative;width:min(980px,100%);max-height:94vh;overflow:auto;background:#fff;border-radius:20px;padding:20px}.emergencyCard h2{font-size:36px;margin:7px 0}.emergencyCard p{color:#475569}.formGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.emergencyCard .primary{margin:14px 0;background:#b91c1c;border-color:#b91c1c}.options{display:grid;gap:9px}.options article{display:flex;justify-content:space-between;gap:12px;border:1px solid #cbd5e1;border-left:6px solid #dc2626;border-radius:12px;padding:12px}.options article div{display:grid;gap:3px}.options article span,.options article small,.options article em{display:block}.options article small{color:#475569}.options article em{color:#92400e;font-style:normal;font-weight:800}.options article button{align-self:center;white-space:nowrap}.red{--tone:#dc2626}.amber{--tone:#f59e0b}.green{--tone:#16a34a}@media(max-width:900px){.hero{display:grid}.kpis{grid-template-columns:repeat(3,1fr)}.lower{grid-template-columns:1fr}.formGrid{grid-template-columns:1fr 1fr}}@media(max-width:600px){.mb{padding:6px}.kpis{grid-template-columns:repeat(2,1fr)}.hero h1{font-size:44px}.formGrid{grid-template-columns:1fr}.options article{display:grid}.gridShell{max-height:64vh}}
`;
