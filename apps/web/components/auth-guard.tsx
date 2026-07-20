"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { getSession, saveSession, type SessionUser } from "@/lib/session";

type AuthGuardChildren = ReactNode | ((user: SessionUser) => ReactNode);

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
      const session = getSession();
      if (!session) {
        if (active) setLoading(false);
        return;
      }
      try {
        const response = await apiFetch("/api/auth/me", { cache: "no-store" });
        if (!response.ok) throw new Error(`identity verification failed: ${response.status}`);
        const data = await response.json();
        const verifiedUser = data.user as SessionUser;
        saveSession(verifiedUser, session.token);
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

  if (loading) return <main style={{ padding: 24 }}>Verifying identity...</main>;

  if (!user) {
    return (
      <main style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
        <h1>Verified login required</h1>
        <p style={{ color: "#94a3b8" }}>{error || "This surface requires a server-verified LucyWorks identity."}</p>
        <Link href="/login">Open login</Link>
      </main>
    );
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <main style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
        <h1>Access restricted</h1>
        <p style={{ color: "#94a3b8" }}>
          {user.name} is verified as {user.role}, but this area needs one of: {allowedRoles.join(", ")}.
        </p>
        <Link href="/workspace">Go to workspace</Link>
      </main>
    );
  }

  return <>{typeof children === "function" ? children(user) : children}</>;
}
