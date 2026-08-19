"use client";

import { useMemo, useState } from "react";
import { apiJson } from "@/lib/api";

export type CoordinationHandover = {
  id: number;
  handoverRef: string;
  episodeRef: string;
  fromActor: string;
  fromRole: string;
  toActor?: string;
  toRole: string;
  status: string;
  summary: string;
  clinicalRisks: string[];
  outstandingActions: (string | Record<string, unknown>)[];
  dueAt?: string;
};

export type CoordinationCriticalResult = {
  id: number;
  resultRef: string;
  episodeRef: string;
  resultType: string;
  severity: string;
  summary: string;
  status: string;
  assignedTo: string;
  assignedRole: string;
  dueAt?: string;
  actionTaken?: string;
};

export type CoordinationDiagnostic = {
  workRef: string;
  episodeRef: string;
  modality: string;
  requestedTest: string;
  urgency: string;
  status: string;
  assignedService?: string;
  reportSummary?: string;
  criticalResult: boolean;
  version: number;
};

export type CoordinationTask = {
  taskRef: string;
  episodeRef: string;
  title: string;
  status: string;
  dueAt: string;
  priority: string;
  assignedRole: string;
  version: number;
};

export type CoordinationObservation = {
  observationRef: string;
  episodeRef: string;
  type: string;
  concernLevel: string;
  escalationStatus: string;
  recordedAt: string;
};

export type Coordination = {
  generatedAt: string;
  handovers: CoordinationHandover[];
  criticalResults: CoordinationCriticalResult[];
  diagnostics: CoordinationDiagnostic[];
  tasks: CoordinationTask[];
  observations: CoordinationObservation[];
  summary: { pendingHandovers: number; unacknowledgedCriticalResults: number; overdueTasks: number; redObservations: number };
};

type Episode = {
  episodeRef: string;
  patientName: string;
  phase: string;
  ownerRole: string;
  ownerSubject?: string;
  currentAreaRef?: string;
  nextAction?: string;
  version: number;
};

type Area = { areaRef: string; name: string };

function readable(value: string) {
  return value.replaceAll("_", " ");
}

function when(value?: string) {
  return value ? new Date(value).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "not timed";
}

