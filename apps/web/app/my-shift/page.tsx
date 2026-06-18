"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { MyAssignedWorkBoard } from "@/components/my-assigned-work-board";
import { MyTimedWorkBoard } from "@/components/my-timed-work-board";

export default function MyShiftPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {(user) => (
        <HospitalShell title="MY SHIFT" subtitle="role-filtered work and handoffs">
          <MyTimedWorkBoard role={user.role || "nurse"} />
          <MyAssignedWorkBoard role={user.role || "nurse"} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
