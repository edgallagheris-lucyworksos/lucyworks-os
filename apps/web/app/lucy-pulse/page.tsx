"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function LucyPulsePage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin", "pca"]}>
      {(user) => (
        <HospitalShell title="LucyPulse" subtitle="pressure, conflicts, interrupts and risk">
          <LucyWorksCommandSurface mode="interrupts" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
