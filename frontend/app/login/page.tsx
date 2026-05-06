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

const FALLBACK_USERS: User[] = [
  { id: 1, name: "Clinical Director", role: "ops_manager", email: "clinical.director@lucyvet.local" },
  { id: 2, name: "Duty Clinician", role: "clinician", email: "clinician@lucyvet.local" },
  { id: 3, name: "Ward Nurse", role: "nurse", email: "nurse@lucyvet.local" },
  { id: 4, name: "Reception / Admin", role: "admin", email: "admin@lucyvet.local" },
];

export default function LoginPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>(FALLBACK_USERS);
  const [selectedUserId, setSelectedUserId] = useState<string>("1");
  const [status, setStatus] = useState<string>("Demo roles available. Backend users will load if connected.");
  const [backendOnline, setBackendOnline] = useState(false);

  useEffect(() => {
    async function loadUsers() {
      try {
        const res = await fetch(`${API_BASE}/api/users`, { cache: "no-store" });
        if (!res.ok) throw new Error(`users ${res.status}`);
        const data = await res.json();
        if (Array.isArray(data) && data.length) {
          setUsers(data);
          setSelectedUserId(String(data[0].id));
          setBackendOnline(true);
          setStatus("Backend connected. Select a role to enter.");
        }
      } catch {
        setUsers(FALLBACK_USERS);
        setSelectedUserId("1");
        setBackendOnline(false);
        setStatus("Backend users unavailable. Using local demo roles so the app still opens.");
      }
    }
    loadUsers();
  }, []);

  async function accessSystem() {
    const selected = users.find((u) => String(u.id) === selectedUserId) || users[0] || FALLBACK_USERS[0];
    setStatus("Opening LucyWorks OS...");

    if (backendOnline) {
      try {
        const res = await fetch(`${API_BASE}/api/auth/login-demo`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: Number(selectedUserId) }),
        });
        if (!res.ok) throw new Error(`login ${res.status}`);
        const data = await res.json();
        saveSession(data.user || selected, data.token || "demo-token");
        router.push("/system-control");
        return;
      } catch {
        setStatus("Backend login failed. Entering with local demo session.");
      }
    }

    saveSession(selected, "local-demo-token");
    router.push("/system-control");
  }

  return (
    <main style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 14, background: "#020617" }}>
      <div style={{ maxWidth: 680, width: "100%", border: "1px solid #1f2937", borderRadius: 14, padding: 18, background: "#0f172a" }}>
        <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>LucyWorks OS access</div>
        <h1 style={{ margin: "8px 0 0", fontSize: 32, letterSpacing: "-0.05em" }}>Open the hospital system</h1>
        <p style={{ color: "#94a3b8" }}>Select a role. If the backend is not connected yet, a local demo session opens System Control so the app is not blocked.</p>

        <div style={{ marginTop: 16, display: "grid", gap: 10 }}>
          <select value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value)} style={{ padding: 12, borderRadius: 10 }}>
            {users.map((user) => (
              <option key={`${user.id}-${user.role}`} value={user.id}>{user.name} — {user.role}</option>
            ))}
          </select>
          <button onClick={accessSystem} style={{ padding: 13, borderRadius: 10, border: "1px solid #14b8a6", background: "#14b8a6", color: "#020617", fontWeight: 950 }}>
            Enter System Control
          </button>
        </div>

        {status ? <p style={{ marginTop: 14, color: backendOnline ? "#86efac" : "#fbbf24" }}>{status}</p> : null}

        <div style={{ marginTop: 14, display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link href="/system-control" style={{ color: "#cbd5e1" }}>System Control</Link>
          <Link href="/" style={{ color: "#cbd5e1" }}>Home</Link>
        </div>
      </div>
    </main>
  );
}
