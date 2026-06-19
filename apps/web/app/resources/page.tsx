"use client";

import { AssignmentDirectoryManager } from "@/components/assignment-directory-manager";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function ResourcesPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {(user) => (
        <HospitalShell title="RESOURCES" subtitle="rooms, staff, theatre, imaging, pharmacy">
          <AssignmentDirectoryManager />
          <LucyWorksCommandSurface mode="resources" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
