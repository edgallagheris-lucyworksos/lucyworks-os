"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { WorkAreaBoard, type WorkAreaRow } from "@/components/work-area-board";

const rows: WorkAreaRow[] = [
  { id: "a", item: "Signoff queue", patient: "queue item", owner: "signing role", status: "red", blocker: "owner missing", next: "assign signoff", due: "09:30", route: "/my-shift" },
  { id: "b", item: "Stock row", patient: "stock item", owner: "area lead", status: "amber", blocker: "low count", next: "request stock", due: "11:00", route: "/resources" },
  { id: "c", item: "Release row", patient: "release item", owner: "area team", status: "amber", blocker: "final check", next: "clear priority items", due: "15:00", route: "/flow" },
];

export default function LucyPharmPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="SUPPLY" subtitle="stock and signoff board"><WorkAreaBoard area="Supply" purpose="Controls signoff queue, stock gaps and release blockers." explanation="This board shows each work row with owner, blocker, next action and due time." rows={rows} /></HospitalShell>}</AuthGuard>;
}
