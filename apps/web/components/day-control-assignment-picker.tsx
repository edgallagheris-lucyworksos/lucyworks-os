"use client";

import { useEffect, useState } from "react";
import type { OperationalTarget } from "@/lib/operational-actions";
import type { ScheduledWorkBlock } from "@/lib/day-control-work";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type StaffOption = { id: number; name: string; role: string; area: string };
type ResourceOption = { id: string; name: string; type: string };
type PatchBlock = (blockId: string, patch: Partial<ScheduledWorkBlock>) => void;

export function DayControlAssignmentPicker({ target, onPatchBlock, onStatus }: { target: OperationalTarget; onPatchBlock?: PatchBlock; onStatus: (message: string) => void }) {
  const [staff, setStaff] = useState<StaffOption[]>([]);
  const [resources, setResources] = useState<ResourceOption[]>([]);
  const [selectedStaffId, setSelectedStaffId] = useState("");
  const [selectedResourceId, setSelectedResourceId] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/api/day-control/staff-options`).then((r) => r.json()).then((data) => setStaff(Array.isArray(data.staff) ? data.staff : [])).catch(() => setStaff([]));
    fetch(`${API_BASE}/api/day-control/resource-options`).then((r) => r.json()).then((data) => setResources(Array.isArray(data.resources) ? data.resources : [])).catch(() => setResources([]));
  }, []);

  async function patchAssignment(patch: Record<string, string | number | null>) {
    if (onPatchBlock) {
      onPatchBlock(String(target.id), patch as Partial<ScheduledWorkBlock>);
      return;
    }
    const response = await fetch(`${API_BASE}/api/day-control/blocks/${target.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) });
    if (!response.ok) throw new Error("assignment patch failed");
  }

  function save() {
    const staffChoice = staff.find((item) => String(item.id) === selectedStaffId);
    const resourceChoice = resources.find((item) => item.id === selectedResourceId);
    patchAssignment({
      assignedStaffId: staffChoice?.id ?? null,
      assignedStaffName: staffChoice?.name ?? null,
      assignedRole: staffChoice?.role ?? target.ownerRole ?? null,
      resourceId: resourceChoice?.id ?? null,
      resourceName: resourceChoice?.name ?? null,
      status: "amber",
      next: "assignment updated",
    }).then(() => onStatus("assignment updated")).catch(() => onStatus("assignment saved locally only"));
  }

  function clear() {
    patchAssignment({ assignedStaffName: null, assignedRole: null, assignedStaffId: null, resourceId: null, resourceName: null, status: "amber", next: "assignment cleared" })
      .then(() => onStatus("assignment cleared"))
      .catch(() => onStatus("assignment clear failed"));
  }

  return <section className="assign"><b>Assign work</b><select value={selectedStaffId} onChange={(event) => setSelectedStaffId(event.target.value)}><option value="">Staff / role</option>{staff.map((item) => <option key={item.id} value={item.id}>{item.name} — {item.role}</option>)}</select><select value={selectedResourceId} onChange={(event) => setSelectedResourceId(event.target.value)}><option value="">Room / resource</option>{resources.map((item) => <option key={item.id} value={item.id}>{item.name} — {item.type}</option>)}</select><button onClick={save}>Save assignment</button><button onClick={clear}>Clear assignment</button></section>;
}
