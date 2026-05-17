"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { saveSession } from "@/lib/session";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type User = { id: number; name: string; role: string; email: string };

const FALLBACK_USERS: User[] = [
  { id: 1, name: "Clinical Director", role: "ops_manager", email: "clinical.director@lucyvet.local" },
  { id: 2, name: "Duty Clinician", role: "clinician", email: "clinician@lucyvet.local" },
  { id: 3, name: "Ward Nurse", role: "nurse", email: "nurse@lucyvet.local" },
  { id: 4, name: "Reception / Admin", role: "admin", email: "admin@lucyvet.local" },
];

export default function LoginPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>(FALLBACK_USERS);
  const [status, setStatus] = useState("Tap a role to enter. Backend users will load if available.");
  const [backendOnline, setBackendOnline] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    async function loadUsers() {
      try {
        const res = await fetch(`${API_BASE}/api/users`, { cache: "no-store" });
        if (!res.ok) throw new Error(`users ${res.status}`);
        const data = await res.json();
        if (Array.isArray(data) && data.length) {
          setUsers(data);
          setBackendOnline(true);
          setStatus("Backend connected. Tap a role to enter.");
        }
      } catch {
        setUsers(FALLBACK_USERS);
        setBackendOnline(false);
        setStatus("Backend user list unavailable. Local demo roles are active so login still works.");
      }
    }
    loadUsers();
  }, []);

  async function enter(user: User) {
    setBusyId(user.id);
    setStatus(`Opening as ${user.name}...`);
    if (backendOnline) {
      try {
        const res = await fetch(`${API_BASE}/api/auth/login-demo`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: user.id }),
        });
        if (!res.ok) throw new Error(`login ${res.status}`);
        const data = await res.json();
        saveSession(data.user || user, data.token || "demo-token");
        router.push("/system-control");
        return;
      } catch {
        setStatus("Backend login failed. Opening with local demo session.");
      }
    }
    saveSession(user, "local-demo-token");
    router.push("/system-control");
  }

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 12, background: "#020617" }}>
      <section className="lw-command-panel" style={{ width: "100%", maxWidth: 760 }}>
        <div className="lw-command-header">
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>LucyWorks OS access</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.05em" }}>Tap role. Enter system.</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>No typing required for login. This removes the mobile dropdown/input failure.</p>
          </div>
          <span className={`lw-pill ${backendOnline ? "lw-green" : "lw-amber"}`}>{backendOnline ? "backend users" : "local roles"}</span>
        </div>

        <div style={{ padding: 12, display: "grid", gap: 10 }}>
          {users.map((user) => (
            <button
              key={`${user.id}-${user.role}`}
              onClick={() => enter(user)}
              disabled={busyId === user.id}
              className="lw-command-panel"
              style={{ textAlign: "left", padding: 14, minHeight: 64, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}
            >
              <span><strong>{user.name}</strong><br /><span style={{ color: "#94a3b8" }}>{user.role} • {user.email}</span></span>
              <span className="lw-pill lw-btn-primary">{busyId === user.id ? "Opening" : "Enter"}</span>
            </button>
          ))}
          <p style={{ color: backendOnline ? "#86efac" : "#fbbf24", margin: 0 }}>{status}</p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <Link href="/system-control" className="lw-pill">System Control</Link>
            <Link href="/" className="lw-pill">Home</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
