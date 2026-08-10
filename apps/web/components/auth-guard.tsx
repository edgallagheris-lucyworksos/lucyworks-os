"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { saveSession, type SessionUser } from "@/lib/session";

type AuthGuardChildren = ReactNode | ((user: SessionUser) => ReactNode);

function AccessShell({
  eyebrow,
  title,
  description,
  status,
  statusTone = "amber",
  primaryHref,
  primaryLabel,
  secondaryHref,
  secondaryLabel,
}: {
  eyebrow: string;
  title: string;
  description: string;
  status: string;
  statusTone?: "green" | "amber" | "red";
  primaryHref: string;
  primaryLabel: string;
  secondaryHref?: string;
  secondaryLabel?: string;
}) {
  const statusClass = statusTone === "green" ? "lw-green" : statusTone === "red" ? "lw-red" : "lw-amber";

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: 16,
        background: "radial-gradient(circle at top, #0f172a 0%, #020617 58%)",
      }}
    >
      <section className="lw-command-panel" style={{ width: "100%", maxWidth: 680, overflow: "hidden" }}>
        <div className="lw-command-header" style={{ alignItems: "flex-start", gap: 18 }}>
          <div>
            <div
              style={{
                color: "#2dd4bf",
                fontWeight: 900,
                letterSpacing: "0.09em",
                textTransform: "uppercase",
                fontSize: 13,
              }}
            >
              {eyebrow}
            </div>
            <h1 style={{ margin: "8px 0 10px", fontSize: "clamp(28px, 6vw, 42px)", letterSpacing: "-0.04em", lineHeight: 1.02 }}>
              {title}
            </h1>
            <p style={{ color: "#94a3b8", margin: 0, maxWidth: 560, lineHeight: 1.6 }}>{description}</p>
          </div>
          <span className={`lw-pill ${statusClass}`} style={{ whiteSpace: "nowrap" }}>{status}</span>
        </div>

        <div style={{ padding: 18, display: "grid", gap: 14 }}>
          <div
            style={{
              border: "1px solid rgba(148, 163, 184, 0.18)",
              borderRadius: 14,
              padding: 14,
              background: "rgba(15, 23, 42, 0.55)",
              color: "#cbd5e1",
              lineHeight: 1.5,
            }}
          >
            LucyWorks only opens patient and hospital operations after the API verifies the user, role and active session.
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <Link href={primaryHref} className="lw-pill lw-btn-primary" style={{ padding: "11px 16px", textDecoration: "none" }}>
              {primaryLabel}
            </Link>
            {secondaryHref && secondaryLabel ? (
              <Link href={secondaryHref} className="lw-pill" style={{ padding: "11px 16px", textDecoration: "none" }}>
                {secondaryLabel}
              </Link>
            ) : null}
          </div>

          <div style={{ color: "#64748b", fontSize: 13 }}>
            LucyWorks OS • Development environment • Server-verified access
          </div>
        </div>
      </section>
    </main>
  );
}

export function AuthGuard({
  children,
  allowedRoles,
}: {
  children: AuthGuardChildren;
  allowedRoles?: string[];
}) {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function verify() {
      try {
        const response = await apiFetch("/api/auth/me", { cache: "no-store" });
        if (!response.ok) throw new Error(`identity verification failed: ${response.status}`);
        const data = await response.json();
        const verifiedUser = data.user as SessionUser;
        saveSession(verifiedUser);
        if (active) setUser(verifiedUser);
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "identity verification failed");
      } finally {
        if (active) setLoading(false);
      }
    }
    void verify();
    return () => { active = false; };
  }, []);

  if (loading) {
    return (
      <AccessShell
        eyebrow="LucyWorks OS access"
        title="Checking secure session"
        description="Verifying your hospital identity and role before loading live operational data."
        status="Verifying"
        statusTone="amber"
        primaryHref="/login"
        primaryLabel="Open sign in"
      />
    );
  }

  if (!user) {
    return (
      <AccessShell
        eyebrow="LucyWorks OS access"
        title="Sign in required"
        description={error || "This area requires a verified LucyWorks hospital identity."}
        status="Locked"
        statusTone="red"
        primaryHref="/login"
        primaryLabel="Sign in securely"
        secondaryHref="/readiness"
        secondaryLabel="View system status"
      />
    );
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <AccessShell
        eyebrow="LucyWorks role control"
        title="Access restricted"
        description={`${user.name} is signed in as ${user.role}. This area requires one of: ${allowedRoles.join(", ")}.`}
        status="Role blocked"
        statusTone="amber"
        primaryHref="/workspace"
        primaryLabel="Open my workspace"
        secondaryHref="/login"
        secondaryLabel="Change account"
      />
    );
  }

  return <>{typeof children === "function" ? children(user) : children}</>;
}
