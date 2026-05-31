"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function LucyCommsPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {(user) => (
        <HospitalShell title="LucyComms" subtitle="owner updates, callbacks, reception and admin messages">
          <LucyWorksCommandSurface mode="interrupts" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
