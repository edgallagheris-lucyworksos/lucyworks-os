"use client";

import { useState } from "react";
import { apiGet, apiJson, apiPost } from "@/lib/api";

type ReconciliationItem = {
  itemRef: string;
  rowNumber: number;
  status: string;
  issueType: string;
  detail: string;
  sourceRecord: Record<string, unknown>;
  suggestedMatch: Record<string, unknown>;
};

type BatchDetail = {
  batch: null | {
    batchRef: string;
    sourceType: string;
    sourceName: string;
    status: string;
    rowCount: number;
    acceptedCount: number;
    rejectedCount: number;
    summary: Record<string, unknown>;
    createdAt: string;
  };
  items: ReconciliationItem[];
};

type PreviewResponse = {
  batchRef: string;
  status: string;
  rowCount: number;
  acceptedCount: number;
  rejectedCount: number;
};

const DEFAULT_CSV = `patientName,procedureName,areaRef,startsAt,endsAt,episodeRef,leadStaffRef
Example dog,MRI,mri,2026-07-20T09:00:00Z,2026-07-20T10:00:00Z,example-episode,1`;

function pretty(value: unknown) {
  return JSON.stringify(value, null, 2);
}

export function HospitalImportManager() {
  const [sourceName, setSourceName] = useState("hospital export");
  const [sourceType, setSourceType] = useState("csv");
  const [content, setContent] = useState(DEFAULT_CSV);
  const [batchRef, setBatchRef] = useState("");
  const [detail, setDetail] = useState<BatchDetail | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("Preview an export. Nothing writes to the board until validation and reconciliation are complete.");

  async function loadBatch(ref: string) {
    const data = await apiGet<BatchDetail>(`/api/hospital-ops/imports/${ref}`);
    setDetail(data);
    setBatchRef(ref);
    setEdits((current) => {
      const next = { ...current };
      for (const item of data.items) {
        if (!next[item.itemRef]) next[item.itemRef] = pretty(item.suggestedMatch || item.sourceRecord);
      }
      return next;
    });
    return data;
  }

  async function preview() {
    setStatus("Validating export in preview mode...");
    try {
      const data = await apiPost<PreviewResponse>("/api/hospital-ops/imports/preview", {
        sourceType,
        sourceName,
        premisesRef: "default-premises",
        content,
        mapping: {},
      });
      await loadBatch(data.batchRef);
      setStatus(`${data.acceptedCount} rows accepted; ${data.rejectedCount} require reconciliation.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Preview failed");
    }
  }

  async function resolve(item: ReconciliationItem) {
    setStatus(`Resolving row ${item.rowNumber}...`);
    try {
      const correctedRecord = JSON.parse(edits[item.itemRef] || "{}");
      await apiJson(`/api/hospital-ops/imports/${batchRef}/items/${item.itemRef}/resolve`, {
        method: "PATCH",
        body: JSON.stringify({ correctedRecord }),
      });
      const next = await loadBatch(batchRef);
      setStatus(next.batch?.rejectedCount ? `${next.batch.rejectedCount} rows still require reconciliation.` : "All rows reconciled. Import is ready to commit.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Resolution failed");
    }
  }

  async function commit() {
    if (!batchRef) return;
    setStatus("Committing accepted, reconciled rows through versioned commands...");
    try {
      const result = await apiPost<{ createdCount: number }>(`/api/hospital-ops/imports/${batchRef}/commit`, {});
      await loadBatch(batchRef);
      setStatus(`${result.createdCount} canonical operational blocks committed. Constraint checks have been rerun.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Commit failed");
    }
  }

  return <main className="him"><style>{css}</style>
    <header>
      <div><span>LucyWorks OS · controlled ingestion</span><h1>Import and reconciliation</h1><p>Vendor, PIMS and spreadsheet exports are previewed, normalised and reconciled before they can create canonical hospital work.</p></div>
      <nav><a href="/hospital-board">Master board</a><a href="/integrations">Integrations</a><a href="/system-control">System control</a></nav>
    </header>

    <section className="status">{status}</section>

    <section className="layout">
      <article className="panel source">
        <h2>1. Preview source data</h2>
        <label>Source name<input value={sourceName} onChange={(event) => setSourceName(event.target.value)} /></label>
        <label>Format<select value={sourceType} onChange={(event) => setSourceType(event.target.value)}><option value="csv">CSV</option><option value="json">JSON</option></select></label>
        <label>Export content<textarea value={content} onChange={(event) => setContent(event.target.value)} /></label>
        <button onClick={() => void preview()}>Validate and preview</button>
      </article>

      <article className="panel summary">
        <h2>2. Batch status</h2>
        {detail?.batch ? <>
          <div className="metrics"><div><b>{detail.batch.rowCount}</b><small>source rows</small></div><div><b>{detail.batch.acceptedCount}</b><small>accepted</small></div><div className={detail.batch.rejectedCount ? "bad" : "good"}><b>{detail.batch.rejectedCount}</b><small>unresolved</small></div></div>
          <p><strong>{detail.batch.batchRef}</strong><br />{detail.batch.sourceName} · {detail.batch.status}</p>
          <button disabled={detail.batch.rejectedCount > 0 || detail.batch.status === "committed"} onClick={() => void commit()}>{detail.batch.status === "committed" ? "Committed" : "Commit reconciled import"}</button>
        </> : <p>No preview batch loaded.</p>}
      </article>
    </section>

    <section className="panel reconciliation">
      <h2>3. Reconciliation queue</h2>
      {detail?.items.length ? detail.items.map((item) => <article key={item.itemRef} className={item.status === "resolved" ? "resolved" : "open"}>
        <div className="itemHead"><div><b>Row {item.rowNumber} · {item.issueType}</b><p>{item.detail}</p></div><span>{item.status}</span></div>
        <div className="compare"><section><h3>Source record</h3><pre>{pretty(item.sourceRecord)}</pre></section><section><h3>Corrected canonical record</h3><textarea disabled={item.status === "resolved"} value={edits[item.itemRef] || "{}"} onChange={(event) => setEdits({ ...edits, [item.itemRef]: event.target.value })} /></section></div>
        {item.status !== "resolved" ? <button onClick={() => void resolve(item)}>Validate corrected row</button> : null}
      </article>) : <p>No reconciliation items. Accepted rows remain in preview until the batch is explicitly committed.</p>}
    </section>
  </main>;
}

const css = `.him{min-height:100vh;background:#edf2f7;color:#0f172a;padding:12px;font-family:Inter,system-ui,sans-serif}.him *{box-sizing:border-box}.him header{display:flex;justify-content:space-between;gap:14px;background:#071019;color:#fff;border-radius:18px;padding:17px}.him header span{color:#2dd4bf;text-transform:uppercase;font-size:11px;font-weight:900;letter-spacing:.13em}.him h1{font-size:clamp(34px,6vw,62px);line-height:.95;margin:6px 0}.him header p{color:#94a3b8}.him nav{display:flex;gap:7px;flex-wrap:wrap;align-content:flex-start}.him a,.him button{border:1px solid #334155;border-radius:999px;background:#0f172a;color:#fff;padding:9px 12px;text-decoration:none;font-weight:800;cursor:pointer}.him button:disabled{opacity:.45;cursor:not-allowed}.status,.panel{background:#fff;border:1px solid #cbd5e1;border-radius:14px;padding:12px}.status{margin:10px 0;color:#334155;font-weight:800}.layout{display:grid;grid-template-columns:1.25fr .75fr;gap:10px}.panel h2{margin-top:0}.panel label{display:grid;gap:4px;margin:9px 0;font-size:12px;font-weight:800;color:#475569}.panel input,.panel select,.panel textarea{width:100%;border:1px solid #cbd5e1;border-radius:9px;padding:9px;background:#fff;color:#0f172a;font:inherit}.source textarea{min-height:260px;font-family:monospace}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.metrics div{border:1px solid #e2e8f0;border-top:5px solid #64748b;border-radius:10px;padding:9px}.metrics .bad{border-top-color:#dc2626}.metrics .good{border-top-color:#16a34a}.metrics b{display:block;font-size:28px}.metrics small{color:#64748b}.reconciliation{margin-top:10px}.reconciliation>article{border:1px solid #e2e8f0;border-left:6px solid #dc2626;border-radius:12px;padding:10px;margin-bottom:9px}.reconciliation>article.resolved{border-left-color:#16a34a;background:#f0fdf4}.itemHead{display:flex;justify-content:space-between;gap:10px}.itemHead p{margin:4px 0;color:#475569}.itemHead span{text-transform:uppercase;font-size:11px;font-weight:900}.compare{display:grid;grid-template-columns:1fr 1fr;gap:9px}.compare section{min-width:0}.compare h3{font-size:13px}.compare pre,.compare textarea{width:100%;min-height:220px;overflow:auto;border:1px solid #cbd5e1;border-radius:9px;padding:9px;background:#f8fafc;font-family:monospace;font-size:12px;white-space:pre-wrap}.compare textarea{resize:vertical}@media(max-width:800px){.him header{display:grid}.layout,.compare{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.compare pre,.compare textarea{min-height:170px}}`;
