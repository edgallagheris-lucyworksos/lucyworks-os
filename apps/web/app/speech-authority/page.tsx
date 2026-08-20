"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { useOperationalContext } from "@/lib/operational-context";
import { saveSpeechAuthority, SPEECH_NOTICE_VERSION } from "@/lib/speech-authority";
import type { SessionUser } from "@/lib/session";

const roles = ["admin", "ops_manager", "hospital_director", "governance_lead", "clinical_director", "senior_clinician", "supervisor", "clinician", "nurse"];

function safeReturnTo(value: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/input";
  return value;
}

function SpeechAuthorityInner({ user }: { user: SessionUser }) {
  const { premisesRef, siteName } = useOperationalContext();
  const [returnTo, setReturnTo] = useState("/input");
  const [confirmed, setConfirmed] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    setReturnTo(safeReturnTo(new URLSearchParams(window.location.search).get("returnTo")));
  }, []);

  function confirm() {
    if (!confirmed || !premisesRef) return;
    saveSpeechAuthority(user, premisesRef);
    setDone(true);
  }

  return <main className="sa">
    <style>{css}</style>
    <section className="sa-card">
      <header><span>LUCYWORKS · SPEECH ACCESS</span><h1>Confirm identity & recording authority</h1><p>Speech capture must know who is acting, which hospital context applies, and that the organisation recording process has been completed.</p></header>

      <div className="sa-facts">
        <div><b>Signed in as</b><span>{user.name}</span></div>
        <div><b>Role</b><span>{user.role.replaceAll("_", " ")}</span></div>
        <div><b>Hospital</b><span>{siteName}</span></div>
        <div><b>Premises reference</b><span>{premisesRef}</span></div>
      </div>

      {!done ? <>
        <section className="sa-notice">
          <h2>Recording authority</h2>
          <p>This does not create owner/client consent by itself and does not replace the hospital's lawful-basis process. It records that the signed-in staff member has followed the organisation's recording notice and authorised recording process for this hospital context.</p>
          <label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>I confirm I have completed the organisation recording notice and authorised recording process. LucyWorks raw-audio retention is off for this speech workflow.</span></label>
          <small>Notice version: {SPEECH_NOTICE_VERSION}</small>
        </section>
        <div className="sa-actions"><Link href={returnTo}>Cancel</Link><button type="button" disabled={!confirmed || !premisesRef} onClick={confirm}>Confirm and continue</button></div>
      </> : <section className="sa-done"><strong>Speech authority confirmed</strong><p>{user.name} · {user.role.replaceAll("_", " ")} · {siteName}</p><Link href={returnTo}>Return to speech capture →</Link></section>}

      <footer>Need another account? <Link href={`/login?returnTo=${encodeURIComponent(`/speech-authority?returnTo=${returnTo}`)}`}>Sign in as someone else</Link>.</footer>
    </section>
  </main>;
}

export default function SpeechAuthorityPage() {
  return <AuthGuard allowedRoles={roles}>{user => <SpeechAuthorityInner user={user} />}</AuthGuard>;
}

const css = `
.sa{min-height:100vh;display:grid;place-items:start center;padding:18px;background:#eef2f7;color:#172033;font-family:Inter,system-ui,sans-serif}.sa *{box-sizing:border-box}.sa-card{width:min(100%,760px);overflow:hidden;border:1px solid #ccd6e0;border-radius:16px;background:#fff;box-shadow:0 18px 45px rgba(15,23,42,.08)}.sa-card>header{padding:22px;background:#071019;color:#fff}.sa-card>header span{color:#2dd4bf;font-size:10px;font-weight:950;letter-spacing:.12em}.sa-card h1{margin:6px 0;font-size:32px;line-height:1.05}.sa-card>header p{margin:0;color:#b6c2d1;line-height:1.5}.sa-facts{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:#dbe3eb;border-bottom:1px solid #dbe3eb}.sa-facts div{display:grid;gap:3px;padding:12px;background:#fff}.sa-facts b{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:#64748b}.sa-facts span{text-transform:capitalize;font-weight:800}.sa-notice{display:grid;gap:9px;margin:14px;padding:14px;border:1px solid #cbd5e1;border-radius:12px;background:#f8fafc}.sa-notice h2{margin:0}.sa-notice p{margin:0;color:#526174;line-height:1.5}.sa-notice label{display:grid;grid-template-columns:24px 1fr;gap:9px;align-items:start;padding:11px;border:1px solid #99b7ad;border-radius:10px;background:#f0fdfa;font-weight:750;line-height:1.45}.sa-notice input{width:20px;height:20px}.sa-notice small{color:#718096}.sa-actions{display:flex;justify-content:flex-end;gap:8px;padding:0 14px 14px}.sa-actions a,.sa-actions button,.sa-done a{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 14px;border:1px solid #64748b;border-radius:9px;background:#fff;color:#172033;text-decoration:none;font-weight:850}.sa-actions button,.sa-done a{border-color:#0f766e;background:#0f766e;color:#fff}.sa-actions button:disabled{opacity:.45}.sa-done{display:grid;gap:8px;margin:14px;padding:16px;border:1px solid #22c55e;border-radius:12px;background:#f0fdf4;color:#166534}.sa-done strong{font-size:22px}.sa-done p{margin:0}.sa-done a{width:max-content}.sa-card>footer{padding:11px 14px;border-top:1px solid #e5eaf0;background:#f8fafc;color:#68778a;font-size:11px}.sa-card>footer a{color:#1d4ed8;font-weight:800}@media(max-width:600px){.sa{padding:8px}.sa-card h1{font-size:27px}.sa-facts{grid-template-columns:1fr}.sa-actions{display:grid}.sa-actions a,.sa-actions button{width:100%}}
`;
