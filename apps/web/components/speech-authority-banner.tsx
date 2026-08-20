"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useOperationalContext } from "@/lib/operational-context";
import { getSession } from "@/lib/session";
import { readSpeechAuthority, type SpeechAuthority } from "@/lib/speech-authority";

export function SpeechAuthorityBanner({ returnTo = "/input" }: { returnTo?: string }) {
  const { premisesRef, siteName } = useOperationalContext();
  const [authority, setAuthority] = useState<SpeechAuthority | null>(null);
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    const session = getSession();
    setSignedIn(Boolean(session?.user));
    setAuthority(readSpeechAuthority(session?.user, premisesRef));
  }, [premisesRef]);

  const href = signedIn
    ? `/speech-authority?returnTo=${encodeURIComponent(returnTo)}`
    : `/login?returnTo=${encodeURIComponent(`/speech-authority?returnTo=${returnTo}`)}`;

  if (authority) {
    return <section className="speech-gate ready">
      <style>{css}</style>
      <div><strong>Speech identity confirmed</strong><span>{authority.userName} · {authority.role.replaceAll("_", " ")} · {siteName}</span><small>Recording authority confirmed {new Date(authority.acknowledgedAt).toLocaleString()}.</small></div>
      <Link href={href}>Review authority →</Link>
    </section>;
  }

  return <section className="speech-gate blocked">
    <style>{css}</style>
    <div><strong>Speech setup required</strong><span>Before using the microphone, confirm who you are and the recording authority for {siteName}.</span><small>This gives the privacy/recording blocker a direct resolution path instead of leaving the microphone disabled.</small></div>
    <Link href={href}>{signedIn ? "Confirm identity & recording authority →" : "Sign in & confirm authority →"}</Link>
  </section>;
}

const css = `
.speech-gate{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px;border-radius:12px;font-family:Inter,system-ui,sans-serif}.speech-gate>div{display:grid;gap:3px}.speech-gate strong{font-size:15px}.speech-gate span{font-size:12px;line-height:1.4}.speech-gate small{font-size:10px;line-height:1.35}.speech-gate a{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:0 12px;border-radius:9px;text-decoration:none;font-size:11px;font-weight:900;white-space:nowrap}.speech-gate.blocked{border:1px solid #f59e0b;background:#fffbeb;color:#92400e}.speech-gate.blocked small{color:#a16207}.speech-gate.blocked a{background:#92400e;color:#fff}.speech-gate.ready{border:1px solid #22c55e;background:#f0fdf4;color:#166534}.speech-gate.ready small{color:#3f7658}.speech-gate.ready a{background:#166534;color:#fff}@media(max-width:650px){.speech-gate{display:grid}.speech-gate a{width:100%;white-space:normal;text-align:center}}
`;
