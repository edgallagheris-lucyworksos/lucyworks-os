"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function SchedulePage() {
  const [blocks, setBlocks] = useState<any[]>([]);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/schedule-blocks`, { cache: "no-store" });
      setBlocks(await res.json());
    }
    load();
  }, []);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse"]}>
      {() => (
        <HospitalShell title="Schedule" subtitle="Procedure timeline">
          <div style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            {blocks.map((b) => (
              <div key={b.id} style={{ padding: 12, borderTop: "1px solid #1f2937" }}>
                {b.room_name} • {b.block_type} • {new Date(b.starts_at).toLocaleTimeString()} → {new Date(b.ends_at).toLocaleTimeString()}
              </div>
            ))}
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
