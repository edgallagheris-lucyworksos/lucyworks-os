"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { WorkAreaBoard, type WorkAreaRow } from "@/components/work-area-board";

const rows: WorkAreaRow[] = [
  { id: "a", item: "Slot order", patient: "queue item", owner: "area lead", status: "amber", blocker: "priority unclear", next: "confirm priority", due: "09:00", route: "/flow" },
  { id: "b", item: "Report row", patient: "queue item", owner: "reporting role", status: "red", blocker: "owner missing", next: "assign owner", due: "10:30", route: "/my-shift" },
  { id: "c", item: "Reserve capacity", patient: "capacity", owner: "coordinator", status: "blue", blocker: "none", next: "keep reserve", due: "12:00", route: "/resources" },
];

export default function ImagingPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="IMAGING" subtitle="area work board"><WorkAreaBoard area="Imaging" purpose="Controls slot order, ownership, queue priority and capacity." explanation="This board shows each work row with owner, blocker, next action and due time." rows={rows} /></HospitalShell>}</AuthGuard>;
}
