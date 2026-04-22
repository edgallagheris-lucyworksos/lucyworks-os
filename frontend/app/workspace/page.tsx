"use client";

import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { clearSession } from "@/lib/session";

const roleLinks: Record<string, { href: string; label: string }[]> = {
  ops_manager: [
    { href: "/command", label: "Clinical Director / Command" },
    { href: "/consult", label: "Consult Rooms" },
    { href: "/ward", label: "Ward / ICU" },
    { href: "/theatre", label: "Theatre / Recovery" },
    { href: "/queues", label: "Queues" },
    { href: "/audit", label: "Audit" },
    { href: "/input", label: "New input" },
  ],
  clinician: [
    { href: "/command", label: "Clinical Director / Command" },
    { href: "/consult", label: "Consult Rooms" },
    { href: "/ward", label: "Ward / ICU" },
    { href: "/theatre", label: "Theatre / Recovery" },
    { href: "/queues", label: "Queues" },
    { href: "/audit", label: "Audit" },
  ],
  nurse: [
    { href: "/ward", label: "Ward / ICU" },
    { href: "/theatre", label: "Theatre / Recovery" },
    { href: "/queues", label: "Queues" },
    { href: "/input", label: "New input" },
  ],
  admin: [
    { href: "/consult", label: "Consult Rooms" },
    { href: "/input", label: "New input" },
    { href: "/queues", label: "Queues" },
    { href: "/audit", label: "Audit" },
  ],
};

export default function WorkspacePage() {
  return (
    <AuthGuard>
      {(user) => (
        <main style={{ padding: 24, maxWidth: 980, margin: "0 auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <h1 style={{ marginTop: 0, fontSize: 36 }}>Workspace</h1>
              <p style={{ color: "#94a3b8" }}>
                Logged in as {user.name} • {user.role}
              </p>
            </div>
            <button
              onClick={() => {
                clearSession();
                window.location.href = "/login";
              }}
              style={{ padding: "10px 12px", borderRadius: 10 }}
            >
              Sign out
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginTop: 20 }}>
            {(roleLinks[user.role] || []).map((item) => (
              <Link key={item.href} href={item.href} style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 18, background: "#0f172a" }}>
                <strong>{item.label}</strong>
                <div style={{ color: "#94a3b8", marginTop: 8 }}>{item.href}</div>
              </Link>
            ))}
          </div>
        </main>
      )}
    </AuthGuard>
  );
}
