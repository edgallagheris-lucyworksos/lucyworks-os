"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { coreOperatingUnits, theatreUnits, type OperatingUnit } from "@/lib/hospital-operating-model";
import { bvsPublicFacilityProfile } from "@/lib/bvs-public-facility-profile";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Status = "red" | "amber" | "green" | "blue";
type Action = { title: string; owner: string; due: string; impact: string; href: string; status: Status };
type DashboardSummary = { rooms?: number; schedule_blocks?: number; active_slots?: number; red_slots?: number; amber_slots?: number; alerts?: number; high_alerts?: number; conflicts?: number; open_work?: number };
type DashboardBlock = { block_type?: string; status?: string; owner_role?: string; room?: { name?: string; state?: string; department?: string }; episode?: { episode_ref?: string; patient?: { name?: string } }; pressure?: { hard_blocks?: unknown[]; warnings?: unknown[] }; next_action?: { detail?: string; owner_role?: string; urgency?: string; section?: string } };
type DashboardSlot = { starts_at?: string; risk?: Status | string; active_count?: number; hard_block_count?: number; warning_count?: number; blocks?: DashboardBlock[] };
type DashboardData = { generated_at?: string; summary?: DashboardSummary; rooms?: Array<{ room_name?: string; name?: string; state?: string; department?: string; current_episode_ref?: string; next_episode_ref?: string }>; slots?: DashboardSlot[]; conflicts?: unknown[]; alerts?: unknown[] };
type PulseConflict = { type?: string; severity?: string; detail?: string; department?: string; next_action?: string; work_item_id?: number; episode_refs?: string[] };
type PulseData = { state?: string; pressure_score?: number; red_conflicts?: number; amber_conflicts?: number; blocked_room_count?: number; open_work_count?: number; active_case_count?: number; pending_result_reviews?: number; conflicts_by_department?: Record<string, number>; conflicts?: PulseConflict[] };

const fallbackActions: Action[] = [
  { title: "Assign senior cover between MRI and operating space", owner: "Clinical Director", due: "now", impact: "Imaging delay pushes theatre recovery and owner updates", href: "/manager-dashboard", status: "red" },
  { title: "Confirm recovery acceptance for Theatre 1", owner: "Recovery nurse", due: "+10", impact: "Theatre 1 remains blocked until recovery capacity is confirmed", href: "/resources", status: "red" },
  { title: "Complete insurance pre-authorisation for urgent CT", owner: "Admin", due: "+20", impact: "CT slot is held but cannot proceed cleanly without cover decision", href: "/lucy-comms", status: "amber" },
  { title: "Release ward beds through discharge meds", owner: "Duty clinician + pharmacy", due: "+30", impact: "Ward beds stay blocked and ICU step-down is delayed", href: "/lucy-pharm", status: "amber" },
  { title: "Resolve lab result owner gap", owner: "Clinician", due: "+30", impact: "Clinical decision is waiting and patient cannot move lanes", href: "/lucy-clinical", status: "amber" },
];

const fallbackTheatreStatus: Status[] = ["red", "green", "amber", "green", "red", "green", "green", "amber", "amber", "green", "amber"];
const fallbackTheatreState = ["Blocked", "Active", "Turnover", "Ready", "Held", "Active", "Ready", "Consent", "Staff gap", "Emergency", "Kit held"];
const fallbackTheatreCase = ["T1-041", "T2-014", "T3-009", "T4-032", "T5-022", "T6-018", "T7-027", "T8-006", "T9-019", "T10-001", "T11-011"];
const timelineLanes = ["Triage", "MRI", "CT", "X-ray", "Interventional", "Lab", "Theatre", "Recovery", "ICU", "Ward", "Pharmacy", "Insurance", "Owner comms"];
const slots = ["Now", "+15", "+30", "+45", "+60", "+90", "+120"];

function statusClass(status: string) { return status === "red" ? "daily-red" : status === "amber" ? "daily-amber" : status === "green" ? "daily-green" : "daily-blue"; }
function statusFromSeverity(severity?: string): Status { return severity === "red" || severity === "high" || severity === "critical" ? "red" : severity === "amber" || severity === "medium" ? "amber" : "blue"; }
function n(value: unknown, fallback = 0) { const parsed = typeof value === "number" ? value : Number(value); return Number.isFinite(parsed) ? parsed : fallback; }
function lower(value: unknown) { return String(value || "").toLowerCase(); }
function laneHref(lane: string) { return lane === "Insurance" || lane === "Owner comms" ? "/lucy-comms" : lane === "Pharmacy" ? "/lucy-pharm" : lane === "Lab" || lane === "Interventional" ? "/lucy-clinical" : lane === "Theatre" || lane === "Recovery" || lane === "ICU" ? "/resources" : "/flow"; }
function sourceLabel(source?: string) { return source === "public_verified" ? "public verified" : "configurable"; }

