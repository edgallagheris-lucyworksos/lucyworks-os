"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function LucyPharmPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {(user) => (
        <HospitalShell title="LucyPharm" subtitle="medicines, stock, controlled-item movement and discharge meds">
          <LucyWorksCommandSurface mode="resources" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
