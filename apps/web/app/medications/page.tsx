"use client";

import { AuthGuard } from "@/components/auth-guard";
import { MedicationSafetyWorkspaceV18 } from "@/components/medication-safety-workspace-v18";

const roles = [
  "admin",
  "clinician",
  "clinical_director",
  "governance_lead",
  "hospital_director",
  "nurse",
  "senior_clinician",
  "supervisor",
];

export default function MedicationsPage() {
  return (
    <AuthGuard allowedRoles={roles}>
      {user => <MedicationSafetyWorkspaceV18 user={user} />}
    </AuthGuard>
  );
}
