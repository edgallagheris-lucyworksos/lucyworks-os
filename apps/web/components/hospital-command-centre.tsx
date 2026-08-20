"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { useDayControlStore } from "@/lib/day-control-store";
import { useOperationalContext } from "@/lib/operational-context";

type Area = { areaRef: string; name: string; areaType: string; department: string; capacity: number; turnoverMinutes: number };
type Block = { blockRef: string; episodeRef?: string; patientRef?: string; patientName?: string; procedureName: string; areaRef: string; areaName: string; startsAt: string; endsAt: string; status: string; riskLevel: string; leadStaffRef?: string; leadStaffName?: string; blockers: unknown[]; version: number };
type Episode = { episodeRef: string; patientRef?: string; patientName: string; phase: string; urgency: string; ownerRole: string; currentAreaRef?: string; nextAction?: string };
type Conflict = { conflictRef?: string; severity: string; primaryBlockRef?: string; relatedRefs: string[]; explanation: string };
type Board = {
  operationalDate: string;
  areas: Area[];
  blocks: Block[];
  episodes: Episode[];
  conflicts: Conflict[];
  summary: { blocks: number; episodes: number; redConflicts: number; amberConflicts: number; unassignedBlocks: number; blockedBlocks: number };
};

type StaffRow = { key: string; name: string; role: string; location: string; work: number; blocked: number };

const DAY_START = 7 * 60;
const DAY_END = 22 * 60;
const DAY_SPAN = DAY_END - DAY_START;

