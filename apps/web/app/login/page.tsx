"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import { saveSession, type SessionUser } from "@/lib/session";

type User = { id: number; name: string; role: string; email: string };
type AuthConfig = {
  mode: "local" | "oidc" | string;
  enforcement: string;
  devLoginEnabled: boolean;
  oidc?: { authorizationUrl?: string | null; clientId?: string | null; audience?: string | null; scope?: string | null } | null;
};

const DEVELOPMENT_USERS: User[] = [
  { id: 1, name: "Clinical Director", role: "ops_manager", email: "clinical.director@lucyvet.local" },
  { id: 2, name: "Duty Clinician", role: "clinician", email: "clinician@lucyvet.local" },
  { id: 3, name: "Ward Nurse", role: "nurse", email: "nurse@lucyvet.local" },
  { id: 4, name: "Reception / Admin", role: "admin", email: "admin@lucyvet.local" },
];

function randomValue(bytes = 32) {
  const values = new Uint8Array(bytes);
  crypto.getRandomValues(values);
  return Array.from(values, (value) => value.toString(16).padStart(2, "0")).join("");
}

function base64Url(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export default function LoginPage() {
  const router = useRouter();
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [status, setStatus] = useState("Loading authentication configuration...");
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    async function loadConfig() {
      try {
        const response = await fetch(`${API_BASE}/api/auth/config`, { cache: "no-store" });
        if (!response.ok) throw new Error(`authentication config ${response.status}`);
        const data = await response.json() as AuthConfig;
        setConfig(data);
        if (data.mode === "oidc") setStatus("Hospital identity sign-in is required.");
        else if (data.devLoginEnabled) setStatus("Controlled development login is enabled. Tokens are signed and verified by the API.");
        else setStatus("Development login is disabled. Configure the hospital identity provider or explicitly enable development login.");
      } catch (error) {
        setStatus(error instanceof Error ? error.message : "Authentication service unavailable");
      }
    }
    void loadConfig();
  }, []);

  async function enterDevelopment(user: User) {
    setBusyId(user.id);
    setStatus(`Verifying ${user.name}...`);
    try {
      const response = await fetch(`${API_BASE}/api/auth/dev-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: user.id }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `login failed: ${response.status}`);
      saveSession(data.user as SessionUser, data.accessToken, data.expiresIn);
      router.push("/system-control");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Verified login failed");
      setBusyId(null);
    }
  }

  async function startOidc() {
    const oidc = config?.oidc;
    if (!oidc?.authorizationUrl || !oidc.clientId) {
      setStatus("OIDC authorization URL or client ID is missing.");
      return;
    }
    const verifier = randomValue(48);
    const challenge = base64Url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
    const state = randomValue(24);
    const redirectUri = `${window.location.origin}/auth/callback`;
    sessionStorage.setItem("lucyworks_oidc", JSON.stringify({ verifier, state, redirectUri }));
    const params = new URLSearchParams({
      response_type: "code",
      client_id: oidc.clientId,
      redirect_uri: redirectUri,
      scope: oidc.scope || "openid profile email",
      code_challenge: challenge,
      code_challenge_method: "S256",
      state,
    });
    if (oidc.audience) params.set("audience", oidc.audience);
    window.location.assign(`${oidc.authorizationUrl}?${params.toString()}`);
  }

  const localEnabled = config?.mode === "local" && config.devLoginEnabled;
  const oidcEnabled = config?.mode === "oidc";

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 12, background: "#020617" }}>
      <section className="lw-command-panel" style={{ width: "100%", maxWidth: 760 }}>
        <div className="lw-command-header">
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>LucyWorks OS access</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.05em" }}>Verified identity required</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>The API now validates token signature, issuer, audience, expiry and authorised role before protected actions run.</p>
          </div>
          <span className={`lw-pill ${config ? "lw-green" : "lw-amber"}`}>{config?.mode || "loading"}</span>
        </div>

        <div style={{ padding: 12, display: "grid", gap: 10 }}>
          {oidcEnabled ? <button onClick={() => void startOidc()} className="lw-command-panel" style={{ textAlign: "left", padding: 16, minHeight: 70 }}><strong>Sign in with hospital identity</strong><br /><span style={{ color: "#94a3b8" }}>OIDC authorization code flow with PKCE</span></button> : null}
          {localEnabled ? DEVELOPMENT_USERS.map((user) => (
            <button key={`${user.id}-${user.role}`} onClick={() => void enterDevelopment(user)} disabled={busyId === user.id} className="lw-command-panel" style={{ textAlign: "left", padding: 14, minHeight: 64, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
              <span><strong>{user.name}</strong><br /><span style={{ color: "#94a3b8" }}>{user.role} • {user.email}</span></span>
              <span className="lw-pill lw-btn-primary">{busyId === user.id ? "Verifying" : "Enter"}</span>
            </button>
          )) : null}
          <p style={{ color: config ? "#86efac" : "#fbbf24", margin: 0 }}>{status}</p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}><Link href="/" className="lw-pill">Home</Link></div>
        </div>
      </section>
    </main>
  );
}
