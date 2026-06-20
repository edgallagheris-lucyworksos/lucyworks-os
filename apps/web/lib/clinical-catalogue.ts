export type ProcedureCatalogueItem = {
  id: string;
  label: string;
  area: string;
  defaultMinutes: number;
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
  { id: "arrival-triage", label: "Arrival triage", area: "front door", defaultMinutes: 15, accountableRole: "triage nurse", supportRoles: ["reception"], resourceType: "reception", pharmacyRefs: [], safetyChecks: ["identity", "presenting complaint", "red flags"] },
  { id: "consult-neuro", label: "Neurology consult", area: "consult", defaultMinutes: 45, accountableRole: "clinician", supportRoles: ["nurse"], resourceType: "consult room", pharmacyRefs: ["antiemetic", "seizure-control"], safetyChecks: ["history", "neuro exam", "owner consent"] },
  { id: "mri", label: "MRI", area: "imaging", defaultMinutes: 90, accountableRole: "imaging lead", supportRoles: ["anaesthesia", "nurse"], resourceType: "MRI", pharmacyRefs: ["anaesthetic-induction", "inhalational-anaesthesia", "contrast-agent"], safetyChecks: ["MRI safety", "anaesthetic plan", "contrast risk"] },
  { id: "ct", label: "CT", area: "imaging", defaultMinutes: 60, accountableRole: "imaging lead", supportRoles: ["anaesthesia", "nurse"], resourceType: "CT", pharmacyRefs: ["anaesthetic-induction", "contrast-agent"], safetyChecks: ["anaesthetic plan", "contrast risk", "positioning"] },
  { id: "major-theatre", label: "Major theatre", area: "theatre", defaultMinutes: 150, accountableRole: "surgeon", supportRoles: ["anaesthesia", "scrub nurse", "PCA"], resourceType: "theatre", pharmacyRefs: ["anaesthetic-induction", "inhalational-anaesthesia", "analgesia-opioid", "antibiotic-periop", "iv-fluids"], safetyChecks: ["consent", "estimate", "WHO-style timeout", "post-op plan"] },
  { id: "recovery", label: "Recovery monitoring", area: "ward/recovery", defaultMinutes: 60, accountableRole: "recovery nurse", supportRoles: ["PCA"], resourceType: "recovery", pharmacyRefs: ["analgesia-opioid", "nsaid", "iv-fluids"], safetyChecks: ["pain score", "temperature", "airway", "owner update"] },
  { id: "discharge", label: "Discharge", area: "client", defaultMinutes: 30, accountableRole: "clinician", supportRoles: ["nurse", "admin"], resourceType: "client contact", pharmacyRefs: ["discharge-meds"], safetyChecks: ["discharge instructions", "medication label", "recheck plan", "invoice"] },
];

export function procedureForWork(what: string, lane?: string) {
  const text = `${what} ${lane || ""}`.toLowerCase();
  if (text.includes("mri")) return procedureCatalogue.find((item) => item.id === "mri");
  if (text.includes("ct")) return procedureCatalogue.find((item) => item.id === "ct");
  if (text.includes("theatre") || text.includes("surgery") || text.includes("surgical")) return procedureCatalogue.find((item) => item.id === "major-theatre");
  if (text.includes("recovery") || text.includes("ward")) return procedureCatalogue.find((item) => item.id === "recovery");
  if (text.includes("discharge")) return procedureCatalogue.find((item) => item.id === "discharge");
  if (text.includes("consult")) return procedureCatalogue.find((item) => item.id === "consult-neuro");
  if (text.includes("arrival") || text.includes("triage") || text.includes("intake")) return procedureCatalogue.find((item) => item.id === "arrival-triage");
  return undefined;
}

export function pharmacyLabels(ids: string[]) {
  return ids.map((id) => pharmacyCatalogue.find((item) => item.id === id)?.label || id);
}
