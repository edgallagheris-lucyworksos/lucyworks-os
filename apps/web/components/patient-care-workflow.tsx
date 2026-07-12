"use client";

import { useMemo, useState } from "react";
import { useDayControlStore } from "@/lib/day-control-store";
import type { ScheduledWorkBlock } from "@/lib/day-control-work";

const stages = [
  { key: "intake", label: "Intake / triage", words: ["arrival", "triage", "check-in", "intake"] },
  { key: "admin", label: "Consent / estimate", words: ["consent", "estimate", "insurance", "payment", "admin"] },
  { key: "procedure", label: "Clinical work", words: ["mri", "ct", "procedure", "surgery", "theatre", "consult", "workup"] },
  { key: "recovery", label: "Recovery / handover", words: ["recovery", "handover", "ward", "nursing"] },
  { key: "closure", label: "Owner / ref vet / discharge", words: ["owner", "client", "referring vet", "report", "discharge", "close"] },
] as const;

type StageKey = (typeof stages)[number]["key"];
type CareCase = {
  id: string;
  patient: string;
  blocks: ScheduledWorkBlock[];
  stage: StageKey;
  owner: string;
  next: string;
  blockers: ScheduledWorkBlock[];
};

function safe(value: string | number | null | undefined) {
  return String(value || "").trim();
}

function caseKey(block: ScheduledWorkBlock) {
  return safe(block.episodeRef) || safe(block.subject) || safe(block.id);
}

function patientName(blocks: ScheduledWorkBlock[], fallback: string) {
  return safe(blocks.find((block) => safe(block.subject))?.subject) || fallback;
}

function blockText(block: ScheduledWorkBlock) {
  return `${safe(block.lane)} ${safe(block.what)} ${safe(block.how)} ${safe(block.where)} ${safe(block.next)} ${safe(block.blocker)}`.toLowerCase();
}

function stageFor(blocks: ScheduledWorkBlock[]): StageKey {
  const open = blocks.filter((block) => safe(block.blocker).toLowerCase() !== "none" || block.status !== "green");
  const source = open.length ? open : blocks;
  const text = source.map(blockText).join(" ");
  return stages.find((stage) => stage.words.some((word) => text.includes(word)))?.key || "intake";
}

function stageLabel(key: StageKey) {
  return stages.find((stage) => stage.key === key)?.label || "Workflow";
}

function blockTimeSort(left: ScheduledWorkBlock, right: ScheduledWorkBlock) {
  return safe(left.time).localeCompare(safe(right.time)) || safe(left.what).localeCompare(safe(right.what));
}

function ownerFor(blocks: ScheduledWorkBlock[]) {
  const named = blocks.find((block) => safe(block.assignedStaffName));
  if (named) return safe(named.assignedStaffName);
  const role = blocks.find((block) => safe(block.assignedRole));
  if (role) return safe(role.assignedRole);
  return safe(blocks[0]?.who) || "unassigned";
}

function nextFor(blocks: ScheduledWorkBlock[]) {
  const blocked = blocks.find((block) => safe(block.blocker).toLowerCase() !== "none");
  if (blocked) return `${blocked.time} · clear blocker: ${blocked.blocker}`;
  const open = blocks.find((block) => block.status !== "green");
  if (open) return `${open.time} · ${open.next}`;
  const last = blocks[blocks.length - 1];
  return last ? `${last.time} · ${last.next}` : "no next action";
}

function gates(blocks: ScheduledWorkBlock[]) {
  const values = {
    consent: blocks.map((b) => b.consentStatus).find(Boolean),
    estimate: blocks.map((b) => b.estimateStatus).find(Boolean),
    insurance: blocks.map((b) => b.insuranceStatus).find(Boolean),
    pharmacy: blocks.map((b) => b.pharmacyReady).find((value) => value !== undefined),
    owner: blocks.map((b) => b.ownerUpdated).find((value) => value !== undefined),
    report: blocks.map((b) => b.referringVetReportSent).find((value) => value !== undefined),
    discharge: blocks.map((b) => b.dischargeClear).find((value) => value !== undefined),
  };
  return [
    ["Consent", values.consent || "not set"],
    ["Estimate", values.estimate || "not set"],
    ["Insurance", values.insurance || "not set"],
    ["Pharmacy", values.pharmacy === undefined ? "not set" : values.pharmacy ? "ready" : "not ready"],
    ["Owner", values.owner === undefined ? "not set" : values.owner ? "updated" : "not updated"],
    ["Report", values.report === undefined ? "not set" : values.report ? "sent" : "not sent"],
    ["Discharge", values.discharge === undefined ? "not set" : values.discharge ? "clear" : "not clear"],
  ];
}

