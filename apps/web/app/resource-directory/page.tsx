"use client";

import { AssignmentDirectoryManager } from "@/components/assignment-directory-manager";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

export default function ResourceDirectoryPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="RESOURCE DIRECTORY" subtitle="assignment options">
          <AssignmentDirectoryManager />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
