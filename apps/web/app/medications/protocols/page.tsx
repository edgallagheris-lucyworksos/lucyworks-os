"use client";

import { AuthGuard } from "@/components/auth-guard";
import { MedicationProtocolGovernanceV18 } from "@/components/medication-protocol-governance-v18";

const roles = ["clinician", "clinical_director", "governance_lead", "senior_clinician", "supervisor"];

export default function MedicationProtocolsPage() {
  return <AuthGuard allowedRoles={roles}>{user => <MedicationProtocolGovernanceV18 user={user} />}</AuthGuard>;
}
