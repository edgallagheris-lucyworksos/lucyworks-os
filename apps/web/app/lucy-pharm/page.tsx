"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { WorkAreaBoard } from "@/components/work-area-board";
import { workItemsForArea } from "@/lib/canonical-operational-work";

export default function LucyPharmPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="SUPPLY" subtitle="stock and signoff board"><WorkAreaBoard area="Supply" purpose="Controls signoff queue, stock gaps and release blockers." explanation="This board shows each work row with owner, blocker, next action and due time." rows={workItemsForArea("supply")} /></HospitalShell>}</AuthGuard>;
}
