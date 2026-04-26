"use client";

import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Shift = {
  id: number;
  staff_member_id: number;
  department: string;
  starts_at: string;
  ends_at: string;
  shift_type: string;
  status: string;
};

type StaffLoad = {
  staff_member_id: number;
  name: string;
  role: string;
  skills: string;
  on_shift: boolean;
  active_blocks: number;
  assigned_block_ids: number[];
};

function time(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function RotaPage() {
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [staff, setStaff] = useState<StaffLoad[]>([]);

  useEffect(() => {
    async function load() {
      const [shiftRes, staffRes] = await Promise.all([
        fetch(`${API_BASE}/api/shifts`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/staff-load`, { cache: "no-store" }),
      ]);
      setShifts(await shiftRes.json());
      setStaff(await staffRes.json());
    }
    load();
  }, []);

  const staffById = useMemo(() => {
    const map: Record<number, StaffLoad> = {};
    for (const member of staff) map[member.staff_member_id] = member;
    return map;
  }, [staff]);

  const roleCoverage = useMemo(() => {
    const roles = ["ops_manager", "clinician", "nurse", "admin"];
    return roles.map((role) => {
      const members = staff.filter((s) => s.role === role);
      const onShift = members.filter((s) => s.on_shift);
      const activeBlocks = members.reduce((sum, s) => sum + s.active_blocks, 0);
      return { role, total: members.length, onShift: onShift.length, activeBlocks };
    });
  }, [staff]);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse"]}>
      {() => (
        <HospitalShell title="Rota" subtitle="Shift coverage, role pressure and live workload">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 18 }}>
            {roleCoverage.map((role) => (
              <section key={role.role} style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}>
                <strong>{role.role}</strong>
                <div style={{ marginTop: 12, fontSize: 30 }}>{role.onShift}/{role.total}</div>
                <div style={{ color: "#94a3b8" }}>on shift</div>
                <div style={{ color: "#94a3b8", marginTop: 8 }}>{role.activeBlocks} assigned active blocks</div>
              </section>
            ))}
          </div>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden", marginBottom: 18 }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Shift list</div>
            {shifts.map((shift) => {
              const member = staffById[shift.staff_member_id];
              return (
                <div key={shift.id} style={{ padding: 16, borderTop: "1px solid #1f2937", display: "grid", gap: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <strong>{member?.name || `Staff #${shift.staff_member_id}`}</strong>
                    <span>{time(shift.starts_at)} → {time(shift.ends_at)}</span>
                  </div>
                  <div style={{ color: "#94a3b8" }}>{member?.role || "unknown role"} • {shift.department} • {shift.shift_type} • {shift.status}</div>
                </div>
              );
            })}
            {!shifts.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No shifts returned.</div> : null}
          </section>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Load warnings</div>
            {staff.filter((s) => s.active_blocks >= 3 || !s.on_shift).map((member) => (
              <div key={member.staff_member_id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <strong>{member.name}</strong>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>
                  {member.on_shift ? "on shift" : "off shift"} • {member.active_blocks} active blocks • {member.skills}
                </div>
              </div>
            ))}
            {!staff.filter((s) => s.active_blocks >= 3 || !s.on_shift).length ? <div style={{ padding: 16, color: "#94a3b8" }}>No rota warnings currently.</div> : null}
          </section>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