export function HospitalPatientCoordination({
  episode,
  areas,
  coordination,
  premisesRef,
  onClose,
  onChanged,
}: {
  episode: Episode;
  areas: Area[];
  coordination: Coordination;
  premisesRef: string;
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const [ownerRole, setOwnerRole] = useState(episode.ownerRole || "");
  const [areaRef, setAreaRef] = useState(episode.currentAreaRef || "");
  const [nextAction, setNextAction] = useState(episode.nextAction || "");
  const [reason, setReason] = useState("");
  const [toRole, setToRole] = useState("nurse");
  const [toActor, setToActor] = useState("");
  const [handoverSummary, setHandoverSummary] = useState("");
  const [risks, setRisks] = useState("");
  const [outstanding, setOutstanding] = useState("");
  const [criticalActions, setCriticalActions] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");

  const handovers = useMemo(() => coordination.handovers.filter((item) => item.episodeRef === episode.episodeRef), [coordination.handovers, episode.episodeRef]);
  const criticalResults = useMemo(() => coordination.criticalResults.filter((item) => item.episodeRef === episode.episodeRef), [coordination.criticalResults, episode.episodeRef]);
  const diagnostics = useMemo(() => coordination.diagnostics.filter((item) => item.episodeRef === episode.episodeRef), [coordination.diagnostics, episode.episodeRef]);
  const tasks = useMemo(() => coordination.tasks.filter((item) => item.episodeRef === episode.episodeRef && item.status !== "completed"), [coordination.tasks, episode.episodeRef]);
  const observations = useMemo(() => coordination.observations.filter((item) => item.episodeRef === episode.episodeRef && (item.concernLevel === "red" || item.escalationStatus === "pending")), [coordination.observations, episode.episodeRef]);

  async function run(label: string, action: () => Promise<unknown>) {
    setBusy(label);
    setNotice("");
    try {
      await action();
      await onChanged();
      setNotice("Saved to the authenticated hospital record.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "The update could not be completed.");
    } finally {
      setBusy("");
    }
  }

  async function saveOperational() {
    await run("operational", () => apiJson(`/api/v11/master-board/episodes/${encodeURIComponent(episode.episodeRef)}/operational`, {
      method: "PATCH",
      body: JSON.stringify({
        premisesRef,
        expectedVersion: episode.version,
        ownerRole,
        currentAreaRef: areaRef,
        nextAction,
        reason: reason || "patient flow coordination update",
        idempotencyKey: crypto.randomUUID(),
      }),
    }));
  }

  async function createHandover() {
    await run("handover", async () => {
      await apiJson(`/api/v11/master-board/episodes/${encodeURIComponent(episode.episodeRef)}/handovers`, {
        method: "POST",
        body: JSON.stringify({
          premisesRef,
          toRole,
          toActor: toActor || undefined,
          summary: handoverSummary,
          clinicalRisks: risks.split("\n").map((item) => item.trim()).filter(Boolean),
          outstandingActions: outstanding.split("\n").map((item) => item.trim()).filter(Boolean),
          idempotencyKey: crypto.randomUUID(),
        }),
      });
      setHandoverSummary("");
      setRisks("");
      setOutstanding("");
    });
  }

  async function decideHandover(id: number, decision: "accepted" | "escalated") {
    await run(`handover-${id}`, () => apiJson(`/api/v11/master-board/handovers/${id}/decision`, {
      method: "PATCH",
      body: JSON.stringify({ premisesRef, decision, note: decision === "accepted" ? "Responsibility accepted in patient flow" : "Escalated from patient flow" }),
    }));
  }

  async function acknowledgeResult(id: number) {
    const actionTaken = (criticalActions[id] || "").trim();
    if (!actionTaken) {
      setNotice("Record the clinical action before acknowledging a critical result.");
      return;
    }
    await run(`result-${id}`, () => apiJson(`/api/v11/master-board/critical-results/${id}/acknowledge`, {
      method: "PATCH",
      body: JSON.stringify({ premisesRef, actionTaken, note: "Acknowledged from hospital patient flow" }),
    }));
  }

  return <div className="coordinationBackdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="coordinationDrawer" role="dialog" aria-modal="true" aria-labelledby="coordination-title">
      <style>{css}</style>
      <header>
        <div><span>Patient coordination</span><h2 id="coordination-title">{episode.patientName}</h2><p>{episode.episodeRef} · {readable(episode.phase)} · version {episode.version}</p></div>
        <button type="button" onClick={onClose} aria-label="Close patient coordination">Close</button>
      </header>

      {notice ? <p className={notice.startsWith("Saved") ? "notice saved" : "notice error"}>{notice}</p> : null}

      <section>
        <h3>Owner, location and next action</h3>
        <div className="formGrid">
          <label><span>Accountable role</span><input value={ownerRole} onChange={(event) => setOwnerRole(event.target.value)} /></label>
          <label><span>Current location</span><select value={areaRef} onChange={(event) => setAreaRef(event.target.value)}><option value="">Not recorded</option>{areas.map((area) => <option value={area.areaRef} key={area.areaRef}>{area.name}</option>)}</select></label>
          <label className="wide"><span>Next action</span><input value={nextAction} onChange={(event) => setNextAction(event.target.value)} /></label>
          <label className="wide"><span>Reason</span><input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Why this coordination record changed" /></label>
        </div>
        <button className="primary" type="button" disabled={Boolean(busy) || !ownerRole.trim() || !nextAction.trim()} onClick={() => void saveOperational()}>{busy === "operational" ? "Saving…" : "Save coordination"}</button>
      </section>

      <section>
        <h3>Create accountable handover</h3>
        <div className="formGrid">
          <label><span>Receiving role</span><input value={toRole} onChange={(event) => setToRole(event.target.value)} /></label>
          <label><span>Named recipient (optional)</span><input value={toActor} onChange={(event) => setToActor(event.target.value)} /></label>
          <label className="wide"><span>Situation and responsibility</span><textarea value={handoverSummary} onChange={(event) => setHandoverSummary(event.target.value)} /></label>
          <label><span>Clinical risks, one per line</span><textarea value={risks} onChange={(event) => setRisks(event.target.value)} /></label>
          <label><span>Outstanding actions, one per line</span><textarea value={outstanding} onChange={(event) => setOutstanding(event.target.value)} /></label>
        </div>
        <button className="primary" type="button" disabled={Boolean(busy) || !toRole.trim() || !handoverSummary.trim()} onClick={() => void createHandover()}>{busy === "handover" ? "Creating…" : "Create handover"}</button>
        <div className="records">
          {handovers.map((item) => <article key={item.handoverRef} className={item.status === "pending" ? "attention" : ""}>
            <div><b>{item.summary}</b><small>{item.fromActor} → {item.toActor || readable(item.toRole)} · {item.status} · {when(item.dueAt)}</small></div>
            {item.status === "pending" ? <div className="recordActions"><button disabled={Boolean(busy)} onClick={() => void decideHandover(item.id, "accepted")}>Accept</button><button disabled={Boolean(busy)} onClick={() => void decideHandover(item.id, "escalated")}>Escalate</button></div> : null}
          </article>)}
          {!handovers.length ? <p className="empty">No handover recorded for this episode.</p> : null}
        </div>
      </section>

      <section>
        <h3>Ward / ICU care</h3>
        <div className="records">
          {observations.map((item) => <article className="critical" key={item.observationRef}><div><b>{readable(item.type)} · {item.concernLevel}</b><small>Escalation {readable(item.escalationStatus)} · {when(item.recordedAt)}</small></div></article>)}
          {tasks.map((item) => <article className={new Date(item.dueAt).getTime() < Date.now() ? "attention" : ""} key={item.taskRef}><div><b>{item.title}</b><small>{readable(item.assignedRole)} · {item.status} · due {when(item.dueAt)}</small></div></article>)}
          {!observations.length && !tasks.length ? <p className="empty">No open care tasks or escalated observations.</p> : null}
        </div>
      </section>

      <section>
        <h3>Diagnostics and critical results</h3>
        <div className="records">
          {diagnostics.map((item) => <article className={item.criticalResult ? "critical" : ""} key={item.workRef}><div><b>{readable(item.modality)} · {item.requestedTest}</b><small>{item.status} · {item.assignedService || "service unassigned"}{item.reportSummary ? ` · ${item.reportSummary}` : ""}</small></div></article>)}
          {criticalResults.map((item) => <article className={item.status === "awaiting_acknowledgement" ? "critical result" : "result"} key={item.resultRef}>
            <div><b>{item.resultType} · {item.summary}</b><small>{item.status} · {item.assignedTo} · due {when(item.dueAt)}</small></div>
            {item.status === "awaiting_acknowledgement" ? <div className="acknowledge"><input aria-label={`Action taken for ${item.resultType}`} value={criticalActions[item.id] || ""} onChange={(event) => setCriticalActions((current) => ({ ...current, [item.id]: event.target.value }))} placeholder="Clinical action taken" /><button disabled={Boolean(busy)} onClick={() => void acknowledgeResult(item.id)}>Acknowledge</button></div> : null}
          </article>)}
          {!diagnostics.length && !criticalResults.length ? <p className="empty">No diagnostic work or critical results recorded.</p> : null}
        </div>
      </section>
    </aside>
  </div>;
}

const css = `
.coordinationBackdrop{position:fixed;inset:0;z-index:80;display:flex;justify-content:flex-end;background:rgba(15,31,45,.46);backdrop-filter:blur(2px)}.coordinationDrawer{width:min(660px,96vw);height:100%;overflow:auto;background:#f3f6f8;color:#1c3144;box-shadow:-18px 0 45px rgba(12,28,42,.2);padding:12px}.coordinationDrawer>header{position:sticky;top:-12px;z-index:3;display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin:-12px -12px 10px;padding:13px 14px;background:#fff;border-bottom:1px solid #d5dee6}.coordinationDrawer>header span{font-size:8px;font-weight:850;text-transform:uppercase;letter-spacing:.08em;color:#55758d}.coordinationDrawer>header h2{margin:2px 0 0;font-size:20px}.coordinationDrawer>header p{margin:3px 0 0;color:#738294;font-size:9px}.coordinationDrawer button{min-height:30px;padding:5px 8px;border:1px solid #c9d5df;border-radius:6px;background:#fff;color:#294a64;font-size:9px;font-weight:800;cursor:pointer}.coordinationDrawer button.primary{margin-top:8px;background:#173f5f;border-color:#173f5f;color:#fff}.coordinationDrawer button:disabled{opacity:.5;cursor:not-allowed}.coordinationDrawer section{margin-bottom:9px;padding:10px;background:#fff;border:1px solid #d7e0e8;border-radius:9px}.coordinationDrawer h3{margin:0 0 8px;color:#1a3b55;font-size:12px}.formGrid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.formGrid label{display:grid;gap:3px}.formGrid label.wide{grid-column:1/-1}.formGrid label>span{font-size:8px;font-weight:800;text-transform:uppercase;color:#6a7c8c}.formGrid input,.formGrid select,.formGrid textarea,.acknowledge input{width:100%;min-height:32px;padding:6px 7px;border:1px solid #c9d5df;border-radius:5px;background:#fff;color:#1c3144;font:inherit;font-size:10px}.formGrid textarea{min-height:58px;resize:vertical}.notice{margin:0 0 9px;padding:8px 10px;border-radius:7px;font-size:9px}.notice.saved{background:#e3f2ea;color:#28674d}.notice.error{background:#f8dedd;color:#932e2b}.records{display:grid;gap:5px;margin-top:8px}.records article{display:flex;justify-content:space-between;gap:8px;padding:8px;border:1px solid #e0e7ed;border-left:3px solid #64859d;border-radius:6px}.records article.attention{border-left-color:#c77c14}.records article.critical{border-left-color:#b63c38;background:#fffafa}.records b{display:block;font-size:9px}.records small{display:block;margin-top:2px;color:#748394;font-size:8px;line-height:1.3}.recordActions{display:flex;gap:4px;align-items:center}.acknowledge{display:grid;grid-template-columns:minmax(150px,1fr) auto;gap:5px;min-width:280px}.empty{margin:4px;color:#728294;font-size:9px}
@media(max-width:560px){.coordinationDrawer{width:100vw}.formGrid{grid-template-columns:1fr}.formGrid label.wide{grid-column:auto}.records article{display:grid}.acknowledge{min-width:0;grid-template-columns:1fr}.recordActions{justify-content:flex-start}}
`;
