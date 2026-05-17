"use client";

import { ReactNode, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { FlowReadinessPanel } from "@/components/flow-readiness-panel";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type EpisodeCommand = {
  episode: any;
  patient: any;
  admissions: any[];
  handovers: any[];
  results: any[];
  schedule_blocks: any[];
  triage: any[];
  ethics_flags: any[];
  decisions: any[];
  blockers: any[];
  escalations: any[];
  care_tasks: any[];
  owner_comms_requirements: any[];
  message_threads: any[];
  work_items: any[];
  room_state?: any | null;
  conflicts: any[];
};

type StaffLoad = { staff_member_id: number; name: string; role: string; skills: string; on_shift: boolean; active_blocks: number; assigned_block_ids: number[] };
type DischargeReadiness = { id: number; episode_id: number; readiness_state: string; status: string; urgency: string; blocker_summary: string; clinician_signoff: boolean; medication_ready: boolean; owner_updated: boolean; admin_ready: boolean; results_reviewed: boolean; care_instructions_ready: boolean };
type PharmacyRequest = { id: number; episode_id?: number | null; medication_name: string; quantity?: string | null; urgency: string; status: string; controlled_or_legal_status: string; compliance_note: string };
type StockOrder = { id: number; episode_id?: number | null; item_name: string; reason: string; urgency: string; status: string; supplier?: string | null };

function time(value: string) { return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
function SpineSection({ title, items, empty, render }: { title: string; items: any[]; empty: string; render: (item: any, index: number) => ReactNode }) { return <section className="lw-card" style={{ overflow: "hidden" }}><div style={{ padding: 16, background: "#0f172a", fontWeight: 800 }}>{title}</div>{items.map(render)}{!items.length ? <div style={{ padding: 16, color: "#94a3b8" }}>{empty}</div> : null}</section>; }

function caseIntelligence(data: EpisodeCommand, discharge: DischargeReadiness[], pharmacy: PharmacyRequest[], stockOrders: StockOrder[]) {
  const openDischarge = discharge.filter((x) => x.readiness_state !== "ready" || x.status !== "complete");
  const openPharmacy = pharmacy.filter((x) => x.status !== "complete");
  const openStock = stockOrders.filter((x) => x.status !== "complete");
  const openEthics = data.ethics_flags.filter((x) => x.status !== "resolved");
  const openBlockers = data.blockers.filter((x) => x.status !== "resolved");
  const openDecisions = data.decisions.filter((x) => x.status !== "resolved");
  const openOwner = data.owner_comms_requirements.filter((x) => x.status !== "complete");
  const redWork = data.work_items.filter((x) => x.urgency === "red" && x.status !== "done");
  const hard = openDischarge.length + openPharmacy.length + openStock.length + openEthics.length + openBlockers.length + redWork.length;
  const warnings = openDecisions.length + openOwner.length + data.conflicts.length;
  const next = openEthics[0] || openBlockers[0] || openPharmacy[0] || openDischarge[0] || openStock[0] || openOwner[0] || openDecisions[0] || redWork[0];
  const owner = next?.owner_role || next?.review_owner || next?.to_role || "ops_manager";
  const state = hard ? "blocked" : warnings ? "caution" : "ready";
  return { state, hard, warnings, next, owner, openDischarge, openPharmacy, openStock, openEthics, openBlockers, openDecisions, openOwner, redWork };
}

export default function EpisodeDetailPage() {
  const params = useParams<{ episodeRef: string }>();
  const episodeRef = params.episodeRef;
  const [data, setData] = useState<EpisodeCommand | null>(null);
  const [staffLoad, setStaffLoad] = useState<StaffLoad[]>([]);
  const [discharge, setDischarge] = useState<DischargeReadiness[]>([]);
  const [pharmacy, setPharmacy] = useState<PharmacyRequest[]>([]);
  const [stockOrders, setStockOrders] = useState<StockOrder[]>([]);
  const [status, setStatus] = useState("");

  async function load() {
    const [episodeRes, staffRes, dischargeRes, pharmacyRes, stockOrderRes] = await Promise.all([
      fetch(`${API_BASE}/api/episode-command/${episodeRef}`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/staff-load`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/discharge-readiness`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/pharmacy-requests`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/stock-orders`, { cache: "no-store" }),
    ]);
    const episodeData = await episodeRes.json();
    setData(episodeData);
    setStaffLoad(await staffRes.json());
    const episodeId = episodeData?.episode?.id;
    setDischarge((await dischargeRes.json()).filter((x: DischargeReadiness) => x.episode_id === episodeId));
    setPharmacy((await pharmacyRes.json()).filter((x: PharmacyRequest) => x.episode_id === episodeId));
    setStockOrders((await stockOrderRes.json()).filter((x: StockOrder) => x.episode_id === episodeId));
  }

  useEffect(() => { load(); }, [episodeRef]);
  const staffById = useMemo(() => { const map: Record<number, StaffLoad> = {}; for (const s of staffLoad) map[s.staff_member_id] = s; return map; }, [staffLoad]);
  const read = useMemo(() => data ? caseIntelligence(data, discharge, pharmacy, stockOrders) : null, [data, discharge, pharmacy, stockOrders]);

  async function shiftBlock(blockId: number, minutes: number) { setStatus(`Shifting block chain ${minutes} minutes...`); await fetch(`${API_BASE}/api/schedule/block/${blockId}/shift`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ minutes, actor_name: "Episode Command" }) }); setStatus("Schedule updated."); await load(); }
  async function allocateStaff(blockId: number, staffId: string) { if (!staffId) return; setStatus("Assigning staff..."); const res = await fetch(`${API_BASE}/api/staff/allocate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ schedule_block_id: blockId, staff_member_id: Number(staffId), actor_name: "Episode Command" }) }); const body = await res.json(); setStatus(body.status === "conflict" ? `Staff conflict: ${body.detail}` : `Assigned ${body.staff}.`); await load(); }
  async function convertConflict(conflict: any) { setStatus("Creating work from conflict..."); await fetch(`${API_BASE}/api/conflicts/to-work?conflict_type=${encodeURIComponent(conflict.type)}&severity=${encodeURIComponent(conflict.severity)}&detail=${encodeURIComponent(conflict.detail)}`, { method: "POST" }); setStatus("Conflict converted to work."); await load(); }
  async function markResultReviewed(resultId: number) { setStatus("Marking result reviewed..."); await fetch(`${API_BASE}/api/results/${resultId}/action`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "reviewed", actor_name: "Episode Command", required_action: "Reviewed from episode command" }) }); setStatus("Result reviewed."); await load(); }
  async function postAction(url: string, done: string) { setStatus("Updating..."); await fetch(url, { method: "POST" }); setStatus(done); await load(); }
  async function updateDischargeReadiness(item: DischargeReadiness) {
    setStatus("Updating discharge readiness...");
    await fetch(`${API_BASE}/api/discharge-readiness/${item.id}/update`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ clinician_signoff: item.clinician_signoff, medication_ready: item.medication_ready, owner_updated: item.owner_updated, admin_ready: item.admin_ready, results_reviewed: item.results_reviewed, care_instructions_ready: item.care_instructions_ready, blocker_summary: item.blocker_summary, urgency: item.urgency }) });
    setStatus("Discharge readiness refreshed."); await load();
  }

  return <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>{() => (
    <HospitalShell title="Episode Command" subtitle={episodeRef}>
      {status ? <div className="lw-card" style={{ padding: 12, marginBottom: 16 }}>{status}</div> : null}
      {!data ? <p>Loading episode command...</p> : null}
      {data && read ? <div style={{ display: "grid", gap: 16 }}>
        <section className="lw-card" style={{ padding: 20, border: read.state === "blocked" ? "1px solid #7f1d1d" : read.state === "caution" ? "1px solid #78350f" : "1px solid #14532d" }}>
          <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Case intelligence</div>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.2fr) minmax(280px,0.8fr)", gap: 18, marginTop: 10 }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 34 }}>{data.patient?.patient_name} • {data.patient?.species} • {read.state.toUpperCase()}</h2>
              <p style={{ color: "#94a3b8", fontSize: 16 }}>Owner {data.patient?.owner_name} • episode {data.episode.episode_ref} • phase {data.episode.current_phase} • {data.episode.current_section_name || "no section"} / {data.episode.current_room_name || "no room"}</p>
              <p style={{ color: "#cbd5e1", marginBottom: 0 }}>Hard blockers {read.hard} • warnings {read.warnings} • next owner {read.owner}. {read.state === "blocked" ? "Do not move the case through flow until hard blockers are cleared." : read.state === "caution" ? "Flow may proceed only with active owner/decision management." : "Case is operationally clear on current data."}</p>
            </div>
            <div className="lw-card" style={{ padding: 14 }}>
              <strong>Next action</strong>
              <div style={{ color: "#94a3b8", marginTop: 8 }}>{read.next ? (read.next.title || read.next.detail || read.next.medication_name || read.next.blocker_summary || read.next.reason || read.next.decision_needed || "Clear linked item") : "Maintain flow and audit changes."}</div>
              <div style={{ color: "#94a3b8", marginTop: 8 }}>Owner: {read.owner}</div>
            </div>
          </div>
        </section>

        <FlowReadinessPanel episodeId={data.episode.id} />

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
          {[["Hard blockers", read.hard], ["Warnings", read.warnings], ["LucyFlow", data.triage.length], ["Ethics", data.ethics_flags.length], ["Decisions", data.decisions.length], ["Blockers", data.blockers.length], ["Escalations", data.escalations.length], ["Lucy Care", data.care_tasks.length], ["Owner Comms", data.owner_comms_requirements.length], ["Discharge", discharge.length], ["Pharmacy", pharmacy.length], ["Stock Orders", stockOrders.length], ["Conflicts", data.conflicts.length]].map(([label, value]) => <div key={String(label)} className="lw-card" style={{ padding: 16 }}><div style={{ color: "#94a3b8" }}>{label}</div><div style={{ fontSize: 32, fontWeight: 900 }}>{value}</div></div>)}
        </div>

        <SpineSection title="Discharge readiness" items={discharge} empty="No discharge readiness linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.readiness_state} • {item.urgency} • {item.status}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.blocker_summary || "No blocker summary"}</div><div style={{ color: "#94a3b8", marginTop: 6 }}>signoff {item.clinician_signoff ? "yes" : "no"} • meds {item.medication_ready ? "yes" : "no"} • owner {item.owner_updated ? "yes" : "no"} • admin {item.admin_ready ? "yes" : "no"} • results {item.results_reviewed ? "yes" : "no"} • instructions {item.care_instructions_ready ? "yes" : "no"}</div>{item.readiness_state !== "ready" ? <button onClick={() => updateDischargeReadiness(item)} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Refresh</button> : null}</div>} />
        <SpineSection title="Pharmacy requests" items={pharmacy} empty="No pharmacy requests linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.medication_name} • {item.urgency} • {item.status}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.quantity || "no quantity"} • {item.controlled_or_legal_status}</div><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.compliance_note || "No compliance note"}</div>{item.status !== "complete" ? <button onClick={() => postAction(`${API_BASE}/api/pharmacy-requests/${item.id}/complete`, "Pharmacy request completed.")} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Complete</button> : null}</div>} />
        <SpineSection title="Stock orders" items={stockOrders} empty="No stock orders linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.item_name} • {item.urgency} • {item.status}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.reason} • supplier {item.supplier || "-"}</div>{item.status !== "complete" ? <button onClick={() => postAction(`${API_BASE}/api/stock-orders/${item.id}/complete`, "Stock order completed.")} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Complete</button> : null}</div>} />
        <SpineSection title="LucyFlow triage" items={data.triage} empty="No LucyFlow assessments linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.urgency?.toUpperCase()} → {item.route}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.presenting_signs}</div><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.reasoning} • flags {item.red_flags || "none"} • handoff {item.handoff_required ? "yes" : "no"}</div>{item.status !== "resolved" ? <button onClick={() => postAction(`${API_BASE}/api/lucyflow/triage/${item.id}/resolve?note=Resolved%20from%20episode`, "LucyFlow resolved.")} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Resolve</button> : null}</div>} />
        <SpineSection title="Lucy Ethics" items={data.ethics_flags} empty="No ethics flags linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.flag_type} • {item.severity?.toUpperCase()} • {item.status}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.detail}</div><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.clinical_reasoning} • decision {item.decision_required} • escalation {item.escalation_path}</div>{item.status !== "resolved" ? <button onClick={() => postAction(`${API_BASE}/api/lucy-ethics/${item.id}/resolve?note=Resolved%20from%20episode`, "Ethics flag resolved.")} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Resolve</button> : null}</div>} />
        <SpineSection title="Decisions" items={data.decisions} empty="No open decisions linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.decision_type} • {item.urgency} • {item.status}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.decision_needed} • owner {item.owner_role} • source {item.source}</div>{item.status !== "resolved" ? <button onClick={() => postAction(`${API_BASE}/api/decisions/${item.id}/resolve?resolution=Resolved%20from%20episode`, "Decision resolved.")} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Resolve</button> : null}</div>} />
        <SpineSection title="Blockers" items={data.blockers} empty="No blockers linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.blocker_type} • {item.urgency} • {item.status}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.detail} • impact {item.impact} • owner {item.owner_role}</div>{item.status !== "resolved" ? <button onClick={() => postAction(`${API_BASE}/api/blockers/${item.id}/resolve`, "Blocker resolved.")} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Resolve</button> : null}</div>} />
        <SpineSection title="Escalations" items={data.escalations} empty="No escalations linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.escalation_type} • {item.severity} • {item.status}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.reason} • {item.from_role} → {item.to_role}</div>{item.status !== "resolved" ? <button onClick={() => postAction(`${API_BASE}/api/escalations/${item.id}/resolve`, "Escalation resolved.")} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Resolve</button> : null}</div>} />
        <SpineSection title="Lucy Care" items={data.care_tasks} empty="No Lucy Care tasks linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.care_area} • {item.task_type} • {item.status}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.detail} • owner {item.owner_role} • escalation {item.escalation_required ? "yes" : "no"}</div>{item.status !== "done" ? <button onClick={() => postAction(`${API_BASE}/api/lucy-care/tasks/${item.id}/complete`, "Lucy Care task completed.")} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Complete</button> : null}</div>} />
        <SpineSection title="Owner Comms requirements" items={data.owner_comms_requirements} empty="No owner comms requirements linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.reason} • {item.urgency} • {item.status}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.required_message} • owner {item.owner_role}</div>{item.status !== "complete" ? <button onClick={() => postAction(`${API_BASE}/api/owner-comms-requirements/${item.id}/complete`, "Owner comms requirement completed.")} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Complete</button> : null}</div>} />
        <section className="lw-card" style={{ padding: 16 }}><h3 style={{ marginTop: 0 }}>Staff load</h3><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>{staffLoad.map((s) => <div key={s.staff_member_id} style={{ border: "1px solid #334155", borderRadius: 12, padding: 12 }}><strong>{s.name}</strong><div style={{ color: "#94a3b8", marginTop: 4 }}>{s.role} • {s.on_shift ? "on shift" : "off shift"} • {s.active_blocks} blocks</div></div>)}</div></section>
        <section className="lw-card" style={{ overflow: "hidden" }}><div style={{ padding: 16, background: "#0f172a", fontWeight: 800 }}>Timeline controls</div>{data.schedule_blocks.map((block) => { const assigned = block.assigned_staff_member_id ? staffById[block.assigned_staff_member_id] : null; return <div key={block.id} style={{ padding: 16, borderTop: "1px solid #1f2937", display: "grid", gap: 10 }}><div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}><strong>{time(block.starts_at)} → {time(block.ends_at)} • {block.block_type}</strong><span>{block.room_name || "unassigned"} • {assigned ? `assigned ${assigned.name}` : block.owner_role || "no owner"}</span></div><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button onClick={() => shiftBlock(block.id, -15)} style={{ padding: "8px 10px", borderRadius: 10 }}>-15 min</button><button onClick={() => shiftBlock(block.id, 15)} style={{ padding: "8px 10px", borderRadius: 10 }}>+15 min</button><select onChange={(e) => allocateStaff(block.id, e.target.value)} defaultValue="" style={{ padding: "8px 10px", borderRadius: 10 }}><option value="">Assign staff</option>{staffLoad.map((s) => <option key={s.staff_member_id} value={s.staff_member_id}>{s.name} • {s.role} • {s.active_blocks} active</option>)}</select></div></div>; })}{!data.schedule_blocks.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No schedule blocks linked yet.</div> : null}</section>
        <SpineSection title="Conflicts affecting this episode" items={data.conflicts} empty="No conflicts linked to this episode." render={(conflict, index) => <div key={`${conflict.type}-${index}`} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{conflict.type}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{conflict.severity} • {conflict.detail}</div><button onClick={() => convertConflict(conflict)} style={{ marginTop: 10, padding: "8px 10px", borderRadius: 10, background: "#14b8a6", color: "#020617", border: 0 }}>Convert to work</button></div>} />
        <SpineSection title="Results" items={data.results} empty="No results linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.result_type}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.status} • owner {item.review_owner} • action {item.required_action || "-"}</div>{item.status !== "reviewed" ? <button onClick={() => markResultReviewed(item.id)} style={{ marginTop: 10, padding: "8px 10px", borderRadius: 10 }}>Mark reviewed</button> : null}</div>} />
        <SpineSection title="Messages" items={data.message_threads} empty="No message threads linked." render={(thread) => <div key={thread.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{thread.subject}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{thread.source_type} • {thread.status} • {thread.owner_role}</div></div>} />
        <SpineSection title="Work" items={data.work_items} empty="No work items linked." render={(item) => <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}><strong>{item.title}</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>{item.urgency} • {item.status} • owner {item.owner_role}</div></div>} />
      </div> : null}
    </HospitalShell>
  )}</AuthGuard>;
}
