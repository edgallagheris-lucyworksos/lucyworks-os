"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { getSession } from "@/lib/session";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Workspace = {
  role: string;
  summary: Record<string, number>;
  queues: Record<string, any[]>;
};

function fmt(value?: string | null) {
  if (!value) return "-";
  try { return new Date(value).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch { return value; }
}

function tone(value?: string) {
  if (["CRITICAL", "HIGH", "red", "blocked"].includes(value || "")) return { border: "#7f1d1d", text: "#fca5a5" };
  if (["MODERATE", "MED", "amber", "requested", "pending_review"].includes(value || "")) return { border: "#78350f", text: "#fbbf24" };
  return { border: "#14532d", text: "#86efac" };
}

function Pill({ value }: { value?: string }) {
  const t = tone(value);
  return <span className="lw-pill" style={{ borderColor: t.border, color: t.text }}>{value || "open"}</span>;
}

function CountCard({ label, value }: { label: string; value: number | string }) {
  return <div className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>{label}</div><div style={{ fontSize: 28, fontWeight: 950 }}>{value}</div></div>;
}

function ActionButton({ children, onClick, busy }: { children: React.ReactNode; onClick: () => void; busy?: boolean }) {
  return <button disabled={busy} onClick={onClick} className="lw-pill lw-btn-primary" style={{ opacity: busy ? 0.6 : 1 }}>{children}</button>;
}

function QueueCard({ item, title, status, owner, detail, time, children }: { item: any; title: string; status?: string; owner?: string; detail?: string; time?: string | null; children: React.ReactNode }) {
  const t = tone(status || item.severity || item.rota_risk || item.status);
  return <article style={{ border: `1px solid ${t.border}`, borderRadius: 14, padding: 12 }}>
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
      <strong>{title}</strong>
      <Pill value={status || item.status || item.severity || item.rota_risk} />
    </div>
    <div style={{ color: "#94a3b8", marginTop: 6 }}>Episode #{item.episode_id || "-"} • owner {owner || item.owner_role || item.review_owner || item.to_owner || item.role_required || "-"}</div>
    {detail ? <div style={{ marginTop: 8 }}>{detail}</div> : null}
    {time ? <div style={{ color: "#94a3b8", marginTop: 6 }}>{fmt(time)}</div> : null}
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>{children}</div>
  </article>;
}

function ActionsInner() {
  const [role, setRole] = useState("ops_manager");
  const [data, setData] = useState<Workspace | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function load(nextRole = role) {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/workspace?role=${encodeURIComponent(nextRole)}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`workspace ${res.status}`);
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Actions failed to load");
    }
  }

  async function run(label: string, url: string, options: RequestInit = {}) {
    setBusy(label);
    setNotice("");
    setError("");
    try {
      const res = await fetch(`${API_BASE}${url}`, { method: "POST", ...options });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body?.detail?.reasons?.join(" | ") || body?.detail || `${label} failed ${res.status}`);
      setNotice(`${label} completed`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${label} failed`);
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    const session = getSession();
    const initialRole = session?.user?.role || "ops_manager";
    setRole(initialRole);
    load(initialRole);
  }, []);

  const q = data?.queues || {};
  const handovers = [...(q.handovers || []), ...(q.night_handovers || [])];
  const results = q.results || [];
  const blockers = q.discharge_blockers || [];
  const staffRisks = q.staff_risks || [];
  const schedules = q.schedule_blocks || [];
  const ownerComms = q.owner_comms || [];

  return <HospitalShell title="Live Actions" subtitle="Acknowledge, review, resolve, approve and start operational work through gates">
    <div style={{ display: "grid", gap: 16 }}>
      <section className="lw-card" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Action layer</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.04em" }}>Queues are not enough — staff need buttons that change state</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>This page wires operational buttons into handover, results, discharge blockers, schedule starts, staff-risk approval and owner-comms closure.</p>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <select value={role} onChange={(e) => { setRole(e.target.value); load(e.target.value); }} className="lw-pill" style={{ background: "#020617", color: "#f8fafc" }}>
              {['ops_manager','clinical_director','clinician','nurse','admin','theatre_staff','ward_staff','imaging_staff','stock_controller'].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <button className="lw-pill lw-btn-primary" onClick={() => load()}>Refresh</button>
            <Link href="/workspace" className="lw-pill">Workspace</Link>
            <Link href="/flow-state" className="lw-pill">Flow State</Link>
          </div>
        </div>
        {notice ? <p style={{ color: "#86efac" }}>{notice}</p> : null}
        {error ? <p style={{ color: "#fca5a5" }}>{error}</p> : null}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(165px, 1fr))", gap: 12 }}>
        <CountCard label="Handovers" value={handovers.length} />
        <CountCard label="Results" value={results.length} />
        <CountCard label="Discharge blockers" value={blockers.length} />
        <CountCard label="Staff risks" value={staffRisks.length} />
        <CountCard label="Schedule blocks" value={schedules.length} />
        <CountCard label="Owner comms" value={ownerComms.length} />
      </section>

      <section className="lw-card" style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Handovers to acknowledge</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 10 }}>
          {handovers.map((h: any) => <QueueCard key={`handover-${h.id}`} item={h} title={`${h.from_owner || h.from_role || "handover"} → ${h.to_owner || h.to_role || "receiver"}`} status="unacknowledged" owner={h.to_owner || h.to_role} detail={h.note || h.summary} time={h.created_at}>
            {h.to_role ? <span className="lw-pill">night handover view only</span> : <ActionButton busy={busy === `ack-${h.id}`} onClick={() => run(`ack-${h.id}`, `/api/flow/handovers/${h.id}/ack?actor_name=Live%20Actions`)}>Acknowledge</ActionButton>}
          </QueueCard>)}
        </div>
      </section>

      <section className="lw-card" style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Results to review</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 10 }}>
          {results.map((r: any) => <QueueCard key={`result-${r.id}`} item={r} title={r.result_type || `Result #${r.id}`} status={r.status} owner={r.review_owner} detail={r.required_action} time={r.created_at}>
            <ActionButton busy={busy === `review-${r.id}`} onClick={() => run(`review-${r.id}`, `/api/flow/results/${r.id}/review?actor_name=Live%20Actions`)}>Mark reviewed</ActionButton>
          </QueueCard>)}
        </div>
      </section>

      <section className="lw-card" style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Discharge blockers to resolve</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 10 }}>
          {blockers.map((b: any) => <QueueCard key={`blocker-${b.id}`} item={b} title={b.blocker_type} status={b.severity} owner={b.owner_role} detail={b.detail} time={b.created_at}>
            <ActionButton busy={busy === `resolve-${b.id}`} onClick={() => run(`resolve-${b.id}`, `/api/flow/discharge-blockers/${b.id}/resolve?note=Resolved%20from%20Live%20Actions&actor_name=Live%20Actions`)}>Resolve blocker</ActionButton>
            <ActionButton busy={busy === `approve-discharge-${b.episode_id}`} onClick={() => run(`approve-discharge-${b.episode_id}`, `/api/live-actions/discharge/${b.episode_id}/approve`, { body: JSON.stringify({ actor_name: "Live Actions" }), headers: { "Content-Type": "application/json" } })}>Try discharge approval</ActionButton>
          </QueueCard>)}
        </div>
      </section>

      <section className="lw-card" style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Staff assignment risks</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 10 }}>
          {staffRisks.map((s: any) => <QueueCard key={`risk-${s.id}`} item={s} title={`${s.role_required} assignment`} status={s.rota_risk} owner={s.role_required} detail={`Required: ${s.required_skills || "-"} • Matched: ${s.matched_skills || "none"} • Load ${Number(s.load_ratio || 0).toFixed(2)}`} time={s.created_at}>
            <ActionButton busy={busy === `approve-risk-${s.id}`} onClick={() => run(`approve-risk-${s.id}`, `/api/live-actions/staff-assignment-risk/${s.id}/approve`, { body: JSON.stringify({ actor_name: "Live Actions", reviewer_name: "Clinical Director", override_reason: "Reviewed from action queue" }), headers: { "Content-Type": "application/json" } })}>Approve with review</ActionButton>
          </QueueCard>)}
        </div>
      </section>

      <section className="lw-card" style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Schedule blocks to start</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 10 }}>
          {schedules.map((s: any) => <QueueCard key={`schedule-${s.id}`} item={s} title={`${s.block_type || "block"} • ${s.room_name || "room"}`} status={s.status} owner={s.owner_role} detail={`${fmt(s.starts_at)} → ${fmt(s.ends_at)}`} time={s.starts_at}>
            <ActionButton busy={busy === `start-${s.id}`} onClick={() => run(`start-${s.id}`, `/api/live-actions/schedule-blocks/${s.id}/start`, { body: JSON.stringify({ actor_name: "Live Actions" }), headers: { "Content-Type": "application/json" } })}>Start through gate</ActionButton>
          </QueueCard>)}
        </div>
      </section>

      <section className="lw-card" style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Owner comms to close</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 10 }}>
          {ownerComms.map((c: any) => <QueueCard key={`owner-comms-${c.id}`} item={c} title={c.requirement_type || `Comms #${c.id}`} status={c.status} owner={c.owner_role} detail={c.reason || c.description} time={c.created_at}>
            <ActionButton busy={busy === `close-comms-${c.id}`} onClick={() => run(`close-comms-${c.id}`, `/api/live-actions/owner-comms/${c.id}/close`, { body: JSON.stringify({ actor_name: "Live Actions", reviewer_name: "Ops Manager", override_reason: "Closed from action queue" }), headers: { "Content-Type": "application/json" } })}>Close comms</ActionButton>
          </QueueCard>)}
        </div>
      </section>
    </div>
  </HospitalShell>;
}

export default function ActionsPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <ActionsInner />}</AuthGuard>;
}
