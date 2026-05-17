"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type StaffLoad = {
  staff_member_id: number;
  name: string;
  role: string;
  skills: string;
  on_shift: boolean;
  active_blocks: number;
  assigned_block_ids: number[];
};

export default function StaffPage() {
  const [staff, setStaff] = useState<StaffLoad[]>([]);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/staff-load`, { cache: "no-store" });
      setStaff(await res.json());
    }
    load();
  }, []);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse"]}>
      {() => (
        <HospitalShell title="Staff" subtitle="Load, shift status and assignments">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
            {staff.map((member) => (
              <section key={member.staff_member_id} style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <strong>{member.name}</strong>
                  <span style={{ color: member.on_shift ? "#22c55e" : "#f59e0b" }}>{member.on_shift ? "on shift" : "off shift"}</span>
                </div>
                <div style={{ color: "#94a3b8", marginTop: 8 }}>{member.role}</div>
                <div style={{ marginTop: 12, fontSize: 32 }}>{member.active_blocks}</div>
                <div style={{ color: "#94a3b8" }}>active assigned blocks</div>
                <div style={{ color: "#94a3b8", marginTop: 10 }}>skills: {member.skills}</div>
                <div style={{ color: "#94a3b8", marginTop: 10 }}>blocks: {member.assigned_block_ids.length ? member.assigned_block_ids.join(", ") : "none"}</div>
              </section>
            ))}
            {!staff.length ? <div style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16 }}>No staff load data returned.</div> : null}
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
