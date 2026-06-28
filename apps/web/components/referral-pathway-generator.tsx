"use client";

import { useMemo, useState } from "react";
import { generateReferralPathway } from "@/lib/referral-pathway";
import { useDayControlStore } from "@/lib/day-control-store";

const procedures = [
  { value: "consult", label: "Referral consult" },
  { value: "mri", label: "MRI pathway" },
  { value: "ct", label: "CT pathway" },
  { value: "major surgery", label: "Major surgery pathway" },
  { value: "discharge", label: "Discharge pathway" },
];

function slug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

export function ReferralPathwayGenerator() {
  const { addBlocks, syncStatus } = useDayControlStore();
  const [subject, setSubject] = useState("New referral");
  const [startTime, setStartTime] = useState("09:00");
  const [procedureText, setProcedureText] = useState("mri");
  const [ownerRole, setOwnerRole] = useState("clinician");
  const [ownerName, setOwnerName] = useState("");
  const caseId = useMemo(() => `ref-${slug(subject || "case")}-${Date.now().toString(36)}`, [subject]);

  function generate() {
    const blocks = generateReferralPathway({
      caseId,
      subject: subject.trim() || "New referral",
      startTime,
      procedureText,
      ownerRole: ownerRole.trim() || undefined,
      ownerName: ownerName.trim() || undefined,
    });
    addBlocks(blocks);
  }

  return <section className="rpg"><style>{css}</style><div><b>Generate referral pathway</b><small>Creates triage, consent/estimate, procedure, pharmacy, handover, owner update and referring-vet report tasks.</small></div><label>Case<input value={subject} onChange={(event) => setSubject(event.target.value)} /></label><label>Start<input type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} /></label><label>Procedure<select value={procedureText} onChange={(event) => setProcedureText(event.target.value)}>{procedures.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label>Lead role<input value={ownerRole} onChange={(event) => setOwnerRole(event.target.value)} /></label><label>Lead name<input value={ownerName} onChange={(event) => setOwnerName(event.target.value)} placeholder="optional" /></label><button onClick={generate}>Generate</button><small>Sync: {syncStatus}</small></section>;
}

const css = `.rpg{display:grid;grid-template-columns:minmax(210px,1.6fr) repeat(5,minmax(120px,1fr)) auto auto;gap:8px;align-items:end;border:1px solid #26364f;background:#07111f;border-radius:16px;padding:10px;margin:10px 0}.rpg b,.rpg small{display:block}.rpg small{color:#9fb0c6}.rpg label{display:grid;gap:4px;color:#bae6fd;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.06em}.rpg input,.rpg select{border:1px solid #334155;background:#020617;color:#e5e7eb;border-radius:10px;padding:8px}.rpg button{border:1px solid #67e8f9;background:#0e7490;color:white;border-radius:999px;padding:9px 14px;font-weight:900}@media(max-width:1200px){.rpg{grid-template-columns:1fr 1fr}.rpg div,.rpg button{grid-column:1/-1}}@media(max-width:720px){.rpg{grid-template-columns:1fr}}`;
