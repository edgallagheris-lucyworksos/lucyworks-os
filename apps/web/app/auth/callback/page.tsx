"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import { saveSession, type SessionUser } from "@/lib/session";

type PendingOIDC = { verifier: string; state: string; redirectUri: string };

export default function AuthCallbackPage() {
  const router = useRouter();
  const [status, setStatus] = useState("Verifying hospital identity...");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    async function completeLogin() {
      try {
        const params = new URLSearchParams(window.location.search);
        const code = params.get("code");
        const returnedState = params.get("state");
        const providerError = params.get("error_description") || params.get("error");
        if (providerError) throw new Error(providerError);
        if (!code || !returnedState) throw new Error("OIDC callback is missing code or state");

        const raw = sessionStorage.getItem("lucyworks_oidc");
        sessionStorage.removeItem("lucyworks_oidc");
        if (!raw) throw new Error("OIDC login state was not found");
        const pending = JSON.parse(raw) as PendingOIDC;
        if (pending.state !== returnedState) throw new Error("OIDC state check failed");

        const response = await fetch(`${API_BASE}/api/auth/oidc/exchange`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, code_verifier: pending.verifier, redirect_uri: pending.redirectUri }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `OIDC exchange failed: ${response.status}`);
        saveSession(data.user as SessionUser, data.accessToken, data.expiresIn);
        if (active) {
          setStatus("Identity verified. Opening LucyWorks...");
          router.replace("/system-control");
        }
      } catch (error) {
        if (active) {
          setFailed(true);
          setStatus(error instanceof Error ? error.message : "OIDC login failed");
        }
      }
    }
    void completeLogin();
    return () => { active = false; };
  }, [router]);

  return <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 20, background: "#020617", color: "white" }}>
    <section style={{ width: "100%", maxWidth: 620, border: "1px solid #334155", borderRadius: 18, padding: 20, background: "#0f172a" }}>
      <h1>{failed ? "Identity verification failed" : "Hospital identity verification"}</h1>
      <p style={{ color: failed ? "#fca5a5" : "#94a3b8" }}>{status}</p>
      {failed ? <Link href="/login" style={{ color: "#5eead4" }}>Return to login</Link> : null}
    </section>
  </main>;
}
