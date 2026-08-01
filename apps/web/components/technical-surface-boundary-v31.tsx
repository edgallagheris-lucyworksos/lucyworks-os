"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const technicalRoutes = new Map<string, string>([
  ["/access-review", "Access and identity administration"],
  ["/assurance-control", "Assurance evidence and release control"],
  ["/automation-control", "Automation authority and evidence"],
  ["/compliance-safety", "Governance and compliance administration"],
  ["/control-plane", "Technical control plane"],
  ["/deployment-control", "Deployment and integration administration"],
  ["/hospital-configuration", "Hospital configuration administration"],
  ["/hospital-configuration/validation-tools", "Configuration validation tools"],
  ["/hospital-imports", "Controlled data import administration"],
  ["/integrations", "External-system administration"],
  ["/live-control", "Event-stream and retry diagnostics"],
  ["/onboarding", "Organisation onboarding administration"],
  ["/operating-context", "Operating-context administration"],
  ["/operating-model", "Operating-model diagnostics"],
  ["/operational-proof", "Synthetic operational proof laboratory"],
  ["/pilot-control", "Pilot authority and UAT evidence"],
  ["/pilot-lab", "Synthetic integration simulator"],
  ["/production-readiness", "Production-readiness evidence control"],
  ["/realtime-status", "Realtime connection diagnostics"],
  ["/resource-directory", "Resource configuration administration"],
  ["/safety-control", "Cross-system safety administration"],
  ["/shadow-mode", "Shadow comparison diagnostics"],
  ["/system", "Technical system status"],
  ["/system-control", "System administration"],
]);

const legacyRoutes = new Map<string, string>([
  ["/actions", "Legacy action queue"],
  ["/command", "Legacy command overview"],
  ["/dashboard", "Legacy dashboard"],
  ["/episodes", "Legacy episode list"],
  ["/flow-state", "Legacy flow-state view"],
  ["/hospital-ops", "Legacy hospital operations view"],
  ["/manager-dashboard", "Legacy role dashboard"],
  ["/nurse-dashboard", "Legacy role dashboard"],
  ["/patient-care", "Legacy patient-care workflow"],
  ["/pca-dashboard", "Legacy role dashboard"],
  ["/role-views", "Legacy role view"],
]);

export function TechnicalSurfaceBoundaryV31() {
  const pathname = usePathname();
  const technical = technicalRoutes.get(pathname);
  const legacy = legacyRoutes.get(pathname);
  const label = technical || legacy;
  if (!label) return null;

  const isLegacy = Boolean(legacy);
  return <aside role="note" aria-label={isLegacy ? "Legacy surface notice" : "Technical administration notice"} style={{ margin: "8px 12px", padding: "11px 13px", borderRadius: 12, border: `2px solid ${isLegacy ? "#f59e0b" : "#2563eb"}`, background: isLegacy ? "#fffbeb" : "#eff6ff", color: "#0f172a", fontFamily: "Inter,system-ui,sans-serif" }}>
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
      <div><strong>{isLegacy ? "Legacy compatibility surface" : "Technical administration surface"}</strong><div>{label}. This is not the normal patient-care route.</div></div>
      <nav aria-label="Return to primary hospital workflow" style={{ display: "flex", gap: 9, flexWrap: "wrap" }}>
        <Link href="/workspace">Patient Command</Link>
        <Link href="/care">Care Brief</Link>
        <Link href="/hospital-board">Hospital Today</Link>
        {isLegacy && <Link href="/system-control">Technical tools</Link>}
      </nav>
    </div>
  </aside>;
}
