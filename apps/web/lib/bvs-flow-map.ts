export type BvsFlowStage = {
  id: string;
  label: string;
  lane: string;
  source: "public_verified" | "internal_configurable";
  ownerRole: string;
  commonBlockers: string[];
  nextActions: string[];
  targetModule: "LucyFlow" | "LucyOps" | "LucyClinical" | "LucyComms" | "LucyPharm";
};

export const bvsFlowStages: BvsFlowStage[] = [
  { id: "arrival-triage", label: "Arrival / triage", lane: "intake", source: "internal_configurable", ownerRole: "triage_owner", commonBlockers: ["untriaged", "service owner missing", "owner info missing"], nextActions: ["assign triage owner", "set urgency", "route to service"], targetModule: "LucyFlow" },
  { id: "ecc-stabilisation", label: "ECC stabilisation", lane: "ecc", source: "public_verified", ownerRole: "ecc_owner", commonBlockers: ["senior review", "ICU space", "handover gap"], nextActions: ["assign ECC owner", "confirm critical care capacity", "create stabilisation task"], targetModule: "LucyFlow" },
  { id: "diagnostic-imaging", label: "Diagnostic imaging", lane: "imaging", source: "public_verified", ownerRole: "imaging_lead", commonBlockers: ["MRI slot", "CT slot", "sedation cover", "report owner"], nextActions: ["reserve imaging slot", "confirm cover", "assign report owner"], targetModule: "LucyOps" },
  { id: "service-ownership", label: "Service ownership", lane: "clinical", source: "public_verified", ownerRole: "service_clinician", commonBlockers: ["decision owner missing", "result review overdue", "case handover incomplete"], nextActions: ["assign clinical owner", "link results", "set next decision"], targetModule: "LucyClinical" },
  { id: "procedure-theatre", label: "Procedure / theatre", lane: "procedure", source: "public_verified", ownerRole: "theatre_lead", commonBlockers: ["theatre capacity", "kit", "anaesthesia", "consent"], nextActions: ["confirm room", "confirm kit", "confirm anaesthesia"], targetModule: "LucyOps" },
  { id: "interventional-suite", label: "Interventional suite", lane: "interventional", source: "public_verified", ownerRole: "interventional_lead", commonBlockers: ["fluoroscopy", "kit", "anaesthesia", "recovery route"], nextActions: ["confirm suite readiness", "confirm kit", "confirm recovery route"], targetModule: "LucyOps" },
  { id: "recovery-icu-ward", label: "Recovery / ICU / ward", lane: "beds", source: "public_verified", ownerRole: "nurse_lead", commonBlockers: ["recovery space", "ICU space", "ward bed", "handover"], nextActions: ["confirm destination", "assign nurse", "complete handover"], targetModule: "LucyFlow" },
  { id: "owner-update", label: "Owner update", lane: "comms", source: "internal_configurable", ownerRole: "admin", commonBlockers: ["callback overdue", "estimate missing", "consent missing"], nextActions: ["draft owner update", "request consent", "confirm estimate"], targetModule: "LucyComms" },
  { id: "pharmacy-discharge", label: "Pharmacy / discharge", lane: "discharge", source: "internal_configurable", ownerRole: "pharmacy_owner", commonBlockers: ["meds missing", "instructions unsigned", "payment hold", "collection not ready"], nextActions: ["prepare meds", "request signoff", "release bed"], targetModule: "LucyPharm" },
];

export function moduleRoute(module: BvsFlowStage["targetModule"]) {
  if (module === "LucyOps") return "/resources";
  if (module === "LucyClinical") return "/lucy-clinical";
  if (module === "LucyComms") return "/lucy-comms";
  if (module === "LucyPharm") return "/lucy-pharm";
  return "/flow";
}
