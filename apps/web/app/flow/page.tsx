"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function FlowPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {(user) => (
        <HospitalShell title="FLOW" subtitle="department movement and blockers">
          <LucyWorksCommandSurface mode="flow" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
