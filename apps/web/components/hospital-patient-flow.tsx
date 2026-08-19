"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { HospitalPatientCoordination, type Coordination } from "@/components/hospital-patient-coordination";
import { apiGet } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";
import { useOperationalContext } from "@/lib/operational-context";

type Area = { areaRef: string; name: string; department: string; areaType: string };
type Block = { blockRef: string; episodeRef?: string; procedureName: string; areaRef: string; areaName: string; startsAt: string; endsAt: string; status: string; riskLevel: string; leadStaffName?: string; leadStaffRole?: string; blockers: unknown[] };
type Episode = { episodeRef: string; patientRef?: string; patientName: string; phase: string; urgency: string; ownerRole: string; ownerSubject?: string; currentAreaRef?: string; nextAction?: string; status?: string; version: number };
type Conflict = { conflictRef?: string; conflictType: string; severity: string; primaryBlockRef?: string; relatedRefs: string[]; explanation: string };
type Board = { generatedAt: string; premises: { name: string }; areas: Area[]; blocks: Block[]; episodes: Episode[]; conflicts: Conflict[] };

type PatientRow = {
  episode: Episode;
  areaName: string;
  current?: Block;
  next?: Block;
  conflicts: Conflict[];
  handovers: Coordination["handovers"];
  criticalResults: Coordination["criticalResults"];
  diagnostics: Coordination["diagnostics"];
  tasks: Coordination["tasks"];
  observations: Coordination["observations"];
  blocked: boolean;
  risk: "red" | "amber" | "green";
};

const CLOSED = new Set(["closed", "discharged", "cancelled"]);
const RANK = { red: 0, amber: 1, green: 2 };

function displayTime(value?: string) {
  return value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";
}

function normalRisk(value: string): "red" | "amber" | "green" {
  const risk = value.toLowerCase();
  return risk === "red" ? "red" : risk === "amber" ? "amber" : "green";
}

