"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { WorkAreaBoard } from "@/components/work-area-board";
import { workItemsForArea } from "@/lib/canonical-operational-work";

export default function ImagingPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="IMAGING" subtitle="area work board"><WorkAreaBoard area="Imaging" purpose="Controls slot order, ownership, queue priority and capacity." explanation="This board shows each work row with owner, blocker, next action and due time." rows={workItemsForArea("imaging")} /></HospitalShell>}</AuthGuard>;
}
