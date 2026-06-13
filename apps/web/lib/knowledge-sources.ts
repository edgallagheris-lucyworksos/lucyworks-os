export type KnowledgeSource = {
  id: string;
  label: string;
  module: string;
  type: string;
  humanApproval: boolean;
};

export type LucyAgent = {
  id: string;
  label: string;
  module: string;
  purpose: string;
};

export const knowledgeSources: KnowledgeSource[] = [
  { id: "hospital-sop", label: "Hospital operating rules", module: "all", type: "internal_rules", humanApproval: true },
  { id: "governance-guidance", label: "Governance guidance", module: "LucyGov", type: "governance", humanApproval: true },
  { id: "business-training", label: "Business training notes", module: "LucyStrategy", type: "business_process", humanApproval: false },
  { id: "logistics-examples", label: "Logistics examples", module: "LucyOps", type: "operations_example", humanApproval: false },
];

export const lucyAgents: LucyAgent[] = [
  { id: "lucy-ops-agent", label: "LucyOps Agent", module: "LucyOps", purpose: "resources theatres imaging beds stock" },
  { id: "lucy-flow-agent", label: "LucyFlow Agent", module: "LucyFlow", purpose: "movement blockers handover" },
  { id: "lucy-hr-agent", label: "LucyHR Agent", module: "LucyHR", purpose: "rota cover fatigue" },
  { id: "lucy-comms-agent", label: "LucyComms Agent", module: "LucyComms", purpose: "owner updates estimates insurance" },
  { id: "lucy-gov-agent", label: "LucyGov Agent", module: "LucyGov", purpose: "audit safety approvals" },
];

export function sourcesForModule(module: string) {
  return knowledgeSources.filter((source) => source.module === module || source.module === "all");
}

export function agentForModule(module: string) {
  return lucyAgents.find((agent) => agent.module === module);
}
