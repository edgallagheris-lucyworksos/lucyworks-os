"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function InterruptsPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {(user) => (
        <HospitalShell title="INTERRUPTS" subtitle="urgent breaks in hospital flow">
          <LucyWorksCommandSurface mode="interrupts" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
