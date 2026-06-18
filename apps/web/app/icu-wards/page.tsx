"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { WorkAreaBoard } from "@/components/work-area-board";
import { workRowsForLanes } from "@/lib/day-control-views";

export default function CareAreaPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="CARE AREA" subtitle="generated recovery and handover work"><WorkAreaBoard area="Care Area" purpose="Shows generated care, recovery and handover work from the 15-minute day-control schedule." explanation="This page is a filtered view of the generated schedule, not a separate standalone board." rows={workRowsForLanes(["care"])} /></HospitalShell>}</AuthGuard>;
}
