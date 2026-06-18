"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";
import { WorkAreaBoard } from "@/components/work-area-board";
import { workRowsForLanes } from "@/lib/day-control-views";

export default function FlowPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {(user) => (
        <HospitalShell title="FLOW" subtitle="consults, admin blockers and client/contact updates">
          <WorkAreaBoard area="Flow Control" purpose="Shows consult, insurance/admin and contact-update work generated from the 15-minute day-control schedule." explanation="This is the source-of-truth flow view before command tools below." rows={workRowsForLanes(["consult", "insurance", "client", "decision"])} />
          <LucyWorksCommandSurface mode="flow" user={user} />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
