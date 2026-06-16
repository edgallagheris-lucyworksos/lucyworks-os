"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { WorkAreaBoard, type WorkAreaRow } from "@/components/work-area-board";

const rows: WorkAreaRow[] = [
  { id: "a", item: "Capacity row", patient: "capacity", owner: "area lead", status: "red", blocker: "destination full", next: "confirm movement plan", due: "08:45", route: "/resources" },
  { id: "b", item: "Handover row", patient: "team task", owner: "senior role", status: "amber", blocker: "plan missing", next: "write plan", due: "10:00", route: "/my-shift" },
  { id: "c", item: "Cover row", patient: "staffing", owner: "ops manager", status: "amber", blocker: "thin cover", next: "rebalance rota", due: "15:30", route: "/rota" },
];

export default function CareAreaPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="CARE AREA" subtitle="capacity and handover board"><WorkAreaBoard area="Care Area" purpose="Controls beds, handover, cover and destination capacity." explanation="This board shows each work row with owner, blocker, next action and due time." rows={rows} /></HospitalShell>}</AuthGuard>;
}