async function getJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function Section({ title, label, children }: { title: string; label: string; children: ReactNode }) {
  return <section className="daily-panel"><div className="daily-panel-head"><span>{label}</span><h2>{title}</h2></div>{children}</section>;
}

function PressureStrip({ dashboard, pulse }: { dashboard: DashboardData | null; pulse: PulseData | null }) {
  const summary = dashboard?.summary || {};
  const red = n(pulse?.red_conflicts, n(summary.red_slots, 9));
  const amber = n(pulse?.amber_conflicts, n(summary.amber_slots, 0));
  const pressure = n(pulse?.pressure_score, Math.min(100, red * 15 + amber * 6));
  const state = lower(pulse?.state) || (red ? "red" : amber ? "amber" : "green");
  const cards = [
    ["Hospital state", state.toUpperCase(), state],
    ["Pressure", `${pressure}/100`, pressure >= 70 ? "red" : pressure >= 35 ? "amber" : "green"],
    ["Unsafe blockers", String(red), red ? "red" : "green"],
    ["Open work", String(n(pulse?.open_work_count, n(summary.open_work, 5))), "amber"],
    ["Operating complex", `${bvsPublicFacilityProfile.publicVerifiedOperatingTheatres} public theatres + ${bvsPublicFacilityProfile.publicVerifiedInterventionalSuites} IR + config`, red ? "amber" : "green"],
    ["Diagnostics", "MRI/CT/X-ray/US", n(pulse?.pending_result_reviews, 0) ? "amber" : "blue"],
    ["Beds", `${n(pulse?.blocked_room_count, 0)} blocked rooms`, n(pulse?.blocked_room_count, 0) ? "amber" : "blue"],
    ["Alerts", `${n(summary.alerts, 0)} / high ${n(summary.high_alerts, 0)}`, n(summary.high_alerts, 0) ? "red" : "blue"],
  ] as const;
  return <div className="daily-pressure">{cards.map(([label, value, status]) => <div className={`daily-kpi ${statusClass(status)}`} key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>;
}

function theatreBlockFor(unitLabel: string, dashboard: DashboardData | null) {
  const allBlocks = (dashboard?.slots || []).flatMap((slot) => slot.blocks || []);
  return allBlocks.find((block) => lower(block.room?.name).includes(lower(unitLabel))) || null;
}

function TheatreComplex({ dashboard }: { dashboard: DashboardData | null }) {
  return <div className="theatre-grid">{theatreUnits.map((unit, index) => {
    const block = theatreBlockFor(unit.label, dashboard);
    const hard = n(block?.pressure?.hard_blocks?.length, 0);
    const warnings = n(block?.pressure?.warnings?.length, 0);
    const status: Status = hard ? "red" : warnings ? "amber" : block ? "green" : fallbackTheatreStatus[index];
    const state = block?.status || block?.room?.state || fallbackTheatreState[index];
    const caseRef = block?.episode?.episode_ref || block?.episode?.patient?.name || fallbackTheatreCase[index];
    return <Link href="/resources" className={`theatre-card ${statusClass(status)}`} key={unit.id}><b>{unit.label}</b><strong>{state}</strong><span>{caseRef}</span><small>{sourceLabel(unit.source)} · {block?.next_action?.detail || unit.blockers[0]}</small></Link>;
  })}</div>;
}

function OperatingUnits({ pulse }: { pulse: PulseData | null }) {
  const support = coreOperatingUnits.filter((unit) => !unit.id.startsWith("theatre-"));
  return <div className="unit-grid">{support.map((unit) => <UnitCard unit={unit} pulse={pulse} key={unit.id} />)}</div>;
}

function UnitCard({ unit, pulse }: { unit: OperatingUnit; pulse: PulseData | null }) {
  const matches = (pulse?.conflicts || []).filter((conflict) => `${lower(conflict.department)} ${lower(conflict.detail)} ${lower(conflict.type)}`.includes(lower(unit.label.split(" ")[0])));
  const worst = matches.find((conflict) => statusFromSeverity(conflict.severity) === "red") || matches[0];
  const status = worst ? statusFromSeverity(worst.severity) : ["mri", "ct", "pharmacy", "insurance", "icu", "recovery"].includes(unit.id) ? "amber" : "blue";
  return <Link href={unit.route} className={`unit-card ${statusClass(status)}`}><b>{unit.label}</b><span>{unit.ownerRole}</span><small>{sourceLabel(unit.source)} · {unit.tracks.slice(0, 3).join(" · ")}</small><em>{worst?.next_action || worst?.detail || unit.blockers[0]}</em></Link>;
}

function ActionRail({ pulse }: { pulse: PulseData | null }) {
  const live = (pulse?.conflicts || []).slice(0, 8).map<Action>((conflict, index) => ({
    title: conflict.next_action || conflict.detail || `Resolve ${conflict.type || "conflict"}`,
    owner: conflict.department || "ops",
    due: index < 2 ? "now" : "+30",
    impact: conflict.detail || "Operational conflict requires ownership.",
    href: conflict.work_item_id ? "/actions" : conflict.episode_refs?.[0] ? `/episodes/${conflict.episode_refs[0]}` : "/interrupts",
    status: statusFromSeverity(conflict.severity),
  }));
  const rows = live.length ? live : fallbackActions;
  return <div className="action-list">{rows.map((action) => <Link href={action.href} className={`action-card ${statusClass(action.status)}`} key={action.title}><b>{action.title}</b><span>Owner: {action.owner}</span><span>Due: {action.due}</span><p>{action.impact}</p></Link>)}</div>;
}

function Timeline({ dashboard }: { dashboard: DashboardData | null }) {
  const liveSlots = (dashboard?.slots || []).slice(0, slots.length);
  function cellText(lane: string, slotIndex: number, fallback: string) {
    const slot = liveSlots[slotIndex];
    const match = (slot?.blocks || []).find((block) => `${lower(block.room?.name)} ${lower(block.room?.department)} ${lower(block.block_type)}`.includes(lower(lane)));
    if (!match) return fallback;
    return match.episode?.episode_ref || match.episode?.patient?.name || match.block_type || `${lane} active`;
  }
  return <div className="daily-timeline"><div className="timeline-cell timeline-head">Lane</div>{slots.map((slot) => <div className="timeline-cell timeline-head" key={slot}>{slot}</div>)}{timelineLanes.map((lane, rowIndex) => <div className="timeline-row" key={lane}><div className="timeline-cell timeline-lane"><b>{lane}</b></div>{slots.map((slot, colIndex) => <Link href={laneHref(lane)} className="timeline-cell" key={`${lane}-${slot}`}>{cellText(lane, colIndex, colIndex === rowIndex % slots.length ? `${lane} task · ${slot}` : "")}</Link>)}</div>)}</div>;
}

export function DailyOperationalBoard() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [pulse, setPulse] = useState<PulseData | null>(null);
  const [updated, setUpdated] = useState("fallback mode");

  useEffect(() => {
    let mounted = true;
    async function load() {
      const [dashboardData, pulseData] = await Promise.all([getJson<DashboardData>("/api/dashboard/intelligence"), getJson<PulseData>("/api/conflict-engine/pulse")]);
      if (!mounted) return;
      setDashboard(dashboardData);
      setPulse(pulseData);
      setUpdated(dashboardData?.generated_at ? new Date(dashboardData.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : dashboardData || pulseData ? "live API" : "fallback mode");
    }
    load();
    const timer = window.setInterval(load, 30000);
    return () => { mounted = false; window.clearInterval(timer); };
  }, []);

  return <div className="daily-board"><style>{css}</style><header className="daily-hero"><div><span>BVS public profile + configurable internal model · {updated}</span><h1>Daily operational control</h1><p>Uses verified public BVS facilities separately from configurable internal operating spaces, then overlays live dashboard intelligence and conflict pulse data.</p></div><div className="daily-hero-actions"><Link href="/interrupts">Open Pulse</Link><Link href="/resources">Resource control</Link><Link href="/lucy-gov">Audit trail</Link></div></header><PressureStrip dashboard={dashboard} pulse={pulse} /><div className="daily-layout"><main><Section label="operating complex" title="5 public theatres + interventional + configurable theatre-like spaces"><TheatreComplex dashboard={dashboard} /></Section><Section label="hospital units" title="Diagnostics, pharmacy, insurance, beds and support"><OperatingUnits pulse={pulse} /></Section><Section label="timeline" title="Now to +120 minutes"><Timeline dashboard={dashboard} /></Section></main><aside><Section label="priority" title="Decision and action rail"><ActionRail pulse={pulse} /></Section><Section label="audit" title="Latest operating decisions"><div className="audit-list"><Link href="/lucy-gov">{n(dashboard?.summary?.conflicts, 0)} conflicts tracked</Link><Link href="/lucy-gov">{n(dashboard?.summary?.alerts, 0)} alerts active</Link><Link href="/resources">{n(dashboard?.summary?.schedule_blocks, 0)} schedule blocks today</Link><Link href="/flow">{n(dashboard?.summary?.active_slots, 0)} active slots</Link></div></Section></aside></div></div>;
}

const css = `.daily-board{min-height:100vh;background:#050b14;color:#e6edf7;padding:20px;font-family:Inter,system-ui,sans-serif}.daily-hero{display:flex;justify-content:space-between;gap:18px;border:1px solid #274568;border-radius:24px;padding:22px;background:linear-gradient(135deg,#0c182a,#07111f)}.daily-hero span,.daily-panel-head span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}.daily-hero h1{font-size:clamp(36px,5vw,64px);line-height:.95;margin:8px 0}.daily-hero p{max-width:900px;color:#a7b5c8}.daily-hero-actions{display:flex;gap:8px;flex-wrap:wrap;align-content:flex-start}.daily-hero a,.action-card,.theatre-card,.unit-card,.timeline-cell,.audit-list a{color:#e6edf7;text-decoration:none}.daily-hero a{border:1px solid #31557f;background:#10223c;border-radius:999px;padding:9px 12px;font-weight:800}.daily-pressure{display:grid;grid-template-columns:repeat(8,1fr);gap:10px;margin:14px 0}.daily-kpi,.daily-panel{background:#0b1728;border:1px solid #243b60;border-radius:18px;padding:13px}.daily-kpi span{display:block;color:#9fb0c6;text-transform:uppercase;font-size:11px}.daily-kpi strong{font-size:22px}.daily-layout{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:14px}.daily-layout main,aside{display:grid;gap:14px;align-content:start}.daily-panel-head{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid #243b60;padding-bottom:10px;margin-bottom:12px}.daily-panel-head h2{margin:0;font-size:19px}.daily-red{border-color:#ef4444!important;background:#2a0d16!important}.daily-amber{border-color:#f59e0b!important;background:#2a1a08!important}.daily-green{border-color:#22c55e!important;background:#071d13!important}.daily-blue{border-color:#38bdf8!important;background:#071a2a!important}.theatre-grid{display:grid;grid-template-columns:repeat(11,minmax(120px,1fr));gap:8px;overflow:auto}.theatre-card,.unit-card,.action-card{display:grid;gap:5px;border:1px solid #28466e;border-radius:14px;background:#101d31;padding:10px}.theatre-card strong,.unit-card b{font-size:18px}.theatre-card small,.unit-card small,.unit-card em,.action-card span,.action-card p{color:#a7b5c8;font-style:normal;margin:0}.unit-grid{display:grid;grid-template-columns:repeat(4,minmax(190px,1fr));gap:10px}.action-list,.audit-list{display:grid;gap:8px}.audit-list a{border-bottom:1px solid #1e3556;padding-bottom:8px;color:#a7b5c8}.daily-timeline{display:grid;grid-template-columns:150px repeat(7,minmax(125px,1fr));gap:1px;background:#243b60;border-radius:16px;overflow:auto}.timeline-row{display:contents}.timeline-cell{min-height:58px;background:#091321;padding:9px}.timeline-head,.timeline-lane{background:#10223c;font-weight:900}.timeline-lane{position:sticky;left:0}@media(max-width:1250px){.daily-layout{grid-template-columns:1fr}.daily-pressure{grid-template-columns:repeat(4,1fr)}.unit-grid{grid-template-columns:repeat(2,1fr)}.theatre-grid{grid-template-columns:repeat(11,130px)}.daily-timeline{grid-template-columns:150px repeat(7,140px)}}@media(max-width:700px){.daily-board{padding:10px}.daily-hero{flex-direction:column}.daily-pressure,.unit-grid{grid-template-columns:1fr}.daily-hero h1{font-size:36px}}`;
