"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";

const PREMISES = "default-premises";

type WorkItem = { id: number; title: string; ownerRole: string; urgency: string; status: string };
type Trigger = {
  triggerRef: string;
  sourceRef: string;
  episodeRef?: string | null;
  status: string;
  mode: string;
  decisionOutcome?: string | null;
  errorCode?: string | null;
  sourceSnapshot: Record<string, unknown>;
  workItems: WorkItem[];
  processedAt?: string | null;
};
type Overview = { configuration: { mode: string }; summary: { count: number; failed: number; active: number; workItems: number }; triggers: Trigger[] };

function label(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase()); }
function tone(value: string) { const normal = value.toLowerCase(); return normal === "failed" ? "red" : ["queued", "processing", "previewed", "preview_only"].includes(normal) ? "amber" : "green"; }

export function AutomationBoardDockV23({ operationalDate }: { operationalDate?: string }) {
  const [date, setDate] = useState(operationalDate || localOperationalDate());
  const [data, setData] = useState<Overview | null>(null);
  const [status, setStatus] = useState("Loading block automation");

  useEffect(() => { if (operationalDate) setDate(operationalDate); }, [operationalDate]);

  const refresh = useCallback(async () => {
    try {
      const result = await apiGet<Overview>(`/api/v23/automation/overview?premises_ref=${PREMISES}&source_type=operational_delay&operational_date=${date}&limit=500`);
      setData(result);
      setStatus(`Recorded block automation · ${result.summary.count} trigger${result.summary.count === 1 ? "" : "s"}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Block automation unavailable");
    }
  }, [date]);

  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 15_000); return () => window.clearInterval(timer); }, [refresh]);

  const latestByBlock = useMemo(() => {
    const map = new Map<string, Trigger>();
    for (const trigger of data?.triggers || []) if (!map.has(trigger.sourceRef)) map.set(trigger.sourceRef, trigger);
    return [...map.values()];
  }, [data]);

  return <section className="abd"><style>{css}</style><header><div><span>AUTOMATION EVIDENCE ON THE MASTER BOARD</span><h2>Recorded delays and owned coordination</h2><p>{status}. LucyWorks has not rescheduled care or made a clinical decision.</p></div><nav>{operationalDate ? <b>{date}</b> : <label>Date<input type="date" value={date} onChange={event => setDate(event.target.value)} /></label>}<button onClick={() => void refresh()}>Refresh</button><Link href="/automation-control">Open authority</Link></nav></header>
    <div className="summary"><article className={tone(data?.configuration.mode || "disabled")}><b>{label(data?.configuration.mode || "disabled")}</b><small>site mode</small></article><article className={data?.summary.failed ? "red" : "green"}><b>{data?.summary.failed || 0}</b><small>failed delay triggers</small></article><article><b>{latestByBlock.length}</b><small>blocks with evidence</small></article><article><b>{data?.summary.workItems || 0}</b><small>owned work items</small></article></div>
    {latestByBlock.length ? <div className="rows">{latestByBlock.map(trigger => {
      const procedure = String(trigger.sourceSnapshot.procedureName || "Operational block");
      const area = String(trigger.sourceSnapshot.areaRef || "Area not recorded");
      const delay = String(trigger.sourceSnapshot.derivedDelayBand || "under_15");
      return <article className={tone(trigger.status)} key={trigger.sourceRef}><div><small>{trigger.sourceRef}</small><b>{procedure}</b><span>{label(area)} · {label(delay)} · {label(trigger.status)}</span></div><div className="work">{trigger.workItems.length ? trigger.workItems.map(item => <span key={item.id}>{item.title} · {label(item.ownerRole)}</span>) : <span>No work created from this state.</span>}</div>{trigger.errorCode ? <strong>{trigger.errorCode}</strong> : null}</article>;
    })}</div> : <div className="empty">No recorded delay automation exists for this operating date.</div>}
  </section>;
}

const css = `
.abd{background:#071019;color:white;border-radius:16px;padding:13px;margin:9px 7px;font-family:Inter,system-ui,sans-serif}.abd *{box-sizing:border-box}.abd>header{display:flex;justify-content:space-between;gap:14px}.abd header span{color:#2dd4bf;font-size:10px;font-weight:950;letter-spacing:.13em}.abd h2{font-size:28px;margin:4px 0}.abd p{color:#b6c2d1;margin:0}.abd nav{display:flex;gap:7px;align-items:flex-end;flex-wrap:wrap}.abd nav label{display:grid;gap:3px;font-size:10px;font-weight:900}.abd nav input,.abd nav button,.abd nav a,.abd nav b{min-height:40px;border:1px solid #475569;border-radius:999px;background:#0f172a;color:white;padding:9px 11px;text-decoration:none;font:inherit;font-weight:900}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:10px}.summary article{background:#111c29;border-top:5px solid #64748b;border-radius:9px;padding:8px}.summary article.red{border-top-color:#ef4444}.summary article.amber{border-top-color:#f59e0b}.summary article.green{border-top-color:#22c55e}.summary b{display:block;font-size:20px}.summary small{color:#b6c2d1}.rows{display:grid;gap:7px;margin-top:9px}.rows>article{display:grid;grid-template-columns:minmax(180px,1fr) minmax(220px,2fr) auto;gap:9px;align-items:center;border:1px solid #334155;border-left:6px solid #22c55e;border-radius:9px;padding:9px;background:#0f172a}.rows>article.red{border-left-color:#ef4444}.rows>article.amber{border-left-color:#f59e0b}.rows>article>div:first-child{display:grid;gap:2px}.rows small,.rows span{color:#cbd5e1}.work{display:flex;gap:5px;flex-wrap:wrap}.work span{border:1px solid #475569;border-radius:999px;padding:5px 7px;font-size:11px}.rows strong{color:#fecaca}.empty{margin-top:9px;border:1px dashed #475569;border-radius:9px;padding:10px;color:#cbd5e1}@media(max-width:800px){.abd>header{display:grid}.summary{grid-template-columns:1fr 1fr}.rows>article{grid-template-columns:1fr}.abd nav{align-items:stretch}.abd nav>*{flex:1;text-align:center}}`;
