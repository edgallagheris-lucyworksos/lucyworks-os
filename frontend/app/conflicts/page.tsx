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

export default function ConflictsPage() {
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/conflicts`, { cache: "no-store" });
      const data = await res.json();
      setConflicts(data.conflicts || []);
    }
    load();
  }, []);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Conflicts" subtitle="Operational failures and overlaps">
          <div style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            {conflicts.map((conflict, index) => (
              <div key={`${conflict.type}-${index}`} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <strong>{conflict.type}</strong>
                  <span>{conflict.severity}</span>
                </div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{conflict.detail}</div>
                <div style={{ marginTop: 8, display: "flex", gap: 12, flexWrap: "wrap" }}>
                  <Link href="/schedule">Open schedule</Link>
                  <Link href="/episodes">Open episodes</Link>
                  <Link href="/queues">Open queues</Link>
                </div>
              </div>
            ))}
            {!conflicts.length ? <div style={{ padding: 16 }}>No conflicts currently detected.</div> : null}
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
