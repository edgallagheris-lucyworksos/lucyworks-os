"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function LucyHRPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin", "pca"]}>
      {(user) => (
        <HospitalShell title="LucyHR" subtitle="shifts, staffing, rota, availability and role work">
          <LucyWorksCommandSurface mode="my-shift" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
