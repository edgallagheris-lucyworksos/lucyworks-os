"use client";

import { AuthGuard } from "@/components/auth-guard";
import { ClinicalDirectorReadPanel } from "@/components/clinical-director-read";
import { HospitalShell } from "@/components/hospital-shell";

export default function ClinicalDirectorPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>{() => (
      <HospitalShell title="Clinical Director" subtitle="Hospital state, unsafe work, blockers, decisions and next 60 minutes">
        <ClinicalDirectorReadPanel />
      </HospitalShell>
    )}</AuthGuard>
  );
}
