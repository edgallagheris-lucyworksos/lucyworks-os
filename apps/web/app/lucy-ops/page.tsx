"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function LucyOpsPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin", "pca"]}>
      {(user) => (
        <HospitalShell title="LucyOps" subtitle="rooms, resources, theatre, imaging, pharmacy and stock pressure">
          <LucyWorksCommandSurface mode="resources" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
