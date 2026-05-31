"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function LucyClinicalPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse"]}>
      {(user) => (
        <HospitalShell title="LucyClinical" subtitle="cases, results, decisions and clinical ownership">
          <LucyWorksCommandSurface mode="now" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
