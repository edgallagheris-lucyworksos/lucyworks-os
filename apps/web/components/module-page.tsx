"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";

type ModulePageProps = { title: string; endpoint: string };
type LoadState = "loading" | "live" | "unavailable";

const navLinks = [
  { href: "/workspace", label: "Patient Command" },
  { href: "/hospital-board", label: "Hospital Today" },
  { href: "/referral-intake", label: "Referrals" },
  { href: "/system-control", label: "More tools" },
] as const;

function titleCase(value: string) {
  return value.replace(/[-_]+/g, " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function objectEntries(value: unknown) {
  return isRecord(value) ? Object.entries(value) : [];
}

function summaryEntries(data: unknown) {
  const record = isRecord(data) ? data : {};
  const summary = isRecord(record.summary) ? record.summary : null;
  if (summary) return Object.entries(summary).slice(0, 8);
  return Object.entries(record)
    .filter(([, value]) => Array.isArray(value) || ["string", "number", "boolean"].includes(typeof value))
    .slice(0, 8)
    .map(([key, value]) => [key, Array.isArray(value) ? value.length : value] as [string, unknown]);
}

function listSections(data: unknown) {
  return objectEntries(data)
    .filter(([, value]) => Array.isArray(value))
    .slice(0, 8)
    .map(([key, value]) => ({ key, rows: value as unknown[] }));
}

function preview(value: unknown) {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  if (isRecord(value)) {
    const useful = ["patientName", "name", "title", "label", "subject", "role", "status", "room", "area", "nextAction"];
    const hit = useful.map(key => value[key]).find(Boolean);
    if (hit) return String(hit);
    return "Structured record";
  }
  return String(value ?? "Not recorded");
}

export function ModulePage({ title, endpoint }: ModulePageProps) {
  const [data, setData] = useState<unknown>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const payload = await apiGet<unknown>(endpoint);
        if (!active) return;
        setData(payload);
        setState("live");
        setError("");
      } catch (reason) {
        if (!active) return;
        setData(null);
        setState("unavailable");
        setError(reason instanceof Error ? reason.message : "This live service is unavailable");
      }
    }
    void load();
    return () => { active = false; };
  }, [endpoint]);

  const summary = useMemo(() => summaryEntries(data), [data]);
  const sections = useMemo(() => listSections(data), [data]);
  const pageTitle = titleCase(title);

  return <main className="module"><style>{css}</style>
    <header className="moduleHeader">
      <div><span>LucyWorks OS · secondary tool</span><h1>{pageTitle}</h1><p>This is a supporting view. Patient Command and Hospital Today remain the operational sources of truth.</p></div>
      <nav>{navLinks.map(item => <Link href={item.href} key={item.href}>{item.label}</Link>)}</nav>
    </header>

    <section className={`status ${state}`}>
      <b>{state === "live" ? "Live authenticated data" : state === "loading" ? "Loading live data" : "Live data unavailable"}</b>
      <small>{state === "unavailable" ? error : endpoint}</small>
    </section>

    {state === "unavailable" ? <section className="unavailable"><b>Do not use demonstration data as a substitute.</b><p>Return to Patient Command or Hospital Today while this supporting service is unavailable.</p><Link href="/workspace">Open Patient Command</Link></section> : <>
      <section className="summary">
        {summary.length ? summary.map(([key, value]) => <article key={key}><b>{preview(value)}</b><small>{titleCase(key)}</small></article>) : <article><b>—</b><small>{state === "loading" ? "Loading" : "No summary returned"}</small></article>}
      </section>
      <section className="sections">
        {sections.length ? sections.map(section => <article className="panel" key={section.key}><div className="panelHead"><b>{titleCase(section.key)}</b><small>{section.rows.length} items</small></div><div className="chips">{section.rows.slice(0, 12).map((row, index) => <span key={index}>{preview(row)}</span>)}</div></article>) : <article className="panel"><b>No operational list returned</b><p>Use Patient Command as the primary route rather than inferring state from an empty supporting page.</p></article>}
      </section>
    </>}
  </main>;
}

const css = `.module{min-height:100vh;background:#f5f7fb;color:#111827;padding:14px;font-family:Inter,system-ui,sans-serif}.module *{box-sizing:border-box}.moduleHeader{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;background:white;border:1px solid #d8e0ec;border-radius:18px;padding:16px;box-shadow:0 10px 28px rgba(15,23,42,.06)}.moduleHeader span{display:block;text-transform:uppercase;letter-spacing:.14em;color:#2563eb;font-size:11px;font-weight:900}.moduleHeader h1{font-size:clamp(34px,7vw,64px);line-height:.95;margin:6px 0;color:#111827}.moduleHeader p{margin:0;color:#475569}.moduleHeader nav{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.moduleHeader a{border:1px solid #cbd5e1;background:white;color:#0f172a;border-radius:999px;padding:9px 12px;text-decoration:none;font-weight:800}.status{margin:12px 0;border:1px solid #d8e0ec;background:white;border-radius:14px;padding:12px}.status b,.status small{display:block}.status small{color:#64748b;margin-top:3px}.status.live{border-left:6px solid #16a34a}.status.unavailable{border-left:6px solid #dc2626}.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:12px}.summary article,.panel,.unavailable{background:white;border:1px solid #d8e0ec;border-radius:16px;padding:14px}.summary b{display:block;font-size:30px;line-height:1}.summary small{display:block;color:#64748b;margin-top:4px}.sections{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.panelHead{display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid #e5e7eb;padding-bottom:8px;margin-bottom:8px}.panelHead b{font-size:20px}.panelHead small,.panel p,.unavailable p{color:#64748b}.chips{display:flex;flex-wrap:wrap;gap:8px}.chips span{border:1px solid #cbd5e1;background:#f8fafc;border-radius:999px;padding:7px 10px;font-size:13px;color:#0f172a}.unavailable{border-left:7px solid #dc2626}.unavailable a{color:#1d4ed8;font-weight:900}@media(max-width:760px){.moduleHeader{display:grid}.moduleHeader nav{justify-content:stretch}.moduleHeader a{flex:1;text-align:center}.summary{grid-template-columns:repeat(2,minmax(0,1fr))}.summary b{font-size:24px}}`;
