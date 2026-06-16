export type HospitalModuleId =
  | "now"
  | "intake"
  | "flow"
  | "ops"
  | "hr"
  | "pulse"
  | "clinical"
  | "care"
  | "move"
  | "gov"
  | "pharm"
  | "knowledge"
  | "bvs_public"
  | "system";

export type HospitalModule = {
  id: HospitalModuleId;
  label: string;
  route: string;
  title: string;
  subtitle: string;
  endpoint: string;
  roles: string[];
  linkedEntities: string[];
  decision: string;
};

export const hospitalModules: HospitalModule[] = [
  {
    id: "now",
    label: "NOW",
    route: "/hospital-board",
    title: "NOW",
    subtitle: "whole hospital live command",
    endpoint: "/api/product/now",
    roles: ["clinical_director", "ops_manager", "clinician", "nurse", "admin"],
    linkedEntities: ["episodes", "work_items", "conflicts", "rooms", "staff"],
    decision: "what is unsafe now and who owns the next action",
  },
  {
    id: "intake",
    label: "LucyIntake",
    route: "/lucy-intake",
    title: "LUCY INTAKE",
    subtitle: "front-door coordination and routing",
    endpoint: "/api/role-queues/overview",
    roles: ["clinical_director", "ops_manager", "clinician", "nurse", "admin"],
    linkedEntities: ["referrals", "advice_requests", "owner_updates", "work_items", "capacity"],
    decision: "what has entered the hospital and where it must be routed next",
  },
  {
    id: "flow",
    label: "LucyFlow",
    route: "/flow",
    title: "FLOW",
    subtitle: "patient movement and blockers",
    endpoint: "/api/product/flow",
    roles: ["clinical_director", "ops_manager", "clinician", "nurse", "pca", "admin"],
    linkedEntities: ["episodes", "sections", "rooms", "handovers", "schedule_blocks"],
    decision: "where each patient is stuck and what unlocks movement",
  },
  {
    id: "ops",
    label: "LucyOps",
    route: "/resources",
    title: "RESOURCES",
    subtitle: "rooms, staff, theatre, imaging, ward and pharmacy",
    endpoint: "/api/product/resources",
    roles: ["clinical_director", "ops_manager", "clinician", "nurse", "admin"],
    linkedEntities: ["rooms", "room_states", "staff", "schedule_blocks", "pharmacy"],
    decision: "which resource is blocking hospital flow",
  },
  {
    id: "hr",
    label: "LucyHR",
    route: "/my-shift",
    title: "MY SHIFT",
    subtitle: "role filtered work and handoffs",
    endpoint: "/api/role-queues/my-shift",
    roles: ["clinical_director", "ops_manager", "clinician", "nurse", "pca", "admin"],
    linkedEntities: ["staff", "shifts", "work_items", "handovers"],
    decision: "what this person must do next",
  },
  {
    id: "pulse",
    label: "LucyPulse",
    route: "/interrupts",
    title: "INTERRUPTS",
    subtitle: "urgent breaks in hospital flow",
    endpoint: "/api/conflict-engine/pulse",
    roles: ["clinical_director", "ops_manager", "clinician", "nurse", "admin"],
    linkedEntities: ["conflicts", "work_items", "episodes", "audit"],
    decision: "which new disruption changes the plan",
  },
  {
    id: "clinical",
    label: "LucyClinical",
    route: "/lucy-clinical",
    title: "CLINICAL",
    subtitle: "results, consults, signoff and decisions",
    endpoint: "/api/clinical-director/summary",
    roles: ["clinical_director", "clinician", "nurse"],
    linkedEntities: ["episodes", "results", "decisions", "work_items"],
    decision: "which clinical decision is waiting for ownership",
  },
  {
    id: "care",
    label: "LucyCare",
    route: "/nurse-dashboard",
    title: "Nurse",
    subtitle: "nursing observations, meds, prep and recovery",
    endpoint: "/api/role-queues/nurse",
    roles: ["clinical_director", "ops_manager", "nurse"],
    linkedEntities: ["work_items", "episodes", "rooms", "handovers"],
    decision: "which nursing task must be done next",
  },
  {
    id: "move",
    label: "LucyMove",
    route: "/pca-dashboard",
    title: "PCA",
    subtitle: "patient movement and handoffs",
    endpoint: "/api/role-queues/pca",
    roles: ["clinical_director", "ops_manager", "pca", "nurse"],
    linkedEntities: ["episodes", "rooms", "handovers", "work_items"],
    decision: "which patient movement is safe and ready",
  },
  {
    id: "gov",
    label: "LucyGov",
    route: "/lucy-gov",
    title: "GOV",
    subtitle: "audit, governance and safety trail",
    endpoint: "/api/audit",
    roles: ["clinical_director", "ops_manager", "admin"],
    linkedEntities: ["audit", "conflicts", "decisions", "episodes"],
    decision: "what decision history needs review",
  },
  {
    id: "pharm",
    label: "LucyPharm",
    route: "/lucy-pharm",
    title: "PHARM",
    subtitle: "medication, stock and discharge flow",
    endpoint: "/api/product/resources",
    roles: ["clinical_director", "ops_manager", "clinician", "nurse", "admin"],
    linkedEntities: ["pharmacy", "work_items", "episodes", "stock"],
    decision: "which medication or stock issue blocks care or discharge",
  },
  {
    id: "knowledge",
    label: "LucyKnowledge",
    route: "/lucy-knowledge",
    title: "LucyKnowledge",
    subtitle: "sources, agents and approval gates",
    endpoint: "/api/knowledge/registry",
    roles: ["clinical_director", "ops_manager", "admin"],
    linkedEntities: ["sources", "agents", "approval_gates", "training_notes"],
    decision: "which knowledge source or agent can inform this workflow",
  },
  {
    id: "bvs_public",
    label: "BVS Public Map",
    route: "/bvs-public-map",
    title: "BVS PUBLIC MAP",
    subtitle: "public website operating model",
    endpoint: "/api/knowledge/registry",
    roles: ["clinical_director", "ops_manager", "admin"],
    linkedEntities: ["public_sources", "services", "pathways", "roles", "capacity"],
    decision: "which public BVS fact informs the model and what remains configurable",
  },
  {
    id: "system",
    label: "System",
    route: "/system-control",
    title: "SYSTEM",
    subtitle: "backend health, users, seed state and controls",
    endpoint: "/api/health",
    roles: ["clinical_director", "ops_manager", "admin"],
    linkedEntities: ["health", "users", "seed", "config"],
    decision: "is the operating system healthy and available",
  },
];

export const primaryHospitalModules = hospitalModules.filter((module) =>
  ["now", "intake", "flow", "ops", "hr", "pulse", "clinical"].includes(module.id),
);

export const secondaryHospitalModules = hospitalModules.filter((module) =>
  ["care", "move", "gov", "pharm", "knowledge", "bvs_public", "system"].includes(module.id),
);

export function moduleByTitle(title: string) {
  return hospitalModules.find((module) => module.title === title || module.label === title);
}

export function moduleByRoute(route: string) {
  return hospitalModules.find((module) => module.route === route);
}