function makeCases(blocks: ScheduledWorkBlock[]): CareCase[] {
  const grouped = new Map<string, ScheduledWorkBlock[]>();
  for (const block of blocks) {
    if (block.lane === "breaks") continue;
    const key = caseKey(block);
    grouped.set(key, [...(grouped.get(key) || []), block]);
  }
  return Array.from(grouped.entries()).map(([id, rows]) => {
    const sorted = [...rows].sort(blockTimeSort);
    return {
      id,
      patient: patientName(sorted, id),
      blocks: sorted,
      stage: stageFor(sorted),
      owner: ownerFor(sorted),
      next: nextFor(sorted),
      blockers: sorted.filter((block) => safe(block.blocker).toLowerCase() !== "none"),
    };
  }).sort((a, b) => b.blockers.length - a.blockers.length || safe(a.blocks[0]?.time).localeCompare(safe(b.blocks[0]?.time)) || a.patient.localeCompare(b.patient));
}

function tone(block: ScheduledWorkBlock) {
  if (safe(block.blocker).toLowerCase() !== "none" || block.status === "red") return "blocked";
  if (block.status === "green") return "clear";
  return "open";
}

export function PatientCareWorkflow() {
  const { blocks, applyAction, syncStatus } = useDayControlStore();
  const cases = useMemo(() => makeCases(blocks), [blocks]);
  const [selectedId, setSelectedId] = useState("");
  const selected = cases.find((item) => item.id === selectedId) || cases[0];
  const blockedCases = cases.filter((item) => item.blockers.length).length;
  const selectedOwnerBlock = selected?.blocks.find((block) => block.what.toLowerCase().includes("owner"));
  const selectedReportBlock = selected?.blocks.find((block) => block.what.toLowerCase().includes("referring") || block.what.toLowerCase().includes("report"));
  const selectedBlockedBlock = selected?.blockers[0];

  return <main className="pcw"><style>{css}</style>
    <header className="hero">
      <div>
        <span>LucyWorks OS</span>
        <h1>Patient care workflow</h1>
        <p>Referral episodes first. Board, staff and rooms sit underneath the patient journey.</p>
      </div>
      <nav>
        <a href="/patient-care">Care workflow</a>
        <a href="/hospital-board">Schedule board</a>
        <a href="/workspace">Workspace</a>
      </nav>
    </header>

    <section className="kpis">
      <article><b>{cases.length}</b><small>active episodes</small></article>
      <article><b>{blockedCases}</b><small>blocked cases</small></article>
      <article><b>{blocks.length}</b><small>workflow tasks</small></article>
      <article><b>{syncStatus}</b><small>sync state</small></article>
    </section>

    <section className="layout">
      <aside className="caseList">
        <h2>Cases</h2>
        {cases.map((item) => <button key={item.id} className={selected?.id === item.id ? "active" : ""} onClick={() => setSelectedId(item.id)}>
          <b>{item.patient}</b>
          <small>{stageLabel(item.stage)}</small>
          <em>{item.blockers.length ? `${item.blockers.length} blocker${item.blockers.length === 1 ? "" : "s"}` : "clear"}</em>
        </button>)}
      </aside>

      {selected ? <section className="caseDetail">
        <div className="caseHeader">
          <div>
            <span>{selected.id}</span>
            <h2>{selected.patient}</h2>
            <p>{stageLabel(selected.stage)} · Owner: {selected.owner}</p>
          </div>
          <strong className={selected.blockers.length ? "bad" : "good"}>{selected.blockers.length ? "Blocked" : "In flow"}</strong>
        </div>

        <section className="nextAction">
          <b>Next action</b>
          <p>{selected.next}</p>
          <div>
            {selectedBlockedBlock ? <button onClick={() => applyAction(selectedBlockedBlock.id, "resolve")}>Resolve blocker</button> : null}
            {selectedOwnerBlock ? <button onClick={() => applyAction(selectedOwnerBlock.id, "owner_update")}>Mark owner updated</button> : null}
            {selectedReportBlock ? <button onClick={() => applyAction(selectedReportBlock.id, "referring_vet_report")}>Mark report sent</button> : null}
            {selectedBlockedBlock ? <button onClick={() => applyAction(selectedBlockedBlock.id, "escalate")}>Escalate</button> : null}
          </div>
        </section>

        <section className="gates">
          {gates(selected.blocks).map(([label, value]) => <article key={label} className={String(value).includes("pending") || String(value).includes("not") ? "gateBad" : ""}>
            <small>{label}</small>
            <b>{value}</b>
          </article>)}
        </section>

        <section className="timeline">
          <h3>Case timeline</h3>
          {selected.blocks.map((block) => <article key={block.id} className={tone(block)}>
            <time>{block.time}</time>
            <div>
              <b>{block.what}</b>
              <p>{block.who} · {block.where}</p>
              <small>{safe(block.blocker).toLowerCase() !== "none" ? `Blocked: ${block.blocker}` : block.next}</small>
            </div>
          </article>)}
        </section>
      </section> : <section className="caseDetail"><h2>No cases</h2><p>Create a referral episode from the hospital board.</p></section>}
    </section>
  </main>;
}

