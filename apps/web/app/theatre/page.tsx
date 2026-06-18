"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { SharedWorkArea } from "@/components/shared-work-area";

export default function TheatrePage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="THEATRE" subtitle="generated room work"><SharedWorkArea area="Theatre" purpose="Shows room work from the shared 15-minute schedule." explanation="This page reads the same saved rows as the main board." lanes={["rooms"]} /></HospitalShell>}</AuthGuard>;
}
