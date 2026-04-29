"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type FlowIssue = {
  type: string;
  section: string;
  detail: string;
  owner_role: string;
  urgency: string;
};

type FlowReadiness = {
  episode_id: number;
  episode_ref: string;
  ready_for_flow: boolean;
  caution: boolean;
  hard_block_count: number;
  warning_count: number;
  hard_blocks: FlowIssue[];
  warnings: FlowIssue[];
};

function border(ready: boolean) {
  return ready ? "1px solid #14532d" : "1px solid #7f1d1d";
}

export function FlowReadinessPanel({ episodeId }: { episodeId: number }) {
  const [data, setData] = useState<FlowReadiness | null>(null);

  async function load() {
    const res = await fetch(`${API_BASE}/api/flow-readiness/${episodeId}`, { cache: "no-store" });
    if (res.ok) setData(await res.json());
  }

  useEffect(() => {
    if (episodeId) load();
  }, [episodeId]);

  if (!data) return null;

  return (
    <section style={{ border: border(data.ready_for_flow), borderRadius: 18, padding: 16, background: "#0f172a" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h3 style={{ margin: 0 }}>Flow readiness</h3>
          <div style={{ color: "#94a3b8", marginTop: 6 }}>
            {data.ready_for_flow ? "Ready for flow" : "Blocked for flow"} • hard blocks {data.hard_block_count} • warnings {data.warning_count}
          </div>
        </div>
        <button onClick={load} style={{ borderRadius: 10, padding: "8px 10px" }}>Refresh safety check</button>
      </div>

      {data.hard_blocks.length ? (
        <div style={{ marginTop: 14 }}>
          <strong>Hard blocks</strong>
          {data.hard_blocks.map((item, index) => (
            <div key={`${item.type}-${index}`} style={{ borderTop: "1px solid #1f2937", paddingTop: 10, marginTop: 10 }}>
              <div><strong>{item.section}</strong> • {item.urgency} • owner {item.owner_role}</div>
              <div style={{ color: "#94a3b8", marginTop: 4 }}>{item.type}: {item.detail}</div>
            </div>
          ))}
        </div>
      ) : null}

      {data.warnings.length ? (
        <div style={{ marginTop: 14 }}>
          <strong>Warnings</strong>
          {data.warnings.map((item, index) => (
            <div key={`${item.type}-${index}`} style={{ borderTop: "1px solid #1f2937", paddingTop: 10, marginTop: 10 }}>
              <div><strong>{item.section}</strong> • {item.urgency} • owner {item.owner_role}</div>
              <div style={{ color: "#94a3b8", marginTop: 4 }}>{item.type}: {item.detail}</div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