const css = `.pcw{min-height:100vh;background:#f5f7fb;color:#111827;padding:14px;font-family:Inter,system-ui,sans-serif}.pcw *{box-sizing:border-box}.hero{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;background:white;border:1px solid #d8e0ec;border-radius:18px;padding:16px;box-shadow:0 10px 28px rgba(15,23,42,.06)}.hero span,.caseHeader span{display:block;text-transform:uppercase;letter-spacing:.14em;color:#2563eb;font-size:11px;font-weight:900}.hero h1{font-size:clamp(34px,7vw,64px);line-height:.95;margin:6px 0;color:#111827}.hero p,.caseHeader p,.nextAction p,.timeline p{color:#475569;margin:6px 0 0}.hero nav{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.hero a,.nextAction button{border:1px solid #cbd5e1;background:white;color:#0f172a;border-radius:999px;padding:9px 12px;text-decoration:none;font-weight:800}.hero a:first-child,.nextAction button:first-child{background:#0f172a;color:white;border-color:#0f172a}.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:12px 0}.kpis article,.caseList,.caseDetail{background:white;border:1px solid #d8e0ec;border-radius:18px;padding:14px}.kpis b{display:block;font-size:32px;line-height:1}.kpis small{display:block;color:#64748b;margin-top:4px}.layout{display:grid;grid-template-columns:minmax(240px,.34fr) 1fr;gap:12px}.caseList{display:grid;gap:8px;align-content:start}.caseList h2{margin:0 0 4px}.caseList button{display:grid;gap:3px;text-align:left;border:1px solid #d8e0ec;background:#f8fafc;border-radius:14px;padding:11px;color:#0f172a}.caseList button.active{border-color:#2563eb;background:#eff6ff}.caseList small{color:#475569}.caseList em{font-style:normal;color:#92400e;font-size:12px}.caseHeader{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;border-bottom:1px solid #e5e7eb;padding-bottom:12px}.caseHeader h2{font-size:clamp(30px,5vw,52px);line-height:1;margin:5px 0}.caseHeader strong{border-radius:999px;padding:8px 11px;font-size:13px}.good{background:#dcfce7;color:#166534}.bad{background:#fee2e2;color:#991b1b}.nextAction{background:#eff6ff;border:1px solid #bfdbfe;border-radius:16px;padding:12px;margin:12px 0}.nextAction b{font-size:18px}.nextAction div{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.nextAction button{cursor:pointer}.gates{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}.gates article{border:1px solid #d8e0ec;background:#f8fafc;border-radius:13px;padding:10px}.gates .gateBad{border-color:#f59e0b;background:#fffbeb}.gates small{display:block;color:#64748b}.gates b{display:block;margin-top:4px;text-transform:capitalize}.timeline{margin-top:14px}.timeline h3{margin:0 0 8px}.timeline article{display:grid;grid-template-columns:68px 1fr;gap:10px;border:1px solid #d8e0ec;border-left-width:6px;border-radius:14px;padding:10px;margin-bottom:8px;background:white}.timeline article.blocked{border-left-color:#dc2626}.timeline article.open{border-left-color:#f59e0b}.timeline article.clear{border-left-color:#16a34a}.timeline time{font-weight:900;color:#075985}.timeline b{display:block}.timeline small{display:block;color:#64748b;margin-top:3px}@media(max-width:820px){.hero,.caseHeader{display:grid}.hero nav{justify-content:stretch}.hero a{flex:1;text-align:center}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.layout{grid-template-columns:1fr}.caseList{grid-template-columns:repeat(auto-fit,minmax(180px,1fr));overflow-x:auto}.timeline article{grid-template-columns:56px 1fr}}`;
