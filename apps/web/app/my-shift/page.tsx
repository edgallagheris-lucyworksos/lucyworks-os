"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function MyShiftPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {(user) => (
        <HospitalShell title="MY SHIFT" subtitle="role-filtered work and handoffs">
          <LucyWorksCommandSurface mode="my-shift" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
