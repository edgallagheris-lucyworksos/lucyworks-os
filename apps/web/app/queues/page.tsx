"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type User = {
  id: number;
  name: string;
  role: string;
};

type WorkItem = {
  id: number;
  title: string;
  urgency: string;
  owner_role: string;
  owner_user_id?: number | null;
  status: string;
  section_name?: string | null;
  room_name?: string | null;
  patient_location_label?: string | null;
  linked_patient_name?: string | null;
  linked_episode_ref?: string | null;
};

function QueuesInner() {
  const [users, setUsers] = useState<User[]>([]);
  const [items, setItems] = useState<WorkItem[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const [usersRes, itemsRes] = await Promise.all([
      fetch(`${API_BASE}/api/users`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/work-items`, { cache: "no-store" }),
    ]);
    setUsers(await usersRes.json());
    setItems(await itemsRes.json());
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  async function setStatus(itemId: number, status: string) {
    await fetch(`${API_BASE}/api/work-items/${itemId}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, actor_name: "Queue UI" }),
    });
    await load();
  }

  async function assign(itemId: number, ownerRole: string, ownerUserId: number | null) {
    await fetch(`${API_BASE}/api/work-items/${itemId}/assign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ owner_role: ownerRole, owner_user_id: ownerUserId, actor_name: "Queue UI" }),
    });
    await load();
  }

  const grouped = items.reduce<Record<string, WorkItem[]>>((acc, item) => {
    acc[item.owner_role] = acc[item.owner_role] || [];
    acc[item.owner_role].push(item);
    return acc;
  }, {});

  return (
    <main style={{ padding: 24, maxWidth: 1280, margin: "0 auto" }}>
      <h1 style={{ fontSize: 36, marginTop: 0 }}>Role Queues</h1>
      <p style={{ color: "#94a3b8" }}>Assignable routed work by operational role.</p>
      {loading ? <p>Loading...</p> : null}
      <div style={{ display: "grid", gap: 16, marginTop: 24 }}>
        {Object.entries(grouped).map(([role, roleItems]) => (
          <section key={role} style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>{role}</div>
            {roleItems.map((item) => {
              const matchingUsers = users.filter((u) => u.role === role);
              return (
                <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <strong>{item.title}</strong>
                    <span>{item.urgency.toUpperCase()} / {item.status}</span>
                  </div>
                  <div style={{ color: "#94a3b8", marginTop: 6 }}>
                    {item.section_name ? `section: ${item.section_name} • ` : ""}
                    {item.room_name ? `room: ${item.room_name} • ` : ""}
                    {item.patient_location_label ? `location: ${item.patient_location_label} • ` : ""}
                    {item.linked_patient_name ? `patient: ${item.linked_patient_name} • ` : ""}
                    {item.linked_episode_ref ? `episode: ${item.linked_episode_ref}` : ""}
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
                    <button onClick={() => setStatus(item.id, "new")} style={{ padding: "8px 10px", borderRadius: 10 }}>Set new</button>
                    <button onClick={() => setStatus(item.id, "in_progress")} style={{ padding: "8px 10px", borderRadius: 10 }}>Set in progress</button>
                    <button onClick={() => setStatus(item.id, "done")} style={{ padding: "8px 10px", borderRadius: 10 }}>Set done</button>
                    {matchingUsers.map((user) => (
                      <button key={user.id} onClick={() => assign(item.id, role, user.id)} style={{ padding: "8px 10px", borderRadius: 10 }}>
                        Assign {user.name}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </section>
        ))}
      </div>
    </main>
  );
}

export default function QueuesPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>{() => <QueuesInner />}</AuthGuard>;
}
