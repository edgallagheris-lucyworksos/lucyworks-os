"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function LucyGovPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "admin"]}>
      {(user) => (
        <HospitalShell title="LucyGov" subtitle="audit, governance, safety and compliance">
          <LucyWorksCommandSurface mode="manager" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
