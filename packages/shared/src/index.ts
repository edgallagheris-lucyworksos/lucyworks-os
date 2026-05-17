export const LUCYWORKS_MODULES = [
  "intake","triage","theatre","procedure_timeline","anaesthesia","icu_wards","imaging","labs","pharmacy","stock","discharge","owner_comms","rota","overtime","handover","ethics_governance","audit","role_views"
] as const;

export type LucyModule = (typeof LUCYWORKS_MODULES)[number];

export const API_BASE_DEFAULT = "http://localhost:8000";

export type PressureLevel = "green" | "amber" | "red";
