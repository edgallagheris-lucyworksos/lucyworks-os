"use client";

import { useState } from "react";
import { generateReferralPathway } from "@/lib/referral-pathway";
import type { ScheduledWorkBlock } from "@/lib/day-control-work";

const procedures = [
  { value: "consult", label: "Referral consult" },
  { value: "mri", label: "MRI pathway" },
  { value: "ct", label: "CT pathway" },
  { value: "major surgery", label: "Major surgery pathway" },
  { value: "discharge", label: "Discharge pathway" },
];

type ReferralPathwayGeneratorProps = {
  onGenerate: (blocks: ScheduledWorkBlock[]) => void;
  syncStatus: string;
};

function slug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function makeCaseId(subject: string) {
  return `ref-${slug(subject || "case")}-${Date.now().toString(36)}`;
}

export function ReferralPathwayGenerator({ onGenerate, syncStatus }: ReferralPathwayGeneratorProps) {
  const [subject, setSubject] = useState("New referral");
  const [startTime, setStartTime] = useState("09:00");
  const [procedureText, setProcedureText] = useState("mri");
  const [ownerRole, setOwnerRole] = useState("clinician");
  const [ownerName, setOwnerName] = useState("");

  function generate() {
    const blocks = generateReferralPathway({
      caseId: makeCaseId(subject),
      subject: subject.trim() || "New referral",
      startTime,
      procedureText,
      ownerRole: ownerRole.trim() || undefined,
      ownerName: ownerName.trim() || undefined,
    });
    onGenerate(blocks);
  }

  return <section className="rpg"><style>{css}</style>
    <div className="rpgIntro"><b>Create referral episode</b><small>Creates triage, consent/estimate, procedure, pharmacy, handover, owner update and referring-vet report steps.</small></div>
    <label>Patient / case<input value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
    <label>Start<input type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} /></label>
    <label>Pathway<select value={procedureText} onChange={(event) => setProcedureText(event.target.value)}>{procedures.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
    <label>Lead role<input value={ownerRole} onChange={(event) => setOwnerRole(event.target.value)} /></label>
    <label>Lead name<input value={ownerName} onChange={(event) => setOwnerName(event.target.value)} placeholder="optional" /></label>
    <button type="button" onClick={generate}>Create episode</button>
    <small className="sync">Sync: {syncStatus}</small>
  </section>;
}

const css = `.rpg{display:grid;grid-template-columns:minmax(210px,1.4fr) repeat(5,minmax(125px,1fr)) auto;gap:10px;align-items:end;border:1px solid #d8e0ec;background:white;border-radius:16px;padding:14px;margin:12px 0;box-shadow:0 10px 28px rgba(15,23,42,.05)}.rpg *{box-sizing:border-box}.rpgIntro b{display:block;font-size:20px;color:#111827}.rpgIntro small,.sync{display:block;color:#64748b;margin-top:4px}.rpg label{display:grid;gap:5px;color:#475569;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.08em}.rpg input,.rpg select{border:1px solid #cbd5e1;background:#f8fafc;color:#0f172a;border-radius:11px;padding:10px;font:inherit;font-weight:800;min-height:42px}.rpg button{border:0;background:#0f172a;color:white;border-radius:12px;padding:11px 14px;font-weight:900;min-height:44px;white-space:nowrap}.sync{align-self:center;font-size:12px}@media(max-width:1200px){.rpg{grid-template-columns:1fr 1fr}.rpgIntro,.rpg button,.sync{grid-column:1/-1}}@media(max-width:720px){.rpg{grid-template-columns:1fr;padding:12px}.rpg button{width:100%}}`;