function today() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}
function mins(value: string) { const d = new Date(value); return d.getHours() * 60 + d.getMinutes(); }
function time(value: string) { return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
function clamp(value: number) { return Math.max(DAY_START, Math.min(DAY_END, value)); }
function level(value: string) { const v = value.toLowerCase(); return v === "red" || v === "critical" || v === "blocked" ? "red" : v === "amber" || v === "warning" ? "amber" : "green"; }

export function HospitalCommandCentre() {
  const { premisesRef, siteName } = useOperationalContext();
  const { blocks: staffWork, syncStatus } = useDayControlStore();
  const [board, setBoard] = useState<Board | null>(null);
  const [status, setStatus] = useState("Loading hospital state");
  const [date, setDate] = useState(today());
  const [query, setQuery] = useState("");
  const [department, setDepartment] = useState("all");
  const [exceptionsOnly, setExceptionsOnly] = useState(false);
  const [selected, setSelected] = useState<Block | null>(null);
  const [staffQuery, setStaffQuery] = useState("");

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<Board>(`/api/v11/master-board/day?premises_ref=${encodeURIComponent(premisesRef)}&operational_date=${date}`);
      setBoard(data);
      setStatus("Live hospital state");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Hospital state unavailable");
    }
  }, [date, premisesRef]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const conflictRefs = useMemo(() => {
    const refs = new Set<string>();
    for (const item of board?.conflicts || []) {
      if (item.primaryBlockRef) refs.add(item.primaryBlockRef);
      for (const ref of item.relatedRefs || []) refs.add(ref);
    }
    return refs;
  }, [board]);

  const departments = useMemo(() => Array.from(new Set((board?.areas || []).map(a => a.department || a.areaType).filter(Boolean))).sort(), [board]);
  const normalized = query.trim().toLowerCase();

  const filteredBlocks = useMemo(() => (board?.blocks || []).filter(block => {
    if (exceptionsOnly && !conflictRefs.has(block.blockRef) && !(block.blockers?.length) && block.leadStaffName) return false;
    if (!normalized) return true;
    return [block.patientName, block.patientRef, block.procedureName, block.areaName, block.leadStaffName, block.episodeRef].some(v => String(v || "").toLowerCase().includes(normalized));
  }), [board, conflictRefs, exceptionsOnly, normalized]);

  const blockRefs = useMemo(() => new Set(filteredBlocks.map(b => b.blockRef)), [filteredBlocks]);
  const roomRows = useMemo(() => (board?.areas || [])
    .filter(area => department === "all" || (area.department || area.areaType) === department)
    .filter(area => !normalized || (area.name + " " + area.department + " " + area.areaType).toLowerCase().includes(normalized) || (board?.blocks || []).some(b => b.areaRef === area.areaRef && blockRefs.has(b.blockRef)))
    .sort((a, b) => (a.department || a.areaType).localeCompare(b.department || b.areaType) || a.name.localeCompare(b.name)), [board, department, normalized, blockRefs]);

  const staffRows = useMemo<StaffRow[]>(() => {
    const map = new Map<string, StaffRow>();
    for (const work of staffWork) {
      const name = String(work.assignedStaffName || "").trim();
      if (!name) continue;
      const key = String(work.assignedStaffId || name.toLowerCase());
      const row = map.get(key) || { key, name, role: String(work.assignedRole || work.who || "staff"), location: String(work.where || "Unlocated"), work: 0, blocked: 0 };
      row.work += 1;
      if (work.blocker && String(work.blocker).toLowerCase() !== "none") row.blocked += 1;
      if (work.where) row.location = String(work.where);
      map.set(key, row);
    }
    for (const block of board?.blocks || []) {
      if (!block.leadStaffName) continue;
      const key = String(block.leadStaffRef || block.leadStaffName.toLowerCase());
      if (!map.has(key)) map.set(key, { key, name: block.leadStaffName, role: "clinical", location: block.areaName, work: 1, blocked: block.blockers?.length ? 1 : 0 });
    }
    return Array.from(map.values()).sort((a, b) => b.blocked - a.blocked || b.work - a.work || a.name.localeCompare(b.name));
  }, [staffWork, board]);

  const visibleStaff = useMemo(() => {
    const q = staffQuery.trim().toLowerCase();
    if (!q) return staffRows;
    return staffRows.filter(row => [row.name, row.role, row.location].some(v => v.toLowerCase().includes(q)));
  }, [staffRows, staffQuery]);

  const episodesWithoutRoom = useMemo(() => (board?.episodes || []).filter(ep => !ep.currentAreaRef), [board]);
  const roomExceptionCount = useMemo(() => roomRows.filter(room => (board?.blocks || []).some(block => block.areaRef === room.areaRef && (conflictRefs.has(block.blockRef) || block.blockers?.length || !block.leadStaffName))).length, [roomRows, board, conflictRefs]);

  if (!board) return <section className="hccLoading">{siteName}: {status}</section>;

  return <section className="hcc">
    <style>{css}</style>
    <header className="hccTop">
      <div><span>LIVE COMMAND</span><h2>{siteName}</h2><p>{roomRows.length} rooms in view · {staffRows.length} staff represented in current operational feeds · updates every 5 seconds</p></div>
      <div className="hccActions"><button type="button" onClick={() => void refresh()}>Refresh now</button><Link href="/input">Quick input</Link><Link href="/referral-intake">New referral</Link></div>
    </header>

    <section className="hccKpis" aria-label="Hospital command summary">
      <article><b>{board.areas.length}</b><span>rooms / areas</span></article>
      <article><b>{board.summary.episodes}</b><span>active episodes</span></article>
      <article className={board.summary.redConflicts ? "bad" : ""}><b>{board.summary.redConflicts}</b><span>red conflicts</span></article>
      <article className={board.summary.unassignedBlocks ? "warn" : ""}><b>{board.summary.unassignedBlocks}</b><span>unassigned blocks</span></article>
      <article className={episodesWithoutRoom.length ? "warn" : ""}><b>{episodesWithoutRoom.length}</b><span>patients without location</span></article>
      <article className={roomExceptionCount ? "warn" : ""}><b>{roomExceptionCount}</b><span>rooms needing attention</span></article>
    </section>

    <section className="hccFilters">
      <label>Find anything<input aria-label="Search hospital command" value={query} onChange={e => setQuery(e.target.value)} placeholder="patient, procedure, room, staff, episode" /></label>
      <label>Date<input type="date" value={date} onChange={e => setDate(e.target.value)} /></label>
      <label>Department<select value={department} onChange={e => setDepartment(e.target.value)}><option value="all">All departments</option>{departments.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
      <button type="button" className={exceptionsOnly ? "active" : ""} onClick={() => setExceptionsOnly(v => !v)}>{exceptionsOnly ? "Showing exceptions" : "Exceptions only"}</button>
      <strong>{status}</strong>
    </section>

    <div className="hccLayout">
      <main className="hccRooms">
        <div className="timelineHead"><div>ROOM / AREA</div><div className="hours">{Array.from({ length: 16 }, (_, i) => <span key={i} style={{ left: `${(i / 15) * 100}%` }}>{String(7 + i).padStart(2, "0")}:00</span>)}</div></div>
        <div className="roomList">
          {roomRows.map(room => {
            const roomBlocks = filteredBlocks.filter(block => block.areaRef === room.areaRef);
            const attention = roomBlocks.some(block => conflictRefs.has(block.blockRef) || block.blockers?.length || !block.leadStaffName);
            return <article className={`roomRow ${attention ? "attention" : ""}`} key={room.areaRef}>
              <div className="roomMeta"><b>{room.name}</b><span>{room.department || room.areaType}</span><small>cap {room.capacity} · turnover {room.turnoverMinutes}m</small></div>
              <div className="roomTimeline">
                {Array.from({ length: 16 }, (_, i) => <i key={i} style={{ left: `${(i / 15) * 100}%` }} />)}
                {roomBlocks.map(block => {
                  const start = clamp(mins(block.startsAt)); const end = clamp(mins(block.endsAt));
                  const left = ((start - DAY_START) / DAY_SPAN) * 100; const width = Math.max(1.2, ((Math.max(end, start + 15) - start) / DAY_SPAN) * 100);
                  const hasConflict = conflictRefs.has(block.blockRef) || block.blockers?.length;
                  return <button type="button" key={block.blockRef} className={`caseBlock ${hasConflict ? "red" : level(block.riskLevel)}`} style={{ left: `${left}%`, width: `${width}%` }} onClick={() => setSelected(block)} title={`${block.patientName || "Operational work"} · ${block.procedureName} · ${block.leadStaffName || "NO LEAD"}`}>
                    <b>{block.patientName || "WORK"}</b><span>{block.procedureName}</span><small>{block.leadStaffName || "NO LEAD"}</small>
                  </button>;
                })}
                {!roomBlocks.length && <span className="roomEmpty">No scheduled work</span>}
              </div>
            </article>;
          })}
          {!roomRows.length && <div className="emptyState">No rooms match the current filters.</div>}
        </div>
      </main>

      <aside className="staffRail">
        <header><div><h3>Staff load</h3><span>{syncStatus === "api" ? "live feed" : syncStatus}</span></div><input aria-label="Search staff" value={staffQuery} onChange={e => setStaffQuery(e.target.value)} placeholder="find staff or location" /></header>
        <div className="staffList">{visibleStaff.map(row => <button type="button" key={row.key} className={row.blocked ? "blocked" : ""} onClick={() => setQuery(row.name)}><b>{row.name}</b><span>{row.role} · {row.location}</span><small>{row.work} work item{row.work === 1 ? "" : "s"}{row.blocked ? ` · ${row.blocked} blocked` : ""}</small></button>)}</div>
        {!visibleStaff.length && <p className="railEmpty">No named staff are present in the current feed.</p>}
      </aside>
    </div>

    {selected && <aside className="caseDrawer" aria-label="Selected case">
      <button type="button" className="drawerClose" aria-label="Close selected case" onClick={() => setSelected(null)}>×</button>
      <span>{time(selected.startsAt)}–{time(selected.endsAt)} · {selected.areaName}</span>
      <h3>{selected.patientName || "Operational work"}</h3>
      <p>{selected.procedureName}</p>
      <dl><div><dt>Lead</dt><dd>{selected.leadStaffName || "UNASSIGNED"}</dd></div><div><dt>Status</dt><dd>{selected.status}</dd></div><div><dt>Version</dt><dd>{selected.version}</dd></div></dl>
      {selected.episodeRef ? <nav><Link href={`/care?episode=${encodeURIComponent(selected.episodeRef)}`}>Care brief</Link><Link href={`/patient-record?episode=${encodeURIComponent(selected.episodeRef)}`}>Patient record</Link><Link href={`/clinical-execution?episode=${encodeURIComponent(selected.episodeRef)}`}>Patient work</Link><Link href={`/episode-command?episode=${encodeURIComponent(selected.episodeRef)}`}>Episode command</Link></nav> : <p>No episode link recorded for this work block.</p>}
    </aside>}
  </section>;
}

