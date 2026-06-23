"use client";

import { StaffLocationGrid } from "@/components/staff-location-grid";
import { AuthGuard } from "@/components/auth-guard";

export default function HospitalBoardPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {() => <StaffLocationGrid />}
    </AuthGuard>
  );
}
