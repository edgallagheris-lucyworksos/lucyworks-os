"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { NowBoard } from "@/components/now-board";

export default function HospitalBoardPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="NOW" subtitle="day control grid">
          <NowBoard />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
