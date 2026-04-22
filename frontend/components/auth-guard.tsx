"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { getSession, type SessionUser } from "@/lib/session";

export function AuthGuard({
  children,
  allowedRoles,
}: {
  children: (user: SessionUser) => ReactNode;
  allowedRoles?: string[];
}) {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<SessionUser | null>(null);

  useEffect(() => {
    const session = getSession();
    setUser(session?.user || null);
    setLoading(false);
  }, []);

  if (loading) return <main style={{ padding: 24 }}>Loading session...</main>;

  if (!user) {
    return (
      <main style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
        <h1>Login required</h1>
        <p style={{ color: "#94a3b8" }}>This surface should be opened through the LucyWorks login flow.</p>
        <Link href="/login">Open login</Link>
      </main>
    );
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <main style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
        <h1>Access restricted</h1>
        <p style={{ color: "#94a3b8" }}>
          {user.name} is logged in as {user.role}, but this area needs one of: {allowedRoles.join(", ")}.
        </p>
        <Link href="/workspace">Go to workspace</Link>
      </main>
    );
  }

  return <>{children(user)}</>;
}
