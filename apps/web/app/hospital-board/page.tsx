"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { DayControlGrid } from "@/components/day-control-grid";

export default function HospitalBoardPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="NOW" subtitle="day control grid">
          <DayControlGrid />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
