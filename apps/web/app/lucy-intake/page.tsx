"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyIntakeBoard } from "@/components/lucy-intake-board";
import { WorkAreaBoard } from "@/components/work-area-board";
import { workRowsForLanes } from "@/lib/day-control-views";

export default function LucyIntakePage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="LUCY INTAKE" subtitle="arrivals, reception and front-door routing">
          <WorkAreaBoard area="Arrivals / Reception" purpose="Shows arrival, reception and intake work generated from the 15-minute day-control schedule." explanation="This is the source-of-truth front-door view before specialist intake tools below." rows={workRowsForLanes(["arrival", "reception", "intake"])} />
          <LucyIntakeBoard />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
