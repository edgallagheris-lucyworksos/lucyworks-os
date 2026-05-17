"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type ClinicalDirectorItem = {
  episode?: {
    episode?: { episode_ref?: string | null; phase?: string | null; section?: string | null } | null;
    patient?: { name?: string | null; species?: string | null; owner_name?: string | null } | null;
  } | null;
  type?: string | null;
  section?: string | null;
  detail?: string | null;
  owner_role?: string | null;
  urgency?: "red" | "amber" | "green" | string | null;
  score?: number | null;
  starts_at?: string | null;
  ends_at?: string | null;
  block_type?: string | null;
  room_name?: string | null;
  hard_block_count?: number | null;
  warning_count?: number | null;
  next_action?: ClinicalDirectorItem | null;
};

type ClinicalDirectorRead = {
  generated_at?: string | null;
  hospital_state: "red" | "amber" | "green" | string;
  reason_for_state?: string | null;
  ignored_risk?: string | null;
  top_risks?: string[];
  next_action?: ClinicalDirectorItem | null;
  lanes: Record<string, ClinicalDirectorItem[]>;
  counts: Record<string, number>;
};

function formatTime(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function stateBorder(state?: string | null) {
  if (state === "red") return "#7f1d1d";
  if (state === "amber") return "#78350f";
  return "#14532d";
}

function stateLabel(state?: string | null) {
  return String(state || "unknown").toUpperCase();
}

function episodeRef(item?: ClinicalDirectorItem | null) {
  return item?.episode?.episode?.episode_ref || null;
}

function ItemCard({ item }: { item: ClinicalDirectorItem }) {
  const ref = episodeRef(item);
  return (
    <article style={{ border: `1px solid ${stateBorder(item.urgency)}`, borderRadius: 14, padding: 12, background: "rgba(15,23,42,0.34)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <strong>{stateLabel(item.urgency)} • {item.section || item.type || item.block_type || "command item"}</strong>
        {item.score != null ? <span style={{ color: "#94a3b8" }}>score {item.score}</span> : null}
      </div>
      <div style={{ color: "#cbd5e1", marginTop: 6 }}>{item.detail || item.next_action?.detail || "No detail supplied"}</div>
      <div style={{ color: "#94a3b8", marginTop: 8, fontSize: 13 }}>
        {ref || "no episode"} • {item.episode?.patient?.name || "patient -"} • owner {item.owner_role || "unowned"}
      </div>
      {item.starts_at || item.ends_at || item.room_name ? (
        <div style={{ color: "#94a3b8", marginTop: 6, fontSize: 13 }}>
          {formatTime(item.starts_at)}–{formatTime(item.ends_at)} • {item.room_name || "no room"} • hard {item.hard_block_count ?? 0} • warn {item.warning_count ?? 0}
        </div>
      ) : null}
      {ref ? (
        <div style={{ marginTop: 10 }}>
          <Link href={`/episodes/${ref}`} className="lw-pill">Open episode</Link>
        </div>
      ) : null}
    </article>
  );
}

function Lane({ title, items, empty }: { title: string; items: ClinicalDirectorItem[]; empty: string }) {
  return (
    <section className="lw-card" style={{ padding: 14 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <div style={{ display: "grid", gap: 10 }}>
        {items.length ? items.map((item, index) => <ItemCard key={`${title}-${index}`} item={item} />) : <p style={{ color: "#94a3b8", margin: 0 }}>{empty}</p>}
      </div>
    </section>
  );
}

export function ClinicalDirectorReadPanel() {
  const [data, setData] = useState<ClinicalDirectorRead | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/clinical-director`, { cache: "no-store" });
      if (!res.ok) throw new Error("Clinical director read failed");
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Clinical director read failed");
    }
  }

  useEffect(() => { load(); }, []);

  if (error) {
    return <section className="lw-card" style={{ padding: 14, border: "1px solid #7f1d1d" }}>Clinical director read unavailable: {error}</section>;
  }

  if (!data) {
    return <section className="lw-card" style={{ padding: 14, color: "#94a3b8" }}>Loading clinical director read...</section>;
  }

  const lanes = data.lanes || {};
  const counts = data.counts || {};

  return (
    <section style={{ display: "grid", gap: 14 }}>
      <section className="lw-card" style={{ padding: 16, border: `1px solid ${stateBorder(data.hospital_state)}` }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div>
            <div style={{ color: "#94a3b8" }}>Clinical director read</div>
            <h2 style={{ margin: "6px 0" }}>Hospital state: {stateLabel(data.hospital_state)}</h2>
            <p style={{ margin: 0, color: "#cbd5e1" }}>{data.reason_for_state}</p>
          </div>
          <button className="lw-pill" onClick={load}>Refresh read</button>
        </div>
        {data.ignored_risk ? <p style={{ color: "#fbbf24", marginBottom: 0 }}>If ignored: {data.ignored_risk}</p> : null}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10 }}>
        {["unsafe_now", "flow_blockers", "decision_required", "owner_failures", "next_60_minutes", "conflicts", "alerts"].map((key) => (
          <div key={key} className="lw-card" style={{ padding: 12 }}>
            <div style={{ color: "#94a3b8", fontSize: 13 }}>{key.replaceAll("_", " ")}</div>
            <strong style={{ fontSize: 24 }}>{counts[key] ?? 0}</strong>
          </div>
        ))}
      </section>

      {data.top_risks?.length ? (
        <section className="lw-card" style={{ padding: 14 }}>
          <strong>Top risks</strong>
          <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
            {data.top_risks.map((risk, index) => <div key={index} style={{ color: "#cbd5e1" }}>{risk}</div>)}
          </div>
        </section>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
        <Lane title="Unsafe now" items={lanes.unsafe_now || []} empty="No live hard blockers in the command read." />
        <Lane title="Flow blockers" items={lanes.flow_blockers || []} empty="No flow blockers currently surfaced." />
        <Lane title="Decision required" items={lanes.decision_required || []} empty="No decision, result, comms or triage ownership gaps." />
        <Lane title="Owner failures" items={lanes.owner_failures || []} empty="No unowned command items surfaced." />
        <Lane title="Next 60 minutes" items={lanes.next_60_minutes || []} empty="No scheduled live work in the next 60 minutes." />
      </div>
    </section>
  );
}
