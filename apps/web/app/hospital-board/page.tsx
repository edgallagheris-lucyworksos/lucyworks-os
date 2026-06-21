"use client";

import { AccountabilityGrid } from "@/components/accountability-grid";
import { AuthGuard } from "@/components/auth-guard";

export default function HospitalBoardPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {() => <AccountabilityGrid />}
    </AuthGuard>
  );
}
