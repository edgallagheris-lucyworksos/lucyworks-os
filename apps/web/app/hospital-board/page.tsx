"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { HospitalOperatingConsole } from "@/components/hospital-operating-console";

export default function HospitalBoardPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="NOW" subtitle="hospital operating console">
          <HospitalOperatingConsole />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
