"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type ConflictItem = {
  type: string;
  severity: string;
  detail: string;
};

type ConflictAction = {
  id: number;
  conflict_type: string;
  severity: string;
  detail: string;
  status: string;
  linked_work_item_id?: number | null;
  resolution_note?: string | null;
};

export default function ConflictsPage() {
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [actions, setActions] = useState<ConflictAction[]>([]);
  const [status, setStatus] = useState("");

  async function load() {
    const [conflictRes, actionRes] = await Promise.all([
      fetch(`${API_BASE}/api/conflicts`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/conflict-actions`, { cache: "no-store" }),
    ]);
    const conflictData = await conflictRes.json();
    setConflicts(conflictData.conflicts || []);
    setActions(await actionRes.json());
  }

  useEffect(() => {
    load();
  }, []);

  async function convert(conflict: ConflictItem) {
    setStatus("Creating work from conflict...");
    await fetch(`${API_BASE}/api/conflicts/to-work?conflict_type=${encodeURIComponent(conflict.type)}&severity=${encodeURIComponent(conflict.severity)}&detail=${encodeURIComponent(conflict.detail)}`, { method: "POST" });
    setStatus("Conflict converted to work.");
    await load();
  }

  async function resolve(id: number) {
    setStatus("Resolving conflict action...");
    await fetch(`${API_BASE}/api/conflict-actions/${id}/resolve?note=${encodeURIComponent("Resolved from Conflicts page")}`, { method: "POST" });
    setStatus("Conflict action resolved.");
    await load();
  }

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Conflicts" subtitle="Operational failures, actions and resolution">
          {status ? <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12, marginBottom: 16, background: "#0f172a" }}>{status}</div> : null}

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden", marginBottom: 16 }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Detected conflicts</div>
            {conflicts.map((conflict, index) => (
              <div key={`${conflict.type}-${index}`} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <strong>{conflict.type}</strong>
                  <span>{conflict.severity}</span>
                </div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{conflict.detail}</div>
                <div style={{ marginTop: 10, display: "flex", gap: 12, flexWrap: "wrap" }}>
                  <button onClick={() => convert(conflict)} style={{ padding: "8px 10px", borderRadius: 10, background: "#14b8a6", color: "#020617", border: 0 }}>Convert to work</button>
                  <Link href="/schedule">Open schedule</Link>
                  <Link href="/episodes">Open episodes</Link>
                </div>
              </div>
            ))}
            {!conflicts.length ? <div style={{ padding: 16 }}>No conflicts currently detected.</div> : null}
          </section>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Conflict actions</div>
            {actions.map((action) => (
              <div key={action.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <strong>{action.conflict_type}</strong>
                  <span>{action.status} • {action.severity}</span>
                </div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{action.detail}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>linked work #{action.linked_work_item_id || "-"}</div>
                {action.status !== "resolved" ? <button onClick={() => resolve(action.id)} style={{ marginTop: 10, padding: "8px 10px", borderRadius: 10 }}>Resolve</button> : null}
              </div>
            ))}
            {!actions.length ? <div style={{ padding: 16 }}>No conflict actions yet.</div> : null}
          </section>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
