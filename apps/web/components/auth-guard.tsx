"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { saveSession, type SessionUser } from "@/lib/session";

type AuthGuardChildren = ReactNode | ((user: SessionUser) => ReactNode);

function AccessShell({
  title,
  description,
  status,
  statusTone = "amber",
  primaryHref,
  primaryLabel,
  secondaryHref,
  secondaryLabel,
}: {
  title: string;
  description: string;
  status: string;
  statusTone?: "green" | "amber" | "red";
  primaryHref: string;
  primaryLabel: string;
  secondaryHref?: string;
  secondaryLabel?: string;
}) {
  return (
    <main className="access-shell">
      <style>{css}</style>
      <section className="access-card">
        <header>
          <div className="access-brand"><div className="access-mark">LW</div><div><strong>LucyWorks</strong><span>Hospital operations</span></div></div>
          <span className={`access-status ${statusTone}`}>{status}</span>
        </header>
        <div className="access-body">
          <h1>{title}</h1>
          <p>{description}</p>
          <div className="access-actions">
            <Link className="primary" href={primaryHref}>{primaryLabel}</Link>
            {secondaryHref && secondaryLabel ? <Link href={secondaryHref}>{secondaryLabel}</Link> : null}
          </div>
        </div>
        <footer>Secure hospital access</footer>
      </section>
    </main>
  );
}

export function AuthGuard({ children, allowedRoles }: { children: AuthGuardChildren; allowedRoles?: string[] }) {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function verify() {
      try {
        const response = await apiFetch("/api/auth/me", { cache: "no-store" });
        if (!response.ok) throw new Error(`Session verification failed (${response.status})`);
        const data = await response.json();
        const verifiedUser = data.user as SessionUser;
        saveSession(verifiedUser);
        if (active) setUser(verifiedUser);
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Session verification failed");
      } finally {
        if (active) setLoading(false);
      }
    }
    void verify();
    return () => { active = false; };
  }, []);

  if (loading) {
    return <AccessShell title="Checking your session" description="Confirming your identity and access before loading hospital data." status="Checking" primaryHref="/login" primaryLabel="Sign in" />;
  }

  if (!user) {
    return <AccessShell title="Sign in required" description={error || "Your session has ended or could not be verified."} status="Locked" statusTone="red" primaryHref="/login" primaryLabel="Sign in" secondaryHref="/readiness" secondaryLabel="System status" />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <AccessShell title="This area is restricted" description={`Your ${user.role.replaceAll("_", " ")} role does not include access to this workspace.`} status="Restricted" statusTone="amber" primaryHref="/workspace" primaryLabel="My workspace" secondaryHref="/login" secondaryLabel="Change account" />;
  }

  return <>{typeof children === "function" ? children(user) : children}</>;
}

const css = `
.access-shell{min-height:100vh;display:grid;place-items:center;padding:20px;background:#eef2f7;color:#172033;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.access-shell *{box-sizing:border-box}.access-card{width:min(100%,560px);background:#fff;border:1px solid #d8e0e8;border-radius:14px;box-shadow:0 18px 50px rgba(15,23,42,.1);overflow:hidden}.access-card>header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:14px 16px;border-bottom:1px solid #e5eaf0}.access-brand{display:flex;align-items:center;gap:10px}.access-mark{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:linear-gradient(145deg,#163a57,#102a42);color:#fff;font-size:11px;font-weight:900}.access-brand>div:last-child{display:grid}.access-brand strong{font-size:13px;color:#1c3348}.access-brand span{margin-top:1px;color:#748195;font-size:9px}.access-status{border-radius:99px;padding:5px 8px;background:#fff1d9;color:#8f5c13;font-size:9px;font-weight:850;text-transform:uppercase;letter-spacing:.05em}.access-status.red{background:#fbe7e5;color:#943630}.access-status.green{background:#e7f3ed;color:#2d684f}.access-body{padding:30px 22px 26px}.access-body h1{margin:0;color:#152d43;font-size:28px;line-height:1.08;letter-spacing:-.03em}.access-body p{margin:10px 0 0;color:#66768a;font-size:13px;line-height:1.55}.access-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:22px}.access-actions a{display:inline-flex;align-items:center;justify-content:center;min-height:39px;padding:0 13px;border:1px solid #ccd5df;border-radius:8px;color:#2d4a62;text-decoration:none;font-size:11px;font-weight:800;background:#fff}.access-actions a.primary{border-color:#173f5f;background:#173f5f;color:#fff}.access-card>footer{padding:10px 16px;border-top:1px solid #edf0f3;background:#f8fafc;color:#8894a3;font-size:9px;font-weight:700}
`;
