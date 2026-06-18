"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { SharedWorkArea } from "@/components/shared-work-area";

export default function CareAreaPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="CARE AREA" subtitle="generated care work"><SharedWorkArea area="Care Area" purpose="Shows care and handover rows from the shared 15-minute schedule." explanation="This page reads the same saved rows as the main board." lanes={["care"]} /></HospitalShell>}</AuthGuard>;
}
