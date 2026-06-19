"use client";

import { DayControlGrid } from "@/components/day-control-grid";
import { AuthGuard } from "@/components/auth-guard";

export default function HospitalBoardPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {() => <DayControlGrid />}
    </AuthGuard>
  );
}