const css = `
.hcc{padding:12px 14px 30px;color:#172033}.hcc *{box-sizing:border-box}.hccLoading{padding:24px}.hccTop{display:flex;justify-content:space-between;gap:20px;align-items:flex-end;margin-bottom:10px}.hccTop span{font-size:10px;font-weight:900;letter-spacing:.16em;color:#60758a}.hccTop h2{font-size:22px;margin:2px 0}.hccTop p{margin:0;color:#667789;font-size:11px}.hccActions{display:flex;gap:6px}.hccActions button,.hccActions a{border:1px solid #cbd5df;background:#fff;color:#17344e;border-radius:7px;padding:7px 10px;text-decoration:none;font-size:11px;font-weight:800;cursor:pointer}.hccActions a:last-child{background:#173f5f;color:#fff;border-color:#173f5f}.hccKpis{display:grid;grid-template-columns:repeat(6,minmax(105px,1fr));gap:6px;margin-bottom:8px}.hccKpis article{background:#fff;border:1px solid #d9e1e9;border-radius:8px;padding:8px 10px}.hccKpis b{display:block;font-size:19px}.hccKpis span{font-size:9px;color:#6b7a8b;font-weight:750}.hccKpis .bad{border-color:#efb0b0;background:#fff7f7}.hccKpis .warn{border-color:#ead4a0;background:#fffbf0}.hccFilters{display:grid;grid-template-columns:minmax(220px,1.5fr) 145px 190px auto auto;gap:7px;align-items:end;background:#f8fafc;border:1px solid #d9e1e9;border-radius:8px;padding:8px;margin-bottom:8px}.hccFilters label{display:grid;gap:3px;font-size:9px;font-weight:800;color:#667789}.hccFilters input,.hccFilters select{min-height:32px;border:1px solid #cbd5df;border-radius:6px;background:#fff;padding:5px 8px;color:#172033}.hccFilters button{min-height:32px;border:1px solid #cbd5df;border-radius:6px;background:#fff;font-weight:800;color:#294761;cursor:pointer}.hccFilters button.active{background:#7f1d1d;color:#fff;border-color:#7f1d1d}.hccFilters strong{font-size:10px;color:#60758a;align-self:center}.hccLayout{display:grid;grid-template-columns:minmax(0,1fr) 250px;gap:8px}.hccRooms,.staffRail{background:#fff;border:1px solid #d7e0e8;border-radius:8px;overflow:hidden}.timelineHead{display:grid;grid-template-columns:154px minmax(900px,1fr);position:sticky;top:0;z-index:5;background:#edf2f6;border-bottom:1px solid #cfd9e2;min-width:1054px}.timelineHead>div:first-child{padding:7px 9px;font-size:9px;font-weight:900;color:#52687b}.hours{position:relative;height:30px}.hours span{position:absolute;top:8px;transform:translateX(-50%);font-size:8px;font-weight:800;color:#60758a}.roomList{max-height:68vh;overflow:auto}.roomRow{display:grid;grid-template-columns:154px minmax(900px,1fr);min-width:1054px;min-height:56px;border-bottom:1px solid #edf1f4}.roomRow.attention{background:#fffcf5}.roomMeta{padding:7px 8px;border-right:1px solid #e1e7ed;display:flex;flex-direction:column;justify-content:center}.roomMeta b{font-size:11px}.roomMeta span,.roomMeta small{font-size:8px;color:#6d7c8b}.roomTimeline{position:relative;min-height:55px;overflow:hidden}.roomTimeline>i{position:absolute;top:0;bottom:0;width:1px;background:#edf1f4}.roomEmpty{position:absolute;left:8px;top:20px;color:#a2acb7;font-size:9px}.caseBlock{position:absolute;top:5px;height:45px;min-width:18px;border:1px solid #b9d0c2;border-left-width:3px;border-radius:5px;background:#f3faf5;color:#173329;padding:4px 5px;text-align:left;overflow:hidden;cursor:pointer}.caseBlock.amber{background:#fff9ea;border-color:#e1bd62}.caseBlock.red{background:#fff1f1;border-color:#dc7777}.caseBlock b,.caseBlock span,.caseBlock small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.caseBlock b{font-size:9px}.caseBlock span{font-size:8px}.caseBlock small{font-size:7px;color:#5f6d78}.staffRail header{padding:9px;border-bottom:1px solid #e1e7ed;background:#f8fafc}.staffRail header>div{display:flex;justify-content:space-between;align-items:center}.staffRail h3{margin:0;font-size:13px}.staffRail header span{font-size:8px;color:#65778a}.staffRail input{width:100%;margin-top:6px;border:1px solid #cbd5df;border-radius:6px;padding:6px 7px;font-size:10px}.staffList{max-height:68vh;overflow:auto}.staffList button{width:100%;border:0;border-bottom:1px solid #edf1f4;background:#fff;text-align:left;padding:7px 9px;cursor:pointer}.staffList button:hover{background:#f4f8fb}.staffList button.blocked{border-left:3px solid #c24141;background:#fff8f8}.staffList b,.staffList span,.staffList small{display:block}.staffList b{font-size:10px}.staffList span,.staffList small{font-size:8px;color:#67798a}.railEmpty,.emptyState{padding:16px;color:#7b8794;font-size:10px}.caseDrawer{position:fixed;right:14px;bottom:14px;z-index:80;width:min(390px,calc(100vw - 28px));background:#fff;border:1px solid #cbd5df;border-radius:10px;box-shadow:0 16px 46px rgba(15,23,42,.2);padding:14px}.drawerClose{position:absolute;right:8px;top:7px;border:0;background:transparent;font-size:22px;cursor:pointer}.caseDrawer>span{font-size:9px;color:#65778a}.caseDrawer h3{font-size:19px;margin:4px 0}.caseDrawer p{font-size:11px}.caseDrawer dl{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}.caseDrawer dl div{background:#f5f8fa;border-radius:6px;padding:6px}.caseDrawer dt{font-size:8px;color:#718091}.caseDrawer dd{margin:2px 0 0;font-size:9px;font-weight:800}.caseDrawer nav{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:10px}.caseDrawer nav a{padding:8px;border-radius:6px;background:#173f5f;color:white;text-decoration:none;font-size:9px;font-weight:800;text-align:center}
@media(max-width:1100px){.hccKpis{grid-template-columns:repeat(3,1fr)}.hccLayout{grid-template-columns:1fr}.staffRail{order:-1}.staffList{max-height:180px;display:grid;grid-template-columns:repeat(3,1fr)}.hccFilters{grid-template-columns:1fr 150px 180px auto}.hccFilters strong{grid-column:1/-1}}
@media(max-width:650px){.hcc{padding:8px}.hccTop{display:block}.hccActions{margin-top:8px;overflow:auto}.hccKpis{grid-template-columns:repeat(2,1fr)}.hccFilters{grid-template-columns:1fr 1fr}.hccFilters label:first-child,.hccFilters strong{grid-column:1/-1}.staffList{grid-template-columns:1fr 1fr}.roomList{max-height:58vh}.caseDrawer nav{grid-template-columns:1fr 1fr}}
`;
