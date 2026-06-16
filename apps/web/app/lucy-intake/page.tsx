"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyIntakeBoard } from "@/components/lucy-intake-board";

export default function LucyIntakePage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="LUCY INTAKE" subtitle="front-door coordination and routing">
          <LucyIntakeBoard />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
