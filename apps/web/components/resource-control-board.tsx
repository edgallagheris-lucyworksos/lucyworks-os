"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { coreOperatingUnits, theatreUnits, type OperatingUnit } from "@/lib/hospital-operating-model";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Tone = "red" | "amber" | "green" | "blue";
type Room = { room_name?: string; name?: string; state?: string; department?: string; current_episode_ref?: string; next_episode_ref?: string };
type Block = { block_type?: string; status?: string; owner_role?: string; room?: { name?: string; state?: string; department?: string }; episode?: { episode_ref?: string; patient?: { name?: string } }; pressure?: { hard_blocks?: unknown[]; warnings?: unknown[] }; next_action?: { detail?: string; owner_role?: string; urgency?: string } };
type Slot = { risk?: string; blocks?: Block[]; starts_at?: string; active_count?: number; hard_block_count?: number; warning_count?: number };
type Dashboard = { summary?: Record<string, number>; rooms?: Room[]; slots?: Slot[]; conflicts?: unknown[]; alerts?: unknown[] };
type Pulse = { state?: string; pressure_score?: number; blocked_room_count?: number; red_conflicts?: number; amber_conflicts?: number; conflicts?: Array<{ severity?: string; department?: string; detail?: string; next_action?: string; type?: string }> };

type ResourceRow = {
  id: string;
  label: string;
  owner: string;
  status: Tone;
  state: string;
  current: string;
  next: string;
  blocker: string;
  route: string;
};

function toneClass(tone: string) { return tone === "red" ? "rc-red" : tone === "amber" ? "rc-amber" : tone === "green" ? "rc-green" : "rc-blue"; }
function text(value: unknown) { return String(value || ""); }
function lower(value: unknown) { return text(value).toLowerCase(); }
function count(value: unknown) { const n = typeof value === "number" ? value : Number(value); return Number.isFinite(n) ? n : 0; }
function statusFrom(value: unknown): Tone { const v = lower(value); return v.includes("red") || v.includes("high") || v.includes("blocked") || v.includes("critical") ? "red" : v.includes("amber") || v.includes("held") || v.includes("pending") || v.includes("turnover") ? "amber" : v.includes("ready") || v.includes("active") || v.includes("green") ? "green" : "blue"; }

async function getJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function roomLabel(room: Room | undefined) { return room?.room_name || room?.name || ""; }
function blockRoom(block: Block | undefined) { return block?.room?.name || ""; }
function allBlocks(data: Dashboard | null) { return (data?.slots || []).flatMap((slot) => slot.blocks || []); }
function findBlock(unit: OperatingUnit, data: Dashboard | null) {
  const unitName = lower(unit.label);
  return allBlocks(data).find((block) => lower(blockRoom(block)).includes(unitName) || lower(block.room?.department).includes(lower(unit.type))) || null;
}
function findRoom(unit: OperatingUnit, data: Dashboard | null) {
  const name = lower(unit.label);
  return (data?.rooms || []).find((room) => lower(roomLabel(room)).includes(name) || lower(room.department).includes(lower(unit.type))) || null;
}
function conflictsFor(unit: OperatingUnit, pulse: Pulse | null) {
  const token = lower(unit.label.split(" ")[0]);
  return (pulse?.conflicts || []).filter((item) => `${lower(item.department)} ${lower(item.detail)} ${lower(item.type)}`.includes(token));
}

const fallbackStates = ["Blocked", "Active", "Turnover", "Ready", "Held", "Active", "Ready", "Consent", "Staff gap", "Emergency", "Kit held"];

function rowFor(unit: OperatingUnit, data: Dashboard | null, pulse: Pulse | null, index: number): ResourceRow {
  const block = findBlock(unit, data);
  const room = findRoom(unit, data);
  const conflicts = conflictsFor(unit, pulse);
  const hard = count(block?.pressure?.hard_blocks?.length);
  const warn = count(block?.pressure?.warnings?.length) + conflicts.length;
  const status: Tone = hard ? "red" : warn ? "amber" : block || room ? statusFrom(block?.status || room?.state || "green") : unit.type === "theatre" ? statusFrom(fallbackStates[index % fallbackStates.length]) : ["mri", "ct", "pharmacy", "insurance", "icu", "recovery"].includes(unit.id) ? "amber" : "blue";
  return {
    id: unit.id,
    label: unit.label,
    owner: unit.ownerRole,
    status,
    state: text(block?.status || room?.state || (unit.type === "theatre" ? fallbackStates[index % fallbackStates.length] : "monitored")),
    current: text(block?.episode?.episode_ref || block?.episode?.patient?.name || room?.current_episode_ref || "—"),
    next: text(room?.next_episode_ref || block?.block_type || unit.tracks[0]),
    blocker: text(block?.next_action?.detail || conflicts[0]?.next_action || conflicts[0]?.detail || unit.blockers[0]),
    route: unit.route,
  };
}

