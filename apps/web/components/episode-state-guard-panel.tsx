"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Guard = {
  current_state: string;
  target_state: string;
  allowed_by_graph: boolean;
  can_transition: boolean;
  hard_failures: any[];
  warnings: any[];
  next_action?: any | null;
  owner_role: string;
};

type Spec = {
  states: string[];
  allowed_transitions: Record<string, string[]>;
  state_owners: Record<string, string>;
};

function border(can?: boolean) {
  return can ? "1px solid #14532d" : "1px solid #7f1d1d";
}

export function EpisodeStateGuardPanel({ episodeRef, currentPhase }: { episodeRef: string; currentPhase?: string }) {
  const [spec, setSpec] = useState<Spec | null>(null);
  const [guards, setGuards] = useState<Guard[]>([]);
  const [status, setStatus] = useState("");

  async function load() {
    setStatus("");
    const specRes = await fetch(`${API_BASE}/api/episode-state-machine`, { cache: "no-store" });
    if (!specRes.ok) {
      setStatus("Episode state machine failed to load.");
      return;
    }
    const nextSpec = await specRes.json();
    setSpec(nextSpec);
    const candidates = Array.from(new Set([...(nextSpec.allowed_transitions?.[currentPhase || "intake"] || []), "procedure", "recovery", "discharge_ready", "discharged", "closed"]));
    const loaded: Guard[] = [];
    for (const target of candidates) {
      const res = await fetch(`${API_BASE}/api/episodes/${episodeRef}/state-guard/${target}`, { cache: "no-store" });
      if (res.ok) loaded.push(await res.json());
    }
    setGuards(loaded);
  }

  async function transition(target: string) {
    setStatus(`Trying transition to ${target}...`);
    const res = await fetch(`${API_BASE}/api/episodes/${episodeRef}/transition`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_state: target, actor_name: "Episode Command", reason: "Transition from episode state guard panel" }),
    });
    const body = await res.json();
    setStatus(body.ok ? `Moved to ${target}.` : `Blocked: ${body.guard?.next_action?.detail || body.guard?.hard_failures?.[0]?.detail || "transition blocked"}`);
    await load();
  }

  useEffect(() => { load(); }, [episodeRef, currentPhase]);

  return (
    <section className="lw-card" style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Episode state guard</div>
          <h3 style={{ margin: "6px 0 0" }}>Current phase: {currentPhase || "unknown"}</h3>
          <p style={{ color: "#94a3b8", marginBottom: 0 }}>Transitions are checked before movement. Blocked moves are audited.</p>
        </div>
        <button onClick={load} className="lw-pill">Refresh guards</button>
      </div>
      {status ? <div style={{ marginTop: 10, color: "#fbbf24" }}>{status}</div> : null}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 10, marginTop: 12 }}>
        {guards.map((guard) => (
          <article key={guard.target_state} style={{ border: border(guard.can_transition), borderRadius: 12, padding: 12 }}>
            <strong>{guard.current_state} → {guard.target_state}</strong>
            <div style={{ color: "#94a3b8", marginTop: 4 }}>{guard.can_transition ? "CAN MOVE" : "BLOCKED"} • graph {guard.allowed_by_graph ? "allowed" : "not allowed"} • owner {guard.owner_role}</div>
            {guard.next_action ? <div style={{ color: "#fbbf24", marginTop: 6 }}>Next: {guard.next_action.detail} • {guard.next_action.owner_role}</div> : null}
            {guard.hard_failures?.slice(0, 3).map((item, index) => <div key={index} style={{ color: "#fca5a5", marginTop: 4 }}>{item.type}: {item.detail}</div>)}
            {guard.can_transition ? <button onClick={() => transition(guard.target_state)} style={{ marginTop: 10, padding: "8px 10px", borderRadius: 10 }}>Move to {guard.target_state}</button> : null}
          </article>
        ))}
      </div>
      {!guards.length ? <div style={{ color: "#94a3b8", marginTop: 10 }}>No guards loaded.</div> : null}
    </section>
  );
}
