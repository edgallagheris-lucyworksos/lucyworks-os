"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { WorkAreaBoard, type WorkAreaRow } from "@/components/work-area-board";

const rows: WorkAreaRow[] = [
  { id: "a", item: "Room order", patient: "slot", owner: "area lead", status: "amber", blocker: "readiness check", next: "confirm order", due: "08:30", route: "/flow" },
  { id: "b", item: "Room reset", patient: "slot", owner: "support", status: "green", blocker: "none", next: "prepare next slot", due: "10:15", route: "/rooms" },
  { id: "c", item: "Late slot", patient: "slot", owner: "lead", status: "red", blocker: "destination capacity", next: "confirm capacity", due: "14:00", route: "/resources" },
];

export default function TheatrePage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="THEATRE" subtitle="area work board"><WorkAreaBoard area="Theatre" purpose="Controls room order, readiness, handoff and daily overrun risk." explanation="This board shows each work row with owner, blocker, next action and due time." rows={rows} /></HospitalShell>}</AuthGuard>;
}
