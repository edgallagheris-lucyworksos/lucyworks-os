"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function ResourcesPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {(user) => (
        <HospitalShell title="RESOURCES" subtitle="rooms, staff, theatre, imaging, pharmacy">
          <LucyWorksCommandSurface mode="resources" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
