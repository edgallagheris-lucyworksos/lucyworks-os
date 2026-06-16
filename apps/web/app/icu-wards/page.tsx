"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { WorkAreaBoard } from "@/components/work-area-board";
import { workItemsForArea } from "@/lib/canonical-operational-work";

export default function CareAreaPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="CARE AREA" subtitle="capacity and handover board"><WorkAreaBoard area="Care Area" purpose="Controls beds, handover, cover and destination capacity." explanation="This board shows each work row with owner, blocker, next action and due time." rows={workItemsForArea("care")} /></HospitalShell>}</AuthGuard>;
}
