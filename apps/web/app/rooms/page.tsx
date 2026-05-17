"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function RoomsPage() {
  const [rooms, setRooms] = useState<any[]>([]);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/room-states`, { cache: "no-store" });
      setRooms(await res.json());
    }
    load();
  }, []);

  async function setState(id: number, state: string) {
    await fetch(`${API_BASE}/api/room-states/${id}/set?state=${state}`, { method: "POST" });
    location.reload();
  }

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician"]}>
      {() => (
        <HospitalShell title="Rooms" subtitle="Control and state">
          <div style={{ display: "grid", gap: 12 }}>
            {rooms.map((r) => (
              <div key={r.id} style={{ border: "1px solid #1f2937", borderRadius: 12, padding: 12 }}>
                <strong>{r.room_name}</strong> • {r.state}
                <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
                  <button onClick={() => setState(r.id, "occupied")}>Occupied</button>
                  <button onClick={() => setState(r.id, "cleaning")}>Cleaning</button>
                  <button onClick={() => setState(r.id, "available")}>Available</button>
                </div>
              </div>
            ))}
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
