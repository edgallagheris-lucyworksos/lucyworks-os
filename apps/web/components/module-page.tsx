"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { API_BASE_DEFAULT } from "@lucyworks/shared";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || API_BASE_DEFAULT;

type ModulePageProps = { title: string; endpoint: string };
type LoadState = "loading" | "api" | "fallback" | "offline";

const navLinks = [
  { href: "/hospital-board", label: "Hospital board" },
  { href: "/workspace", label: "Workspace" },
  { href: "/actions", label: "Actions" },
  { href: "/flow-state", label: "Flow state" },
] as const;

function titleCase(value: string) {
  return value.replace(/[-_]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
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
    const useful = ["name", "title", "label", "subject", "role", "status", "room", "area"];
    const hit = useful.map((key) => value[key]).find(Boolean);
    if (hit) return String(hit);
    return Object.values(value).slice(0, 2).map((item) => String(item)).join(" · ");
  }
  return String(value ?? "-");
}

export function ModulePage({ title, endpoint }: ModulePageProps) {
  const [data, setData] = useState<unknown>(null);
  const [state, setState] = useState<LoadState>("loading");

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const response = await fetch(`${API_BASE}${endpoint}`, { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        if (!active) return;
        setData(payload);
        setState("api");
      } catch {
        try {
          const fallback = await fetch("/seed/hospital_snapshot.json", { cache: "no-store" }).then((response) => response.json());
          if (!active) return;
          setData(fallback);
          setState("fallback");
        } catch {
          if (!active) return;
          setData(null);
          setState("offline");
        }
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
      <div>
        <span>LucyWorks OS</span>
        <h1>{pageTitle}</h1>
        <p>Operational view. Data is presented as working cards, not a raw JSON dump.</p>
      </div>
      <nav>{navLinks.map((item) => <Link href={item.href} key={item.href}>{item.label}</Link>)}</nav>
    </header>

    <section className={`status ${state}`}>
      <b>{state === "api" ? "API connected" : state === "fallback" ? "Using local snapshot" : state === "loading" ? "Loading" : "Offline"}</b>
      <small>{endpoint}</small>
    </section>

    <section className="summary">
      {summary.length ? summary.map(([key, value]) => <article key={key}>
        <b>{preview(value)}</b>
        <small>{titleCase(key)}</small>
      </article>) : <article><b>-</b><small>No summary available</small></article>}
    </section>

    <section className="sections">
      {sections.length ? sections.map((section) => <article className="panel" key={section.key}>
        <div className="panelHead"><b>{titleCase(section.key)}</b><small>{section.rows.length} items</small></div>
        <div className="chips">
          {section.rows.slice(0, 12).map((row, index) => <span key={index}>{preview(row)}</span>)}
        </div>
      </article>) : <article className="panel"><b>No operational lists returned</b><p>Use the hospital board as the main control surface while this module is being wired.</p></article>}
    </section>

    <details className="raw"><summary>Raw data</summary><pre>{JSON.stringify(data, null, 2)}</pre></details>
  </main>;
}

const css = `.module{min-height:100vh;background:#f5f7fb;color:#111827;padding:14px;font-family:Inter,system-ui,sans-serif}.module *{box-sizing:border-box}.moduleHeader{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;background:white;border:1px solid #d8e0ec;border-radius:18px;padding:16px;box-shadow:0 10px 28px rgba(15,23,42,.06)}.moduleHeader span{display:block;text-transform:uppercase;letter-spacing:.14em;color:#2563eb;font-size:11px;font-weight:900}.moduleHeader h1{font-size:clamp(34px,7vw,64px);line-height:.95;margin:6px 0;color:#111827}.moduleHeader p{margin:0;color:#475569}.moduleHeader nav{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.moduleHeader a{border:1px solid #cbd5e1;background:white;color:#0f172a;border-radius:999px;padding:9px 12px;text-decoration:none;font-weight:800}.status{margin:12px 0;border:1px solid #d8e0ec;background:white;border-radius:14px;padding:12px}.status b,.status small{display:block}.status small{color:#64748b;margin-top:3px}.status.api{border-left:6px solid #16a34a}.status.fallback{border-left:6px solid #f59e0b}.status.offline{border-left:6px solid #dc2626}.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:12px}.summary article,.panel,.raw{background:white;border:1px solid #d8e0ec;border-radius:16px;padding:14px}.summary b{display:block;font-size:30px;line-height:1}.summary small{display:block;color:#64748b;margin-top:4px}.sections{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.panelHead{display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid #e5e7eb;padding-bottom:8px;margin-bottom:8px}.panelHead b{font-size:20px}.panelHead small,.panel p{color:#64748b}.chips{display:flex;flex-wrap:wrap;gap:8px}.chips span{border:1px solid #cbd5e1;background:#f8fafc;border-radius:999px;padding:7px 10px;font-size:13px;color:#0f172a}.raw{margin-top:12px}.raw summary{cursor:pointer;font-weight:900}.raw pre{overflow:auto;background:#0f172a;color:#e5e7eb;border-radius:12px;padding:12px;font-size:12px}@media(max-width:760px){.moduleHeader{display:grid}.moduleHeader nav{justify-content:stretch}.moduleHeader a{flex:1;text-align:center}.summary{grid-template-columns:repeat(2,minmax(0,1fr))}.summary b{font-size:24px}}`;
