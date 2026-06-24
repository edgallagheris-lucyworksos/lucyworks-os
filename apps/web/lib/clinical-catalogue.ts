export type ProcedureCatalogueItem = {
  id: string;
  label: string;
  area: string;
  defaultMinutes: number;
  setupMinutes: number;
  handoverMinutes: number;
  contingencyMinutes: number;
  referralAdminMinutes: number;
  accountableRole: string;
  supportRoles: string[];
  resourceType: string;
  pharmacyRefs: string[];
  safetyChecks: string[];
};

export type PharmacyCatalogueItem = {
  id: string;
  label: string;
  category: string;
  governance: string;
};

export const pharmacyCatalogue: PharmacyCatalogueItem[] = [
  { id: "analgesia-opioid", label: "Opioid analgesia", category: "controlled analgesia", governance: "vet authorisation and controlled-drug record" },
  { id: "anaesthetic-induction", label: "Anaesthetic induction agent", category: "anaesthesia", governance: "anaesthetist/vet plan required" },
  { id: "inhalational-anaesthesia", label: "Inhalational anaesthesia", category: "anaesthesia", governance: "machine/checklist/monitoring required" },
  { id: "nsaid", label: "NSAID analgesia", category: "analgesia", governance: "vet sign-off and contraindication check" },
  { id: "antibiotic-periop", label: "Peri-operative antibiotic", category: "antimicrobial", governance: "indication and stewardship check" },
  { id: "antiemetic", label: "Antiemetic", category: "supportive care", governance: "clinical indication recorded" },
  { id: "seizure-control", label: "Seizure-control medication", category: "neurology", governance: "vet plan and monitoring" },
  { id: "contrast-agent", label: "Imaging contrast", category: "imaging", governance: "renal/risk/consent check" },
  { id: "iv-fluids", label: "IV fluids", category: "supportive care", governance: "rate and monitoring plan" },
  { id: "discharge-meds", label: "Discharge medication pack", category: "discharge", governance: "label, dose, owner instruction" },
];

export const procedureCatalogue: ProcedureCatalogueItem[] = [
  { id: "arrival-triage", label: "Arrival triage", area: "front door", defaultMinutes: 15, setupMinutes: 5, handoverMinutes: 10, contingencyMinutes: 10, referralAdminMinutes: 10, accountableRole: "triage nurse", supportRoles: ["reception"], resourceType: "reception", pharmacyRefs: [], safetyChecks: ["identity", "presenting complaint", "red flags"] },
  { id: "consult-neuro", label: "Neurology referral consult", area: "consult", defaultMinutes: 45, setupMinutes: 10, handoverMinutes: 15, contingencyMinutes: 20, referralAdminMinutes: 30, accountableRole: "clinician", supportRoles: ["nurse", "admin"], resourceType: "consult room", pharmacyRefs: ["antiemetic", "seizure-control"], safetyChecks: ["history", "neuro exam", "owner consent", "estimate", "referral notes"] },
  { id: "mri", label: "MRI referral pathway", area: "imaging", defaultMinutes: 90, setupMinutes: 30, handoverMinutes: 30, contingencyMinutes: 30, referralAdminMinutes: 25, accountableRole: "imaging lead", supportRoles: ["anaesthesia", "nurse", "admin"], resourceType: "MRI", pharmacyRefs: ["anaesthetic-induction", "inhalational-anaesthesia", "contrast-agent"], safetyChecks: ["MRI safety", "anaesthetic plan", "contrast risk", "owner consent", "estimate"] },
  { id: "ct", label: "CT referral pathway", area: "imaging", defaultMinutes: 60, setupMinutes: 20, handoverMinutes: 20, contingencyMinutes: 20, referralAdminMinutes: 20, accountableRole: "imaging lead", supportRoles: ["anaesthesia", "nurse", "admin"], resourceType: "CT", pharmacyRefs: ["anaesthetic-induction", "contrast-agent"], safetyChecks: ["anaesthetic plan", "contrast risk", "positioning", "owner consent", "estimate"] },
  { id: "major-theatre", label: "Major surgery referral pathway", area: "theatre", defaultMinutes: 150, setupMinutes: 45, handoverMinutes: 45, contingencyMinutes: 60, referralAdminMinutes: 40, accountableRole: "surgeon", supportRoles: ["anaesthesia", "scrub nurse", "PCA", "admin"], resourceType: "theatre", pharmacyRefs: ["anaesthetic-induction", "inhalational-anaesthesia", "analgesia-opioid", "antibiotic-periop", "iv-fluids"], safetyChecks: ["consent", "estimate", "WHO-style timeout", "post-op plan", "owner update", "discharge risk"] },
  { id: "recovery", label: "Recovery monitoring", area: "ward/recovery", defaultMinutes: 60, setupMinutes: 10, handoverMinutes: 20, contingencyMinutes: 20, referralAdminMinutes: 10, accountableRole: "recovery nurse", supportRoles: ["PCA", "clinician"], resourceType: "recovery", pharmacyRefs: ["analgesia-opioid", "nsaid", "iv-fluids"], safetyChecks: ["pain score", "temperature", "airway", "owner update", "handover"] },
  { id: "discharge", label: "Referral discharge", area: "client", defaultMinutes: 30, setupMinutes: 10, handoverMinutes: 10, contingencyMinutes: 15, referralAdminMinutes: 25, accountableRole: "clinician", supportRoles: ["nurse", "admin", "pharmacy"], resourceType: "client contact", pharmacyRefs: ["discharge-meds"], safetyChecks: ["discharge instructions", "medication label", "recheck plan", "invoice", "owner understanding"] },
];

export function procedureForWork(what: string, lane?: string) {
  const text = `${what} ${lane || ""}`.toLowerCase();
  if (text.includes("mri")) return procedureCatalogue.find((item) => item.id === "mri");
  if (text.includes("ct")) return procedureCatalogue.find((item) => item.id === "ct");
  if (text.includes("theatre") || text.includes("surgery") || text.includes("surgical")) return procedureCatalogue.find((item) => item.id === "major-theatre");
  if (text.includes("recovery") || text.includes("ward")) return procedureCatalogue.find((item) => item.id === "recovery");
  if (text.includes("discharge")) return procedureCatalogue.find((item) => item.id === "discharge");
  if (text.includes("consult") || text.includes("referral")) return procedureCatalogue.find((item) => item.id === "consult-neuro");
  if (text.includes("arrival") || text.includes("triage") || text.includes("intake")) return procedureCatalogue.find((item) => item.id === "arrival-triage");
  return undefined;
}

export function pharmacyLabels(ids: string[]) {
  return ids.map((id) => pharmacyCatalogue.find((item) => item.id === id)?.label || id);
}

export function protectedMinutesForProcedure(item: ProcedureCatalogueItem) {
  return item.setupMinutes + item.defaultMinutes + item.handoverMinutes + item.contingencyMinutes + item.referralAdminMinutes;
}

export function protectedTimeLabel(item: ProcedureCatalogueItem) {
  return `${protectedMinutesForProcedure(item)}m protected (${item.setupMinutes}m setup, ${item.defaultMinutes}m work, ${item.handoverMinutes}m handover, ${item.contingencyMinutes}m contingency, ${item.referralAdminMinutes}m referral admin)`;
}
