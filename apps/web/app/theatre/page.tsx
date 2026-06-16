"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { WorkAreaBoard } from "@/components/work-area-board";
import { workItemsForArea } from "@/lib/canonical-operational-work";

export default function TheatrePage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="THEATRE" subtitle="area work board"><WorkAreaBoard area="Theatre" purpose="Controls room order, readiness, handoff and daily overrun risk." explanation="This board shows each work row with owner, blocker, next action and due time." rows={workItemsForArea("theatre")} /></HospitalShell>}</AuthGuard>;
}
