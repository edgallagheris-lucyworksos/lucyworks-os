"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { saveSession } from "@/lib/session";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type User = {
  id: number;
  name: string;
  role: string;
  email: string;
};

export default function LoginPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [status, setStatus] = useState<string>("");

  useEffect(() => {
    async function loadUsers() {
      const res = await fetch(`${API_BASE}/api/users`, { cache: "no-store" });
      const data = await res.json();
      setUsers(data);
      if (data[0]) setSelectedUserId(String(data[0].id));
    }
    loadUsers();
  }, []);

  async function accessSystem() {
    setStatus("Opening workspace...");
    const res = await fetch(`${API_BASE}/api/auth/login-demo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: Number(selectedUserId) }),
    });
    const data = await res.json();
    saveSession(data.user, data.token);
    setStatus(`Active user: ${data.user.name} (${data.user.role})`);
    router.push("/workspace");
  }

  return (
    <main style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ maxWidth: 720, width: "100%", border: "1px solid #1f2937", borderRadius: 24, padding: 32, background: "#0f172a" }}>
        <h1 style={{ marginTop: 0, fontSize: 36 }}>LucyWorks Access</h1>
        <p style={{ color: "#94a3b8" }}>Role-based entry into the operational system.</p>

        <div style={{ marginTop: 20, display: "grid", gap: 12 }}>
          <select value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value)} style={{ padding: 12, borderRadius: 12 }}>
            {users.map((user) => (
              <option key={user.id} value={user.id}>{user.name} — {user.role}</option>
            ))}
          </select>
          <button onClick={accessSystem} style={{ padding: 14, borderRadius: 12, border: 0, background: "#14b8a6", color: "#020617" }}>
            Enter workspace
          </button>
        </div>

        {status ? <p style={{ marginTop: 16 }}>{status}</p> : null}

        <div style={{ marginTop: 16, display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link href="/workspace">Open workspace</Link>
          <Link href="/">Back home</Link>
        </div>
      </div>
    </main>
  );
}