export function HospitalPatientFlow({ onOpenResourceGrid }: { onOpenResourceGrid: () => void }) {
  const { premisesRef, siteName } = useOperationalContext();
  const [board, setBoard] = useState<Board | null>(null);
  const [coordination, setCoordination] = useState<Coordination | null>(null);
  const [selectedEpisodeRef, setSelectedEpisodeRef] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [urgency, setUrgency] = useState("all");
  const [area, setArea] = useState("all");
  const [blockedOnly, setBlockedOnly] = useState(false);
  const [status, setStatus] = useState("Loading patient flow");
  const operationalDate = localOperationalDate();

  const refresh = useCallback(async () => {
    try {
      const [data, coordinationData] = await Promise.all([
        apiGet<Board>(`/api/v11/master-board/day?premises_ref=${encodeURIComponent(premisesRef)}&operational_date=${operationalDate}`),
        apiGet<Coordination>(`/api/v11/master-board/coordination?premises_ref=${encodeURIComponent(premisesRef)}`),
      ]);
      setBoard(data);
      setCoordination(coordinationData);
      setStatus("Live");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Patient flow unavailable");
    }
  }, [operationalDate, premisesRef]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const rows = useMemo<PatientRow[]>(() => {
    if (!board || !coordination) return [];
    const now = Date.now();
    const areaNames = new Map(board.areas.map((item) => [item.areaRef, item.name]));
    return board.episodes
      .filter((episode) => !CLOSED.has((episode.status || "").toLowerCase()))
      .map((episode) => {
        const work = board.blocks.filter((block) => block.episodeRef === episode.episodeRef).sort((a, b) => a.startsAt.localeCompare(b.startsAt));
        const current = work.find((block) => new Date(block.startsAt).getTime() <= now && new Date(block.endsAt).getTime() >= now)
          || work.find((block) => new Date(block.endsAt).getTime() >= now)
          || work[work.length - 1];
        const next = work.find((block) => current && block.startsAt > current.startsAt) || current;
        const blockRefs = new Set(work.map((block) => block.blockRef));
        const conflicts = board.conflicts.filter((conflict) => Boolean(conflict.primaryBlockRef && blockRefs.has(conflict.primaryBlockRef)) || conflict.relatedRefs.some((ref) => blockRefs.has(ref)));
        const handovers = coordination.handovers.filter((item) => item.episodeRef === episode.episodeRef);
        const criticalResults = coordination.criticalResults.filter((item) => item.episodeRef === episode.episodeRef);
        const diagnostics = coordination.diagnostics.filter((item) => item.episodeRef === episode.episodeRef);
        const tasks = coordination.tasks.filter((item) => item.episodeRef === episode.episodeRef && item.status !== "completed");
        const observations = coordination.observations.filter((item) => item.episodeRef === episode.episodeRef && (item.concernLevel === "red" || item.escalationStatus === "pending"));
        const overdueCare = tasks.some((item) => new Date(item.dueAt).getTime() < now);
        const redCoordination = criticalResults.some((item) => item.status === "awaiting_acknowledgement") || observations.some((item) => item.concernLevel === "red");
        const amberCoordination = handovers.some((item) => item.status === "pending") || overdueCare;
        const blocked = Boolean(current && (current.status.toLowerCase() === "blocked" || current.blockers.length)) || conflicts.length > 0;
        const risk = redCoordination || conflicts.some((conflict) => conflict.severity.toLowerCase() === "red")
          ? "red"
          : amberCoordination ? "amber" : current ? normalRisk(current.riskLevel) : episode.urgency.toLowerCase() === "urgent" ? "amber" : "green";
        return { episode, areaName: areaNames.get(episode.currentAreaRef || "") || current?.areaName || "Location not recorded", current, next, conflicts, handovers, criticalResults, diagnostics, tasks, observations, blocked, risk };
      });
  }, [board, coordination]);

  const visible = useMemo(() => rows.filter((row) => {
    if (urgency !== "all" && row.episode.urgency.toLowerCase() !== urgency) return false;
    if (area !== "all" && (row.episode.currentAreaRef || row.current?.areaRef) !== area) return false;
    if (blockedOnly && !row.blocked) return false;
    const needle = query.trim().toLowerCase();
    if (!needle) return true;
    return [row.episode.patientName, row.episode.patientRef, row.episode.episodeRef, row.episode.phase, row.episode.ownerRole, row.areaName, row.current?.procedureName, row.next?.procedureName]
      .some((value) => String(value || "").toLowerCase().includes(needle));
  }).sort((left, right) => RANK[left.risk] - RANK[right.risk] || left.episode.patientName.localeCompare(right.episode.patientName)), [area, blockedOnly, query, rows, urgency]);

  const selected = rows.find((row) => row.episode.episodeRef === selectedEpisodeRef);

  if (!board || !coordination) return <section className="patientFlow loading"><style>{css}</style><b>{siteName}</b><span>{status}</span><button onClick={() => void refresh()}>Retry</button></section>;

  return <main className="patientFlow">
    <style>{css}</style>
    <header className="flowTitle">
      <div><span>Canonical patient flow</span><h2>Active patients</h2><p>One row per episode with governed owner, location, next action, handover, ward/ICU care and diagnostic status.</p></div>
      <div className="titleActions"><span className={status === "Live" ? "live" : "warning"}>{status}</span><button onClick={() => void refresh()}>Refresh</button><button onClick={onOpenResourceGrid}>Resource grid</button></div>
    </header>

    <section className="flowSummary">
      <article><b>{rows.length}</b><span>active patients</span></article>
      <article className={rows.some((row) => row.risk === "red") ? "critical" : ""}><b>{rows.filter((row) => row.risk === "red").length}</b><span>red priority</span></article>
      <article className={rows.some((row) => row.blocked) ? "warning" : ""}><b>{rows.filter((row) => row.blocked).length}</b><span>blocked</span></article>
      <article><b>{rows.filter((row) => !row.current?.leadStaffName && !row.current?.leadStaffRole && !row.episode.ownerRole).length}</b><span>unowned</span></article>
      <article><b>{visible.length}</b><span>shown</span></article>
    </section>

    <section className="flowFilters">
      <label><span>Find patient or work</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name, episode, owner, procedure or location" /></label>
      <label><span>Urgency</span><select value={urgency} onChange={(event) => setUrgency(event.target.value)}><option value="all">All urgency</option><option value="emergency">Emergency</option><option value="urgent">Urgent</option><option value="routine">Routine</option></select></label>
      <label><span>Location</span><select value={area} onChange={(event) => setArea(event.target.value)}><option value="all">All locations</option>{board.areas.map((item) => <option value={item.areaRef} key={item.areaRef}>{item.name}</option>)}</select></label>
      <label className="check"><input type="checkbox" checked={blockedOnly} onChange={(event) => setBlockedOnly(event.target.checked)} /><span>Blocked only</span></label>
    </section>

    <section className="flowTableWrap">
      <table>
        <thead><tr><th>Priority</th><th>Patient / episode</th><th>Current stage</th><th>Location</th><th>Accountable owner</th><th>Next timed work</th><th>Care / handover</th><th>Diagnostics</th><th>Blocker / conflict</th><th></th></tr></thead>
        <tbody>{visible.map((row) => <tr key={row.episode.episodeRef} data-risk={row.risk}>
          <td><span className={`risk ${row.risk}`}>{row.risk}</span><small>{row.episode.urgency}</small></td>
          <td><b>{row.episode.patientName}</b><small>{row.episode.episodeRef} · {row.episode.patientRef || "patient ref unavailable"}</small></td>
          <td><b>{row.episode.phase.replaceAll("_", " ")}</b><small>{row.current?.procedureName || "No scheduled block"}</small></td>
          <td><b>{row.areaName}</b><small>{row.current ? `${displayTime(row.current.startsAt)}–${displayTime(row.current.endsAt)}` : "time not scheduled"}</small></td>
          <td><b>{row.current?.leadStaffName || row.current?.leadStaffRole || row.episode.ownerRole || "Unowned"}</b><small>accountable now</small></td>
          <td><b>{row.next?.procedureName || row.episode.nextAction || "Next action not recorded"}</b><small>{row.next ? `${displayTime(row.next.startsAt)} · ${row.next.areaName}` : "untimed"}</small></td>
          <td className={row.observations.some((item) => item.concernLevel === "red") ? "blocked" : ""}><b>{row.handovers.filter((item) => item.status === "pending").length} pending handover</b><small>{row.tasks.filter((item) => item.status !== "completed" && new Date(item.dueAt).getTime() < Date.now()).length} overdue care · {row.observations.length} escalated observation</small></td>
          <td className={row.criticalResults.some((item) => item.status === "awaiting_acknowledgement") ? "blocked" : ""}><b>{row.criticalResults.filter((item) => item.status === "awaiting_acknowledgement").length} critical result</b><small>{row.diagnostics.length ? `${row.diagnostics.length} item · ${row.diagnostics[0].status}` : "No diagnostic work"}</small></td>
          <td className={row.blocked ? "blocked" : ""}><b>{row.conflicts[0]?.conflictType || (row.blocked ? "Operational blocker" : "Clear")}</b><small>{row.conflicts[0]?.explanation || row.episode.nextAction || "No active conflict"}</small></td>
          <td><div className="rowActions"><button type="button" onClick={() => setSelectedEpisodeRef(row.episode.episodeRef)}>Manage</button><Link aria-label={`Open patient record for ${row.episode.patientName}`} href={`/patient-record?episode=${encodeURIComponent(row.episode.episodeRef)}`}>Record</Link></div></td>
        </tr>)}</tbody>
      </table>
      {!visible.length ? <p className="empty">No active patients match the current filters.</p> : null}
    </section>

    <footer><span>Generated {new Date(board.generatedAt).toLocaleString()}</span><b>Source: authenticated v11 master board and coordination projection</b></footer>
    {selected ? <HospitalPatientCoordination episode={selected.episode} areas={board.areas} coordination={coordination} premisesRef={premisesRef} onClose={() => setSelectedEpisodeRef(null)} onChanged={refresh} /> : null}
  </main>;
}

const css = `
.patientFlow{display:grid;gap:9px;padding:12px 18px 28px;background:#eef2f7;color:#182c3f}.patientFlow.loading{margin:12px 18px;padding:18px;background:#fff;border:1px solid #d8e0e8;border-radius:10px;grid-template-columns:1fr auto auto;align-items:center}.patientFlow button,.patientFlow a{display:inline-flex;align-items:center;justify-content:center;min-height:31px;padding:5px 8px;border:1px solid #cad5df;border-radius:6px;background:#fff;color:#294a64;font-size:9px;font-weight:800;text-decoration:none}.flowTitle{display:flex;justify-content:space-between;gap:16px;align-items:center;padding:12px 14px;background:#fff;border:1px solid #d8e0e8;border-radius:10px}.flowTitle>div:first-child>span{color:#42657f;font-size:8px;font-weight:850;text-transform:uppercase;letter-spacing:.08em}.flowTitle h2{margin:3px 0 0;font-size:20px;color:#17344e}.flowTitle p{margin:3px 0 0;color:#718092;font-size:9px}.titleActions{display:flex;gap:5px;align-items:center}.titleActions>span{padding:5px 7px;border-radius:99px;font-size:8px;font-weight:850;text-transform:uppercase}.titleActions .live{background:#e3f2ea;color:#28674d}.titleActions .warning{background:#fff0da;color:#8c5a12}
.flowSummary{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}.flowSummary article{display:flex;align-items:baseline;gap:7px;padding:8px 10px;background:#fff;border:1px solid #d8e0e8;border-left:3px solid #64859d;border-radius:8px}.flowSummary article.warning{border-left-color:#c77c14}.flowSummary article.critical{border-left-color:#b63c38}.flowSummary b{font-size:20px;color:#17344e}.flowSummary span{font-size:8px;color:#68798a;text-transform:uppercase;font-weight:800}
.flowFilters{display:grid;grid-template-columns:minmax(280px,1fr) 150px 190px auto;gap:6px;align-items:end;padding:7px;background:#fff;border:1px solid #d8e0e8;border-radius:8px}.flowFilters label{display:grid;gap:3px;color:#65778a;font-size:8px;font-weight:800;text-transform:uppercase}.flowFilters input,.flowFilters select{width:100%;min-height:32px;padding:5px 7px;border:1px solid #cad5df;border-radius:5px;background:#fff;color:#182c3f;font-size:10px}.flowFilters .check{display:flex;align-items:center;gap:6px;min-height:32px;padding:0 7px;border:1px solid #d8e0e8;border-radius:5px}.flowFilters .check input{width:auto;min-height:auto}
.flowTableWrap{max-height:70vh;overflow:auto;background:#fff;border:1px solid #d8e0e8;border-radius:9px}.flowTableWrap table{width:100%;min-width:1480px;border-collapse:separate;border-spacing:0;font-size:9px}.flowTableWrap th{position:sticky;top:0;z-index:2;padding:6px 7px;text-align:left;background:#edf2f6;color:#637588;border-bottom:1px solid #d8e0e8;font-size:8px;text-transform:uppercase;letter-spacing:.04em}.flowTableWrap td{padding:6px 7px;border-bottom:1px solid #e8edf1;vertical-align:top}.flowTableWrap tr[data-risk=red] td:first-child{border-left:4px solid #b63c38}.flowTableWrap tr[data-risk=amber] td:first-child{border-left:4px solid #c77c14}.flowTableWrap b{display:block;font-size:9px;color:#20384c}.flowTableWrap small{display:block;margin-top:2px;color:#788697;font-size:8px;line-height:1.25}.risk{display:inline-block;padding:3px 5px;border-radius:99px;font-size:7px;font-weight:900;text-transform:uppercase}.risk.red{background:#f8dedd;color:#932e2b}.risk.amber{background:#fff0d6;color:#85570f}.risk.green{background:#e1f1e8;color:#2b694f}.blocked b{color:#9f312e}.rowActions{display:flex;gap:4px}.empty{padding:18px;color:#6c7c8e;font-size:10px}.patientFlow footer{display:flex;justify-content:space-between;padding:7px 9px;border:1px solid #d5dee6;border-radius:7px;background:#f8fafb;color:#69798a;font-size:8px}
@media(max-width:900px){.flowSummary{grid-template-columns:repeat(3,1fr)}.flowFilters{grid-template-columns:1fr 1fr}.flowTitle{align-items:flex-start}}
@media(max-width:560px){.patientFlow{padding:8px}.flowTitle{display:grid}.flowSummary{grid-template-columns:1fr 1fr}.flowFilters{grid-template-columns:1fr}.titleActions{overflow-x:auto}.patientFlow footer{display:grid;gap:3px}}
`;
