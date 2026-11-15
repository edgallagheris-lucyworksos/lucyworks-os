"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalOsHomeV32 } from "@/components/hospital-os-home-v32";

const roles = [
  "admin",
  "clinician",
  "clinical_director",
  "governance_lead",
  "hospital_director",
  "nurse",
  "ops_manager",
  "senior_clinician",
  "supervisor",
  "reception",
  "referral_coordinator",
  "insurance",
  "pharmacy",
  "laboratory",
  "imaging",
  "ward_assistant",
  "facilities",
  "hr",
  "finance",
  "viewer",
];

export default function HomePage() {
  return (
    <AuthGuard allowedRoles={roles}>
      {user => <HospitalOsHomeV32 user={user} />}
    </AuthGuard>
  );
}
