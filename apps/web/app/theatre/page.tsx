"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { WorkAreaBoard } from "@/components/work-area-board";
import { workRowsForLanes } from "@/lib/day-control-views";

export default function TheatrePage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="THEATRE" subtitle="generated room work"><WorkAreaBoard area="Theatre" purpose="Shows generated room/resource work from the 15-minute day-control schedule." explanation="This page is a filtered view of the generated schedule, not a separate standalone board." rows={workRowsForLanes(["rooms"])} /></HospitalShell>}</AuthGuard>;
}