function Section({ label, title, children }: { label: string; title: string; children: ReactNode }) {
  return <section className="rc-panel"><div className="rc-head"><span>{label}</span><h2>{title}</h2></div>{children}</section>;
}

function ResourceTable({ rows }: { rows: ResourceRow[] }) {
  return <div className="rc-table"><div className="rc-tr rc-th"><span>Unit</span><span>State</span><span>Current</span><span>Next</span><span>Owner</span><span>Blocker / next action</span></div>{rows.map((row) => <Link href={row.route} className={`rc-tr ${toneClass(row.status)}`} key={row.id}><span><b>{row.label}</b></span><span>{row.state}</span><span>{row.current}</span><span>{row.next}</span><span>{row.owner}</span><span>{row.blocker}</span></Link>)}</div>;
}

function TheatreGrid({ rows }: { rows: ResourceRow[] }) {
  return <div className="rc-theatre-grid">{rows.map((row) => <Link href={row.route} className={`rc-theatre ${toneClass(row.status)}`} key={row.id}><b>{row.label}</b><strong>{row.state}</strong><span>{row.current}</span><small>{row.blocker}</small></Link>)}</div>;
}

function PressureStrip({ data, pulse }: { data: Dashboard | null; pulse: Pulse | null }) {
  const summary = data?.summary || {};
  const red = count(pulse?.red_conflicts || summary.red_slots);
  const amber = count(pulse?.amber_conflicts || summary.amber_slots);
  const pressure = count(pulse?.pressure_score) || Math.min(100, red * 15 + amber * 6);
  const cards = [
    ["Resource pressure", `${pressure}/100`, pressure >= 70 ? "red" : pressure >= 35 ? "amber" : "green"],
    ["Rooms", String(count(summary.rooms)), "blue"],
    ["Blocked rooms", String(count(pulse?.blocked_room_count)), count(pulse?.blocked_room_count) ? "amber" : "green"],
    ["Schedule blocks", String(count(summary.schedule_blocks)), "blue"],
    ["Red slots", String(count(summary.red_slots)), count(summary.red_slots) ? "red" : "green"],
    ["Amber slots", String(count(summary.amber_slots)), count(summary.amber_slots) ? "amber" : "green"],
  ] as const;
  return <div className="rc-kpis">{cards.map(([label, value, tone]) => <div className={`rc-kpi ${toneClass(tone)}`} key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>;
}

export function ResourceControlBoard() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [pulse, setPulse] = useState<Pulse | null>(null);
  const [updated, setUpdated] = useState("fallback mode");

  useEffect(() => {
    let mounted = true;
    async function load() {
      const [dash, livePulse] = await Promise.all([getJson<Dashboard>("/api/dashboard/intelligence"), getJson<Pulse>("/api/conflict-engine/pulse")]);
      if (!mounted) return;
      setDashboard(dash);
      setPulse(livePulse);
      setUpdated(dash || livePulse ? new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "fallback mode");
    }
    load();
    const timer = window.setInterval(load, 30000);
    return () => { mounted = false; window.clearInterval(timer); };
  }, []);

  const theatreRows = theatreUnits.map((unit, index) => rowFor(unit, dashboard, pulse, index));
  const supportRows = coreOperatingUnits.filter((unit) => !unit.id.startsWith("theatre-")).map((unit, index) => rowFor(unit, dashboard, pulse, index));
  const diagnostics = supportRows.filter((row) => ["mri", "ct", "xray", "lab"].includes(row.id));
  const beds = supportRows.filter((row) => ["icu", "recovery", "ward"].includes(row.id));
  const admin = supportRows.filter((row) => ["pharmacy", "insurance", "owner-comms", "stock-equipment", "governance"].includes(row.id));

  return <div className="rc-board"><style>{css}</style><header className="rc-hero"><div><span>BVS resource control · {updated}</span><h1>Resource control</h1><p>11 theatres, diagnostics, beds, pharmacy, insurance, owner comms, stock and governance. This is the detail view behind the daily operational board.</p></div><nav><Link href="/hospital-board">Daily board</Link><Link href="/interrupts">Pulse</Link><Link href="/actions">Actions</Link></nav></header><PressureStrip data={dashboard} pulse={pulse} /><div className="rc-layout"><main><Section label="theatre complex" title="11-theatre resource grid"><TheatreGrid rows={theatreRows} /></Section><Section label="all resources" title="Operating units by blocker and owner"><ResourceTable rows={[...theatreRows, ...supportRows]} /></Section></main><aside><Section label="diagnostics" title="MRI / CT / X-ray / lab"><ResourceTable rows={diagnostics} /></Section><Section label="beds" title="ICU / recovery / ward"><ResourceTable rows={beds} /></Section><Section label="admin + support" title="Pharmacy / insurance / comms / stock"><ResourceTable rows={admin} /></Section></aside></div></div>;
}

const css = `.rc-board{min-height:100vh;background:#050b14;color:#e6edf7;padding:20px;font-family:Inter,system-ui,sans-serif}.rc-hero{display:flex;justify-content:space-between;gap:18px;border:1px solid #274568;border-radius:24px;padding:22px;background:linear-gradient(135deg,#0c182a,#07111f)}.rc-hero span,.rc-head span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}.rc-hero h1{font-size:clamp(36px,5vw,64px);line-height:.95;margin:8px 0}.rc-hero p{max-width:900px;color:#a7b5c8}.rc-hero nav{display:flex;gap:8px;flex-wrap:wrap;align-content:flex-start}.rc-hero a,.rc-tr,.rc-theatre{color:#e6edf7;text-decoration:none}.rc-hero a{border:1px solid #31557f;background:#10223c;border-radius:999px;padding:9px 12px;font-weight:800}.rc-kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:14px 0}.rc-kpi,.rc-panel{background:#0b1728;border:1px solid #243b60;border-radius:18px;padding:13px}.rc-kpi span{display:block;color:#9fb0c6;text-transform:uppercase;font-size:11px}.rc-kpi strong{font-size:24px}.rc-layout{display:grid;grid-template-columns:minmax(0,1fr) 440px;gap:14px}.rc-layout main,aside{display:grid;gap:14px;align-content:start}.rc-head{display:flex;justify-content:space-between;border-bottom:1px solid #243b60;margin-bottom:12px;padding-bottom:10px}.rc-head h2{margin:0;font-size:19px}.rc-red{border-color:#ef4444!important;background:#2a0d16!important}.rc-amber{border-color:#f59e0b!important;background:#2a1a08!important}.rc-green{border-color:#22c55e!important;background:#071d13!important}.rc-blue{border-color:#38bdf8!important;background:#071a2a!important}.rc-theatre-grid{display:grid;grid-template-columns:repeat(11,minmax(120px,1fr));gap:8px;overflow:auto}.rc-theatre{display:grid;gap:5px;border:1px solid #28466e;border-radius:14px;background:#101d31;padding:10px}.rc-theatre strong{font-size:18px}.rc-theatre small,.rc-theatre span{color:#a7b5c8}.rc-table{display:grid;gap:4px;overflow:auto}.rc-tr{display:grid;grid-template-columns:1fr .8fr .85fr .85fr .9fr 1.4fr;gap:8px;border:1px solid #28466e;border-radius:12px;background:#091321;padding:9px;min-width:780px}.rc-th{background:#10223c;color:#93c5fd;font-size:12px;text-transform:uppercase;font-weight:900}.rc-tr span{overflow:hidden;text-overflow:ellipsis}.rc-tr:not(.rc-th):hover,.rc-theatre:hover{outline:2px solid #5eead4}@media(max-width:1250px){.rc-layout{grid-template-columns:1fr}.rc-kpis{grid-template-columns:repeat(3,1fr)}.rc-theatre-grid{grid-template-columns:repeat(11,130px)}}@media(max-width:720px){.rc-board{padding:10px}.rc-hero{flex-direction:column}.rc-kpis{grid-template-columns:1fr}}`;
