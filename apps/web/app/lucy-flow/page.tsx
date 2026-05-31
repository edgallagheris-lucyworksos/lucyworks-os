"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function LucyFlowPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {(user) => (
        <HospitalShell title="LucyFlow" subtitle="movement, stage progression, schedule and bottlenecks">
          <LucyWorksCommandSurface mode="flow" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
