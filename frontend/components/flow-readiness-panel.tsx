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

type OperatingProcedure = {
  procedure_name: string;
  template: any;
  family?: any;
  anaesthesia?: any;
  recovery?: any;
  cleaning?: any;
  expected_blocks: string[];
  actual_blocks: string[];
  missing_blocks: string[];
  readiness_gates: string[];
  ready: boolean;
};

type OperatingReadiness = {
  episode_ref: string;
  procedure_count: number;
  procedures: OperatingProcedure[];
  missing_templates: string[];
  operating_blockers: any[];
  ready: boolean;
};

function border(ready: boolean) {
  return ready ? "1px solid #14532d" : "1px solid #7f1d1d";
}

export function FlowReadinessPanel({ episodeId }: { episodeId: number }) {
  const [data, setData] = useState<FlowReadiness | null>(null);
  const [operating, setOperating] = useState<OperatingReadiness | null>(null);

  async function load() {
    const res = await fetch(`${API_BASE}/api/flow-readiness/${episodeId}`, { cache: "no-store" });
    if (!res.ok) return;
    const flow = await res.json();
    setData(flow);
    const opRes = await fetch(`${API_BASE}/api/episode-operating-readiness/${flow.episode_ref}`, { cache: "no-store" });
    if (opRes.ok) setOperating(await opRes.json());
  }

  useEffect(() => {
    if (episodeId) load();
  }, [episodeId]);

  if (!data) return null;

  return (
    <section style={{ border: border(data.ready_for_flow && (operating?.ready ?? true)), borderRadius: 18, padding: 16, background: "#0f172a" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h3 style={{ margin: 0 }}>Flow and operating readiness</h3>
          <div style={{ color: "#94a3b8", marginTop: 6 }}>
            {data.ready_for_flow ? "Ready for flow" : "Blocked for flow"} • hard blocks {data.hard_block_count} • warnings {data.warning_count}
            {operating ? ` • operating ${operating.ready ? "ready" : "blocked"} • procedures ${operating.procedure_count}` : ""}
          </div>
        </div>
        <button onClick={load} style={{ borderRadius: 10, padding: "8px 10px" }}>Refresh safety check</button>
      </div>

      {operating?.procedures.length ? (
        <div style={{ marginTop: 14 }}>
          <strong>Procedure operating standards</strong>
          {operating.procedures.map((procedure, index) => (
            <div key={`${procedure.procedure_name}-${index}`} style={{ borderTop: "1px solid #1f2937", paddingTop: 10, marginTop: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                <strong>{procedure.procedure_name}</strong>
                <span>{procedure.ready ? "READY" : "BLOCKED"}</span>
              </div>
              <div style={{ color: "#94a3b8", marginTop: 4 }}>
                family {procedure.template?.family || "-"} • anaesthesia {procedure.template?.anaesthesia_level || "-"} • recovery {procedure.template?.recovery_class || "-"} • cleaning {procedure.template?.cleaning_standard || "-"}
              </div>
              <div style={{ color: "#94a3b8", marginTop: 4 }}>
                expected {procedure.expected_blocks.join(" → ")} • actual {procedure.actual_blocks.join(" → ") || "none"}
              </div>
              {procedure.missing_blocks.length ? <div style={{ color: "#fca5a5", marginTop: 4 }}>Missing blocks: {procedure.missing_blocks.join(", ")}</div> : null}
              {procedure.readiness_gates.length ? <div style={{ color: "#94a3b8", marginTop: 4 }}>Gates/checks: {procedure.readiness_gates.slice(0, 10).join(" • ")}</div> : null}
            </div>
          ))}
        </div>
      ) : null}

      {operating?.missing_templates.length ? (
        <div style={{ marginTop: 14 }}>
          <strong>Missing procedure templates</strong>
          <div style={{ color: "#fca5a5", marginTop: 4 }}>{operating.missing_templates.join(", ")}</div>
        </div>
      ) : null}

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
